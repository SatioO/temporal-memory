import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

from logger import get_logger
from schema import HybridSearchResult

logger = get_logger("rerank")

_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
_MAX_TEXT_LEN = 512
_executor = ThreadPoolExecutor(max_workers=1)

_model: Optional[object] = None
_model_lock = asyncio.Lock()
_model_unavailable = False


async def _load_model():
    global _model, _model_unavailable
    if _model_unavailable:
        return None
    if _model is not None:
        return _model
    async with _model_lock:
        if _model is not None:
            return _model
        try:
            from sentence_transformers import CrossEncoder
            _model = await asyncio.get_event_loop().run_in_executor(
                _executor,
                lambda: CrossEncoder(_MODEL_NAME),
            )
            logger.info(f"reranker loaded: {_MODEL_NAME}")
            return _model
        except Exception as e:
            logger.warning(f"reranker unavailable: {e}")
            _model_unavailable = True
            return None


def is_reranker_available() -> bool:
    return _model is not None


async def rerank(
    query: str,
    results: List[HybridSearchResult],
    top_k: int = 20,
) -> List[HybridSearchResult]:
    if len(results) <= 1:
        return results

    model = await _load_model()
    if model is None:
        return results

    candidates = results[:top_k]

    pairs = [
        (
            query,
            f"{r.observation.title} {r.observation.narrative}".strip()[:_MAX_TEXT_LEN],
        )
        for r in candidates
    ]

    try:
        scores: List[float] = await asyncio.get_event_loop().run_in_executor(
            _executor,
            lambda: model.predict(pairs).tolist(),
        )
    except Exception as e:
        logger.warning(f"rerank predict failed: {e}")
        return results

    ranked = sorted(
        zip(scores, candidates),
        key=lambda x: x[0],
        reverse=True,
    )

    return [
        HybridSearchResult(
            observation=r.observation,
            bm25_score=r.bm25_score,
            vector_score=r.vector_score,
            combined_score=score,
            session_id=r.session_id,
        )
        for score, r in ranked
    ]
