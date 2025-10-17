"""
Simple Search - Direct vector similarity search without KG enhancement

This module provides the original search_knowledge functionality:
- Direct embedding-based similarity search against SQLite vector DB
- No entity extraction, no graph expansion, no multi-signal ranking
- Fast, straightforward semantic search for basic queries
"""

from typing import Dict, Any, Optional, List


def simple_search(
    db_manager,
    query: str,
    limit: int = 10,
    tags: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Simple vector similarity search (original search_knowledge behavior)

    Args:
        db_manager: Database manager instance (GLOBAL_DB)
        query: Search query string
        limit: Maximum number of results to return
        tags: Optional list of tags to filter by (ANY match)

    Returns:
        Dict with search results in original format:
        {
            "success": bool,
            "query": str,
            "results": List[Dict],
            "count": int,
            "tags_filter": Optional[List[str]],
            "message": str
        }
    """

    # Use the existing search_similar method from storage
    results = db_manager.search_similar(query, limit=limit, tags=tags)

    return {
        "success": True,
        "query": query,
        "results": results,
        "count": len(results),
        "tags_filter": tags if tags else None,
        "message": f"Found {len(results)} results for '{query}'"
    }


def get_simple_search_handler(db_manager):
    """
    Factory function to create a simple search handler

    Args:
        db_manager: Database manager instance

    Returns:
        Callable that performs simple search
    """
    def search(query: str, limit: int = 10, tags: Optional[List[str]] = None) -> Dict[str, Any]:
        return simple_search(db_manager, query, limit, tags)

    return search
