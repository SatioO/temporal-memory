import asyncio
from typing import Optional
from unittest.mock import patch

import numpy as np
import pytest
import pytest_asyncio

from query.bm25_index import BM25Index
from query.index_persistence import IndexPersistence, rebuild_index, DEBOUNCE_S
from query.vector_index import VectorIndex
from schema.domain import CompressedObservation, ObservationType, Session, SessionStatus
from state.schema import KV


# ---------------------------------------------------------------------------
# MockKV
# ---------------------------------------------------------------------------

class MockKV:
    def __init__(self):
        self._store: dict[str, dict[str, object]] = {}

    async def get(self, scope: str, key: str, type=None) -> Optional[object]:
        return self._store.get(scope, {}).get(key)

    async def set(self, scope: str, key: str, value: object) -> object:
        self._store.setdefault(scope, {})[key] = value
        return value

    async def delete(self, scope: str, key: str) -> None:
        self._store.get(scope, {}).pop(key, None)

    async def list(self, scope: str, type=None) -> list:
        raw = list(self._store.get(scope, {}).values())
        if type is not None and hasattr(type, "from_dict"):
            return [type.from_dict(v) if isinstance(v, dict) else v for v in raw]
        return raw


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_obs(
    id: str = "obs_1",
    session_id: str = "ses_1",
    title: str = "Edit auth middleware",
) -> CompressedObservation:
    return CompressedObservation(
        id=id,
        session_id=session_id,
        timestamp="2026-01-01T00:00:00Z",
        type=ObservationType.FILE_EDIT,
        title=title,
        subtitle=None,
        narrative="Modified the auth middleware",
        facts=["Added token check"],
        concepts=["authentication"],
        files=["src/auth.ts"],
        importance=7,
    )


def vec(*values: float) -> np.ndarray:
    return np.array(values, dtype=np.float32)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def kv() -> MockKV:
    return MockKV()


@pytest.fixture
def bm25() -> BM25Index:
    return BM25Index()


@pytest.fixture
def vector() -> VectorIndex:
    return VectorIndex()


# ---------------------------------------------------------------------------
# save / load — BM25
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_save_load_bm25_round_trip(kv, bm25):
    bm25.add(make_obs(id="obs_1", title="auth handler redis"))
    persistence = IndexPersistence(kv, bm25, None)
    await persistence.save()

    bm25_loaded, _ = await persistence.load()
    assert bm25_loaded is not None
    assert bm25_loaded.size == 1
    assert len(bm25_loaded.search("auth")) == 1


@pytest.mark.asyncio
async def test_save_load_bm25_multiple_docs(kv, bm25):
    bm25.add(make_obs(id="obs_1", title="auth middleware"))
    bm25.add(make_obs(id="obs_2", title="redis cache layer"))
    persistence = IndexPersistence(kv, bm25, None)
    await persistence.save()

    bm25_loaded, _ = await persistence.load()
    assert bm25_loaded.size == 2


# ---------------------------------------------------------------------------
# save / load — vector
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_save_load_vector_round_trip(kv, bm25, vector):
    vector.add("obs_1", "ses_1", vec(1, 0, 0))
    persistence = IndexPersistence(kv, bm25, vector)
    await persistence.save()

    _, vector_loaded = await persistence.load()
    assert vector_loaded is not None
    assert vector_loaded.size == 1
    results = vector_loaded.search(vec(1, 0, 0), limit=1)
    assert results[0]["obs_id"] == "obs_1"


@pytest.mark.asyncio
async def test_empty_vector_index_not_saved(kv, bm25, vector):
    # vector.size == 0 → should not write vectors key
    persistence = IndexPersistence(kv, bm25, vector)
    await persistence.save()

    _, vector_loaded = await persistence.load()
    assert vector_loaded is None


# ---------------------------------------------------------------------------
# load — nothing saved
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_load_returns_none_when_nothing_saved(kv, bm25):
    persistence = IndexPersistence(kv, bm25, None)
    bm25_loaded, vector_loaded = await persistence.load()
    assert bm25_loaded is None
    assert vector_loaded is None


@pytest.mark.asyncio
async def test_load_bm25_none_when_only_vectors_saved(kv, bm25, vector):
    vector.add("obs_1", "ses_1", vec(1, 0, 0))
    persistence = IndexPersistence(kv, bm25, vector)
    # manually save only the vector key to simulate partial state
    await kv.set(KV.bm25_index, "vectors", vector.serialize())

    bm25_loaded, vector_loaded = await persistence.load()
    assert bm25_loaded is None
    assert vector_loaded is not None


# ---------------------------------------------------------------------------
# schedule_save — debounce
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_schedule_save_saves_after_debounce(kv, bm25):
    bm25.add(make_obs(id="obs_1"))
    persistence = IndexPersistence(kv, bm25, None)

    with patch("query.index_persistence.DEBOUNCE_S", 0.02):
        persistence.schedule_save()
        # Before the debounce fires, nothing is saved
        assert await kv.get(KV.bm25_index, "data", str) is None
        await asyncio.sleep(0.05)

    saved = await kv.get(KV.bm25_index, "data", str)
    assert saved is not None


@pytest.mark.asyncio
async def test_schedule_save_debounces_multiple_calls(kv, bm25):
    bm25.add(make_obs(id="obs_1"))
    persistence = IndexPersistence(kv, bm25, None)

    save_count = 0
    original_save = persistence.save

    async def counting_save():
        nonlocal save_count
        save_count += 1
        await original_save()

    persistence.save = counting_save  # type: ignore[method-assign]

    with patch("query.index_persistence.DEBOUNCE_S", 0.02):
        persistence.schedule_save()
        persistence.schedule_save()
        persistence.schedule_save()
        await asyncio.sleep(0.05)

    assert save_count == 1


# ---------------------------------------------------------------------------
# stop
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stop_cancels_pending_save(kv, bm25):
    bm25.add(make_obs(id="obs_1"))
    persistence = IndexPersistence(kv, bm25, None)

    with patch("query.index_persistence.DEBOUNCE_S", 0.02):
        persistence.schedule_save()
        persistence.stop()
        await asyncio.sleep(0.05)

    # Save should not have been written
    assert await kv.get(KV.bm25_index, "data", str) is None


@pytest.mark.asyncio
async def test_stop_is_idempotent_when_no_task(kv, bm25):
    persistence = IndexPersistence(kv, bm25, None)
    persistence.stop()  # should not raise
    persistence.stop()


# ---------------------------------------------------------------------------
# save — immediate flush cancels debounce
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_save_cancels_pending_debounce(kv, bm25):
    bm25.add(make_obs(id="obs_1"))
    persistence = IndexPersistence(kv, bm25, None)

    with patch("query.index_persistence.DEBOUNCE_S", 10.0):
        persistence.schedule_save()
        await persistence.save()  # immediate flush

    # After save, the task should be gone (not double-fire)
    assert persistence._task is None


# ---------------------------------------------------------------------------
# rebuild_index
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_rebuild_index_loads_observations(kv, bm25):
    session = Session(
        id="ses_1", project="proj", cwd="/tmp",
        started_at="2026-01-01T00:00:00Z",
        status=SessionStatus.ACTIVE, observation_count=2,
    )
    await kv.set(KV.sessions, "ses_1", session.to_dict())
    await kv.set(KV.observations("ses_1"), "obs_1", make_obs(id="obs_1", title="auth handler").to_dict())
    await kv.set(KV.observations("ses_1"), "obs_2", CompressedObservation(
        id="obs_2", session_id="ses_1", timestamp="2026-01-01T00:00:00Z",
        type=ObservationType.FILE_EDIT, title="redis cache", subtitle=None,
        narrative="Set up redis", facts=[], concepts=["redis"],
        files=["src/redis.ts"], importance=5,
    ).to_dict())

    count = await rebuild_index(kv, bm25)

    assert count == 2
    assert bm25.size == 2
    assert len(bm25.search("auth")) == 1
    assert len(bm25.search("redis")) == 1


@pytest.mark.asyncio
async def test_rebuild_index_returns_zero_for_empty_kv(kv, bm25):
    count = await rebuild_index(kv, bm25)
    assert count == 0
    assert bm25.size == 0


@pytest.mark.asyncio
async def test_rebuild_index_spans_multiple_sessions(kv, bm25):
    for i in range(3):
        session = Session(
            id=f"ses_{i}", project="proj", cwd="/tmp",
            started_at="2026-01-01T00:00:00Z",
            status=SessionStatus.ACTIVE, observation_count=1,
        )
        await kv.set(KV.sessions, f"ses_{i}", session.to_dict())
        await kv.set(
            KV.observations(f"ses_{i}"), f"obs_{i}",
            make_obs(id=f"obs_{i}", session_id=f"ses_{i}").to_dict(),
        )

    count = await rebuild_index(kv, bm25)
    assert count == 3
    assert bm25.size == 3
