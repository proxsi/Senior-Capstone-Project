/* Same-origin HTTP client for chat and speech requests.
 * Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024. */
import axios from 'axios';

/**
 * Requests are sent back to whatever origin served the page. In production the FastAPI
 * backend serves both the built assets and the API, so no host or port has to be configured
 * at build time and no CORS preflight is triggered.
 */
const API_BASE_URL = window.location.origin;

/** A single bubble in the transcript, including optional attachment and provenance info. */
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  /** Which tier answered the question; drives the coloured source badge under each answer. */
  source_type?: 'local' | 'web' | 'llm' | 'image';
  source_url?: string;
  /** Data-URL preview kept only on the client so the sent image can be rendered in the log. */
  image_preview?: string;
  timestamp: number;
}

/** Request body for POST /chat. History is text-only; images are sent per turn. */
export interface ChatRequest {
  query: string;
  history?: Array<{ role: string; content: string }>;
  image_base64?: string;
  image_mime_type?: string;
}

/** Response body for POST /chat. Always a complete answer, never a token stream. */
export interface ChatResponse {
  answer: string;
  source_type: 'local' | 'web' | 'llm' | 'image';
  /** Reference URL, document name, or empty string depending on the answering tier. */
  reference: string;
  confidence: number;
  fallback_used: boolean;
  timestamp: string;
}

/** Response body for POST /tts: raw MP3 bytes encoded as standard base64. */
export interface TTSResponse {
  audio: string;
  format: string;
}

/**
 * Shared axios instance.
 * The long timeout (three minutes) accommodates LLM plus web-search round trips that can
 * exceed the default axios timeout; JSON is the only content type this client sends.
 */
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 180000,
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Send the current query and history to the same-origin chat endpoint and wait for the
 * complete response.
 *
 * Note: this backend does not implement server-sent events. `/chat` returns one JSON body
 * containing the finished answer, which is why ChatWindow reveals the text client-side
 * rather than parsing `data:` frames.
 *
 * The full message objects are trimmed to `{ role, content }` because the extra UI fields
 * (id, timestamps, previews) are meaningless to the model and would only inflate the prompt.
 */
export const sendChatMessage = async (
  message: string,
  history?: ChatMessage[],
  imageBase64?: string,
  imageMimeType?: string
): Promise<ChatResponse> => {
  const formattedHistory = history?.map(h => ({
    role: h.role,
    content: h.content
  }));
  
  const response = await api.post<ChatResponse>('/chat', {
    query: message,
    history: formattedHistory,
    image_base64: imageBase64,
    image_mime_type: imageMimeType,
  });
  return response.data;
};

/**
 * Legacy client helper; this backend does not implement the referenced graph endpoint.
 * Kept for API compatibility only - the graph view builds its data from `/knowledge-base/chunks`.
 */
export const getKnowledgeGraph = async (entity: string) => {
  const response = await api.get('/knowledge-graph', {
    params: { entity },
  });
  return response.data;
};

/**
 * Request base64 MP3 speech from the same-origin backend.
 * The caller decodes the base64 payload into a Blob and plays it through an <audio> element,
 * so the browser never needs a separate media URL.
 */
export const synthesizeSpeech = async (text: string): Promise<TTSResponse> => {
  const response = await api.post<TTSResponse>('/tts', {
    text,
  });
  return response.data;
};
