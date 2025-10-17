"""
Phase 4 Demo: Advanced Ranking & Complete Pipeline

This script demonstrates the full KG-Enhanced RAG pipeline:
- Phase 1: Query parsing & entity extraction (GLiNER)
- Phase 2: Parallel vector + graph retrieval
- Phase 3: KG-powered entity expansion
- Phase 4: Advanced multi-signal ranking
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

from core.search.query_parser import get_query_parser
from core.search.embeddings import get_query_embedder
from core.search.vector_retriever import VectorRetriever
from core.search.graph_retriever import GraphRetriever
from core.search.hybrid_retriever import HybridRetrieverSync
from core.search.entity_expander import get_entity_expander
from core.search.expanded_retriever import ExpandedHybridRetrieverSync
from core.search.final_retriever import create_final_retriever
from core.data.storage import GLOBAL_DB


def demo_phase4():
    """Demonstrate complete Phase 4 pipeline"""

    print("\n" + "="*80)
    print("Phase 4 Demo: Complete KG-Enhanced RAG Pipeline")
    print("="*80)

    # Initialize all components
    print("\n[Initialization] Building pipeline...")
    print("-" * 80)

    parser = get_query_parser()
    embedder = get_query_embedder()
    print(f"   ✓ Phase 1: QueryParser + QueryEmbedder")

    vector_retriever = VectorRetriever(GLOBAL_DB)
    graph_retriever = GraphRetriever()
    hybrid_retriever = HybridRetrieverSync(vector_retriever, graph_retriever, kg_enabled=True)
    print(f"   ✓ Phase 2: VectorRetriever + GraphRetriever + HybridRetriever")

    entity_expander = get_entity_expander()
    expanded_retriever = ExpandedHybridRetrieverSync(
        hybrid_retriever,
        entity_expander,
        enable_expansion=True
    )
    print(f"   ✓ Phase 3: EntityExpander + ExpandedHybridRetriever")

    final_retriever = create_final_retriever(parser, embedder, expanded_retriever)
    print(f"   ✓ Phase 4: AdvancedRanker + ContextExtractor + FinalRetriever")

    print("\n✅ Complete pipeline ready!")

    # Test queries
    test_queries = [
        "How to use FastAPI with async requests?",
        "Docker deployment best practices",
    ]

    for query in test_queries:
        print("\n" + "="*80)
        print(f"Query: {query}")
        print("="*80)

        # Run complete search
        result = final_retriever.search(
            query,
            limit=5,
            include_context=True,
            enable_expansion=True
        )

        # Show parsed query
        parsed = result.get('parsed_query', {})
        print(f"\n[Phase 1] Query Understanding")
        print("-" * 80)
        print(f"   Normalized: {parsed.get('normalized')}")
        print(f"   Entities: {parsed.get('entities')}")
        print(f"   Intent: {parsed.get('intent')}")
        print(f"   Confidence: {parsed.get('confidence', 0.0):.2f}")

        # Show expansion
        expansion = result.get('expansion')
        if expansion and expansion.get('expanded_entities'):
            print(f"\n[Phase 3] Entity Expansion")
            print("-" * 80)
            print(f"   Original: {expansion.get('original_entities')}")
            print(f"   Discovered: {expansion.get('expanded_entities')}")

        # Show stats
        stats = result.get('stats', {})
        print(f"\n[Pipeline Stats]")
        print("-" * 80)
        print(f"   Total retrieved: {stats.get('total_retrieved', 0)}")
        print(f"   After ranking: {stats.get('returned', 0)}")

        # Show ranked results
        results_list = result.get('results', [])
        if results_list:
            print(f"\n[Phase 4] Ranked Results")
            print("=" * 80)

            for i, doc in enumerate(results_list, 1):
                print(f"\n[{i}] {doc.get('title', 'Untitled')}")
                print(f"    URL: {doc.get('url', 'N/A')}")

                # Show ranking scores
                scores = doc.get('ranking_scores', {})
                final_score = doc.get('final_rank_score', 0.0)
                print(f"\n    Final Score: {final_score:.4f}")
                print(f"    ├─ Vector:  {scores.get('vector', 0.0):.4f}")
                print(f"    ├─ Graph:   {scores.get('graph', 0.0):.4f}")
                print(f"    ├─ Text:    {scores.get('text', 0.0):.4f}")
                print(f"    ├─ Recency: {scores.get('recency', 0.0):.4f}")
                print(f"    └─ Title:   {scores.get('title', 0.0):.4f}")

                # Show context snippet
                context = doc.get('context_snippet')
                if context:
                    print(f"\n    Context:")
                    print(f"    {context[:200]}{'...' if len(context) > 200 else ''}")

                print("-" * 80)
        else:
            print(f"\n   ⚠️  No results found")

    print("\n" + "="*80)
    print("✅ Phase 4 Demo Complete!")
    print("="*80)
    print("\nComplete Pipeline Summary:")
    print("  • Phase 1: GLiNER entity extraction + intent detection")
    print("  • Phase 2: Parallel SQLite vector + Neo4j graph search")
    print("  • Phase 3: KG-powered entity expansion & traversal")
    print("  • Phase 4: Multi-signal ranking + context extraction")
    print("\nRanking Signals:")
    print("  • Vector similarity (35%)")
    print("  • Graph relevance (25%)")
    print("  • BM25 text matching (20%)")
    print("  • Document recency (10%)")
    print("  • Title matching (10%)")


if __name__ == "__main__":
    try:
        demo_phase4()
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
