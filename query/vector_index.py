import base64
import json
import threading
from typing import Dict, List, Optional, Tuple

import numpy as np

from schema import EmbeddingProvider


class VectorIndex:
    def __init__(self):
        # obs_id -> (session_id, pre-normalized float32 embedding)
        self._store: Dict[str, Tuple[str, np.ndarray]] = {}
        # Lazy cache: stacked matrix of all embeddings, shape (n, dim)
        self._matrix: Optional[np.ndarray] = None
        self._matrix_ids: Optional[List[str]] = None

    @property
    def size(self) -> int:
        return len(self._store)

    def add(self, obs_id: str, session_id: str, embedding: np.ndarray) -> None:
        vec = embedding.astype(np.float32, copy=False)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        self._store[obs_id] = (session_id, vec)
        self._matrix = None

    def remove(self, obs_id: str) -> None:
        if obs_id in self._store:
            del self._store[obs_id]
            self._matrix = None

    def search(
        self,
        query: np.ndarray,
        limit: int = 20,
    ) -> List[Dict]:
        if not self._store:
            return []

        matrix, ids = self._get_matrix()

        q = query.astype(np.float32, copy=False)
        q_norm = np.linalg.norm(q)
        if q_norm > 0:
            q = q / q_norm

        # Single BLAS call — embeddings are pre-normalized so this is cosine similarity
        scores: np.ndarray = matrix @ q  # shape (n,)

        n = len(ids)
        k = min(limit, n)

        if k == n:
            top_idx = np.argsort(scores)[::-1]
        else:
            # O(n) partition, then sort only the top-k: O(k log k)
            top_idx = np.argpartition(scores, -k)[-k:]
            top_idx = top_idx[np.argsort(scores[top_idx])[::-1]]

        return [
            {
                "obs_id": ids[i],
                "session_id": self._store[ids[i]][0],
                "score": float(scores[i]),
            }
            for i in top_idx
        ]

    def clear(self) -> None:
        self._store.clear()
        self._matrix = None

    def restore_from(self, other: "VectorIndex") -> None:
        self._store = {
            obs_id: (session_id, vec.copy())
            for obs_id, (session_id, vec) in other._store.items()
        }
        self._matrix = None

    def serialize(self) -> str:
        data = [
            [
                obs_id,
                {
                    "embedding": base64.b64encode(vec.tobytes()).decode(),
                    "session_id": session_id,
                },
            ]
            for obs_id, (session_id, vec) in self._store.items()
        ]
        return json.dumps(data)

    @staticmethod
    def deserialize(json_str: str) -> "VectorIndex":
        idx = VectorIndex()
        try:
            data = json.loads(json_str)
        except Exception:
            return idx

        if not isinstance(data, list):
            return idx

        for row in data:
            try:
                if not isinstance(row, list) or len(row) < 2:
                    continue
                obs_id, entry = row
                if (
                    not isinstance(obs_id, str)
                    or not isinstance(entry.get("embedding"), str)
                    or not isinstance(entry.get("session_id"), str)
                ):
                    continue
                # Embeddings were pre-normalized before serialization — load directly
                vec = np.frombuffer(
                    base64.b64decode(entry["embedding"]), dtype=np.float32
                ).copy()
                idx._store[obs_id] = (entry["session_id"], vec)
            except Exception:
                continue

        return idx

    def _get_matrix(self) -> Tuple[np.ndarray, List[str]]:
        if self._matrix is None:
            ids = list(self._store.keys())
            self._matrix_ids = ids
            self._matrix = np.stack([self._store[oid][1] for oid in ids])
        return self._matrix, self._matrix_ids


_vector_index: Optional[VectorIndex] = None
_lock = threading.Lock()


def init_vector_index(embedding_provider: Optional[EmbeddingProvider]) -> Optional[VectorIndex]:
    """Initialize the singleton VectorIndex. Call once at startup.
    Returns None if no embedding provider is configured (BM25-only mode)."""
    global _vector_index
    if embedding_provider is None:
        return None
    with _lock:
        if _vector_index is None:
            _vector_index = VectorIndex()
    return _vector_index


def get_vector_index() -> Optional[VectorIndex]:
    """Return the singleton VectorIndex, or None if not initialized."""
    return _vector_index
