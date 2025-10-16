"""
Phase 3 Demo: KG-Powered Expansion & Traversal

This script demonstrates:
- Entity expansion using Neo4j relationships
- Discovery of related entities
- Co-occurrence detection
- Expanded search with discovered entities
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
from core.search.entity_expander import get_entity_expander
from core.search.expanded_retriever import ExpandedHybridRetrieverSync
from core.data.storage import GLOBAL_DB


def demo_phase3():
    """Demonstrate Phase 3 expanded retrieval"""

    print("\n" + "="*80)
    print("Phase 3 Demo: KG-Powered Expansion & Traversal")
    print("="*80)

    # Initialize components
    print("\n[1] Initializing components...")
    parser = get_query_parser()
    embedder = get_query_embedder()
    print(f"   ✓ QueryParser loaded")
    print(f"   ✓ QueryEmbedder loaded")

    # Initialize retrievers
    vector_retriever = VectorRetriever(GLOBAL_DB)
    graph_retriever = GraphRetriever()
    hybrid_retriever = HybridRetrieverSync(
        vector_retriever,
        graph_retriever,
        kg_enabled=True
    )
    print(f"   ✓ HybridRetriever ready")

    # Initialize entity expander (Phase 3)
    entity_expander = get_entity_expander()
    expanded_retriever = ExpandedHybridRetrieverSync(
        hybrid_retriever,
        entity_expander,
        enable_expansion=True
    )
    print(f"   ✓ EntityExpander ready")
    print(f"   ✓ ExpandedHybridRetriever ready")

    # Test queries
    test_queries = [
        "How to use FastAPI with async requests?",
        "Docker deployment best practices",
    ]

    for query in test_queries:
        print("\n" + "="*80)
        print(f"Query: {query}")
        print("="*80)

        # Phase 1: Parse query
        print("\n[Phase 1] Query Understanding")
        print("-" * 80)
        parsed = parser.parse(query)
        print(f"   Original Entities: {parsed.extracted_entities}")
        print(f"   Intent: {parsed.query_intent}")

        # Generate embedding
        embedding = embedder.embed_query(parsed.normalized_query)

        # Phase 3: Expanded retrieval
        print("\n[Phase 3] KG-Powered Expansion & Retrieval")
        print("-" * 80)

        try:
            result = expanded_retriever.retrieve(
                query_embedding=embedding,
                entities=parsed.extracted_entities,
                limit=5,
                vector_weight=0.5,
                graph_weight=0.3,
                expansion_weight=0.2,
                max_expansions=5
            )

            # Show expansion results
            expansion = result.get('expansion')
            if expansion and expansion.get('expanded_entities'):
                print(f"   ✓ Entity Expansion:")
                print(f"      Original: {expansion.get('original_entities', [])}")
                print(f"      Discovered: {expansion.get('expanded_entities', [])}")

                # Show relationships
                relationships = expansion.get('relationships', [])
                if relationships:
                    print(f"\n   ✓ Discovered Relationships:")
                    for rel in relationships[:3]:
                        print(f"      - {rel.get('entity')}: {rel.get('relationship')} "
                              f"(confidence: {rel.get('confidence', 0.0):.2f})")
            else:
                print(f"   ⚠️  No entity expansion (kg-service unavailable)")

            # Show stats
            stats = result.get('stats', {})
            print(f"\n   ✓ Retrieval Stats:")
            print(f"      Original entities: {stats.get('original_entities', 0)}")
            print(f"      Expanded entities: {stats.get('expanded_entities', 0)}")
            print(f"      Original results: {stats.get('original_results', 0)}")
            print(f"      Expanded results: {stats.get('expanded_results', 0)}")
            print(f"      Final merged results: {stats.get('final_results', 0)}")

            # Show top results
            results_list = result.get('results', [])
            if results_list:
                print(f"\n   Top Results:")
                for i, doc in enumerate(results_list[:3], 1):
                    print(f"\n   [{i}] {doc.get('title', 'Untitled')}")
                    print(f"       URL: {doc.get('url', 'N/A')}")
                    print(f"       Final Score: {doc.get('final_score', 0.0):.4f}")
                    print(f"       From Original: {doc.get('from_original', False)}")
                    print(f"       From Expansion: {doc.get('from_expansion', False)}")
                    if doc.get('expansion_boost'):
                        print(f"       Expansion Boost: {doc.get('expansion_boost', 0.0):.4f}")
            else:
                print(f"   ⚠️  No results found")

        except Exception as e:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*80)
    print("✅ Phase 3 Demo Complete!")
    print("="*80)
    print("\nKey Improvements over Phase 2:")
    print("  • Entity expansion discovers related concepts")
    print("  • Graph relationships enhance relevance")
    print("  • Co-occurrence detection finds connected entities")
    print("  • Expanded search covers broader topic space")


if __name__ == "__main__":
    try:
        demo_phase3()
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
