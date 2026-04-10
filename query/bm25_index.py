import bisect
import json
import re
import threading
from collections import Counter, defaultdict
from dataclasses import dataclass
from math import floor, isfinite, log
from typing import Any, Dict, Final, List, Optional, Set

from schema import CompressedObservation, Model
from query.stemmer import stem
from query.synonym import get_synonyms

_TOKENIZE_RE = re.compile(r"[^a-zA-Z0-9_\s/.\-]")


@dataclass
class IndexEntry(Model):
    obs_id: str
    session_id: str
    term_count: int


class BM25Index:
    def __init__(self):
        self._entries: Dict[str, IndexEntry] = {}
        self._inverted_index: Dict[str, Set[str]] = {}
        self._doc_term_counts: Dict[str, Dict[str, int]] = {}
        self._total_doc_length: int = 0
        self._sorted_terms: Optional[List[str]] = None
        self._idf_cache: Dict[str, float] = {}

        self._k1: Final[float] = 1.2
        self._b: Final[float] = 0.75

    @property
    def size(self) -> int:
        return len(self._entries)

    def add(self, obs: CompressedObservation) -> None:
        # Upsert: remove stale data for this obs_id before re-indexing
        if obs.id in self._entries:
            old = self._entries[obs.id]
            self._total_doc_length -= old.term_count
            for term in self._doc_term_counts.get(obs.id, {}):
                obs_set = self._inverted_index.get(term)
                if obs_set:
                    obs_set.discard(obs.id)
                    if not obs_set:
                        del self._inverted_index[term]
            del self._doc_term_counts[obs.id]

        terms = self._extract_terms(obs)
        term_freq: Dict[str, int] = Counter(terms)
        term_count = len(terms)

        self._entries[obs.id] = IndexEntry(obs.id, obs.session_id, term_count)
        self._doc_term_counts[obs.id] = term_freq
        self._total_doc_length += term_count

        for term in term_freq:
            if term not in self._inverted_index:
                self._inverted_index[term] = set()
            self._inverted_index[term].add(obs.id)

        self._sorted_terms = None
        self._idf_cache = {}

    def search(
        self,
        query: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        raw_terms = self._tokenize(query.lower())
        if not raw_terms:
            return []

        n = len(self._entries)
        if n == 0:
            return []

        avg_doc_len = self._total_doc_length / n
        k1 = self._k1
        b = self._b
        k1_plus1 = k1 + 1

        seen: Set[str] = set()
        query_terms: List[tuple[str, float]] = []
        for term in raw_terms:
            if term not in seen:
                seen.add(term)
                query_terms.append((term, 1.0))
            for syn in get_synonyms(term):
                if syn not in seen:
                    seen.add(syn)
                    query_terms.append((syn, 0.7))

        scores: Dict[str, float] = defaultdict(float)
        sorted_terms = self._get_sorted_terms()

        for term, weight in query_terms:
            matching_docs = self._inverted_index.get(term)
            if matching_docs:
                idf_w = self._get_idf(term, n) * weight

                for obs_id in matching_docs:
                    tf = self._doc_term_counts[obs_id][term]
                    doc_len = self._entries[obs_id].term_count

                    numerator = tf * k1_plus1
                    denominator = tf + k1 * (1 - b + b * (doc_len / avg_doc_len))
                    scores[obs_id] += idf_w * (numerator / denominator)

            start_idx = bisect.bisect_left(sorted_terms, term)
            for si in range(start_idx, len(sorted_terms)):
                index_term = sorted_terms[si]
                if not index_term.startswith(term):
                    break
                if index_term == term:
                    continue

                obs_ids = self._inverted_index[index_term]
                prefix_idf_w = self._get_idf(index_term, n) * 0.5 * weight

                for obs_id in obs_ids:
                    tf = self._doc_term_counts[obs_id][index_term]
                    doc_len = self._entries[obs_id].term_count

                    numerator = tf * k1_plus1
                    denominator = tf + k1 * (1 - b + b * (doc_len / avg_doc_len))
                    scores[obs_id] += prefix_idf_w * (numerator / denominator)

        results = [
            {"obs_id": obs_id, "session_id": self._entries[obs_id].session_id, "score": score}
            for obs_id, score in scores.items()
        ]
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def clear(self) -> None:
        self._entries = {}
        self._inverted_index = {}
        self._doc_term_counts = {}
        self._total_doc_length = 0
        self._sorted_terms = None
        self._idf_cache = {}

    def restore_from(self, other: "BM25Index") -> None:
        self._entries = dict(other._entries)
        self._inverted_index = {k: set(v) for k, v in other._inverted_index.items()}
        self._doc_term_counts = {k: dict(v) for k, v in other._doc_term_counts.items()}
        self._total_doc_length = other._total_doc_length
        self._sorted_terms = None
        self._idf_cache = {}

    def serialize(self) -> str:
        return json.dumps({
            "v": 2,
            "entries": [(oid, e.to_dict()) for oid, e in self._entries.items()],
            "inverted": [(term, list(ids)) for term, ids in self._inverted_index.items()],
            "doc_terms": [(doc_id, list(counts.items())) for doc_id, counts in self._doc_term_counts.items()],
            "total_doc_length": self._total_doc_length,
        })

    @staticmethod
    def deserialize(json_str: str) -> "BM25Index":
        try:
            idx = BM25Index()
            data = json.loads(json_str)

            if not isinstance(data, dict):
                return idx
            if not data.get("entries") or not data.get("inverted") or not data.get("doc_terms"):
                return idx

            for key, val in data["entries"]:
                idx._entries[key] = IndexEntry.from_dict(val)

            for term, ids in data["inverted"]:
                idx._inverted_index[term] = set(ids)

            for doc_id, counts in data["doc_terms"]:
                idx._doc_term_counts[doc_id] = dict(counts)

            raw_len = data.get("total_doc_length", 0)
            try:
                raw_len = float(raw_len)
                idx._total_doc_length = floor(raw_len) if isfinite(raw_len) and raw_len >= 0 else 0
            except (ValueError, TypeError):
                idx._total_doc_length = 0

            return idx

        except Exception:
            return BM25Index()

    def _get_idf(self, term: str, n: int) -> float:
        cached = self._idf_cache.get(term)
        if cached is not None:
            return cached
        df = len(self._inverted_index.get(term, set()))
        idf = log((n - df + 0.5) / (df + 0.5) + 1)
        self._idf_cache[term] = idf
        return idf

    def _get_sorted_terms(self) -> List[str]:
        if self._sorted_terms is None:
            self._sorted_terms = sorted(self._inverted_index.keys())
        return self._sorted_terms

    def _extract_terms(self, obs: CompressedObservation) -> List[str]:
        parts = [
            obs.title,
            obs.subtitle or "",
            obs.narrative,
            *obs.facts,
            *obs.concepts,
            *obs.files,
            obs.type,
        ]
        return self._tokenize(" ".join(parts).lower())

    def _tokenize(self, text: str) -> List[str]:
        return [stem(t) for t in _TOKENIZE_RE.sub(" ", text).split() if len(t) > 1]


_bm25_index: Optional[BM25Index] = None
_lock = threading.Lock()


def get_bm25_index() -> BM25Index:
    global _bm25_index
    if _bm25_index is None:
        with _lock:
            if _bm25_index is None:
                _bm25_index = BM25Index()
    return _bm25_index
