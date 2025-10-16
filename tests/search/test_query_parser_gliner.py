"""
Unit tests for QueryParser with GLiNER integration
Tests entity extraction using GLiNER small model
"""

import pytest
from core.search.query_parser import QueryParser, ParsedQuery


class TestQueryParserGLiNER:
    """Test suite for QueryParser with GLiNER"""

    @pytest.fixture(scope="class")
    def parser(self):
        """Create QueryParser instance (shared for all tests for speed)"""
        return QueryParser()

    def test_entity_extraction_frameworks(self, parser):
        """Test extraction of framework names"""
        result = parser.parse("How to use FastAPI with PostgreSQL?")

        # GLiNER should extract at least one entity
        assert len(result.extracted_entities) > 0

        # Check that entities are reasonable
        entities_str = " ".join(result.extracted_entities).lower()
        assert "fastapi" in entities_str or "postgresql" in entities_str

    def test_entity_extraction_multiple(self, parser):
        """Test extraction of multiple technologies"""
        result = parser.parse("Deploy Django app with Docker and Redis")

        # Should find multiple entities
        assert len(result.extracted_entities) >= 2

    def test_query_normalization(self, parser):
        """Test query normalization"""
        result = parser.parse("  How   to   USE    FastAPI?!?  ")

        # Should be lowercase, trimmed, and normalized
        assert result.normalized_query == "how to use fastapi"
        assert "  " not in result.normalized_query
        assert result.normalized_query.islower()

    def test_intent_detection_informational(self, parser):
        """Test detection of informational intent"""
        queries = [
            "How does FastAPI work?",
            "What is async programming?",
            "Why use Docker?",
            "Explain microservices",
        ]

        for query in queries:
            result = parser.parse(query)
            assert result.query_intent == "informational"

    def test_intent_detection_navigational(self, parser):
        """Test detection of navigational intent"""
        queries = [
            "Find FastAPI documentation",
            "Search for Python tutorials",
            "Get Docker examples",
            "Show me Redis commands",
        ]

        for query in queries:
            result = parser.parse(query)
            assert result.query_intent == "navigational"

    def test_intent_detection_transactional(self, parser):
        """Test detection of transactional intent"""
        queries = [
            "Install FastAPI",
            "Setup PostgreSQL",
            "Configure Docker",
            "Create REST API",
        ]

        for query in queries:
            result = parser.parse(query)
            assert result.query_intent == "transactional"

    def test_variant_generation(self, parser):
        """Test generation of query variants"""
        result = parser.parse("How to use FastAPI?")

        # Should have at least the original query
        assert len(result.search_variants) >= 1

        # First variant should be the normalized query
        assert result.search_variants[0] == result.normalized_query

    def test_confidence_bounds(self, parser):
        """Test confidence is always between 0 and 1"""
        queries = [
            "test",
            "How to use FastAPI with PostgreSQL?",
            "x",
        ]

        for query in queries:
            result = parser.parse(query)
            assert 0.0 <= result.confidence <= 1.0

    def test_empty_query(self, parser):
        """Test handling of empty query"""
        result = parser.parse("")

        assert result.original_query == ""
        assert result.normalized_query == ""

    def test_parsed_query_structure(self, parser):
        """Test that ParsedQuery has all expected fields"""
        result = parser.parse("How to use FastAPI?")

        assert hasattr(result, 'original_query')
        assert hasattr(result, 'normalized_query')
        assert hasattr(result, 'extracted_entities')
        assert hasattr(result, 'query_intent')
        assert hasattr(result, 'search_variants')
        assert hasattr(result, 'confidence')

        assert isinstance(result.extracted_entities, list)
        assert isinstance(result.search_variants, list)
        assert isinstance(result.confidence, float)

    def test_get_query_parser_singleton(self):
        """Test that get_query_parser returns same instance"""
        from core.search.query_parser import get_query_parser

        parser1 = get_query_parser()
        parser2 = get_query_parser()

        assert parser1 is parser2

    def test_gliner_model_loaded(self, parser):
        """Test that GLiNER model is loaded"""
        assert parser.model is not None
        assert parser.model_name == "urchade/gliner_small-v2.1"

    def test_taxonomy_loaded(self, parser):
        """Test that entity types are loaded"""
        assert len(parser.entity_types) > 0
        # Should have some common types
        types_str = " ".join(parser.entity_types)
        assert "Programming" in types_str or "Technology" in types_str


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
