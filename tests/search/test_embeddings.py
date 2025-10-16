"""
Unit tests for QueryEmbedder
Tests embedding generation for search queries
"""

import pytest
import numpy as np
from core.search.embeddings import QueryEmbedder, get_query_embedder


class TestQueryEmbedder:
    """Test suite for QueryEmbedder"""

    @pytest.fixture
    def embedder(self):
        """Create QueryEmbedder instance for tests"""
        return QueryEmbedder()

    def test_embed_single_query(self, embedder):
        """Test embedding generation for single query"""
        query = "How to use FastAPI?"
        embedding = embedder.embed_query(query)

        # Check shape (all-MiniLM-L6-v2 produces 384-dim embeddings)
        assert embedding.shape == (384,)

        # Check dtype (sqlite-vec requires float32)
        assert embedding.dtype == np.float32

        # Check that embedding is not all zeros
        assert not np.allclose(embedding, 0.0)

    def test_embed_multiple_queries(self, embedder):
        """Test batch embedding generation"""
        queries = [
            "How to use FastAPI?",
            "What is async programming?",
            "Docker deployment tutorial"
        ]
        embeddings = embedder.embed_queries(queries)

        # Check shape
        assert embeddings.shape == (3, 384)

        # Check dtype
        assert embeddings.dtype == np.float32

        # Check that embeddings are different
        assert not np.allclose(embeddings[0], embeddings[1])
        assert not np.allclose(embeddings[1], embeddings[2])

    def test_embed_empty_query(self, embedder):
        """Test handling of empty query"""
        query = ""
        embedding = embedder.embed_query(query)

        # Should still produce valid embedding
        assert embedding.shape == (384,)
        assert embedding.dtype == np.float32

    def test_embed_special_characters(self, embedder):
        """Test embedding of queries with special characters"""
        query = "What is @decorator in Python???"
        embedding = embedder.embed_query(query)

        # Should handle special characters gracefully
        assert embedding.shape == (384,)
        assert not np.allclose(embedding, 0.0)

    def test_embedding_similarity(self, embedder):
        """Test that similar queries produce similar embeddings"""
        query1 = "How to use FastAPI"
        query2 = "Using FastAPI framework"
        query3 = "Docker deployment"

        emb1 = embedder.embed_query(query1)
        emb2 = embedder.embed_query(query2)
        emb3 = embedder.embed_query(query3)

        # Compute cosine similarity
        def cosine_sim(a, b):
            return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

        sim_1_2 = cosine_sim(emb1, emb2)  # Similar queries
        sim_1_3 = cosine_sim(emb1, emb3)  # Different queries

        # Similar queries should have higher similarity
        assert sim_1_2 > sim_1_3

    def test_embedding_consistency(self, embedder):
        """Test that same query produces same embedding"""
        query = "How to use FastAPI?"

        emb1 = embedder.embed_query(query)
        emb2 = embedder.embed_query(query)

        # Should be identical (or very close due to floating point)
        assert np.allclose(emb1, emb2)

    def test_embedding_range(self, embedder):
        """Test that embeddings are in reasonable range"""
        query = "How to use FastAPI?"
        embedding = embedder.embed_query(query)

        # Sentence-BERT embeddings are typically in [-1, 1] range
        assert np.all(embedding >= -2.0)
        assert np.all(embedding <= 2.0)

    def test_batch_consistency(self, embedder):
        """Test that batch and single embedding produce same results"""
        queries = ["How to use FastAPI?", "What is Docker?"]

        # Single embeddings
        emb1_single = embedder.embed_query(queries[0])
        emb2_single = embedder.embed_query(queries[1])

        # Batch embeddings
        emb_batch = embedder.embed_queries(queries)

        # Should be identical
        assert np.allclose(emb1_single, emb_batch[0])
        assert np.allclose(emb2_single, emb_batch[1])

    def test_long_query(self, embedder):
        """Test embedding of long query"""
        query = " ".join([
            "How to deploy a FastAPI application with Docker",
            "using PostgreSQL database and Redis cache",
            "with proper authentication and async request handling"
        ])
        embedding = embedder.embed_query(query)

        # Should handle long queries
        assert embedding.shape == (384,)
        assert not np.allclose(embedding, 0.0)

    def test_multilingual_query(self, embedder):
        """Test handling of non-English queries"""
        # Note: all-MiniLM-L6-v2 supports multiple languages
        query = "Comment utiliser FastAPI?"  # French
        embedding = embedder.embed_query(query)

        # Should still produce valid embedding
        assert embedding.shape == (384,)
        assert not np.allclose(embedding, 0.0)

    def test_model_loading(self):
        """Test that model loads correctly"""
        embedder = QueryEmbedder()

        # Model should be loaded
        assert embedder.model is not None
        assert embedder.model_name == "all-MiniLM-L6-v2"

    def test_get_query_embedder_singleton(self):
        """Test that get_query_embedder returns same instance"""
        embedder1 = get_query_embedder()
        embedder2 = get_query_embedder()

        assert embedder1 is embedder2

    def test_embedding_normalization(self, embedder):
        """Test that embeddings can be normalized"""
        query = "How to use FastAPI?"
        embedding = embedder.embed_query(query)

        # Normalize
        normalized = embedding / np.linalg.norm(embedding)

        # Should have unit length
        assert np.isclose(np.linalg.norm(normalized), 1.0)

    def test_zero_vector_not_produced(self, embedder):
        """Test that embedder never produces zero vectors"""
        queries = [
            "test",
            "a",
            "123",
            "!@#$%",
            "",
        ]

        for query in queries:
            embedding = embedder.embed_query(query)
            # Should not be zero vector
            assert np.linalg.norm(embedding) > 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
