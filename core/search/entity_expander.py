"""
Entity Expander - KG-Powered Query Expansion
Uses Neo4j relationships to discover related entities
"""

import logging
import asyncio
from typing import List, Dict, Set, Optional, Tuple
import httpx

logger = logging.getLogger(__name__)


class EntityExpander:
    """
    Expand query entities using knowledge graph relationships

    Discovers related entities through:
    - Direct relationships (e.g., FastAPI -> Python, Pydantic)
    - Co-occurrences (entities mentioned together)
    - Hierarchical relationships (e.g., Framework -> Web::Framework)
    """

    def __init__(self, kg_service_url: str = "http://kg-service:8088"):
        """
        Initialize entity expander

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

    async def expand_entities(
        self,
        entities: List[str],
        max_expansions: int = 5,
        min_confidence: float = 0.4,
        include_cooccurrences: bool = True
    ) -> Dict:
        """
        Expand entities using knowledge graph

        Args:
            entities: Original entities from query
            max_expansions: Max number of related entities to add
            min_confidence: Minimum relationship confidence
            include_cooccurrences: Include co-occurring entities

        Returns:
            Dict with:
            - original_entities: Input entities
            - expanded_entities: New related entities discovered
            - relationships: Entity relationships found
            - confidence_scores: Confidence for each expansion
        """
        try:
            if not entities:
                logger.debug("No entities to expand")
                return self._empty_expansion()

            logger.debug(f"Expanding {len(entities)} entities: {entities}")

            # Find related entities through relationships
            related = await self._find_related_entities(
                entities,
                max_expansions,
                min_confidence
            )

            # Optionally include co-occurring entities
            if include_cooccurrences:
                cooccur = await self._find_cooccurring_entities(
                    entities,
                    max_expansions // 2,
                    min_confidence
                )
                related = self._merge_expansions(related, cooccur)

            logger.info(
                f"Entity expansion: {len(entities)} → "
                f"{len(related.get('expanded_entities', []))} new entities"
            )

            return related

        except Exception as e:
            logger.error(f"Entity expansion failed: {e}")
            return self._empty_expansion()

    async def _find_related_entities(
        self,
        entities: List[str],
        max_results: int,
        min_confidence: float
    ) -> Dict:
        """
        Find entities directly related through Neo4j relationships

        Args:
            entities: Source entities
            max_results: Max related entities to return
            min_confidence: Min relationship confidence

        Returns:
            Expansion dictionary
        """
        try:
            client = await self._get_client()

            # Cypher query to find related entities
            cypher = """
            MATCH (e1:Entity)-[r:RELATED_TO|:CO_OCCURS_WITH]-(e2:Entity)
            WHERE e1.name IN $entity_names
              AND r.confidence >= $min_confidence
              AND e2.name <> e1.name
            WITH e2, r, COUNT(DISTINCT e1) as connection_count
            ORDER BY connection_count DESC, r.confidence DESC
            LIMIT $max_results
            RETURN e2.name as entity,
                   e2.type as entity_type,
                   r.confidence as confidence,
                   connection_count,
                   type(r) as relationship_type
            """

            response = await client.post(
                f"{self.kg_service_url}/api/v1/query/cypher",
                json={
                    "query": cypher,
                    "parameters": {
                        "entity_names": entities,
                        "min_confidence": min_confidence,
                        "max_results": max_results
                    }
                }
            )

            if response.status_code != 200:
                logger.warning(f"kg-service returned {response.status_code}")
                return self._empty_expansion()

            data = response.json()
            records = data.get('results', [])

            # Format results
            expanded_entities = []
            relationships = []
            confidence_scores = {}

            for record in records:
                entity = record.get('entity')
                if entity and entity not in entities:
                    expanded_entities.append(entity)
                    confidence_scores[entity] = record.get('confidence', 0.5)
                    relationships.append({
                        'entity': entity,
                        'type': record.get('entity_type'),
                        'relationship': record.get('relationship_type'),
                        'confidence': record.get('confidence'),
                        'connections': record.get('connection_count')
                    })

            return {
                'original_entities': entities,
                'expanded_entities': expanded_entities,
                'relationships': relationships,
                'confidence_scores': confidence_scores
            }

        except httpx.ConnectError:
            logger.warning("kg-service not available")
            return self._empty_expansion()
        except Exception as e:
            logger.error(f"Related entity search failed: {e}")
            return self._empty_expansion()

    async def _find_cooccurring_entities(
        self,
        entities: List[str],
        max_results: int,
        min_confidence: float
    ) -> Dict:
        """
        Find entities that co-occur with query entities in documents

        Args:
            entities: Source entities
            max_results: Max co-occurring entities
            min_confidence: Min co-occurrence confidence

        Returns:
            Expansion dictionary
        """
        try:
            client = await self._get_client()

            # Cypher query for co-occurrences
            cypher = """
            MATCH (e1:Entity)-[:MENTIONED_IN]->(d:Document)<-[:MENTIONED_IN]-(e2:Entity)
            WHERE e1.name IN $entity_names
              AND e2.name <> e1.name
            WITH e2, COUNT(DISTINCT d) as doc_count
            WHERE doc_count >= 2
            ORDER BY doc_count DESC
            LIMIT $max_results
            RETURN e2.name as entity,
                   e2.type as entity_type,
                   doc_count
            """

            response = await client.post(
                f"{self.kg_service_url}/api/v1/query/cypher",
                json={
                    "query": cypher,
                    "parameters": {
                        "entity_names": entities,
                        "max_results": max_results
                    }
                }
            )

            if response.status_code != 200:
                return {'expanded_entities': [], 'relationships': [], 'confidence_scores': {}}

            data = response.json()
            records = data.get('results', [])

            expanded_entities = []
            relationships = []
            confidence_scores = {}

            for record in records:
                entity = record.get('entity')
                if entity and entity not in entities:
                    doc_count = record.get('doc_count', 1)
                    confidence = min(1.0, doc_count / 10.0)  # Normalize

                    if confidence >= min_confidence:
                        expanded_entities.append(entity)
                        confidence_scores[entity] = confidence
                        relationships.append({
                            'entity': entity,
                            'type': record.get('entity_type'),
                            'relationship': 'CO_OCCURS_IN_DOCS',
                            'confidence': confidence,
                            'doc_count': doc_count
                        })

            return {
                'expanded_entities': expanded_entities,
                'relationships': relationships,
                'confidence_scores': confidence_scores
            }

        except Exception as e:
            logger.error(f"Co-occurrence search failed: {e}")
            return {'expanded_entities': [], 'relationships': [], 'confidence_scores': {}}

    def _merge_expansions(self, expansion1: Dict, expansion2: Dict) -> Dict:
        """Merge two expansion results"""
        merged_entities = list(set(
            expansion1.get('expanded_entities', []) +
            expansion2.get('expanded_entities', [])
        ))

        merged_relationships = (
            expansion1.get('relationships', []) +
            expansion2.get('relationships', [])
        )

        merged_scores = {
            **expansion1.get('confidence_scores', {}),
            **expansion2.get('confidence_scores', {})
        }

        return {
            'original_entities': expansion1.get('original_entities', []),
            'expanded_entities': merged_entities,
            'relationships': merged_relationships,
            'confidence_scores': merged_scores
        }

    def _empty_expansion(self) -> Dict:
        """Return empty expansion result"""
        return {
            'original_entities': [],
            'expanded_entities': [],
            'relationships': [],
            'confidence_scores': {}
        }

    async def close(self):
        """Close HTTP client"""
        if self.client:
            await self.client.aclose()
            self.client = None


# Synchronous wrapper
class EntityExpanderSync:
    """Synchronous wrapper for EntityExpander"""

    def __init__(self, kg_service_url: str = "http://kg-service:8088"):
        self.expander = EntityExpander(kg_service_url)

    def expand_entities(
        self,
        entities: List[str],
        max_expansions: int = 5,
        min_confidence: float = 0.4,
        include_cooccurrences: bool = True
    ) -> Dict:
        """Synchronous expand"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            self.expander.expand_entities(
                entities,
                max_expansions,
                min_confidence,
                include_cooccurrences
            )
        )


# Global instance
_entity_expander: Optional[EntityExpanderSync] = None


def get_entity_expander(kg_service_url: str = "http://kg-service:8088") -> EntityExpanderSync:
    """Get or create entity expander instance"""
    global _entity_expander
    if _entity_expander is None:
        _entity_expander = EntityExpanderSync(kg_service_url)
    return _entity_expander
