import re
import math
from typing import Dict, Set, List, Tuple
from dataclasses import dataclass

from state.stemmer import stem
from state.synonym import get_synonyms


@dataclass
class IndexEntry:
    obs_id: str
    session_id: str
    term_count: int


class SearchIndex:
    def __init__(self):
        self.entries: Dict[str, IndexEntry] = {}
        self.inverted_index: Dict[str, Set[str]] = {}
        self.doc_term_counts: Dict[str, Dict[str, int]] = {}
        self.total_doc_length: int = 0
        self.sorted_terms: List[str] | None = None

        self.k1 = 1.2
        self.b = 0.75

    def add(self, obs):
        terms = self.extract_terms(obs)
        term_freq: Dict[str, int] = {}
        term_count = 0

        for term in terms:
            term_freq[term] = term_freq.get(term, 0) + 1
            term_count += 1

        self.entries[obs.id] = IndexEntry(
            obs_id=obs.id,
            session_id=obs.sessionId,
            term_count=term_count,
        )

        self.doc_term_counts[obs.id] = term_freq
        self.total_doc_length += term_count

        for term in term_freq:
            if term not in self.inverted_index:
                self.inverted_index[term] = set()
            self.inverted_index[term].add(obs.id)

        self.sorted_terms = None

    # ---------------- SEARCH ----------------
    def search(self, query: str, limit: int = 20):
        raw_terms = self.tokenize(query.lower())
        if not raw_terms:
            return []

        N = len(self.entries)
        if N == 0:
            return []

        avg_doc_len = self.total_doc_length / N

        query_terms: List[Tuple[str, float]] = []
        seen = set()

        for term in raw_terms:
            if term not in seen:
                seen.add(term)
                query_terms.append((term, 1.0))

            for syn in get_synonyms(term):
                if syn not in seen:
                    seen.add(syn)
                    query_terms.append((syn, 0.7))

        scores: Dict[str, float] = {}
        sorted_terms = self.get_sorted_terms()

        for term, weight in query_terms:
            matching_docs = self.inverted_index.get(term)

            if matching_docs:
                df = len(matching_docs)
                idf = math.log((N - df + 0.5) / (df + 0.5) + 1)

                for obs_id in matching_docs:
                    entry = self.entries[obs_id]
                    doc_terms = self.doc_term_counts.get(obs_id, {})
                    tf = doc_terms.get(term, 0)
                    doc_len = entry.term_count

                    numerator = tf * (self.k1 + 1)
                    denominator = tf + self.k1 * (
                        1 - self.b + self.b * (doc_len / avg_doc_len)
                    )

                    bm25 = idf * (numerator / denominator) * weight
                    scores[obs_id] = scores.get(obs_id, 0) + bm25

            start_idx = self.lower_bound(sorted_terms, term)

            for i in range(start_idx, len(sorted_terms)):
                index_term = sorted_terms[i]
                if not index_term.startswith(term):
                    break
                if index_term == term:
                    continue

                obs_ids = self.inverted_index[index_term]
                prefix_df = len(obs_ids)

                prefix_idf = (
                    math.log((N - prefix_df + 0.5) /
                             (prefix_df + 0.5) + 1) * 0.5
                )

                for obs_id in obs_ids:
                    entry = self.entries[obs_id]
                    doc_terms = self.doc_term_counts.get(obs_id, {})
                    tf = doc_terms.get(index_term, 0)
                    doc_len = entry.term_count

                    numerator = tf * (self.k1 + 1)
                    denominator = tf + self.k1 * (
                        1 - self.b + self.b * (doc_len / avg_doc_len)
                    )

                    scores[obs_id] = scores.get(obs_id, 0) + (
                        prefix_idf * (numerator / denominator) * weight
                    )

        results = [
            {
                "obsId": obs_id,
                "sessionId": self.entries[obs_id].session_id,
                "score": score,
            }
            for obs_id, score in scores.items()
        ]

        return sorted(results, key=lambda x: x["score"], reverse=True)[:limit]

    # ---------------- UTILS ----------------
    @property
    def size(self):
        return len(self.entries)

    def clear(self):
        self.entries.clear()
        self.inverted_index.clear()
        self.doc_term_counts.clear()
        self.total_doc_length = 0
        self.sorted_terms = None

    def restore_from(self, other: "SearchIndex"):
        self.entries = {k: IndexEntry(**vars(v))
                        for k, v in other.entries.items()}
        self.inverted_index = {k: set(v)
                               for k, v in other.inverted_index.items()}
        self.doc_term_counts = {
            k: dict(v) for k, v in other.doc_term_counts.items()
        }
        self.total_doc_length = other.total_doc_length
        self.sorted_terms = None

    def serialize(self) -> str:
        return str({
            "entries": {k: vars(v) for k, v in self.entries.items()},
            "inverted": {k: list(v) for k, v in self.inverted_index.items()},
            "docTerms": self.doc_term_counts,
            "totalDocLength": self.total_doc_length,
        })

    @staticmethod
    def deserialize(data: dict):
        idx = SearchIndex()
        if not data:
            return idx

        for k, v in data.get("entries", {}).items():
            idx.entries[k] = IndexEntry(**v)

        for term, ids in data.get("inverted", {}).items():
            idx.inverted_index[term] = set(ids)

        idx.doc_term_counts = data.get("docTerms", {})
        idx.total_doc_length = int(data.get("totalDocLength", 0))

        return idx

    # ---------------- TOKENIZATION ----------------
    def extract_terms(self, obs) -> List[str]:
        parts = [
            obs.title,
            obs.subtitle or "",
            obs.narrative,
            *obs.facts,
            *obs.concepts,
            *obs.files,
            obs.type,
        ]
        return self.tokenize(" ".join(parts).lower())

    def tokenize(self, text: str) -> List[str]:
        return [
            stem(t)
            for t in re.sub(r"[^\w\s/.\-_]", " ", text).split()
            if len(t) > 1
        ]

    def get_sorted_terms(self) -> List[str]:
        if self.sorted_terms is None:
            self.sorted_terms = sorted(self.inverted_index.keys())
        return self.sorted_terms

    def lower_bound(self, arr: List[str], target: str) -> int:
        lo, hi = 0, len(arr)
        while lo < hi:
            mid = (lo + hi) // 2
            if arr[mid] < target:
                lo = mid + 1
            else:
                hi = mid
        return lo
