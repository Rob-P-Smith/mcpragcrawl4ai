"""
Vector Retriever for SQLite-based vector search
Uses query embeddings to find similar documents
"""

import logging
from typing import List, Dict, Optional
import numpy as np

logger = logging.getLogger(__name__)


class VectorRetriever:
    """
    Retrieve documents from SQLite using vector similarity search

    Uses TEMPORARY query embeddings (never stored) to find similar
    document embeddings (stored during crawling).
    """

    def __init__(self, db_manager):
        """
        Initialize vector retriever

        Args:
            db_manager: SQLiteManager instance with search_similar method
        """
        self.db = db_manager

    def retrieve(
        self,
        query_embedding: np.ndarray,
        limit: int = 10,
        tags: Optional[List[str]] = None,
        min_similarity: float = 0.0
    ) -> List[Dict]:
        """
        Retrieve similar documents using vector search

        Args:
            query_embedding: TEMPORARY query embedding (384-dim, float32)
            limit: Maximum number of results
            tags: Optional tags to filter results
            min_similarity: Minimum similarity threshold (0.0-1.0)

        Returns:
            List of documents with similarity scores
        """
        try:
            logger.debug(f"Vector search: limit={limit}, tags={tags}")

            # Validate embedding
            if query_embedding.shape != (384,):
                raise ValueError(f"Expected (384,) embedding, got {query_embedding.shape}")
            if query_embedding.dtype != np.float32:
                raise ValueError(f"Expected float32, got {query_embedding.dtype}")

            # Convert embedding to query string for SQLite
            # Note: db.search_similar expects a text query, not embedding bytes
            # We need to use the raw vector search API
            results = self._search_by_vector(
                query_embedding,
                limit=limit * 2,  # Get extra for filtering
                tags=tags
            )

            # Filter by minimum similarity
            filtered = [
                r for r in results
                if r.get('similarity_score', 0.0) >= min_similarity
            ]

            # Limit results
            limited = filtered[:limit]

            logger.info(
                f"Vector search returned {len(limited)} results "
                f"(filtered from {len(results)})"
            )

            return limited

        except Exception as e:
            logger.error(f"Vector retrieval failed: {e}")
            return []

    def _search_by_vector(
        self,
        embedding: np.ndarray,
        limit: int,
        tags: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Low-level vector search using embedding bytes

        Args:
            embedding: Query embedding vector
            limit: Number of results
            tags: Optional tag filters

        Returns:
            List of matching documents
        """
        try:
            # Convert to bytes for SQLite vec search
            embedding_bytes = embedding.tobytes()

            # Build query based on whether tags are provided
            if tags and len(tags) > 0:
                # With tag filtering
                tag_conditions = ' OR '.join(['cc.tags LIKE ?' for _ in tags])
                tag_params = [f'%{tag}%' for tag in tags]

                sql = f'''
                    SELECT
                        cc.url, cc.title, cc.markdown, cc.content,
                        cc.timestamp, cc.tags, distance
                    FROM content_vectors
                    JOIN crawled_content cc ON content_vectors.content_id = cc.id
                    WHERE embedding MATCH ? AND k = ? AND ({tag_conditions})
                    ORDER BY distance
                '''
                params = (embedding_bytes, limit, *tag_params)
            else:
                # No tag filtering
                sql = '''
                    SELECT
                        cc.url, cc.title, cc.markdown, cc.content,
                        cc.timestamp, cc.tags, distance
                    FROM content_vectors
                    JOIN crawled_content cc ON content_vectors.content_id = cc.id
                    WHERE embedding MATCH ? AND k = ?
                    ORDER BY distance
                '''
                params = (embedding_bytes, limit)

            # Execute query
            rows = self.db.execute_with_retry(sql, params).fetchall()

            # Format results
            results = []
            seen_urls = set()

            for row in rows:
                url = row[0]

                # Deduplicate by URL
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                distance = row[6]

                # Convert distance to similarity score
                # sqlite-vec uses cosine distance (0 = identical, 2 = opposite)
                similarity_score = 1 - (distance / 2.0) if distance <= 2.0 else 0.0

                # Get content (prefer markdown over raw content)
                content_text = row[2] if row[2] else row[3]

                # Truncate long content
                if content_text and len(content_text) > 10000:
                    content_text = content_text[:10000] + '...'

                results.append({
                    'url': url,
                    'title': row[1],
                    'content': content_text,
                    'timestamp': row[4],
                    'tags': row[5],
                    'similarity_score': similarity_score,
                    'source': 'vector',  # Mark source for result merging
                })

            return results

        except Exception as e:
            logger.error(f"Low-level vector search failed: {e}")
            return []


# Global instance
_vector_retriever: Optional[VectorRetriever] = None


def get_vector_retriever(db_manager) -> VectorRetriever:
    """Get or create vector retriever instance"""
    global _vector_retriever
    if _vector_retriever is None:
        _vector_retriever = VectorRetriever(db_manager)
    return _vector_retriever
