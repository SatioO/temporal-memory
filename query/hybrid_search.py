import asyncio
from typing import List, Optional
from query.bm25_index import BM25Index
from query.vector_index import VectorIndex
from schema import CompressedObservation, EmbeddingProvider, HybridSearchResult
from state.kv import StateKV
from state.schema import KV

RRF_K = 60


class HybridSearch:
    def __init__(
            self,
            kv: StateKV,
            bm25: BM25Index,
            vector: Optional[VectorIndex] = None,
            embedding_provider: Optional[EmbeddingProvider] = None,
            bm25_weight: Optional[float] = 0.4,
            vector_weight: Optional[float] = 0.6
    ):
        self._kv = kv
        self._bm25 = bm25
        self._vector = vector
        self._embedding_provider = embedding_provider
        self._bm25_weight = bm25_weight
        self._vector_weight = vector_weight

    async def search(self, query: str, limit: int = 20) -> List[HybridSearchResult]:
        bm25_results = self._bm25.search(query, limit * 2)

        if not self._vector or self._vector.size == 0:
            return await self._enrich_results(
                [
                    {
                        "obs_id": r.obs_id,
                        "session_id": r.session_id,
                        "bm25_score": r.score,
                        "vector_score": 0.0,
                        "combined_score": r.score,
                    } for r in bm25_results
                ],
                limit
            )

        query_embedding = await self._embedding_provider.embed(query)
        vector_results = self._vector.search(query_embedding, limit * 2)

        scores: dict[str, dict] = {}

        # BM25 results
        for i, r in enumerate(bm25_results):
            scores[r.obs_id] = {
                "bm25_rank": i + 1,
                "vector_rank": float("inf"),
                "session_id": r.session_id,
                "bm25_score": r.score,
                "vector_score": 0.0,
            }

        # Vector results — VectorIndex.search() returns plain dicts, use [] not .
        for i, r in enumerate(vector_results):
            existing = scores.get(r["obs_id"])

            if existing:
                existing["vector_rank"] = i + 1
                existing["vector_score"] = r["score"]
            else:
                scores[r["obs_id"]] = {
                    "bm25_rank": float("inf"),
                    "vector_rank": i + 1,
                    "session_id": r["session_id"],
                    "bm25_score": 0.0,
                    "vector_score": r["score"],
                }

        combined = [
            {
                "obs_id": obs_id,
                "session_id": s["session_id"],
                "bm25_score": s["bm25_score"],
                "vector_score": s["vector_score"],
                "combined_score": (

                    self._bm25_weight * (1 / (RRF_K + s["bm25_rank"])) +

                    self._vector_weight * (1 / (RRF_K + s["vector_rank"]))
                ),
            }
            for obs_id, s in scores.items()
        ]

        combined.sort(key=lambda x: x["combined_score"], reverse=True)

        return await self._enrich_results(combined[:limit], limit)

    async def _enrich_results(
        self,
        results: List[dict],
        limit: int,
    ) -> List[HybridSearchResult]:

        async def fetch(r: dict) -> Optional[HybridSearchResult]:
            obs = await self._kv.get(
                KV.observations(r["session_id"]),
                r["obs_id"],
                CompressedObservation,
            )
            if obs is None:
                return None
            return HybridSearchResult(
                observation=obs,
                bm25_score=r["bm25_score"],
                vector_score=r["vector_score"],
                combined_score=r["combined_score"],
                session_id=r["session_id"],
            )

        fetched = await asyncio.gather(*[fetch(r) for r in results[:limit]])
        return [r for r in fetched if r is not None]
