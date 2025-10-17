"""
Final Retriever - Complete KG-Enhanced RAG Pipeline
Phases 1-4 integrated
"""

import logging
from typing import List, Dict, Optional
import numpy as np

from .query_parser import QueryParser
from .embeddings import QueryEmbedder
from .expanded_retriever import ExpandedHybridRetrieverSync
from .advanced_ranker import AdvancedRanker, ContextExtractor

logger = logging.getLogger(__name__)


class FinalRetriever:
    """
    Complete KG-Enhanced RAG retrieval pipeline

    Integrates all phases:
    - Phase 1: Query parsing & entity extraction
    - Phase 2: Parallel vector + graph retrieval
    - Phase 3: KG-powered entity expansion
    - Phase 4: Advanced ranking & context extraction
    """

    def __init__(
        self,
        parser: QueryParser,
        embedder: QueryEmbedder,
        expanded_retriever: ExpandedHybridRetrieverSync,
        ranker: Optional[AdvancedRanker] = None,
        context_extractor: Optional[ContextExtractor] = None
    ):
        """
        Initialize final retriever

        Args:
            parser: QueryParser instance
            embedder: QueryEmbedder instance
            expanded_retriever: ExpandedHybridRetrieverSync instance
            ranker: Optional AdvancedRanker (creates default if None)
            context_extractor: Optional ContextExtractor
        """
        self.parser = parser
        self.embedder = embedder
        self.expanded_retriever = expanded_retriever
        self.ranker = ranker or AdvancedRanker()
        self.context_extractor = context_extractor or ContextExtractor()

    def search(
        self,
        query: str,
        limit: int = 10,
        tags: Optional[List[str]] = None,
        include_context: bool = True,
        enable_expansion: bool = True
    ) -> Dict:
        """
        Complete end-to-end search

        Args:
            query: User query string
            limit: Max results to return
            tags: Optional tag filters
            include_context: Extract relevant context snippets
            enable_expansion: Use entity expansion

        Returns:
            Dict with results, metadata, and scores
        """
        try:
            logger.info(f"Search query: {query}")

            # Phase 1: Parse query
            parsed = self.parser.parse(query)
            logger.debug(f"Entities: {parsed.extracted_entities}")

            # Generate embedding
            embedding = self.embedder.embed_query(parsed.normalized_query)

            # Phase 2-3: Retrieve with expansion
            retrieval_result = self.expanded_retriever.retrieve(
                query_embedding=embedding,
                entities=parsed.extracted_entities,
                limit=limit * 2,  # Get more for ranking
                tags=tags,
                max_expansions=5
            )

            results = retrieval_result.get('results', [])

            # Phase 4: Advanced ranking
            ranked_results = self.ranker.rank(
                results,
                query,
                parsed.extracted_entities
            )

            # Limit to requested count
            ranked_results = ranked_results[:limit]

            # Extract context snippets
            if include_context:
                for result in ranked_results:
                    if result.get('content'):
                        result['context_snippet'] = self.context_extractor.extract_context(
                            result['content'],
                            query,
                            parsed.extracted_entities,
                            max_length=300
                        )

            # Build response
            return {
                'query': query,
                'parsed_query': {
                    'normalized': parsed.normalized_query,
                    'entities': parsed.extracted_entities,
                    'intent': parsed.query_intent,
                    'confidence': parsed.confidence
                },
                'expansion': retrieval_result.get('expansion'),
                'results': ranked_results,
                'stats': {
                    'total_retrieved': len(results),
                    'returned': len(ranked_results),
                    **retrieval_result.get('stats', {})
                }
            }

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return {
                'query': query,
                'error': str(e),
                'results': []
            }


def create_final_retriever(
    parser: QueryParser,
    embedder: QueryEmbedder,
    expanded_retriever: ExpandedHybridRetrieverSync
) -> FinalRetriever:
    """
    Factory function to create fully configured retriever

    Args:
        parser: QueryParser instance
        embedder: QueryEmbedder instance
        expanded_retriever: ExpandedHybridRetrieverSync instance

    Returns:
        FinalRetriever ready to use
    """
    ranker = AdvancedRanker(
        vector_weight=0.35,
        graph_weight=0.25,
        text_weight=0.20,
        recency_weight=0.10,
        title_weight=0.10
    )

    context_extractor = ContextExtractor()

    return FinalRetriever(
        parser,
        embedder,
        expanded_retriever,
        ranker,
        context_extractor
    )
