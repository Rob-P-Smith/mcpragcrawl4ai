"""
Graph Retriever for Neo4j-based entity search
Uses extracted entities to traverse knowledge graph
"""

import logging
import asyncio
from typing import List, Dict, Optional
import httpx

logger = logging.getLogger(__name__)


class GraphRetriever:
    """
    Retrieve documents from Neo4j using entity-based graph traversal

    Uses entities extracted by GLiNER to find related documents
    through the knowledge graph.
    """

    def __init__(self, kg_service_url: str = "http://kg-service:8088"):
        """
        Initialize graph retriever

        Args:
            kg_service_url: URL of kg-service API
        """
        self.kg_service_url = kg_service_url.rstrip('/')
        self.client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self.client is None:
            self.client = httpx.AsyncClient(timeout=30.0)
        return self.client

    async def retrieve(
        self,
        entities: List[str],
        limit: int = 10,
        min_confidence: float = 0.3
    ) -> List[Dict]:
        """
        Retrieve documents related to extracted entities

        Args:
            entities: List of entity names from GLiNER
            limit: Maximum number of results
            min_confidence: Minimum entity match confidence

        Returns:
            List of documents connected to entities
        """
        try:
            if not entities:
                logger.debug("No entities provided, skipping graph search")
                return []

            logger.debug(f"Graph search for entities: {entities}")

            # Query kg-service for entity-related documents
            results = await self._query_entity_documents(
                entities,
                limit=limit,
                min_confidence=min_confidence
            )

            logger.info(f"Graph search returned {len(results)} results")

            return results

        except Exception as e:
            logger.error(f"Graph retrieval failed: {e}")
            return []

    async def _query_entity_documents(
        self,
        entities: List[str],
        limit: int,
        min_confidence: float
    ) -> List[Dict]:
        """
        Query kg-service for documents related to entities

        Strategy:
        1. Search for entities matching query terms
        2. Get chunks containing those entities (with vector_rowids)
        3. Retrieve chunk content from SQLite using vector_rowids
        4. Return formatted results

        Args:
            entities: Entity names to search for
            limit: Max results
            min_confidence: Min match confidence

        Returns:
            List of related document chunks with graph metadata
        """
        try:
            client = await self._get_client()

            # Step 1: Find matching entities
            entity_search_response = await client.post(
                f"{self.kg_service_url}/api/v1/search/entities",
                json={
                    "entity_terms": entities,
                    "limit": 50,
                    "min_mentions": 1
                }
            )

            if entity_search_response.status_code != 200:
                logger.warning(
                    f"Entity search failed: {entity_search_response.status_code}"
                )
                return []

            entity_data = entity_search_response.json()
            found_entities = entity_data.get('entities', [])

            if not found_entities:
                logger.debug(f"No entities found matching: {entities}")
                return []

            entity_names = [e['text'] for e in found_entities]
            logger.debug(f"Found {len(entity_names)} matching entities")

            # Step 2: Get chunks containing these entities
            chunk_search_response = await client.post(
                f"{self.kg_service_url}/api/v1/search/chunks",
                json={
                    "entity_names": entity_names,
                    "limit": limit,
                    "include_document_info": True
                }
            )

            if chunk_search_response.status_code != 200:
                logger.warning(
                    f"Chunk search failed: {chunk_search_response.status_code}"
                )
                return []

            chunk_data = chunk_search_response.json()
            chunks = chunk_data.get('chunks', [])

            if not chunks:
                logger.debug("No chunks found for entities")
                return []

            # Step 3: Format results for hybrid retriever
            # Note: We return chunk info with vector_rowid for SQLite lookup
            # The actual content will be retrieved from SQLite in VectorRetriever
            results = []
            for chunk in chunks:
                # Calculate relevance score based on entity matches
                entity_count = chunk.get('entity_count', 1)
                relevance_score = min(1.0, entity_count / len(entities))

                # Build result with chunk metadata
                results.append({
                    'vector_rowid': chunk['vector_rowid'],
                    'url': chunk.get('document_url', 'unknown'),
                    'title': chunk.get('document_title', 'unknown'),
                    'chunk_index': chunk.get('chunk_index', 0),
                    'matched_entities': chunk.get('matched_entities', []),
                    'relevance_score': relevance_score,
                    'entity_matches': entity_count,
                    'source': 'graph',  # Mark source for result merging
                })

            logger.info(
                f"Graph search: {len(entities)} query entities → "
                f"{len(found_entities)} matches → {len(results)} chunks"
            )

            return results

        except httpx.ConnectError:
            logger.warning("kg-service not available, skipping graph search")
            return []
        except Exception as e:
            logger.error(f"kg-service query failed: {e}", exc_info=True)
            return []

    async def close(self):
        """Close HTTP client"""
        if self.client:
            await self.client.aclose()
            self.client = None


# Synchronous wrapper for backward compatibility
class GraphRetrieverSync:
    """Synchronous wrapper for GraphRetriever"""

    def __init__(self, kg_service_url: str = "http://kg-service:8088"):
        self.retriever = GraphRetriever(kg_service_url)

    def retrieve(
        self,
        entities: List[str],
        limit: int = 10,
        min_confidence: float = 0.3
    ) -> List[Dict]:
        """Synchronous retrieve"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            self.retriever.retrieve(entities, limit, min_confidence)
        )


# Global instance
_graph_retriever: Optional[GraphRetrieverSync] = None


def get_graph_retriever(kg_service_url: str = "http://kg-service:8088") -> GraphRetrieverSync:
    """Get or create graph retriever instance"""
    global _graph_retriever
    if _graph_retriever is None:
        _graph_retriever = GraphRetrieverSync(kg_service_url)
    return _graph_retriever
