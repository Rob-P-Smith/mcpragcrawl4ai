"""
Search Handler - Phase 5
High-level search interface for MCP tools and API
"""

import logging
import time
from typing import Dict, Optional, List

from .query_parser import get_query_parser
from .embeddings import get_query_embedder
from .vector_retriever import VectorRetriever
from .graph_retriever import GraphRetriever
from .hybrid_retriever import HybridRetrieverSync
from .entity_expander import get_entity_expander
from .expanded_retriever import ExpandedHybridRetrieverSync
from .final_retriever import create_final_retriever
from .response_formatter import get_response_formatter

logger = logging.getLogger(__name__)


class SearchHandler:
    """
    High-level search interface

    Provides simple API for executing complete KG-enhanced searches
    Used by:
    - MCP tools (search_memory)
    - REST API endpoints
    - Direct Python usage
    """

    def __init__(self, db_manager, kg_service_url: str = "http://kg-service:8088"):
        """
        Initialize search handler

        Args:
            db_manager: Database manager instance
            kg_service_url: KG service URL
        """
        logger.info("Initializing SearchHandler...")

        # Initialize components
        self.parser = get_query_parser()
        self.embedder = get_query_embedder()

        # Retrievers
        vector_retriever = VectorRetriever(db_manager)
        graph_retriever = GraphRetriever(kg_service_url)
        hybrid_retriever = HybridRetrieverSync(
            vector_retriever,
            graph_retriever,
            kg_enabled=True
        )

        # Expansion
        entity_expander = get_entity_expander(kg_service_url)
        expanded_retriever = ExpandedHybridRetrieverSync(
            hybrid_retriever,
            entity_expander,
            enable_expansion=True
        )

        # Final retriever
        self.retriever = create_final_retriever(
            self.parser,
            self.embedder,
            expanded_retriever
        )

        # Formatter
        self.formatter = get_response_formatter()

        logger.info("✓ SearchHandler initialized")

    def search(
        self,
        query: str,
        limit: int = 10,
        tags: Optional[List[str]] = None,
        enable_expansion: bool = True,
        include_context: bool = True
    ) -> Dict:
        """
        Execute complete search

        Args:
            query: Search query
            limit: Max results
            tags: Optional tag filters
            enable_expansion: Use entity expansion
            include_context: Extract context snippets

        Returns:
            Formatted search response
        """
        start_time = time.time()

        try:
            logger.info(f"Search query: '{query}'")

            # Execute search
            result = self.retriever.search(
                query=query,
                limit=limit,
                tags=tags,
                include_context=include_context,
                enable_expansion=enable_expansion
            )

            # Calculate timing
            processing_time_ms = (time.time() - start_time) * 1000

            # Format response
            response = self.formatter.format_search_response(
                result,
                processing_time_ms=processing_time_ms
            )

            logger.info(
                f"Search complete: {response['results_count']} results "
                f"in {processing_time_ms:.0f}ms"
            )

            return response

        except Exception as e:
            logger.error(f"Search failed: {e}")
            processing_time_ms = (time.time() - start_time) * 1000

            return {
                "success": False,
                "query": query,
                "error": str(e),
                "processing_time_ms": round(processing_time_ms, 2),
                "results": []
            }


# Global instance
_search_handler: Optional[SearchHandler] = None


def get_search_handler(db_manager, kg_service_url: str = "http://kg-service:8088") -> SearchHandler:
    """Get or create search handler instance"""
    global _search_handler
    if _search_handler is None:
        _search_handler = SearchHandler(db_manager, kg_service_url)
    return _search_handler


def initialize_search_handler(db_manager, kg_service_url: str = "http://kg-service:8088"):
    """Initialize search handler (call on startup)"""
    global _search_handler
    _search_handler = SearchHandler(db_manager, kg_service_url)
    return _search_handler
