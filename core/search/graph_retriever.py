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

        Args:
            entities: Entity names to search for
            limit: Max results
            min_confidence: Min match confidence

        Returns:
            List of related documents
        """
        try:
            client = await self._get_client()

            # Build Cypher query to find documents mentioning entities
            # This is a simplified version - you can expand based on kg-service API
            cypher = """
            MATCH (e:Entity)-[:MENTIONED_IN]->(d:Document)
            WHERE e.name IN $entity_names
            WITH d, COUNT(DISTINCT e) as entity_count
            ORDER BY entity_count DESC
            LIMIT $limit
            RETURN d.url as url, d.title as title, d.content as content,
                   d.timestamp as timestamp, entity_count
            """

            # Call kg-service API
            response = await client.post(
                f"{self.kg_service_url}/api/v1/query/cypher",
                json={
                    "query": cypher,
                    "parameters": {
                        "entity_names": entities,
                        "limit": limit
                    }
                }
            )

            if response.status_code != 200:
                logger.warning(
                    f"kg-service returned {response.status_code}: "
                    f"{response.text}"
                )
                return []

            data = response.json()
            records = data.get('results', [])

            # Format results
            results = []
            for record in records:
                # Calculate relevance score based on entity matches
                entity_count = record.get('entity_count', 1)
                relevance_score = min(1.0, entity_count / len(entities))

                results.append({
                    'url': record.get('url'),
                    'title': record.get('title'),
                    'content': record.get('content', '')[:10000],  # Truncate
                    'timestamp': record.get('timestamp'),
                    'tags': None,  # Neo4j doesn't have tags
                    'relevance_score': relevance_score,
                    'entity_matches': entity_count,
                    'source': 'graph',  # Mark source for result merging
                })

            return results

        except httpx.ConnectError:
            logger.warning("kg-service not available, skipping graph search")
            return []
        except Exception as e:
            logger.error(f"kg-service query failed: {e}")
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
