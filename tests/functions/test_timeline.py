import pytest
import pytest_asyncio
from typing import Optional

from schema.domain import CompressedObservation, ObservationType, Session, SessionStatus
from state.schema import KV
from functions.timeline import register_timeline_function


# --- Shared mocks (same pattern as test_smart_search.py) ---

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

    async def trigger(self, id: str, data: dict) -> object:
        fn = self._functions.get(id)
        if fn is None:
            raise KeyError(f"No function registered: {id}")
        return await fn(data)


# --- Helpers ---

def make_obs(id: str, timestamp: str, title: str, session_id: str = "ses_1") -> CompressedObservation:
    return CompressedObservation(
        id=id,
        session_id=session_id,
        timestamp=timestamp,
        type=ObservationType.FILE_EDIT,
        title=title,
        facts=[],
        narrative=title,
        concepts=[],
        files=[],
        importance=5,
    )


def make_session(id: str = "ses_1", project: str = "my-project") -> Session:
    return Session(
        id=id,
        project=project,
        cwd="/tmp",
        started_at="2026-02-01T00:00:00Z",
        status=SessionStatus.COMPLETED,
        observation_count=5,
    )


# --- Fixture ---

@pytest_asyncio.fixture
async def setup():
    sdk = MockSDK()
    kv = MockKV()
    register_timeline_function(sdk, kv)

    session = make_session()
    await kv.set(KV.sessions, "ses_1", session)

    await kv.set(KV.observations("ses_1"), "obs_1", make_obs("obs_1", "2026-02-01T10:00:00Z", "First edit"))
    await kv.set(KV.observations("ses_1"), "obs_2", make_obs("obs_2", "2026-02-01T11:00:00Z", "Second edit"))
    await kv.set(KV.observations("ses_1"), "obs_3", make_obs("obs_3", "2026-02-01T12:00:00Z", "Third edit"))
    await kv.set(KV.observations("ses_1"), "obs_4", make_obs("obs_4", "2026-02-01T13:00:00Z", "Fourth edit"))
    await kv.set(KV.observations("ses_1"), "obs_5", make_obs("obs_5", "2026-02-01T14:00:00Z", "Fifth edit"))

    return sdk, kv


# --- Tests ---

@pytest.mark.asyncio
async def test_iso_anchor_returns_surrounding_observations(setup):
    sdk, _ = setup

    result = await sdk.trigger("mem::timeline", {
        "anchor": "2026-02-01T12:00:00Z",
        "before": 2,
        "after": 2,
    })

    assert len(result["entries"]) == 5
    assert result["entries"][0]["observation"]["id"] == "obs_1"
    assert result["entries"][4]["observation"]["id"] == "obs_5"


@pytest.mark.asyncio
async def test_relative_position_is_correct(setup):
    sdk, _ = setup

    result = await sdk.trigger("mem::timeline", {
        "anchor": "2026-02-01T12:00:00Z",
        "before": 2,
        "after": 2,
    })

    positions = [e["relative_position"] for e in result["entries"]]
    assert positions == [-2, -1, 0, 1, 2]


@pytest.mark.asyncio
async def test_respects_before_and_after_limits(setup):
    sdk, _ = setup

    result = await sdk.trigger("mem::timeline", {
        "anchor": "2026-02-01T12:00:00Z",
        "before": 1,
        "after": 1,
    })

    assert len(result["entries"]) == 3
    assert result["entries"][0]["observation"]["id"] == "obs_2"
    assert result["entries"][2]["observation"]["id"] == "obs_4"


@pytest.mark.asyncio
async def test_returns_empty_for_nonexistent_project(setup):
    sdk, _ = setup

    result = await sdk.trigger("mem::timeline", {
        "anchor": "2026-02-01T12:00:00Z",
        "project": "nonexistent-project",
    })

    assert result["entries"] == []


@pytest.mark.asyncio
async def test_keyword_anchor_finds_matching_observation(setup):
    sdk, _ = setup

    result = await sdk.trigger("mem::timeline", {
        "anchor": "Third",
        "before": 1,
        "after": 1,
    })

    assert len(result["entries"]) == 3
    titles = [e["observation"]["title"] for e in result["entries"]]
    assert "Third edit" in titles


@pytest.mark.asyncio
async def test_keyword_anchor_no_match_returns_no_match_reason(setup):
    sdk, _ = setup

    result = await sdk.trigger("mem::timeline", {
        "anchor": "nonexistent keyword",
    })

    assert result["entries"] == []
    assert result["reason"] == "no_match"


@pytest.mark.asyncio
async def test_anchor_index_points_to_correct_entry(setup):
    sdk, _ = setup

    result = await sdk.trigger("mem::timeline", {
        "anchor": "2026-02-01T12:00:00Z",
        "before": 2,
        "after": 2,
    })

    # anchor_index is the position of the anchor within the returned entries slice
    anchor_idx = result["anchor_index"]
    assert result["entries"][anchor_idx]["relative_position"] == 0
