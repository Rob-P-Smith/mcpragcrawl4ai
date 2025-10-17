"""
Response Formatter - Phase 5
Formats search results into consistent API responses
"""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class ResponseFormatter:
    """
    Format search results into final API response structure

    Creates consistent, well-structured responses for:
    - MCP tools
    - REST API endpoints
    - Direct Python API usage
    """

    def format_search_response(
        self,
        search_result: Dict,
        processing_time_ms: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Format complete search result from FinalRetriever

        Args:
            search_result: Result from FinalRetriever.search()
            processing_time_ms: Optional processing time override

        Returns:
            Formatted API response
        """
        try:
            # Extract components
            query = search_result.get('query', '')
            parsed_query = search_result.get('parsed_query', {})
            results = search_result.get('results', [])
            expansion = search_result.get('expansion')
            stats = search_result.get('stats', {})
            error = search_result.get('error')

            # Handle errors
            if error:
                return self._format_error_response(query, error)

            # Format results
            formatted_results = [
                self._format_single_result(r, i+1)
                for i, r in enumerate(results)
            ]

            # Build exploration summary
            exploration_summary = self._build_exploration_summary(
                expansion,
                stats
            )

            # Generate suggestions
            suggested_queries = self._generate_query_suggestions(
                query,
                parsed_query,
                expansion
            )

            # Calculate timing
            calc_time = processing_time_ms if processing_time_ms is not None else 0.0

            response = {
                "success": True,
                "query": query,
                "results_count": len(formatted_results),
                "total_found": stats.get('total_retrieved', 0),
                "processing_time_ms": round(calc_time, 2),

                # Query understanding
                "parsed_query": {
                    "normalized": parsed_query.get('normalized'),
                    "entities": parsed_query.get('entities', []),
                    "intent": parsed_query.get('intent'),
                    "confidence": round(parsed_query.get('confidence', 0.0), 2)
                },

                # Exploration metadata
                "exploration_summary": exploration_summary,

                # Results
                "results": formatted_results,

                # Suggestions
                "suggested_queries": suggested_queries,
                "related_entities": self._extract_related_entities(expansion),

                # Metadata
                "search_metadata": {
                    "vector_search": True,
                    "graph_search": stats.get('expanded_entities', 0) > 0,
                    "expansion_enabled": expansion is not None,
                    "ranking_signals": ["vector", "graph", "text", "recency", "title"]
                },

                "timestamp": datetime.utcnow().isoformat() + "Z"
            }

            return response

        except Exception as e:
            logger.error(f"Response formatting failed: {e}")
            return self._format_error_response(
                search_result.get('query', ''),
                str(e)
            )

    def _format_single_result(self, result: Dict, rank: int) -> Dict[str, Any]:
        """Format a single search result"""
        # Get scoring breakdown
        ranking_scores = result.get('ranking_scores', {})

        return {
            "rank": rank,
            "url": result.get('url'),
            "title": result.get('title'),
            "content_preview": result.get('context_snippet') or result.get('content', '')[:300],

            # Scoring
            "score": round(result.get('final_rank_score', 0.0), 4),
            "score_breakdown": {
                "vector_similarity": round(ranking_scores.get('vector', 0.0), 4),
                "graph_relevance": round(ranking_scores.get('graph', 0.0), 4),
                "text_match": round(ranking_scores.get('text', 0.0), 4),
                "recency": round(ranking_scores.get('recency', 0.0), 4),
                "title_match": round(ranking_scores.get('title', 0.0), 4)
            },

            # Metadata
            "timestamp": result.get('timestamp'),
            "tags": result.get('tags'),

            # Provenance
            "sources": result.get('sources', ['vector']),
            "from_expansion": result.get('from_expansion', False),

            # Context
            "context_snippet": result.get('context_snippet')
        }

    def _build_exploration_summary(
        self,
        expansion: Optional[Dict],
        stats: Dict
    ) -> Dict[str, Any]:
        """Build exploration summary from expansion data"""
        if not expansion:
            return {
                "graph_enabled": False,
                "entities_expanded": 0,
                "relationships_found": 0,
                "expansion_successful": False
            }

        return {
            "graph_enabled": True,
            "entities_expanded": len(expansion.get('expanded_entities', [])),
            "relationships_found": len(expansion.get('relationships', [])),
            "expansion_successful": len(expansion.get('expanded_entities', [])) > 0,
            "original_entities": expansion.get('original_entities', []),
            "discovered_entities": expansion.get('expanded_entities', [])
        }

    def _generate_query_suggestions(
        self,
        query: str,
        parsed_query: Dict,
        expansion: Optional[Dict]
    ) -> List[str]:
        """Generate suggested follow-up queries"""
        suggestions = []

        entities = parsed_query.get('entities', [])

        # Suggest entity-focused queries
        if entities:
            for entity in entities[:2]:
                suggestions.append(f"What is {entity}?")
                suggestions.append(f"How to use {entity}?")

        # Suggest expanded entity queries
        if expansion and expansion.get('expanded_entities'):
            expanded = expansion['expanded_entities'][:2]
            for entity in expanded:
                suggestions.append(f"{query} with {entity}")

        return suggestions[:5]  # Limit to 5

    def _extract_related_entities(
        self,
        expansion: Optional[Dict]
    ) -> List[Dict[str, Any]]:
        """Extract related entities from expansion"""
        if not expansion:
            return []

        entities = []

        # From relationships
        for rel in expansion.get('relationships', [])[:10]:
            entities.append({
                "name": rel.get('entity'),
                "type": rel.get('type'),
                "relationship": rel.get('relationship'),
                "confidence": round(rel.get('confidence', 0.0), 2)
            })

        return entities

    def _format_error_response(
        self,
        query: str,
        error: str
    ) -> Dict[str, Any]:
        """Format error response"""
        return {
            "success": False,
            "query": query,
            "error": error,
            "results_count": 0,
            "total_found": 0,
            "results": [],
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }


# Global instance
_response_formatter: Optional[ResponseFormatter] = None


def get_response_formatter() -> ResponseFormatter:
    """Get global response formatter instance"""
    global _response_formatter
    if _response_formatter is None:
        _response_formatter = ResponseFormatter()
    return _response_formatter
