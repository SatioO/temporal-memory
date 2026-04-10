from typing import Optional
from query.bm25_index import BM25Index
from query.vector_index import VectorIndex
from schema import EmbeddingProvider, HybridSearchResult
from state.kv import StateKV


class Search:
    def __init__(
        self,
        kv: StateKV,
        bm25_index: BM25Index,
        vector_index: Optional[VectorIndex],
        embedding_provider: Optional[EmbeddingProvider],
        bm25_weight: Optional[float] = 0.4,
        vector_weight: Optional[float] = 0.6
    ):
        self._kv = kv
        self._bm25_index = bm25_index
        self._vector_index = vector_index
        self._embedding_provider = embedding_provider
        self._bm25_weight = bm25_weight
        self._vector_weight = vector_weight

    async def search(self, query: str, limit: Optional[int] = 20) -> HybridSearchResult:
        self._triple_stream_search(query, limit)

    def _triple_stream_search(self, query, limit):
        bm25_results = self._bm25_index.search(query, limit)
