"""
Phase 1 Demo: Query Understanding & Entity Extraction

This script demonstrates the functionality of Phase 1 components:
- QueryParser: Entity extraction and intent detection
- QueryEmbedder: Temporary query embedding generation

Note: Query embeddings are NEVER stored - they are temporary search parameters only.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.search.query_parser import get_query_parser
from core.search.embeddings import get_query_embedder


def demo_query_parser():
    """Demonstrate QueryParser functionality with GLiNER"""
    print("\n" + "="*70)
    print("PHASE 1 DEMO: Query Parser (GLiNER small-v2.1)")
    print("="*70)

    parser = get_query_parser()

    print(f"\n✓ GLiNER Model: {parser.model_name}")
    print(f"✓ Entity Types Loaded: {len(parser.entity_types)}")
    print(f"✓ Threshold: {parser.threshold}")

    # Test queries
    test_queries = [
        "How does FastAPI handle async requests?",
        "Find Docker deployment tutorials",
        "Install PostgreSQL on Ubuntu",
        "What is the difference between REST and GraphQL?",
        "How to use fastapi.APIRouter with Pydantic?",
    ]

    for query in test_queries:
        print(f"\n📝 Query: {query}")
        print("-" * 70)

        result = parser.parse(query)

        print(f"   Normalized: {result.normalized_query}")
        print(f"   Intent: {result.query_intent}")
        print(f"   Entities (GLiNER): {result.extracted_entities}")
        print(f"   Confidence: {result.confidence:.2f}")
        print(f"   Variants: {len(result.search_variants)} generated")


def demo_query_embedder():
    """Demonstrate QueryEmbedder functionality"""
    print("\n" + "="*70)
    print("PHASE 1 DEMO: Query Embedder")
    print("="*70)

    embedder = get_query_embedder()

    test_queries = [
        "How does FastAPI handle async requests?",
        "FastAPI async request handling",
        "Docker deployment tutorial",
    ]

    print("\n📊 Generating temporary query embeddings...")
    print("   (These are NEVER stored - temporary search parameters only)")
    print("-" * 70)

    embeddings = []
    for query in test_queries:
        print(f"\n   Query: {query}")
        embedding = embedder.embed_query(query)
        embeddings.append(embedding)

        print(f"   ✓ Embedding shape: {embedding.shape}")
        print(f"   ✓ Dtype: {embedding.dtype}")
        print(f"   ✓ Sample values: [{embedding[0]:.4f}, {embedding[1]:.4f}, {embedding[2]:.4f}, ...]")

    # Demonstrate similarity
    import numpy as np

    def cosine_similarity(a, b):
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

    print("\n📈 Similarity Analysis:")
    print("-" * 70)
    sim_0_1 = cosine_similarity(embeddings[0], embeddings[1])
    sim_0_2 = cosine_similarity(embeddings[0], embeddings[2])

    print(f"   Similarity (Query 1 vs Query 2): {sim_0_1:.4f}")
    print(f"   → Similar topics (FastAPI async)")
    print(f"\n   Similarity (Query 1 vs Query 3): {sim_0_2:.4f}")
    print(f"   → Different topics (FastAPI vs Docker)")


def demo_integrated_workflow():
    """Demonstrate integrated Phase 1 workflow"""
    print("\n" + "="*70)
    print("PHASE 1 DEMO: Integrated Workflow")
    print("="*70)

    parser = get_query_parser()
    embedder = get_query_embedder()

    query = "How does FastAPI handle async requests with PostgreSQL?"

    print(f"\n🔍 User Query: {query}")
    print("="*70)

    # Step 1: Parse query
    print("\n[Step 1] Parse Query")
    parsed = parser.parse(query)
    print(f"   ✓ Extracted entities: {parsed.extracted_entities}")
    print(f"   ✓ Intent: {parsed.query_intent}")
    print(f"   ✓ Confidence: {parsed.confidence:.2f}")

    # Step 2: Generate embedding (TEMPORARY)
    print("\n[Step 2] Generate Temporary Embedding")
    embedding = embedder.embed_query(parsed.normalized_query)
    print(f"   ✓ Embedding generated: shape={embedding.shape}, dtype={embedding.dtype}")
    print(f"   ⚠️  This embedding is TEMPORARY and will NOT be stored")

    # Step 3: Prepare search context
    print("\n[Step 3] Prepare Search Context")
    search_context = {
        "original_query": query,
        "normalized_query": parsed.normalized_query,
        "entities": parsed.extracted_entities,
        "intent": parsed.query_intent,
        "embedding": embedding,  # TEMPORARY - used only for this search
        "confidence": parsed.confidence,
    }

    print("   ✓ Search context prepared:")
    print(f"      - Entities for Neo4j graph search: {search_context['entities']}")
    print(f"      - Embedding for SQLite vector search: {search_context['embedding'].shape}")
    print(f"      - Query intent: {search_context['intent']}")

    print("\n" + "="*70)
    print("✅ Phase 1 Complete - Ready for Phase 2 (Parallel Retrieval)")
    print("="*70)


if __name__ == "__main__":
    print("\n" + "="*70)
    print("Knowledge Graph-Enhanced RAG: Phase 1 Implementation")
    print("Query Understanding & Entity Extraction")
    print("="*70)

    try:
        demo_query_parser()
        demo_query_embedder()
        demo_integrated_workflow()

        print("\n" + "="*70)
        print("🎉 Phase 1 Demo Complete!")
        print("="*70)
        print("\nNext Steps:")
        print("  - Phase 2: Parallel Multi-Modal Retrieval (Vector + Graph)")
        print("  - Phase 3: KG-Powered Expansion & Traversal")
        print("  - Phase 4: Hybrid Ranking & Context Augmentation")
        print("  - Phase 5: Result Assembly & API Integration")

    except Exception as e:
        print(f"\n❌ Error running demo: {e}")
        import traceback
        traceback.print_exc()
