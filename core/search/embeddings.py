"""
Query Embedding Generation
Generates temporary embeddings for search queries
"""

import numpy as np
import logging
from typing import List, Optional
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class QueryEmbedder:
    """
    Generate embeddings for search queries

    Important: Query embeddings are TEMPORARY and never stored.
    Only document embeddings (generated during crawling) are persisted.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize embedder with specified model

        Args:
            model_name: SentenceTransformer model name
        """
        self.model_name = model_name
        self.model: Optional[SentenceTransformer] = None
        self._load_model()

    def _load_model(self):
        """Load embedding model (lazy loading)"""
        try:
            logger.info(f"Loading embedding model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            logger.info("✓ Embedding model loaded")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise

    def embed_query(self, query: str) -> np.ndarray:
        """
        Generate embedding for a single query

        Args:
            query: Search query string

        Returns:
            NumPy array of shape (384,) - TEMPORARY, not stored
        """
        if not self.model:
            self._load_model()

        # Generate embedding
        embedding = self.model.encode([query])[0]

        # Ensure float32 (required by sqlite-vec)
        embedding = embedding.astype(np.float32)

        logger.debug(f"Generated query embedding: shape={embedding.shape}")

        return embedding

    def embed_queries(self, queries: List[str]) -> np.ndarray:
        """
        Generate embeddings for multiple queries (batch processing)

        Args:
            queries: List of query strings

        Returns:
            NumPy array of shape (N, 384) - TEMPORARY, not stored
        """
        if not self.model:
            self._load_model()

        embeddings = self.model.encode(queries)
        embeddings = embeddings.astype(np.float32)

        logger.debug(
            f"Generated {len(queries)} query embeddings: "
            f"shape={embeddings.shape}"
        )

        return embeddings


# Global instance (reuses model from storage.py if possible)
_query_embedder: Optional[QueryEmbedder] = None


def get_query_embedder() -> QueryEmbedder:
    """Get global query embedder instance"""
    global _query_embedder
    if _query_embedder is None:
        _query_embedder = QueryEmbedder()
    return _query_embedder
