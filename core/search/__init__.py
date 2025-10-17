"""
Search Module for KG-Enhanced RAG

This module provides query parsing, entity extraction,
embedding generation, and hybrid retrieval across
SQLite vector DB and Neo4j Knowledge Graph.
"""

# Phase 1: Query Understanding
from .query_parser import QueryParser, ParsedQuery, get_query_parser
from .embeddings import QueryEmbedder, get_query_embedder

# Phase 2: Parallel Retrieval
from .vector_retriever import VectorRetriever, get_vector_retriever
from .graph_retriever import GraphRetriever, GraphRetrieverSync, get_graph_retriever
from .hybrid_retriever import HybridRetriever, HybridRetrieverSync

# Phase 3: KG-Powered Expansion
from .entity_expander import EntityExpander, EntityExpanderSync, get_entity_expander
from .expanded_retriever import ExpandedHybridRetriever, ExpandedHybridRetrieverSync

# Phase 4: Advanced Ranking
from .advanced_ranker import AdvancedRanker, ContextExtractor
from .final_retriever import FinalRetriever, create_final_retriever

# Phase 5: API Integration
from .response_formatter import ResponseFormatter, get_response_formatter
from .search_handler import SearchHandler, get_search_handler, initialize_search_handler

# Simple Search (original behavior, no KG enhancement)
from .simple_search import simple_search, get_simple_search_handler

__all__ = [
    # Phase 1
    "QueryParser",
    "ParsedQuery",
    "get_query_parser",
    "QueryEmbedder",
    "get_query_embedder",
    # Phase 2
    "VectorRetriever",
    "get_vector_retriever",
    "GraphRetriever",
    "GraphRetrieverSync",
    "get_graph_retriever",
    "HybridRetriever",
    "HybridRetrieverSync",
    # Phase 3
    "EntityExpander",
    "EntityExpanderSync",
    "get_entity_expander",
    "ExpandedHybridRetriever",
    "ExpandedHybridRetrieverSync",
    # Phase 4
    "AdvancedRanker",
    "ContextExtractor",
    "FinalRetriever",
    "create_final_retriever",
    # Phase 5
    "ResponseFormatter",
    "get_response_formatter",
    "SearchHandler",
    "get_search_handler",
    "initialize_search_handler",
    # Simple Search
    "simple_search",
    "get_simple_search_handler",
]
