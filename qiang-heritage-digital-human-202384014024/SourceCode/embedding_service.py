# Compatibility methods for the active embedding provider.
# Coursework annotation: NE2301 ShengruiDu StevenDu 杜晟瑞 202384014024.
"""Compatibility embedding adapter using Zhipu embedding-3 for knowledge chunks."""
from typing import Optional, List

from gemini_embedding import ZhipuEmbeddingClient


class EmbeddingClient(ZhipuEmbeddingClient):
    """Expose legacy embedding method names on the Zhipu client."""

    def get_embedding(self, text: str) -> Optional[List[float]]:
        """Convert an empty embedding into None for database-ingestion callers."""
        embedding = self.embed_text(text)
        return embedding or None

    def get_embeddings_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """Process inputs sequentially through the compatibility embedding method."""
        # Sequential calls keep the provider rate limit respected; there is no batch endpoint used here.
        return [self.get_embedding(text) for text in texts]


embedding_client = EmbeddingClient()
