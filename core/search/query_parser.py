"""
Query Parser for KG-Enhanced Search
Extracts entities and intent from user queries using GLiNER
"""

import re
import logging
import os
from typing import List, Dict, Optional, Set
from dataclasses import dataclass
import yaml
from gliner import GLiNER

logger = logging.getLogger(__name__)


@dataclass
class ParsedQuery:
    """Structured representation of parsed query"""
    original_query: str
    normalized_query: str
    extracted_entities: List[str]
    query_intent: str  # "informational", "navigational", "transactional"
    search_variants: List[str]
    confidence: float


class QueryParser:
    """
    Parse user queries using GLiNER small model
    Uses same taxonomy as kg-service for consistency
    """

    def __init__(
        self,
        model_name: str = "urchade/gliner_small-v2.1",
        taxonomy_path: Optional[str] = None,
        threshold: float = 0.1
    ):
        self.model_name = model_name
        self.threshold = threshold

        # Load GLiNER model
        logger.info(f"Loading GLiNER model: {model_name}")
        try:
            self.model = GLiNER.from_pretrained(model_name)
            logger.info("✓ GLiNER model loaded")
        except Exception as e:
            logger.error(f"Failed to load GLiNER: {e}")
            raise

        # Load taxonomy
        if taxonomy_path is None:
            taxonomy_path = os.path.join(
                os.path.dirname(__file__), "../../taxonomy/entities.yaml"
            )

        if os.path.exists(taxonomy_path):
            self.entity_types = self._load_taxonomy(taxonomy_path)
            logger.info(f"✓ Loaded {len(self.entity_types)} entity types")
        else:
            logger.warning("Taxonomy not found, using defaults")
            self.entity_types = self._get_default_types()

        # Intent patterns
        self.intent_patterns = [
            ("transactional", [
                r"\binstall\b", r"\bsetup\b", r"\bconfigure\b",
                r"\bcreate\b", r"\bbuild\b", r"\bdeploy\b"
            ]),
            ("navigational", [
                r"\bfind\b", r"\bsearch\b", r"\blocate\b", r"\bget\b",
                r"\bshow me\b", r"\bgive me\b"
            ]),
            ("informational", [
                r"\bhow\b", r"\bwhat\b", r"\bwhy\b", r"\bexplain\b",
                r"\bdescribe\b", r"\btell me\b", r"\bshow\b"
            ])
        ]

    def _load_taxonomy(self, path: str) -> List[str]:
        """Load entity types from YAML"""
        try:
            with open(path, 'r') as f:
                data = yaml.safe_load(f)
            types = []
            for cat, t in data.get('entity_categories', {}).items():
                types.extend(t)
            return types
        except Exception as e:
            logger.error(f"Failed to load taxonomy: {e}")
            return self._get_default_types()

    def _get_default_types(self) -> List[str]:
        """Fallback entity types"""
        return [
            "Programming::Language",
            "Programming::Framework",
            "Web::Framework",
            "Database::Relational",
            "Database::NoSQL",
            "Technology::Tool",
        ]

    def parse(self, query: str) -> ParsedQuery:
        """
        Parse user query into structured components

        Args:
            query: Raw user query string

        Returns:
            ParsedQuery object with extracted information
        """
        # Extract entities from original query (before normalization removes quotes)
        entities = self._extract_entities(query)

        # Normalize query
        normalized = self._normalize_query(query)

        # Detect intent
        intent = self._detect_intent(query)

        # Generate search variants
        variants = self._generate_variants(normalized, entities)

        # Calculate confidence
        confidence = self._calculate_confidence(entities, intent)

        return ParsedQuery(
            original_query=query,
            normalized_query=normalized,
            extracted_entities=entities,
            query_intent=intent,
            search_variants=variants,
            confidence=confidence
        )

    def _normalize_query(self, query: str) -> str:
        """Normalize query text"""
        # Convert to lowercase
        normalized = query.lower()

        # Remove special characters but keep meaningful ones
        normalized = re.sub(r'[^\w\s\-\.]', ' ', normalized)

        # Remove extra whitespace and trim
        normalized = re.sub(r'\s+', ' ', normalized).strip()

        return normalized

    def _extract_entities(self, query: str) -> List[str]:
        """Extract entities using GLiNER"""
        try:
            # Use GLiNER to extract entities
            predictions = self.model.predict_entities(
                query,
                self.entity_types,
                threshold=self.threshold
            )

            # Extract entity text
            entities = [pred["text"] for pred in predictions]

            # Deduplicate
            seen = set()
            unique = []
            for ent in entities:
                ent_lower = ent.lower()
                if ent_lower not in seen:
                    seen.add(ent_lower)
                    unique.append(ent)

            return unique

        except Exception as e:
            logger.error(f"GLiNER extraction failed: {e}")
            return []

    def _detect_intent(self, query: str) -> str:
        """Detect query intent from patterns"""
        query_lower = query.lower()

        # Check each intent category (order matters - more specific first)
        for intent, patterns in self.intent_patterns:
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    return intent

        # Default to informational
        return "informational"

    def _generate_variants(
        self,
        query: str,
        entities: List[str]
    ) -> List[str]:
        """
        Generate query variants for better matching

        Variants:
        - Original query
        - Query with entity emphasis (entity terms repeated)
        - Entity-only query
        """
        variants = [query]

        if entities:
            # Entity-emphasized variant
            entity_str = " ".join(entities)
            variants.append(f"{query} {entity_str}")

            # Entity-only variant
            variants.append(entity_str)

        return variants

    def _calculate_confidence(
        self,
        entities: List[str],
        intent: str
    ) -> float:
        """
        Calculate confidence score for parsed query

        Higher confidence = more structured, more entities
        """
        confidence = 0.5  # Base confidence

        # Boost for entities found
        if entities:
            confidence += min(0.3, len(entities) * 0.1)

        # Boost for clear intent
        if intent != "informational":
            confidence += 0.1

        # Clamp to [0.0, 1.0]
        return min(1.0, confidence)


# Global instance
_query_parser: Optional[QueryParser] = None


def get_query_parser() -> QueryParser:
    """Get global query parser instance"""
    global _query_parser
    if _query_parser is None:
        _query_parser = QueryParser()
    return _query_parser
