import pytest
import pytest_asyncio
from typing import List, Optional
from unittest.mock import MagicMock

from schema.domain import CompressedObservation, HybridSearchResult, ObservationType, Session, SessionStatus
from state.schema import KV
from functions.smart_search import register_smart_search_fn


# --- Helpers ---

def make_obs(
    id: str = "obs_1",
    session_id: str = "ses_1",
    title: str = "Edit auth handler",
    **kwargs,
) -> CompressedObservation:
    return CompressedObservation(
        id=id,
        session_id=session_id,
        timestamp="2026-02-01T10:00:00Z",
        type=ObservationType.FILE_EDIT,
        title=title,
        facts=[],
        narrative="Modified auth",
        concepts=["auth"],
        files=["src/auth.ts"],
        importance=7,
        **kwargs,
    )


def make_hybrid_result(obs: CompressedObservation, bm25_score: float = 0.8) -> HybridSearchResult:
    return HybridSearchResult(
        observation=obs,
        bm25_score=bm25_score,
        vector_score=0.0,
        combined_score=bm25_score,
        session_id=obs.session_id,
    )


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
        return list(self._store.get(scope, {}).values())


class MockSDK:
    def __init__(self):
        self._functions: dict[str, object] = {}

    def register_function(self, opts: dict, handler) -> None:
        self._functions[opts["id"]] = handler

    def register_trigger(self, *args, **kwargs) -> None:
        pass

    async def trigger(self, id: str, data: dict) -> object:
        fn = self._functions.get(id)
        if fn is None:
            raise KeyError(f"No function registered: {id}")
        return await fn(data)


# --- Fixtures ---

@pytest.fixture
def obs1():
    return make_obs(id="obs_1", session_id="ses_1", title="Auth handler")


@pytest.fixture
def obs2():
    return make_obs(id="obs_2", session_id="ses_1", title="Database setup")


@pytest.fixture
def session():
    return Session(
        id="ses_1",
        project="my-project",
        cwd="/tmp",
        started_at="2026-02-01T00:00:00Z",
        status=SessionStatus.COMPLETED,
        observation_count=2,
    )


@pytest_asyncio.fixture
async def setup(obs1, obs2, session):
    sdk = MockSDK()
    kv = MockKV()

    await kv.set(KV.sessions, "ses_1", session)
    await kv.set(KV.observations("ses_1"), "obs_1", obs1)
    await kv.set(KV.observations("ses_1"), "obs_2", obs2)

    search_results = [
        make_hybrid_result(obs1, bm25_score=0.8),
        make_hybrid_result(obs2, bm25_score=0.3),
    ]

    async def search_fn(_query: str, _limit: int) -> List[HybridSearchResult]:
        return search_results

    register_smart_search_fn(sdk, kv, search_fn)
    return sdk, kv


# --- Tests ---

@pytest.mark.asyncio
async def test_compact_mode_returns_compact_results(setup):
    sdk, _ = setup

    result = await sdk.trigger("mem::smart_search", {"query": "auth"})

    assert result["mode"] == "compact"
    assert len(result["results"]) == 2

    first = result["results"][0]
    assert hasattr(first, "obs_id")


@pytest.mark.asyncio
async def test_compact_result_excludes_narrative(setup):
    sdk, _ = setup

    result = await sdk.trigger("mem::smart_search", {"query": "auth"})

    first = result["results"][0]

    # compact results should not expose the full narrative
    if isinstance(first, dict):
        assert "narrative" not in first
    else:
        assert not hasattr(first, "narrative")


@pytest.mark.asyncio
async def test_expand_mode_returns_full_observation(setup, obs1):
    sdk, _ = setup

    result = await sdk.trigger("mem::smart_search", {"expand_ids": ["obs_1"]})

    assert result["mode"] == "expanded"
    assert len(result["results"]) == 1

    expanded = result["results"][0]
    obs = expanded["observation"] if isinstance(expanded, dict) else expanded.observation
    title = obs["title"] if isinstance(obs, dict) else obs.title
    assert title == "Auth handler"


@pytest.mark.asyncio
async def test_missing_query_returns_error(setup):
    sdk, _ = setup

    result = await sdk.trigger("mem::smart_search", {})

    assert result["mode"] == "compact"
    assert result["error"] == "query is required"
    assert result["results"] == []


@pytest.mark.asyncio
async def test_limit_is_passed_to_search_fn():
    sdk = MockSDK()
    kv = MockKV()

    captured_limit = {}

    async def search_fn(query: str, limit: int) -> List[HybridSearchResult]:
        captured_limit["value"] = limit
        return []

    register_smart_search_fn(sdk, kv, search_fn)

    await sdk.trigger("mem::smart_search", {"query": "auth", "limit": 5})

    assert captured_limit["value"] == 5


@pytest.mark.asyncio
async def test_expand_nonexistent_id_returns_empty(setup):
    sdk, _ = setup

    result = await sdk.trigger("mem::smart_search", {"expand_ids": ["obs_nonexistent"]})

    assert result["mode"] == "expanded"
    assert result["results"] == []


@pytest.mark.asyncio
async def test_empty_expand_ids_falls_through_to_query_error(setup):
    sdk, _ = setup

    # empty expand_ids list with no query → should fall through to query required error
    result = await sdk.trigger("mem::smart_search", {"expand_ids": []})

    assert result["error"] == "query is required"
