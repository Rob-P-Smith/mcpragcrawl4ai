"""
Phase 2 Demo: Parallel Multi-Modal Retrieval

This script demonstrates:
- Vector search using SQLite
- Graph search using Neo4j (if available)
- Parallel execution of both searches
- Result merging and deduplication
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

from core.search.query_parser import get_query_parser
from core.search.embeddings import get_query_embedder
from core.search.vector_retriever import VectorRetriever
from core.search.graph_retriever import GraphRetriever
from core.search.hybrid_retriever import HybridRetrieverSync
from core.data.storage import GLOBAL_DB


def demo_phase2():
    """Demonstrate Phase 2 hybrid retrieval"""

    print("\n" + "="*80)
    print("Phase 2 Demo: Parallel Multi-Modal Retrieval")
    print("="*80)

    # Initialize components
    print("\n[1] Initializing Phase 1 components...")
    parser = get_query_parser()
    embedder = get_query_embedder()
    print(f"   ✓ QueryParser loaded ({parser.model_name})")
    print(f"   ✓ QueryEmbedder loaded")

    # Initialize retrievers
    print("\n[2] Initializing Phase 2 retrievers...")
    vector_retriever = VectorRetriever(GLOBAL_DB)
    graph_retriever = GraphRetriever()
    hybrid_retriever = HybridRetrieverSync(
        vector_retriever,
        graph_retriever,
        kg_enabled=True  # Try graph search if available
    )
    print(f"   ✓ VectorRetriever ready (SQLite)")
    print(f"   ✓ GraphRetriever ready (Neo4j)")
    print(f"   ✓ HybridRetriever ready")

    # Test queries
    test_queries = [
        "How to use FastAPI with async requests?",
        "Docker deployment best practices",
        "PostgreSQL performance optimization",
    ]

    for query in test_queries:
        print("\n" + "="*80)
        print(f"Query: {query}")
        print("="*80)

        # Phase 1: Parse query
        print("\n[Phase 1] Query Understanding")
        print("-" * 80)
        parsed = parser.parse(query)
        print(f"   Entities: {parsed.extracted_entities}")
        print(f"   Intent: {parsed.query_intent}")
        print(f"   Confidence: {parsed.confidence:.2f}")

        # Generate embedding
        embedding = embedder.embed_query(parsed.normalized_query)
        print(f"   Embedding: shape={embedding.shape}, dtype={embedding.dtype}")

        # Phase 2: Hybrid retrieval
        print("\n[Phase 2] Parallel Retrieval")
        print("-" * 80)

        try:
            results = hybrid_retriever.retrieve(
                query_embedding=embedding,
                entities=parsed.extracted_entities,
                limit=5,
                vector_weight=0.6,
                graph_weight=0.4
            )

            print(f"   ✓ Retrieved {len(results)} results")

            if results:
                print("\n   Top Results:")
                for i, result in enumerate(results[:3], 1):
                    print(f"\n   [{i}] {result.get('title', 'Untitled')}")
                    print(f"       URL: {result.get('url', 'N/A')}")
                    print(f"       Hybrid Score: {result.get('hybrid_score', 0.0):.4f}")
                    print(f"       Sources: {', '.join(result.get('sources', []))}")
                    if 'vector' in result.get('sources', []):
                        print(f"       Vector Score: {result.get('vector_score', 0.0):.4f}")
                    if 'graph' in result.get('sources', []):
                        print(f"       Graph Score: {result.get('graph_score', 0.0):.4f}")
                        print(f"       Entity Matches: {result.get('entity_matches', 0)}")
            else:
                print("   ⚠️  No results found")

        except Exception as e:
            print(f"   ❌ Error: {e}")

    print("\n" + "="*80)
    print("✅ Phase 2 Demo Complete!")
    print("="*80)


if __name__ == "__main__":
    try:
        demo_phase2()
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
