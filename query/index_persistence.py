import asyncio
from typing import Optional, Tuple

from query.bm25_index import BM25Index
from query.vector_index import VectorIndex
from schema import CompressedObservation, Session
from state.kv import StateKV
from state.schema import KV
from logger import get_logger

logger = get_logger("index_persistence")

DEBOUNCE_S = 5.0


class IndexPersistence:
    def __init__(
        self,
        bm25: BM25Index,
        vector: Optional[VectorIndex],
        kv: StateKV,
    ):
        self._bm25 = bm25
        self._vector = vector
        self._kv = kv
        self._task: Optional[asyncio.Task] = None

    def schedule_save(self) -> None:
        """Debounced save — resets the 5s timer on every call."""
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = asyncio.get_running_loop().create_task(self._delayed_save())

    async def _delayed_save(self) -> None:
        await asyncio.sleep(DEBOUNCE_S)
        await self.save()

    async def save(self) -> None:
        """Flush both indexes to KV immediately, cancelling any pending debounce."""
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None

        try:
            await self._kv.set(KV.bm25_index, "data", self._bm25.serialize())
        except Exception as e:
            logger.warning("failed to save BM25 index: %s", e)

        if self._vector and self._vector.size > 0:
            try:
                await self._kv.set(KV.vector_index, "data", self._vector.serialize())
            except Exception as e:
                logger.warning("failed to save vector index: %s", e)

        logger.info(
            "index persisted (bm25=%d docs, vectors=%d)",
            self._bm25.size,
            self._vector.size if self._vector else 0,
        )

    async def load(self) -> Tuple[Optional[BM25Index], Optional[VectorIndex]]:
        """Load both indexes from KV. Returns (None, None) on miss."""
        bm25: Optional[BM25Index] = None
        vector: Optional[VectorIndex] = None

        try:
            data = await self._kv.get(KV.bm25_index, "data", str)
            if data is not None:
                bm25 = BM25Index.deserialize(data)
        except Exception as e:
            logger.warning("failed to load BM25 index: %s", e)

        try:
            data = await self._kv.get(KV.vector_index, "data", str)
            if data is not None:
                vector = VectorIndex.deserialize(data)
        except Exception as e:
            logger.warning("failed to load vector index: %s", e)

        return bm25, vector

    def stop(self) -> None:
        """Cancel any pending debounced save."""
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None


async def rebuild_index(kv: StateKV, bm25: BM25Index) -> int:
    """Cold-start rebuild: re-index all persisted observations into BM25.
    Vector index is not rebuilt here — re-embedding all docs is too expensive
    and is handled incrementally via compress.py on next ingest.
    Returns the number of documents indexed."""
    count = 0
    try:
        sessions = await kv.list(KV.sessions, Session)
        for session in sessions:
            observations = await kv.list(KV.observations(session.id), CompressedObservation)
            for obs in observations:
                bm25.add(obs)
                count += 1
    except Exception as e:
        logger.warning("rebuild_index error: %s", e)
    return count
