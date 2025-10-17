"""
Advanced Ranker - Phase 4
Multi-signal ranking with text matching, recency, and relevance
"""

import logging
import re
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from collections import Counter
import math

logger = logging.getLogger(__name__)


class AdvancedRanker:
    """
    Advanced ranking algorithm combining multiple signals:
    - Vector similarity (from Phase 2)
    - Graph relevance (from Phase 2)
    - Entity match count (from Phase 3)
    - BM25 text relevance (Phase 4)
    - Recency boost (Phase 4)
    - Title match boost (Phase 4)
    """

    def __init__(
        self,
        vector_weight: float = 0.35,
        graph_weight: float = 0.25,
        text_weight: float = 0.20,
        recency_weight: float = 0.10,
        title_weight: float = 0.10
    ):
        """
        Initialize ranker with signal weights

        Args:
            vector_weight: Weight for vector similarity
            graph_weight: Weight for graph relevance
            text_weight: Weight for BM25 text matching
            recency_weight: Weight for document freshness
            title_weight: Weight for title matching
        """
        self.vector_weight = vector_weight
        self.graph_weight = graph_weight
        self.text_weight = text_weight
        self.recency_weight = recency_weight
        self.title_weight = title_weight

        # Normalize weights
        total = sum([
            vector_weight, graph_weight, text_weight,
            recency_weight, title_weight
        ])
        if total > 0:
            self.vector_weight /= total
            self.graph_weight /= total
            self.text_weight /= total
            self.recency_weight /= total
            self.title_weight /= total

    def rank(
        self,
        results: List[Dict],
        query: str,
        entities: List[str]
    ) -> List[Dict]:
        """
        Rerank results using multiple signals

        Args:
            results: List of search results
            query: Original query text
            entities: Extracted entities

        Returns:
            Reranked results with scores
        """
        if not results:
            return results

        logger.debug(f"Ranking {len(results)} results")

        # Calculate each signal
        for result in results:
            scores = self._calculate_scores(result, query, entities)
            result['ranking_scores'] = scores
            result['final_rank_score'] = self._combine_scores(scores)

        # Sort by final score
        ranked = sorted(
            results,
            key=lambda x: x.get('final_rank_score', 0.0),
            reverse=True
        )

        logger.info(f"Ranked {len(ranked)} results")
        return ranked

    def _calculate_scores(
        self,
        result: Dict,
        query: str,
        entities: List[str]
    ) -> Dict:
        """Calculate individual ranking scores"""

        # Vector similarity (already computed)
        vector_score = result.get('vector_score', 0.0)

        # Graph relevance (already computed)
        graph_score = result.get('graph_score', 0.0)

        # BM25-style text matching
        text_score = self._calculate_text_score(
            result.get('content', ''),
            result.get('title', ''),
            query,
            entities
        )

        # Recency boost
        recency_score = self._calculate_recency_score(
            result.get('timestamp')
        )

        # Title match boost
        title_score = self._calculate_title_score(
            result.get('title', ''),
            query,
            entities
        )

        return {
            'vector': vector_score,
            'graph': graph_score,
            'text': text_score,
            'recency': recency_score,
            'title': title_score
        }

    def _calculate_text_score(
        self,
        content: str,
        title: str,
        query: str,
        entities: List[str]
    ) -> float:
        """
        Calculate BM25-style text relevance score

        Simplified BM25:
        - Term frequency in document
        - Query term importance
        - Document length normalization
        """
        if not content:
            return 0.0

        # Combine content and title (title weighted higher)
        title_text = (title + ' ') * 3 if title else ''
        text = title_text + content
        text_lower = text.lower()

        # Extract query terms
        query_terms = self._extract_terms(query)
        entity_terms = [e.lower() for e in entities]
        all_terms = list(set(query_terms + entity_terms))

        if not all_terms:
            return 0.0

        # Calculate term frequencies
        doc_length = len(text_lower.split())
        avg_doc_length = 500  # Assume average

        score = 0.0
        k1 = 1.5  # BM25 parameter
        b = 0.75  # BM25 parameter

        for term in all_terms:
            # Term frequency
            tf = text_lower.count(term)
            if tf == 0:
                continue

            # BM25 formula (simplified - no IDF)
            norm_tf = tf / (1.0 + b * (doc_length / avg_doc_length - 1.0))
            term_score = (k1 + 1.0) * norm_tf / (k1 + norm_tf)

            # Boost for entity matches
            if term in entity_terms:
                term_score *= 1.5

            score += term_score

        # Normalize to [0, 1]
        return min(1.0, score / (len(all_terms) * 3.0))

    def _calculate_recency_score(self, timestamp: Optional[str]) -> float:
        """
        Calculate recency boost

        Newer content scores higher:
        - Last 7 days: 1.0
        - Last 30 days: 0.8
        - Last 90 days: 0.6
        - Last year: 0.4
        - Older: 0.2
        """
        if not timestamp:
            return 0.5  # Unknown age - moderate score

        try:
            # Parse timestamp
            if isinstance(timestamp, str):
                # Try common formats
                for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y-%m-%dT%H:%M:%S']:
                    try:
                        doc_date = datetime.strptime(timestamp[:19], fmt)
                        break
                    except ValueError:
                        continue
                else:
                    return 0.5
            else:
                return 0.5

            # Calculate age
            age = datetime.now() - doc_date

            # Recency scoring
            if age < timedelta(days=7):
                return 1.0
            elif age < timedelta(days=30):
                return 0.8
            elif age < timedelta(days=90):
                return 0.6
            elif age < timedelta(days=365):
                return 0.4
            else:
                return 0.2

        except Exception as e:
            logger.debug(f"Recency calculation failed: {e}")
            return 0.5

    def _calculate_title_score(
        self,
        title: str,
        query: str,
        entities: List[str]
    ) -> float:
        """
        Calculate title match score

        Higher scores for:
        - Exact query match
        - Entity mentions
        - Query term overlap
        """
        if not title:
            return 0.0

        title_lower = title.lower()
        query_lower = query.lower()

        score = 0.0

        # Exact query match
        if query_lower in title_lower:
            score += 1.0

        # Entity matches in title
        entity_matches = sum(
            1 for e in entities
            if e.lower() in title_lower
        )
        score += min(1.0, entity_matches / max(1, len(entities)))

        # Query term overlap
        query_terms = set(self._extract_terms(query))
        title_terms = set(self._extract_terms(title))
        if query_terms:
            overlap = len(query_terms & title_terms) / len(query_terms)
            score += overlap

        # Normalize
        return min(1.0, score / 3.0)

    def _combine_scores(self, scores: Dict) -> float:
        """Combine individual scores with weights"""
        return (
            scores['vector'] * self.vector_weight +
            scores['graph'] * self.graph_weight +
            scores['text'] * self.text_weight +
            scores['recency'] * self.recency_weight +
            scores['title'] * self.title_weight
        )

    def _extract_terms(self, text: str) -> List[str]:
        """Extract search terms from text"""
        # Remove punctuation and split
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        terms = text.split()

        # Remove stop words
        stop_words = {
            'a', 'an', 'the', 'is', 'are', 'was', 'were',
            'to', 'of', 'in', 'on', 'at', 'for', 'with',
            'how', 'what', 'when', 'where', 'why', 'who'
        }
        terms = [t for t in terms if t not in stop_words and len(t) > 2]

        return terms


class ContextExtractor:
    """
    Extract relevant context snippets from documents

    Finds passages that best match the query for display
    """

    def extract_context(
        self,
        content: str,
        query: str,
        entities: List[str],
        max_length: int = 300
    ) -> str:
        """
        Extract most relevant snippet from content

        Args:
            content: Full document content
            query: Search query
            entities: Extracted entities
            max_length: Max snippet length

        Returns:
            Relevant snippet
        """
        if not content or len(content) <= max_length:
            return content

        # Split into sentences
        sentences = self._split_sentences(content)

        # Score each sentence
        query_terms = set(query.lower().split())
        entity_terms = set(e.lower() for e in entities)

        scored_sentences = []
        for i, sent in enumerate(sentences):
            sent_lower = sent.lower()

            # Count matches
            query_matches = sum(1 for term in query_terms if term in sent_lower)
            entity_matches = sum(1 for term in entity_terms if term in sent_lower)

            score = query_matches * 2.0 + entity_matches * 1.5

            # Boost for position (earlier sentences)
            position_boost = 1.0 - (i / len(sentences)) * 0.3

            scored_sentences.append((score * position_boost, i, sent))

        # Sort by score
        scored_sentences.sort(reverse=True)

        # Take top sentences
        top_sentences = sorted(
            scored_sentences[:3],
            key=lambda x: x[1]  # Restore original order
        )

        # Combine
        snippet = ' '.join(s[2] for s in top_sentences)

        # Truncate if needed
        if len(snippet) > max_length:
            snippet = snippet[:max_length].rsplit(' ', 1)[0] + '...'

        return snippet

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        # Simple sentence splitter
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
        return sentences
