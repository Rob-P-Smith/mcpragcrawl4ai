"""
Phase 5 Demo: Complete API Integration with SearchHandler

This script demonstrates the high-level SearchHandler interface that:
- Provides a simple search() API for MCP tools and REST endpoints
- Integrates all 4 phases into a single call
- Returns formatted, consistent responses
- Includes metadata, suggestions, and related entities
"""

import sys
import os
import json

# Force disk DB mode for demo
os.environ['USE_MEMORY_DB'] = 'false'
# Get absolute path to DB file
script_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(os.path.dirname(script_dir), 'data', 'crawl4ai_rag.db')
os.environ['DB_PATH'] = db_path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.search.search_handler import SearchHandler
from core.data.storage import GLOBAL_DB


def demo_phase5():
    """Demonstrate complete Phase 5 API integration"""

    print("\n" + "="*80)
    print("Phase 5 Demo: Complete API Integration with SearchHandler")
    print("="*80)

    # Initialize SearchHandler (single entry point)
    print("\n[Initialization] Creating SearchHandler...")
    print("-" * 80)

    handler = SearchHandler(
        db_manager=GLOBAL_DB,
        kg_service_url="http://kg-service:8088"
    )

    print("✓ SearchHandler initialized (all phases integrated)")

    # Test queries with different options
    test_cases = [
        {
            "query": "How to use FastAPI with async requests?",
            "limit": 5,
            "enable_expansion": True,
            "include_context": True
        },
        {
            "query": "Docker deployment best practices",
            "limit": 3,
            "enable_expansion": True,
            "include_context": True
        },
    ]

    for i, test_case in enumerate(test_cases, 1):
        print("\n" + "="*80)
        print(f"Test Case {i}: {test_case['query']}")
        print("="*80)

        # Execute complete search via single API call
        response = handler.search(**test_case)

        # Show API response structure
        print("\n[API Response Structure]")
        print("-" * 80)
        print(f"   Success: {response.get('success', False)}")
        print(f"   Query: {response.get('query')}")
        print(f"   Results Count: {response.get('results_count', 0)}")
        print(f"   Processing Time: {response.get('processing_time_ms', 0):.2f}ms")

        # Show parsed query metadata
        parsed = response.get('parsed_query', {})
        if parsed:
            print(f"\n[Query Understanding]")
            print("-" * 80)
            print(f"   Normalized: {parsed.get('normalized')}")
            print(f"   Entities: {parsed.get('entities', [])}")
            print(f"   Intent: {parsed.get('intent')}")
            print(f"   Confidence: {parsed.get('confidence', 0.0):.2f}")

        # Show exploration summary
        exploration = response.get('exploration_summary', {})
        if exploration:
            print(f"\n[Exploration Summary]")
            print("-" * 80)
            print(f"   Sources Searched: {exploration.get('sources_searched', [])}")
            print(f"   Entities Explored: {exploration.get('entities_explored', 0)}")
            print(f"   Graph Expansion: {exploration.get('graph_expansion_used', False)}")

        # Show ranked results
        results = response.get('results', [])
        if results:
            print(f"\n[Ranked Results]")
            print("=" * 80)

            for j, result in enumerate(results, 1):
                print(f"\n[{j}] {result.get('title', 'Untitled')}")
                print(f"    URL: {result.get('url', 'N/A')}")

                # Show final score
                final_score = result.get('final_rank_score', 0.0)
                print(f"\n    Final Score: {final_score:.4f}")

                # Show score breakdown
                scores = result.get('ranking_scores', {})
                if scores:
                    print(f"    Score Breakdown:")
                    print(f"      • Vector:  {scores.get('vector', 0.0):.4f} (35%)")
                    print(f"      • Graph:   {scores.get('graph', 0.0):.4f} (25%)")
                    print(f"      • Text:    {scores.get('text', 0.0):.4f} (20%)")
                    print(f"      • Recency: {scores.get('recency', 0.0):.4f} (10%)")
                    print(f"      • Title:   {scores.get('title', 0.0):.4f} (10%)")

                # Show context snippet
                context = result.get('context_snippet')
                if context:
                    print(f"\n    Context Snippet:")
                    print(f"    {context[:250]}{'...' if len(context) > 250 else ''}")

                print("-" * 80)

        # Show suggested queries
        suggestions = response.get('suggested_queries', [])
        if suggestions:
            print(f"\n[Suggested Follow-up Queries]")
            print("-" * 80)
            for suggestion in suggestions:
                print(f"   • {suggestion}")

        # Show related entities
        related = response.get('related_entities', [])
        if related:
            print(f"\n[Related Entities]")
            print("-" * 80)
            print(f"   {', '.join(related)}")

    # Show API usage patterns
    print("\n" + "="*80)
    print("✅ Phase 5 Demo Complete!")
    print("="*80)

    print("\n[API Usage Patterns]")
    print("-" * 80)
    print("1. MCP Tool Integration:")
    print("   handler = SearchHandler(db_manager, kg_service_url)")
    print("   response = handler.search(query, limit=10)")
    print()
    print("2. REST API Endpoint:")
    print("   @app.post('/search')")
    print("   def search_endpoint(request: SearchRequest):")
    print("       return handler.search(**request.dict())")
    print()
    print("3. Direct Python Usage:")
    print("   from core.search import SearchHandler")
    print("   handler = SearchHandler(GLOBAL_DB)")
    print("   results = handler.search('my query')")

    print("\n[Complete Pipeline Summary]")
    print("-" * 80)
    print("Phase 1: GLiNER entity extraction + query embedding")
    print("Phase 2: Parallel SQLite vector + Neo4j graph search")
    print("Phase 3: KG-powered entity expansion & traversal")
    print("Phase 4: Multi-signal ranking + context extraction")
    print("Phase 5: Unified API with formatted responses")

    print("\n[Response Format]")
    print("-" * 80)
    print("• success: bool")
    print("• query: str")
    print("• results_count: int")
    print("• processing_time_ms: float")
    print("• parsed_query: {normalized, entities, intent, confidence}")
    print("• exploration_summary: {sources, entities_explored, expansion_used}")
    print("• results: [{title, url, scores, context_snippet, ...}]")
    print("• suggested_queries: [str]")
    print("• related_entities: [str]")


if __name__ == "__main__":
    try:
        demo_phase5()
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
