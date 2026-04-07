
import math
import re
from typing import Dict, Final, List, Optional, Set
from dataclasses import dataclass
from logger import get_logger
from schema import CompressedObservation, SearchResult

logger = get_logger("search_index")


@dataclass
class IndexEntry:
    obs_id: str
    session_id: str
    term_count: int


class SearchIndex:
    def __init__(self):
        self._entries: Dict[str, IndexEntry] = {}
        self._inverted_index: Dict[str, Set[str]] = {}
        self._doc_term_counts: Dict[str, Dict[str, int]] = {}
        self._total_doc_length = 0

        self._k1: Final[float] = 1.2
        self._b: Final[float] = 0.75

    def add(self, obs: CompressedObservation):
        terms = self._extract_terms(obs)
        term_freq: Dict[str, int] = {}
        term_count = 0

        for term in terms:
            term_freq[term] = term_freq.get(term, 0) + 1
            term_count += 1

        self._entries[obs.id] = IndexEntry(obs.id, obs.session_id, term_count)
        self._doc_term_counts[obs.id] = term_freq
        self._total_doc_length += term_count

        for term in term_freq:
            if term not in self._inverted_index:
                self._inverted_index[term] = set()

            self._inverted_index[term].add(obs.id)

    def search(self, query: str, limit: Optional[int] = 20) -> List[SearchResult]:
        query_terms = self._tokenize(query.lower())
        if len(query_terms) == 0:
            return []

        N = len(self._entries)
        if N == 0:
            return []

        avg_doc_len = self._total_doc_length / N

        scores: Dict[str, float] = {}

        for term in query_terms:
            matching_docs = self._inverted_index.get(term)
            if matching_docs is None:
                continue

            df = len(matching_docs)
            idf = math.log((N - df + 0.5) / (df + 0.5) + 1)

            # --- BM25 scoring ---
            for obs_id in matching_docs:
                entry = self._entries[obs_id]
                doc_terms = self._doc_term_counts.get(obs_id)

                tf = doc_terms.get(term, 0) if doc_terms else 0
                doc_len = entry.term_count

                numerator = tf * (self._k1 + 1)
                denominator = tf + self._k1 * (
                    1 - self._b + self._b * (doc_len / avg_doc_len)
                )

                bm25_score = idf * (numerator / denominator)

                scores[obs_id] = scores.get(obs_id, 0) + bm25_score

            for index_term, obs_ids in self._inverted_index.items():
                if index_term != term and index_term.startswith(term):
                    prefix_df = len(obs_ids)
                    prefix_idf = math.log(
                        (N - prefix_df + 0.5) / (prefix_df + 0.5) + 1
                    ) * 0.5

                    for obs_id in obs_ids:
                        entry = self._entries[obs_id]
                        doc_terms = self._doc_term_counts.get(obs_id)

                        tf = doc_terms.get(index_term, 0) if doc_terms else 0
                        doc_len = entry.term_count

                        numerator = tf * (self._k1 + 1)
                        denominator = tf + self._k1 * (
                            1 - self._b + self._b * (doc_len / avg_doc_len)
                        )

                        scores[obs_id] = scores.get(obs_id, 0) + (
                            prefix_idf * (numerator / denominator)
                        )

        results = [
            SearchResult(obs_id, score, self._entries[obs_id].session_id)
            for obs_id, score in scores.items()
        ]

        results.sort(key=lambda x: x.score, reverse=True)

        return results[:limit]

    def clear(self):
        self._entries = {}
        self._inverted_index = {}
        self._doc_term_counts = {}
        self._total_doc_length = 0

    @property
    def doc_term_counts(self):
        return self._doc_term_counts

    @property
    def inverted_index(self):
        return self._inverted_index

    def _extract_terms(self, obs: CompressedObservation):
        parts = [
            obs.title,
            obs.subtitle or "",
            obs.narrative,
            *obs.facts,
            *obs.concepts,
            *obs.files,
            obs.type
        ]

        return self._tokenize(" ".join(parts).lower())

    def _tokenize(self, text: str) -> list[str]:
        return [t for t in re.sub(r"[^a-zA-Z0-9_\s/.\-]", " ", text).split() if len(t) > 1]
