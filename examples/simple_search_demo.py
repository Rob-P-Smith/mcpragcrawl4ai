"""
Simple Search Demo

Demonstrates the simple_search function that provides
direct vector similarity search without KG enhancement.

This is the original search_knowledge behavior:
- Fast embedding-based similarity search
- No entity extraction, no graph expansion
- Straightforward semantic search for basic queries
"""

import sys
import os

# Force disk DB mode for demo
os.environ['USE_MEMORY_DB'] = 'false'
# Get absolute path to DB file
script_dir = os.path.dirname(os.path.abspath(__file__))
db_path = os.path.join(os.path.dirname(script_dir), 'data', 'crawl4ai_rag.db')
os.environ['DB_PATH'] = db_path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.search import simple_search
from core.data.storage import GLOBAL_DB


def demo_simple_search():
    """Demonstrate simple vector similarity search"""

    print("\n" + "="*80)
    print("Simple Search Demo: Direct Vector Similarity Search")
    print("="*80)
    print("No entity extraction | No graph expansion | No multi-signal ranking")
    print("Just fast, straightforward semantic search")
    print("="*80)

    # Test queries
    test_queries = [
        ("FastAPI async requests", 5),
        ("Docker deployment", 3),
        ("Python web scraping", 4),
    ]

    for query, limit in test_queries:
        print(f"\n{'='*80}")
        print(f"Query: {query}")
        print(f"Limit: {limit}")
        print("="*80)

        # Execute simple search
        result = simple_search(GLOBAL_DB, query, limit=limit, tags=None)

        # Display results
        print(f"\n✓ Success: {result['success']}")
        print(f"✓ Found: {result['count']} results")
        print(f"✓ Message: {result['message']}")

        if result['results']:
            print(f"\n{'Results':-^80}")
            for i, res in enumerate(result['results'], 1):
                print(f"\n[{i}] {res.get('title', 'Untitled')}")
                print(f"    URL: {res.get('url', 'N/A')}")
                print(f"    Similarity: {res.get('similarity', 0.0):.4f}")

                # Show snippet
                content = res.get('content', '')
                if content:
                    snippet = content[:200] + '...' if len(content) > 200 else content
                    print(f"    Snippet: {snippet}")

    # Demo with tags filter
    print(f"\n{'='*80}")
    print("Demo: Search with Tags Filter")
    print("="*80)

    result = simple_search(GLOBAL_DB, "crawl4ai", limit=3, tags=["documentation"])
    print(f"✓ Query: 'crawl4ai' with tags=['documentation']")
    print(f"✓ Found: {result['count']} results")
    print(f"✓ Tags filter: {result.get('tags_filter')}")

    print("\n" + "="*80)
    print("✅ Simple Search Demo Complete!")
    print("="*80)
    print("\nUsage:")
    print("  from core.search import simple_search")
    print("  from core.data.storage import GLOBAL_DB")
    print("  result = simple_search(GLOBAL_DB, 'your query', limit=10)")
    print("\nReturns:")
    print("  {")
    print("    'success': bool,")
    print("    'query': str,")
    print("    'results': List[Dict],")
    print("    'count': int,")
    print("    'tags_filter': Optional[List[str]],")
    print("    'message': str")
    print("  }")


if __name__ == "__main__":
    try:
        demo_simple_search()
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
