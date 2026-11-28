# Qiang Heritage Q&A System — Source Code

Annotated copy of the project used for the NE2301 coursework submission. The full illustrated
guide, architecture discussion, and technical paper live one level up in `../README.md` and
`../docs/`.

## Layout

```text
SourceCode/
├── api_server/          FastAPI application and request/response models
├── rag_core/            three-tier retrieval and persona prompt assembly
├── knowledge_base/      optional Neo4j loader (not used by online retrieval)
├── crawler/             Scrapy spiders and ingestion pipeline
├── frontend/            React 19 + TypeScript + Vite client
├── config.py            environment-backed settings
├── db_connection.py     PostgreSQL chunk store and cosine ranking
├── gemini_chat.py       DeepSeek chat adapter (historical module name)
├── gemini_embedding.py  Zhipu embedding-3 adapter
├── gemini_search.py     Qwen web-search adapter
├── embedding_service.py compatibility layer over the Zhipu client
├── knowledge_processor.py  unstructured text -> structured chunks
├── tts_service.py       iFlytek WebSocket text-to-speech
├── run_server.py        server entry point
├── run_crawler.py       crawler entry point
├── requirements.txt     Python dependency pins
├── .env.example         placeholder configuration (copy to .env)
├── start.sh             build frontend and start the server
├── start_server.sh      start the server only
└── entrypoint.sh        container entry point
```

## Quick start

### 1. Environment

- Python 3.10+ (the project pins FastAPI 0.104, psycopg2 2.9, Scrapy 2.11)
- Node.js 18+ and npm
- PostgreSQL 14+ reachable from the host, with permission to create a table and indexes
- Optional: Neo4j 5.x for the graph ingestion path

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configuration

```bash
copy .env.example .env    # Windows
# cp .env.example .env    # Linux/macOS
```

Fill in the provider keys you actually have. The application starts without them, but the
corresponding feature will fail at call time:

| Variable group | Enables |
| --- | --- |
| `DEEPSEEK_*` | chat answers and chunk extraction |
| `ZHIPU_*` | embeddings and vector retrieval |
| `QWEN_*` | the web-search fallback tier |
| `XF_*` | spoken replies through iFlytek TTS |
| `POSTGRES_*` | knowledge chunk storage |
| `NEO4J_*` | the optional graph loader |

### 3. Frontend build

```bash
cd frontend
npm install
npm run build
```

The server mounts `frontend/dist/assets` at `/assets` and returns `frontend/dist/index.html` at `/`,
so the API and the UI share an origin.

### 4. Run

```bash
python run_server.py
```

The default address is `0.0.0.0:8080` from `config.py`, overridable through `API_HOST` and
`API_PORT`. Interactive API documentation is available at `/docs`.

## API surface

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Built frontend page, or API metadata when no build exists |
| `GET` | `/health` | Liveness response with version and timestamp |
| `POST` | `/chat` | Answer a question, optionally with a base64 image |
| `POST` | `/chat/stream` | Server-sent events; the current client does not use it |
| `POST` | `/tts` | Base64 MP3 speech for a piece of text |
| `GET` | `/knowledge-base` | Entries from the JSON-backed demonstration store |
| `POST` | `/knowledge-base` | Append one entry to the JSON-backed store |
| `POST` | `/knowledge-base/single` | Embed and insert one structured chunk |
| `POST` | `/knowledge-base/preview` | Extract chunks from raw text without writing |
| `POST` | `/knowledge-base/confirm` | Embed and insert confirmed chunks |
| `POST` | `/knowledge-base/bulk` | Extract and insert in one call |
| `GET` | `/knowledge-base/chunks` | Paginated stored chunks |
| `GET` | `/stats` | Process-local query counters |
| `POST` | `/reset-stats` | Reset those counters |

## Crawler

```bash
python run_crawler.py
```

The spiders target the China Intangible Cultural Heritage site and the Sichuan culture portal, and
the pipeline forwards extracted articles to the knowledge loader. Crawling is rate-limited and is
disabled by default unless `CRAWLER_ENABLED=true`.

## Notes

- The `.env` file is not part of this package; only placeholders are shipped.
- Chinese strings inside the code are product content (prompts, UI text, logs) and are preserved.
- Comments and docstrings are in English throughout the handwritten source.
- No credentials, database dumps, or measured benchmark results are included.

---

**NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024**
