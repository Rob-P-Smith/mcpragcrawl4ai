"""
Expanded Hybrid Retriever - Phase 3
Includes KG-powered entity expansion before retrieval
"""

import logging
import asyncio
from typing import List, Dict, Optional
import numpy as np

from .hybrid_retriever import HybridRetriever
from .entity_expander import EntityExpander

logger = logging.getLogger(__name__)


class ExpandedHybridRetriever:
    """
    Enhanced hybrid retrieval with entity expansion

    Phase 3 addition: Expands query entities using KG relationships
    before performing parallel retrieval.
    """

    def __init__(
        self,
        hybrid_retriever: HybridRetriever,
        entity_expander: EntityExpander,
        enable_expansion: bool = True
    ):
        """
        Initialize expanded retriever

        Args:
            hybrid_retriever: HybridRetriever instance
            entity_expander: EntityExpander instance
            enable_expansion: Whether to use entity expansion
        """
        self.hybrid_retriever = hybrid_retriever
        self.entity_expander = entity_expander
        self.enable_expansion = enable_expansion

    async def retrieve(
        self,
        query_embedding: np.ndarray,
        entities: List[str],
        limit: int = 10,
        vector_weight: float = 0.5,
        graph_weight: float = 0.3,
        expansion_weight: float = 0.2,
        tags: Optional[List[str]] = None,
        max_expansions: int = 5
    ) -> Dict:
        """
        Retrieve with entity expansion

        Args:
            query_embedding: Query embedding
            entities: Original extracted entities
            limit: Max results
            vector_weight: Weight for vector search
            graph_weight: Weight for graph search
            expansion_weight: Weight for expanded entity results
            tags: Optional tag filters
            max_expansions: Max entities to discover

        Returns:
            Dict with results and expansion info
        """
        try:
            logger.info(
                f"Expanded retrieval: {len(entities)} entities, "
                f"expansion={'enabled' if self.enable_expansion else 'disabled'}"
            )

            # Phase 3: Expand entities using KG
            expansion_result = None
            expanded_entities = []

            if self.enable_expansion and entities:
                expansion_result = await self.entity_expander.expand_entities(
                    entities,
                    max_expansions=max_expansions,
                    min_confidence=0.4,
                    include_cooccurrences=True
                )
                expanded_entities = expansion_result.get('expanded_entities', [])

                logger.info(
                    f"Entity expansion: {len(entities)} → "
                    f"{len(expanded_entities)} new entities"
                )

            # Retrieve with original entities
            original_results = await self.hybrid_retriever.retrieve(
                query_embedding,
                entities,
                limit=limit * 2,  # Get more for merging
                vector_weight=vector_weight,
                graph_weight=graph_weight,
                tags=tags
            )

            # If we have expanded entities, retrieve with them too
            expanded_results = []
            if expanded_entities:
                expanded_results = await self.hybrid_retriever.retrieve(
                    query_embedding,
                    expanded_entities,
                    limit=limit,
                    vector_weight=vector_weight * 0.7,  # Lower weight
                    graph_weight=graph_weight * 0.7,
                    tags=tags
                )

            # Merge results with expansion boost
            merged = self._merge_with_expansion(
                original_results,
                expanded_results,
                expansion_result,
                expansion_weight,
                limit
            )

            return {
                'results': merged,
                'expansion': expansion_result,
                'stats': {
                    'original_entities': len(entities),
                    'expanded_entities': len(expanded_entities),
                    'original_results': len(original_results),
                    'expanded_results': len(expanded_results),
                    'final_results': len(merged)
                }
            }

        except Exception as e:
            logger.error(f"Expanded retrieval failed: {e}")
            # Fallback to basic retrieval
            results = await self.hybrid_retriever.retrieve(
                query_embedding,
                entities,
                limit,
                vector_weight,
                graph_weight,
                tags
            )
            return {
                'results': results,
                'expansion': None,
                'stats': {'error': str(e)}
            }

    def _merge_with_expansion(
        self,
        original_results: List[Dict],
        expanded_results: List[Dict],
        expansion_info: Optional[Dict],
        expansion_weight: float,
        limit: int
    ) -> List[Dict]:
        """
        Merge original and expanded results with boosting

        Args:
            original_results: Results from original entities
            expanded_results: Results from expanded entities
            expansion_info: Entity expansion metadata
            expansion_weight: Weight for expansion boost
            limit: Max results

        Returns:
            Merged and ranked results
        """
        # Create URL-based map
        merged_map = {}

        # Add original results (higher priority)
        for result in original_results:
            url = result.get('url')
            if not url:
                continue

            merged_map[url] = {
                **result,
                'final_score': result.get('hybrid_score', 0.0),
                'from_original': True,
                'from_expansion': False
            }

        # Add/merge expanded results
        for result in expanded_results:
            url = result.get('url')
            if not url:
                continue

            # Calculate expansion boost based on entity relationships
            expansion_boost = self._calculate_expansion_boost(
                result,
                expansion_info,
                expansion_weight
            )

            if url in merged_map:
                # URL already in original results - boost its score
                merged_map[url]['final_score'] += expansion_boost
                merged_map[url]['from_expansion'] = True
                merged_map[url]['expansion_boost'] = expansion_boost
            else:
                # New URL from expansion
                merged_map[url] = {
                    **result,
                    'final_score': result.get('hybrid_score', 0.0) + expansion_boost,
                    'from_original': False,
                    'from_expansion': True,
                    'expansion_boost': expansion_boost
                }

        # Sort by final score
        merged_list = sorted(
            merged_map.values(),
            key=lambda x: x['final_score'],
            reverse=True
        )

        return merged_list[:limit]

    def _calculate_expansion_boost(
        self,
        result: Dict,
        expansion_info: Optional[Dict],
        base_weight: float
    ) -> float:
        """
        Calculate score boost for expansion-discovered results

        Args:
            result: Result document
            expansion_info: Expansion metadata
            base_weight: Base expansion weight

        Returns:
            Boost score to add
        """
        if not expansion_info:
            return 0.0

        # Base boost
        boost = base_weight * 0.5

        # Additional boost based on relationship confidence
        confidence_scores = expansion_info.get('confidence_scores', {})
        if confidence_scores:
            avg_confidence = sum(confidence_scores.values()) / len(confidence_scores)
            boost += base_weight * 0.5 * avg_confidence

        return boost


# Synchronous wrapper
class ExpandedHybridRetrieverSync:
    """Synchronous wrapper"""

    def __init__(
        self,
        hybrid_retriever,
        entity_expander,
        enable_expansion: bool = True
    ):
        from .hybrid_retriever import HybridRetriever
        # Unwrap if sync wrapper
        if hasattr(hybrid_retriever, 'retriever'):
            hybrid_retriever = hybrid_retriever.retriever

        self.retriever = ExpandedHybridRetriever(
            hybrid_retriever,
            entity_expander.expander if hasattr(entity_expander, 'expander') else entity_expander,
            enable_expansion
        )

    def retrieve(
        self,
        query_embedding: np.ndarray,
        entities: List[str],
        limit: int = 10,
        vector_weight: float = 0.5,
        graph_weight: float = 0.3,
        expansion_weight: float = 0.2,
        tags: Optional[List[str]] = None,
        max_expansions: int = 5
    ) -> Dict:
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
                expansion_weight,
                tags,
                max_expansions
            )
        )
