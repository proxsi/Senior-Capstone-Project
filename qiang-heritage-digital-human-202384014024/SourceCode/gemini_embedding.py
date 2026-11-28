# Zhipu embedding requests, retry handling, and similarity helpers.
# Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024.
"""Zhipu embedding adapter retaining the embedding_client name for existing imports."""
import http.client
import json
import logging
import math
import socket
import time
from typing import Optional, List, Dict, Any

import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ZhipuEmbeddingClient:
    """Zhipu embedding HTTP client."""

    # Class-level timestamp shared by every instance so throttling applies process-wide.
    _last_request_time = 0.0
    _min_interval = 1.0

    def __init__(self, api_key: Optional[str] = None):
        """Resolve the API key, base URL, model name, and endpoint from configuration."""
        self.api_key = api_key or config.ZHIPU_API_KEY
        self.base_url = config.ZHIPU_BASE_URL
        self.model = config.EMBEDDING_MODEL
        self.endpoint = config.EMBEDDING_API_ENDPOINT

    def _wait_for_rate_limit(self):
        """Throttle sequential requests using the configured minimum interval."""
        elapsed = time.time() - ZhipuEmbeddingClient._last_request_time
        if elapsed < ZhipuEmbeddingClient._min_interval:
            time.sleep(ZhipuEmbeddingClient._min_interval - elapsed)
        ZhipuEmbeddingClient._last_request_time = time.time()

    def _build_payload(self, text: str) -> Dict[str, Any]:
        """Construct the embedding model and input-text JSON payload."""
        return {
            "model": self.model,
            "input": text,
        }

    def _parse_response(self, data: str) -> List[float]:
        """Read the first embedding vector from the provider response, or return an empty list."""
        try:
            response_json = json.loads(data)
            items = response_json.get("data", [])
            if items and "embedding" in items[0]:
                return items[0]["embedding"]
            logger.warning(f"未在响应中找到 embedding: {data[:300]}")
            return []
        except Exception as e:
            logger.error(f"解析 embedding 响应失败: {e}")
            return []

    def embed_text(
        self,
        text: str,
        max_retries: int = 5,
        timeout: int = 30,
    ) -> List[float]:
        """Request one embedding with retries and rate-limit backoff; return an empty list on failure."""
        conn = None
        for attempt in range(max_retries):
            try:
                self._wait_for_rate_limit()
                payload = self._build_payload(text)
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }

                conn = http.client.HTTPSConnection(self.base_url, timeout=timeout)
                conn.request("POST", self.endpoint, json.dumps(payload), headers)
                response = conn.getresponse()
                data = response.read().decode("utf-8")
                status = response.status
                conn.close()
                conn = None

                if status == 200:
                    return self._parse_response(data)
                if status == 429 and attempt < max_retries - 1:
                    # Rate limiting uses a longer exponential backoff capped at 30 seconds.
                    wait_time = min(2 ** (attempt + 1), 30)
                    logger.warning(f"智谱 Embedding 限流，{wait_time} 秒后重试")
                    time.sleep(wait_time)
                    continue

                logger.error(f"智谱 Embedding 请求失败: {status} - {data[:500]}")
                if attempt < max_retries - 1:
                    # Other failures retry with plain exponential backoff (2, 4, 8 ... seconds).
                    time.sleep(2 ** (attempt + 1))
                    continue
                return []
            except socket.timeout:
                logger.error(f"智谱 Embedding 请求超时 (timeout={timeout}s)")
                # Release the socket before sleeping so retries do not leak connections.
                if conn:
                    conn.close()
                    conn = None
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return []
            except Exception as e:
                logger.error(f"智谱 Embedding 调用失败: {e}")
                if conn:
                    conn.close()
                    conn = None
                if attempt < max_retries - 1:
                    time.sleep(2 ** (attempt + 1))
                    continue
                return []

        return []

    def get_embedding(self, text: str) -> Optional[List[float]]:
        """Expose the legacy nullable-vector interface for one input text."""
        embedding = self.embed_text(text)
        return embedding or None

    def get_embeddings_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """Embed inputs sequentially, preserving nullable failure results and input order."""
        return [self.get_embedding(text) for text in texts]

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed inputs sequentially; this method does not use a provider batch endpoint."""
        return [self.embed_text(text) for text in texts]

    def compute_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calculate cosine similarity, returning zero when either vector has zero magnitude."""
        if not embedding1 or not embedding2:
            return 0.0
        dot = sum(a * b for a, b in zip(embedding1, embedding2))
        norm1 = math.sqrt(sum(a * a for a in embedding1))
        norm2 = math.sqrt(sum(b * b for b in embedding2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)

    def find_most_similar(
        self,
        query_embedding: List[float],
        embeddings: List[List[float]],
        top_k: int = 5,
    ) -> List[tuple]:
        """Rank candidate vectors by cosine similarity and return the highest-scoring texts."""
        similarities = [
            (i, self.compute_similarity(query_embedding, embedding))
            for i, embedding in enumerate(embeddings)
        ]
        similarities.sort(key=lambda item: item[1], reverse=True)
        return similarities[:top_k]


embedding_client = ZhipuEmbeddingClient()


if __name__ == "__main__":
    print("测试智谱 AI 嵌入模型...")
    text = "这是一个测试文本，用于生成嵌入向量。"
    embedding = embedding_client.embed_text(text)
    print(f"嵌入向量维度: {len(embedding)}")
