import asyncio
from dataclasses import dataclass
from typing import Dict, List, Optional
from query.bm25_index import BM25Index
from query.rerank import rerank
from query.vector_index import VectorIndex
from schema import CompressedObservation, EmbeddingProvider, HybridSearchResult, Model
from state.schema import KV
from state.kv import StateKV


@dataclass
class ScoreEntry(Model):
    bm25_rank: float
    vector_rank: float
    graph_rank: float
    session_id: str
    bm25_score: float
    vector_score: float
    graph_score: float
    graph_context: Optional[str] = None


@dataclass
class CombinedResult(Model):
    obs_id: str
    session_id: str
    bm25_score: float
    vector_score: float
    graph_score: float
    graph_context: Optional[str]
    combined_score: float


class Search:
    def __init__(
        self,
        kv: StateKV,
        bm25_index: BM25Index,
        vector_index: Optional[VectorIndex],
        embedding_provider: Optional[EmbeddingProvider],
        bm25_weight: Optional[float] = 0.4,
        vector_weight: Optional[float] = 0.6,
        rerank_enabled: bool = False,
    ):
        self._kv = kv
        self._bm25_index = bm25_index
        self._vector_index = vector_index
        self._embedding_provider = embedding_provider
        self._bm25_weight = bm25_weight
        self._vector_weight = vector_weight
        self._rerank_enabled = rerank_enabled

    def _diversify_by_session(
        self,
        results: List[CombinedResult],
        limit: int,
        max_per_session: int = 3,
    ) -> List[CombinedResult]:
        selected: List[CombinedResult] = []
        session_counts: Dict[str, int] = {}

        for r in results:
            count = session_counts.get(r.session_id, 0)
            if count >= max_per_session:
                continue
            selected.append(r)
            session_counts[r.session_id] = count + 1
            if len(selected) >= limit:
                break

        if len(selected) < limit:
            selected_ids = {r.obs_id for r in selected}
            for r in results:
                if len(selected) >= limit:
                    break
                if r.obs_id not in selected_ids:
                    selected.append(r)

        return selected

    async def _enrich_results(
        self,
        results: List[CombinedResult],
        limit: int,
    ) -> List[HybridSearchResult]:
        sliced = results[:limit]

        observations = await asyncio.gather(
            *[self._kv.get(KV.observations(r.session_id), r.obs_id,
                           CompressedObservation) for r in sliced],
            return_exceptions=True
        )

        enriched: List[HybridSearchResult] = []
        for i, obs in enumerate(observations):
            if isinstance(obs, CompressedObservation):
                enriched.append(HybridSearchResult(
                    observation=obs,
                    bm25_score=sliced[i].bm25_score,
                    vector_score=sliced[i].vector_score,
                    combined_score=sliced[i].combined_score,
                    session_id=sliced[i].session_id,
                ))

        return enriched

    async def search(self, query: str, limit: Optional[int] = 20) -> List[HybridSearchResult]:
        return await self._triple_stream_search(query, limit)

    async def _triple_stream_search(self, query, limit, early_hints: Optional[str] = None):
        # BM25 search results
        bm25_results = self._bm25_index.search(query, limit)

        # Vector search results
        vector_results: List[Dict] = []
        query_embeddings: Optional[List[float]] = None
        if self._vector_index and self._vector_index.size() > 0:
            try:
                query_embeddings = self._embedding_provider.embed(query)
                vector_results = self._vector_index.search(query_embeddings)
            except:
                pass

        # TODO: Graph Results

        scores: Dict[str, ScoreEntry] = {}

        for i, r in enumerate(bm25_results):
            scores[r["obs_id"]] = ScoreEntry(
                bm25_rank=i + 1,
                vector_rank=float("inf"),
                graph_rank=float("inf"),
                session_id=r["session_id"],
                bm25_score=r["score"],
                vector_score=0.0,
                graph_score=0.0,
            )

        for i, r in enumerate(vector_results):
            existing = scores.get(r.obs_id)
            if existing:
                existing.vector_rank = i + 1
                existing.vector_score = r.score
            else:
                scores[r.obs_id] = ScoreEntry(
                    bm25_rank=float("inf"),
                    vector_rank=i + 1,
                    graph_rank=float("inf"),
                    session_id=r.session_id,
                    bm25_score=0.0,
                    vector_score=r.score,
                    graph_score=0.0,
                )

        RRF_K = 60
        effective_bm25 = self._bm25_weight
        effective_vector = self._vector_weight if len(
            vector_results) > 0 else 0.0

        total_weight = effective_bm25 + effective_vector
        if total_weight > 0:
            effective_bm25 /= total_weight
            effective_vector /= total_weight

        combined = sorted([
            CombinedResult(
                obs_id=obs_id,
                session_id=s.session_id,
                bm25_score=s.bm25_score,
                vector_score=s.vector_score,
                graph_score=0.0,
                graph_context=None,
                combined_score=(
                    effective_bm25 * (1 / (RRF_K + s.bm25_rank)) +
                    effective_vector * (1 / (RRF_K + s.vector_rank))
                ),
            )
            for obs_id, s in scores.items()
        ], key=lambda k: k.combined_score, reverse=True)

        retrieval_depth = max(limit, 20)
        rerank_window = 20
        diversified = self._diversify_by_session(combined, retrieval_depth)
        enriched = await self._enrich_results(diversified, retrieval_depth)

        if self._rerank_enabled and len(enriched) > 1:
            try:
                head = enriched[:rerank_window]
                tail = enriched[rerank_window:]
                reranked = await rerank(query, head, rerank_window)
                return (reranked + tail)[:limit]
            except Exception:
                pass

        return enriched[:limit]
