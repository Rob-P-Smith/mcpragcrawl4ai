"""
Hybrid Retriever - Parallel Multi-Modal Search
Coordinates vector and graph retrieval, merges results
"""

import logging
import asyncio
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
import numpy as np

from .vector_retriever import VectorRetriever
from .graph_retriever import GraphRetriever

logger = logging.getLogger(__name__)


class HybridRetriever:
    """
    Orchestrates parallel retrieval from both vector and graph sources

    Runs SQLite vector search and Neo4j graph search concurrently,
    then merges and deduplicates results.
    """

    def __init__(
        self,
        vector_retriever: VectorRetriever,
        graph_retriever: GraphRetriever,
        kg_enabled: bool = True
    ):
        """
        Initialize hybrid retriever

        Args:
            vector_retriever: VectorRetriever instance
            graph_retriever: GraphRetriever instance
            kg_enabled: Whether to use graph retrieval
        """
        self.vector_retriever = vector_retriever
        self.graph_retriever = graph_retriever
        self.kg_enabled = kg_enabled

    async def retrieve(
        self,
        query_embedding: np.ndarray,
        entities: List[str],
        limit: int = 10,
        vector_weight: float = 0.6,
        graph_weight: float = 0.4,
        tags: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Retrieve documents using both vector and graph search in parallel

        Args:
            query_embedding: TEMPORARY query embedding for vector search
            entities: Extracted entities for graph search
            limit: Total number of results to return
            vector_weight: Weight for vector search results (0.0-1.0)
            graph_weight: Weight for graph search results (0.0-1.0)
            tags: Optional tags to filter vector results

        Returns:
            Merged and ranked list of documents
        """
        try:
            logger.info(
                f"Hybrid search: {len(entities)} entities, "
                f"limit={limit}, kg_enabled={self.kg_enabled}"
            )

            # Run both searches in parallel
            vector_results, graph_results = await self._parallel_retrieve(
                query_embedding,
                entities,
                limit,
                tags
            )

            logger.info(
                f"Retrieval complete: {len(vector_results)} vector, "
                f"{len(graph_results)} graph"
            )

            # Merge and deduplicate results
            merged = self._merge_results(
                vector_results,
                graph_results,
                vector_weight,
                graph_weight,
                limit
            )

            logger.info(f"Hybrid search returning {len(merged)} merged results")

            return merged

        except Exception as e:
            logger.error(f"Hybrid retrieval failed: {e}")
            # Fallback to vector-only
            logger.warning("Falling back to vector-only search")
            return await self._vector_only_retrieve(query_embedding, limit, tags)

    async def _parallel_retrieve(
        self,
        query_embedding: np.ndarray,
        entities: List[str],
        limit: int,
        tags: Optional[List[str]]
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Execute vector and graph retrieval in parallel

        Args:
            query_embedding: Query embedding
            entities: Entity list
            limit: Result limit
            tags: Tag filters

        Returns:
            Tuple of (vector_results, graph_results)
        """
        # Request more results from each source for better merging
        per_source_limit = limit * 2

        # Create tasks for parallel execution
        tasks = []

        # Vector search (synchronous, run in thread)
        vector_task = asyncio.to_thread(
            self.vector_retriever.retrieve,
            query_embedding,
            limit=per_source_limit,
            tags=tags
        )
        tasks.append(vector_task)

        # Graph search (async)
        if self.kg_enabled and entities:
            graph_task = self.graph_retriever.retrieve(
                entities,
                limit=per_source_limit
            )
            tasks.append(graph_task)
        else:
            # Placeholder for no graph search
            tasks.append(asyncio.sleep(0, result=[]))

        # Execute in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions
        vector_results = results[0] if not isinstance(results[0], Exception) else []
        graph_results = results[1] if not isinstance(results[1], Exception) else []

        if isinstance(results[0], Exception):
            logger.error(f"Vector search failed: {results[0]}")
        if isinstance(results[1], Exception):
            logger.error(f"Graph search failed: {results[1]}")

        return vector_results, graph_results

    def _merge_results(
        self,
        vector_results: List[Dict],
        graph_results: List[Dict],
        vector_weight: float,
        graph_weight: float,
        limit: int
    ) -> List[Dict]:
        """
        Merge and deduplicate results from both sources

        Args:
            vector_results: Results from vector search
            graph_results: Results from graph search
            vector_weight: Weight for vector scores
            graph_weight: Weight for graph scores
            limit: Max results to return

        Returns:
            Merged and ranked list
        """
        # Normalize weights
        total_weight = vector_weight + graph_weight
        if total_weight > 0:
            vector_weight /= total_weight
            graph_weight /= total_weight

        # Deduplicate by URL
        merged_map = {}

        # Add vector results
        for result in vector_results:
            url = result.get('url')
            if not url:
                continue

            score = result.get('similarity_score', 0.0) * vector_weight

            merged_map[url] = {
                **result,
                'hybrid_score': score,
                'sources': ['vector'],
                'vector_score': result.get('similarity_score', 0.0),
                'graph_score': 0.0,
            }

        # Merge graph results
        for result in graph_results:
            url = result.get('url')
            if not url:
                continue

            graph_score = result.get('relevance_score', 0.0)

            if url in merged_map:
                # URL exists from vector search - combine scores
                merged_map[url]['hybrid_score'] += graph_score * graph_weight
                merged_map[url]['graph_score'] = graph_score
                merged_map[url]['sources'].append('graph')
                merged_map[url]['entity_matches'] = result.get('entity_matches', 0)
            else:
                # New URL from graph search only
                merged_map[url] = {
                    **result,
                    'hybrid_score': graph_score * graph_weight,
                    'sources': ['graph'],
                    'vector_score': 0.0,
                    'graph_score': graph_score,
                }

        # Sort by hybrid score
        merged_list = sorted(
            merged_map.values(),
            key=lambda x: x['hybrid_score'],
            reverse=True
        )

        # Limit results
        return merged_list[:limit]

    async def _vector_only_retrieve(
        self,
        query_embedding: np.ndarray,
        limit: int,
        tags: Optional[List[str]]
    ) -> List[Dict]:
        """Fallback to vector-only search"""
        try:
            results = await asyncio.to_thread(
                self.vector_retriever.retrieve,
                query_embedding,
                limit=limit,
                tags=tags
            )
            return results
        except Exception as e:
            logger.error(f"Vector fallback failed: {e}")
            return []


# Synchronous wrapper
class HybridRetrieverSync:
    """Synchronous wrapper for HybridRetriever"""

    def __init__(
        self,
        vector_retriever: VectorRetriever,
        graph_retriever: GraphRetriever,
        kg_enabled: bool = True
    ):
        self.retriever = HybridRetriever(vector_retriever, graph_retriever, kg_enabled)

    def retrieve(
        self,
        query_embedding: np.ndarray,
        entities: List[str],
        limit: int = 10,
        vector_weight: float = 0.6,
        graph_weight: float = 0.4,
        tags: Optional[List[str]] = None
    ) -> List[Dict]:
        """Synchronous retrieve"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            self.retriever.retrieve(
                query_embedding,
                entities,
                limit,
                vector_weight,
                graph_weight,
                tags
            )
        )
