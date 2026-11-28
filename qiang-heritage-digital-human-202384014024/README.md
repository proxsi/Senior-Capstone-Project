# Qiang Heritage Digital Human — Course Project Documentation

**Coursework package: annotated source code, system walkthrough, and technical paper**

| Item | Value |
| --- | --- |
| Course / class | NE2301 |
| Student | Shengrui Du (StevenDu) / 杜晟瑞 |
| Student ID | 202384014024 |
| Project | Qiang Heritage Digital Human Knowledge Q&A System (羌智传承) |
| Deliverables | `SourceCode/` (annotated), `README.md`, `docs/TechnicalPaper.html`, `docs/TechnicalPaper.pdf` |

All source files, folders, images, and documents in this package use English names. Chinese text
that remains inside the program is product content — dialogue prompts, UI labels, and log
messages — and is intentionally preserved so that the running system still speaks to its users in
Chinese.

---

## 1. What the project does

The system is a single-page web application in which a visitor talks to **Qiangqiang (羌羌)**, a
digital-human presenter of Qiang ethnic heritage, in natural Chinese. Behind the chat panel, the
answer is produced by a retrieval pipeline that prefers a curated heritage knowledge base, falls
back to live web search, and only then falls back to the language model's own knowledge. The same
page also exposes a knowledge-management console for curators and a force-directed knowledge graph
of the stored entities.

The interface is organised as three columns on a wide screen: conversation on the left, the
digital-human avatar in the centre, and the knowledge graph on the right. Figure 1 shows the
default state of the application.

![Figure 1. Default workspace of the system](docs/images/01-system-home.png)

*Figure 1. The three-column workspace: chat panel, digital-human avatar, and knowledge graph.*

---

## 2. Architecture at a glance

The deployment is deliberately simple: one FastAPI process serves both the JSON API and the built
React bundle, so the browser and the API share an origin and no CORS configuration is required.

```text
┌──────────────────────────────── Browser (React 19 + Vite) ────────────────────────────────┐
│  ChatWindow          DigitalHuman              KnowledgeGraph        KnowledgeBaseModal   │
│  chat + attachments  avatar video state machine force-directed graph  upload / browse     │
└───────────────┬───────────────────────────────────────────────────────────────────────────┘
                │  same-origin HTTP (axios), JSON
┌───────────────▼───────────────────────────────────────────────────────────────────────────┐
│                            FastAPI application (api_server/server.py)                     │
│  /chat  /chat/stream  /tts  /knowledge-base*  /stats  /health  /welcome.mp3  /assets      │
├───────────────────────────────┬──────────────────────────┬────────────────────────────────┤
│  rag_core/rag_engine.py       │  knowledge_processor.py  │  gemini_chat.py                │
│  routing + prompt assembly    │  text → structured chunks│  DeepSeek chat completion      │
├───────────────────────────────┼──────────────────────────┼────────────────────────────────┤
│  db_connection.py             │  gemini_embedding.py     │  gemini_search.py              │
│  PostgreSQL chunk store       │  Zhipu embedding-3       │  Qwen web search               │
├───────────────────────────────┴──────────────────────────┴────────────────────────────────┤
│  Optional: knowledge_base/knowledge_loader.py (Neo4j graph + vector index)                 │
│  Optional: crawler/ (Scrapy spiders and ingestion pipeline)                                │
│  Speech:   tts_service.py (iFlytek WebSocket TTS)                                          │
└───────────────────────────────────────────────────────────────────────────────────────────┘
```

Two practical consequences follow from this layout and are worth stating up front:

1. The **online retrieval path reads PostgreSQL only**. The Neo4j loader is a separate, optional
   ingestion path; `QiangRetriever` never queries Neo4j.
2. The **answer is not token-streamed by the model**. `/chat` returns one complete JSON body. The
   frontend simulates typing locally, and a separate `/chat/stream` endpoint exists on the server
   but is not used by the current client.

---

## 3. Screen-by-screen walkthrough

### 3.1 Asking a heritage question

A question is typed into the composer and sent as `POST /chat` together with the visible
conversation history. The answer bubble carries a source badge — local knowledge base, web search,
general model knowledge, or image analysis — so the reader can see which tier answered.

![Figure 2. A heritage question and its answer](docs/images/02-qa-example.png)

*Figure 2. A heritage question answered with provenance metadata under the bubble.*

The request path is:

```text
ChatWindow → POST /chat → QiangRetriever.chat_with_history
          → casual-chat detector
          → local vector + keyword search (threshold 0.75)
          → Qwen web search (if the threshold is missed)
          → DeepSeek general answer (if search returns nothing)
          → ChatResponse {answer, source_type, reference, confidence, fallback_used}
```

### 3.2 The digital human

The avatar is a small state machine over pre-rendered video clips: a welcome clip, two idle loops,
two thinking clips, and a talking loop. It reacts to three events forwarded from `App.tsx`:
question submitted (thinking), speech started (talking, with the clip duration taken from the audio
element), and speech finished or stopped (idle). The heritage entity found in the latest answer is
shown as a caption.

![Figure 3. The digital-human avatar](docs/images/03-digital-ambassador.png)

*Figure 3. The avatar panel. Clip playback is driven by conversation state, not by phoneme data.*

### 3.3 Browsing the knowledge base

The knowledge console lists stored chunks with pagination, entity type, topic tag, relation text,
and source URL. A free-text filter runs on the client over the page that has already been loaded.

![Figure 4. Knowledge browsing](docs/images/04-knowledge-browse.png)

*Figure 4. Browsing stored knowledge chunks, with entity type and topic tag on each row.*

### 3.4 Adding a single structured entry

An operator can bypass the extraction model and submit one already-structured chunk: subject name,
entity type, topic tag, embedding text, relation description, and source URL. The vector is
requested for the embedding text before the row is written.

![Figure 5. Single-entry upload](docs/images/05-single-upload.png)

*Figure 5. Single-entry upload with explicit entity type and topic tag selection.*

### 3.5 Bulk upload with preview and confirmation

Free-form text is first sent to `POST /knowledge-base/preview`. DeepSeek is asked to return a JSON
array of chunks; the response is parsed, clipped to the outermost bracketed block, and shown in an
editable table. Nothing is written to the database until the operator confirms, which calls
`POST /knowledge-base/confirm`. Each chunk is embedded and inserted independently, so one failure
does not abort the batch.

![Figure 6. Bulk upload and extraction preview](docs/images/06-bulk-upload.png)

*Figure 6. Bulk ingestion: raw text, extracted chunks, and the confirmation step.*

### 3.6 The knowledge graph

The graph view builds nodes and edges on the client from `/knowledge-base/chunks`. Heritage
projects, inheritors, places, and generic entities become typed nodes; the relation description is
scanned for a related project name to create edges. When a chat answer mentions a known entity, the
graph re-centres on the matching node.

![Figure 7. Knowledge graph](docs/images/07-knowledge-graph.png)

*Figure 7. Force-directed graph with colour-coded entity types and a legend.*

### 3.7 Image question

An attached image is converted to a data URL in the browser and posted as `image_base64` plus
`image_mime_type`. When that field is present, the server skips retrieval entirely and sends the
image to the configured vision model with a dedicated system prompt.

![Figure 8. Attaching an image to a question](docs/images/08-image-upload.png)

*Figure 8. Image attachment in the composer; the selected file is previewed before sending.*

---

## 4. Source-code map

| Path | Responsibility |
| --- | --- |
| `SourceCode/api_server/server.py` | FastAPI application, request models, chat/SSE/TTS endpoints, knowledge endpoints, static asset mounting |
| `SourceCode/rag_core/rag_engine.py` | Casual-chat detection, three-tier routing, prompt assembly, provenance metadata |
| `SourceCode/db_connection.py` | PostgreSQL connection context manager, chunk table, JSONB vector storage, Python-side cosine ranking |
| `SourceCode/gemini_embedding.py` | Zhipu `embedding-3` client with throttling, retry, and cosine helpers |
| `SourceCode/embedding_service.py` | Thin compatibility layer exposing `get_embedding` / `get_embeddings_batch` |
| `SourceCode/gemini_chat.py` | DeepSeek chat-completion client (text and image), bounded retries, history assembly |
| `SourceCode/gemini_search.py` | Qwen web-search generation with the `web_search` tool |
| `SourceCode/knowledge_processor.py` | Prompting the model for structured chunks, JSON isolation, per-chunk persistence |
| `SourceCode/knowledge_base/knowledge_loader.py` | Optional Neo4j ingestion: sentence-aware chunking, regex entity extraction, vector index |
| `SourceCode/tts_service.py` | iFlytek WebSocket TTS with HMAC-SHA256 request signing |
| `SourceCode/crawler/` | Scrapy spiders for heritage news, plus the ingestion pipeline |
| `SourceCode/config.py` | Environment-backed settings: providers, model names, thresholds, server, logging |
| `SourceCode/frontend/src/` | React components, API client, Tailwind styling |
| `SourceCode/*.sh` | Shell entry points for container and local startup |

Every handwritten Python, TypeScript, and JavaScript file in `SourceCode/` carries an English
header, module docstring or file comment, per-function docstrings, and step-level comments on
non-obvious logic. The compiled bundle (`frontend/dist/`) is not shipped; run `npm run build` to
produce it.

---

## 5. Retrieval and answering logic

### 5.1 Casual conversation is separated from knowledge questions

Before any retrieval happens, the query is matched against pattern lists for greetings,
self-introductions, small talk, emotional support, care, praise, and teasing. Short conversational
inputs bypass retrieval entirely and are answered with a direct persona prompt. This avoids
pointless database lookups for "hello" and keeps the character natural.

### 5.2 Three-tier answer routing

For knowledge questions the retriever executes:

1. **Local knowledge base.** The query is embedded, the best five vector neighbours are loaded, and
   up to five keyword matches (`LIKE` on chunk text and subject name) are merged in. Keyword hits
   are given a fixed score of 0.5 so that they never outrank a strong vector match. The reported
   score is the top vector similarity.
2. **Web search.** Only if the top vector score is below `SIMILARITY_THRESHOLD` (default `0.75`).
3. **General model knowledge.** Only if web search returns nothing.

The chosen tier is returned to the client as `source_type` (`local` / `web` / `llm`), together
with a confidence value and a `fallback_used` flag.

### 5.3 Prompt construction

All tiers share one system prompt that defines the persona: an 18-year-old Qiang woman from Li
County, warm and plain-spoken, who admits ignorance rather than inventing facts and who never
mentions being a program, a database, or an AI model. Each tier then supplies a different context
framing — "old records in the village" for retrieved knowledge, "news from beyond the mountains"
for web results — and the last six history turns are folded into the prompt.

### 5.4 Knowledge ingestion and storage

Chunks are stored in the table `non_heritage_knowledge_chunks`:

| Column | Type | Meaning |
| --- | --- | --- |
| `chunk_id` | `VARCHAR(50)` PK | `QX_<timestamp>_<counter>` identifier |
| `source_entity` | `VARCHAR(100)` | Subject name, e.g. a heritage project |
| `entity_type` | `VARCHAR(50)` | Project / inheritor / festival / place / craft / other |
| `topic_tag` | `VARCHAR(50)` | Definition, history, process, value, works, etc. |
| `embedding_text` | `TEXT` | The text that is actually embedded and shown to the model |
| `relation_desc` | `TEXT` | Free-text relations, scanned by the graph view |
| `source_url` | `TEXT` | Provenance |
| `embedding` | `JSONB` | Embedding vector serialized as JSON |
| `created_at` / `updated_at` | `TIMESTAMP` | Bookkeeping |

The vector is stored as JSONB rather than in a `pgvector` column. Similarity is therefore computed
in Python: every embedded row is loaded, cosine similarity is calculated with NumPy, and the
ranking is truncated to the top *k*. This keeps the deployment free of a database extension at the
cost of scanning the whole table per query.

The optional Neo4j path splits text with a 500-character window and 50-character overlap, prefers
sentence-ending punctuation at the boundary, extracts entities with regex rules, creates
`Inheritor` / `HeritageProject` / `Location` nodes plus `INHERITS` edges, and stores embeddings in a
cosine vector index of dimension 768.

---

## 6. Running the project

### 6.1 Backend

```bash
cd SourceCode
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

copy .env.example .env        # Windows
# cp .env.example .env        # Linux/macOS
# then edit .env and supply your own keys

python run_server.py
```

`run_server.py` reads `API_HOST`, `API_PORT`, `API_RELOAD`, and `LOG_LEVEL` from configuration. The
server listens on `0.0.0.0:8080` by default; the template sets `8000` if you prefer it.

### 6.2 Frontend

```bash
cd SourceCode/frontend
npm install
npm run dev        # development server on Vite's default port
npm run build      # emits dist/, which the backend serves at /
```

### 6.3 What will and will not work without credentials

| Capability | Requirement |
| --- | --- |
| Chat answers | `DEEPSEEK_API_KEY` |
| Vector search and ingestion | `ZHIPU_API_KEY`, reachable PostgreSQL with the chunk table |
| Web-search tier | `QWEN_API_KEY` |
| Spoken replies | `XF_APP_ID` / `XF_API_KEY` / `XF_API_SECRET` |
| Image questions | A vision-capable DeepSeek model name in `VISION_MODEL` |
| Neo4j ingestion | `NEO4J_*` settings and a running Neo4j instance |
| Frontend static assets | `npm run build` must have produced `frontend/dist/` |

The package ships **no live credentials**. `.env.example` contains placeholders only, and the
original `.env` was deliberately excluded from the coursework copy.

---

## 7. Honest limitations

These are properties of the implementation as submitted, not hypothetical risks:

- **Vector search is linear.** All embeddings are fetched and ranked in Python; this does not scale
  beyond a modest table.
- **Keyword search builds SQL with an f-string.** The `LIKE` patterns are interpolated directly,
  which is acceptable for a supervised course demo but should use bound parameters in production.
- **No authentication or rate limiting** on any API route, including the knowledge write routes.
- **Statistics are process-local.** `/stats` counters reset when the process restarts.
- **Streaming is simulated.** `/chat/stream` emits per-character SSE frames only after the full
  answer already exists; the client does not use it and instead reveals text locally.
- **Avatar video is remote.** The clips are loaded from a public object-store URL; the interface
  degrades to the caption if that host is unreachable.
- **The graph view is client-derived.** It infers edges from relation text with a regular
  expression and falls back to a small illustrative graph when the API returns nothing.
- **No automated test suite.** The repository contains connectivity and embedding probes, not
  regression tests.

---

## 8. Notes on the annotation work in this copy

- Only comments and docstrings were added or translated. An AST comparison against the original
  project confirms that every Python module has identical executable structure; shell command
  sequences, JSON payloads, and binary assets are byte-identical apart from the documented
  sanitisation below.
- The original `.env` file was not copied. `.env.example` was rewritten in English and its
  real-looking database host, port, and password were replaced with placeholders.
- Chinese product strings were preserved. Translating them would change the system's behaviour and
  the screenshots in this document would no longer match the code.
- No performance or accuracy numbers are claimed anywhere in this package, because no controlled
  experiment was run. The parameters quoted above are code constants, not measured results.

---

## 9. Package contents

```text
NE2301/StevenDu/
├── README.md                     this document
├── SourceCode/                   annotated project copy
│   ├── api_server/               FastAPI application
│   ├── rag_core/                 retrieval and answer routing
│   ├── knowledge_base/           optional Neo4j loader
│   ├── crawler/                  Scrapy spiders and pipeline
│   ├── frontend/                 React + TypeScript client
│   ├── .env.example              English placeholder configuration
│   └── requirements.txt          Python dependency pins
└── docs/
    ├── TechnicalPaper.html       English technical paper (print layout)
    ├── TechnicalPaper.pdf        exported PDF of the paper
    └── images/                   eight interface screenshots used by both documents
```

---

**NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024**
