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

        Uses the new /api/v1/expand/entities endpoint which handles
        entity expansion via co-occurrence and relationships.

        Args:
            entities: Source entities
            max_results: Max related entities to return
            min_confidence: Min relationship confidence

        Returns:
            Expansion dictionary
        """
        try:
            client = await self._get_client()

            # Call entity expansion endpoint
            response = await client.post(
                f"{self.kg_service_url}/api/v1/expand/entities",
                json={
                    "entity_names": entities,
                    "max_expansions": max_results,
                    "min_confidence": min_confidence,
                    "expansion_depth": 1
                }
            )

            if response.status_code != 200:
                logger.warning(
                    f"Entity expansion returned {response.status_code}: "
                    f"{response.text}"
                )
                return self._empty_expansion()

            data = response.json()

            if not data.get('success'):
                logger.warning("Entity expansion failed")
                return self._empty_expansion()

            # Extract expanded entities
            expanded_list = data.get('expanded_entities', [])
            original = data.get('original_entities', entities)

            # Format results
            expanded_entities = []
            relationships = []
            confidence_scores = {}

            for entity_obj in expanded_list:
                entity_text = entity_obj.get('text')
                if entity_text and entity_text not in original:
                    expanded_entities.append(entity_text)
                    confidence = entity_obj.get('relationship_confidence', 0.5)
                    confidence_scores[entity_text] = confidence
                    relationships.append({
                        'entity': entity_text,
                        'type': entity_obj.get('type_primary'),
                        'relationship': entity_obj.get('relationship_type', 'CO_OCCURS'),
                        'confidence': confidence,
                        'mention_count': entity_obj.get('mention_count', 0)
                    })

            logger.debug(
                f"Entity expansion: {len(original)} → {len(expanded_entities)} new"
            )

            return {
                'original_entities': original,
                'expanded_entities': expanded_entities,
                'relationships': relationships,
                'confidence_scores': confidence_scores
            }

        except httpx.ConnectError:
            logger.warning("kg-service not available")
            return self._empty_expansion()
        except Exception as e:
            logger.error(f"Related entity search failed: {e}", exc_info=True)
            return self._empty_expansion()

    async def _find_cooccurring_entities(
        self,
        entities: List[str],
        max_results: int,
        min_confidence: float
    ) -> Dict:
        """
        Find entities that co-occur with query entities in documents

        Note: The /api/v1/expand/entities endpoint already handles co-occurrence,
        so this method reuses the same endpoint with different parameters.

        Args:
            entities: Source entities
            max_results: Max co-occurring entities
            min_confidence: Min co-occurrence confidence

        Returns:
            Expansion dictionary
        """
        try:
            # The expansion endpoint already handles co-occurrence
            # So we can just call it with appropriate parameters
            return await self._find_related_entities(
                entities,
                max_results,
                min_confidence
            )

        except Exception as e:
            logger.error(f"Co-occurrence search failed: {e}", exc_info=True)
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
