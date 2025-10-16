"""
Unit tests for QueryParser
Tests entity extraction, intent detection, and query normalization
"""

import pytest
from core.search.query_parser import QueryParser, ParsedQuery


class TestQueryParser:
    """Test suite for QueryParser"""

    @pytest.fixture
    def parser(self):
        """Create QueryParser instance for tests"""
        return QueryParser()

    def test_entity_extraction_framework_names(self, parser):
        """Test extraction of framework names"""
        result = parser.parse("How to use FastAPI with PostgreSQL?")

        # Check that entities were extracted (case-insensitive matching)
        entities_lower = [e.lower() for e in result.extracted_entities]
        assert "fastapi" in entities_lower
        assert "postgresql" in entities_lower

    def test_entity_extraction_quoted_phrases(self, parser):
        """Test extraction of quoted phrases"""
        result = parser.parse('What is "async await" in Python?')

        assert "async await" in result.extracted_entities
        entities_lower = [e.lower() for e in result.extracted_entities]
        assert "python" in entities_lower

    def test_entity_extraction_dotted_notation(self, parser):
        """Test extraction of dotted module names"""
        result = parser.parse("How to use fastapi.APIRouter?")

        # Should extract both the dotted name and the base module
        assert "fastapi.APIRouter" in result.extracted_entities or "fastapi.apirouter" in result.extracted_entities

    def test_entity_extraction_multiple_technologies(self, parser):
        """Test extraction of multiple tech entities"""
        result = parser.parse("Deploy Django app with Docker and Redis")

        entities_lower = [e.lower() for e in result.extracted_entities]
        assert "django" in entities_lower
        assert "docker" in entities_lower
        assert "redis" in entities_lower

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

        # If entities found, should have additional variants
        if result.extracted_entities:
            assert len(result.search_variants) > 1

    def test_confidence_calculation_with_entities(self, parser):
        """Test confidence increases with entities found"""
        result_no_entities = parser.parse("Tell me about that thing")
        result_with_entities = parser.parse("How to use FastAPI with PostgreSQL")

        # More entities should increase confidence
        assert result_with_entities.confidence >= result_no_entities.confidence

    def test_confidence_calculation_with_clear_intent(self, parser):
        """Test confidence increases with clear intent"""
        result = parser.parse("Install FastAPI")

        # Clear transactional intent should boost confidence
        assert result.confidence > 0.5

    def test_confidence_bounds(self, parser):
        """Test confidence is always between 0 and 1"""
        queries = [
            "test",
            "How to use FastAPI with PostgreSQL and Docker and Redis?",
            "x",
            "Explain Python async await in FastAPI with examples",
        ]

        for query in queries:
            result = parser.parse(query)
            assert 0.0 <= result.confidence <= 1.0

    def test_empty_query(self, parser):
        """Test handling of empty query"""
        result = parser.parse("")

        assert result.original_query == ""
        assert result.normalized_query == ""
        assert len(result.extracted_entities) == 0

    def test_special_characters_handling(self, parser):
        """Test handling of special characters"""
        result = parser.parse("How to use @decorators in Python???")

        # Should normalize but preserve meaningful content
        assert len(result.normalized_query) > 0
        assert "???" not in result.normalized_query

    def test_case_sensitivity_tech_keywords(self, parser):
        """Test case-insensitive matching of tech keywords"""
        queries = [
            "How to use FASTAPI?",
            "How to use FastApi?",
            "How to use fastapi?",
        ]

        for query in queries:
            result = parser.parse(query)
            entities_lower = [e.lower() for e in result.extracted_entities]
            assert "fastapi" in entities_lower

    def test_deduplication_of_entities(self, parser):
        """Test that duplicate entities are removed"""
        result = parser.parse("FastAPI fastapi FastApi tutorial")

        # All variations of "FastAPI" should be deduplicated
        entities_lower = [e.lower() for e in result.extracted_entities]
        assert entities_lower.count("fastapi") <= 1

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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
