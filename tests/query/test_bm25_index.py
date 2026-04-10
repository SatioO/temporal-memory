import pytest
from schema.domain import CompressedObservation, ObservationType
from query.bm25_index import BM25Index


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_obs(
    id: str = "obs_1",
    session_id: str = "ses_1",
    title: str = "Edit auth middleware",
    subtitle: str = "JWT validation",
    narrative: str = "Modified the auth middleware to validate JWT tokens",
    facts: list | None = None,
    concepts: list | None = None,
    files: list | None = None,
    **kwargs,
) -> CompressedObservation:
    return CompressedObservation(
        id=id,
        session_id=session_id,
        timestamp="2026-01-01T00:00:00Z",
        type=ObservationType.FILE_EDIT,
        title=title,
        subtitle=subtitle,
        narrative=narrative,
        facts=facts if facts is not None else ["Added token check"],
        concepts=concepts if concepts is not None else ["authentication", "jwt"],
        files=files if files is not None else ["src/middleware/auth.ts"],
        importance=7,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def index() -> BM25Index:
    return BM25Index()


# ---------------------------------------------------------------------------
# Basic state
# ---------------------------------------------------------------------------

def test_starts_empty(index):
    assert index.size == 0


def test_add_increments_size(index):
    index.add(make_obs())
    assert index.size == 1


def test_add_multiple(index):
    index.add(make_obs(id="obs_1"))
    index.add(make_obs(id="obs_2"))
    assert index.size == 2


# ---------------------------------------------------------------------------
# Search — hits
# ---------------------------------------------------------------------------

def test_search_finds_by_title_word(index):
    index.add(make_obs(id="obs_1"))
    results = index.search("auth")
    assert len(results) == 1
    assert results[0]["obs_id"] == "obs_1"


def test_search_returns_session_id(index):
    index.add(make_obs(id="obs_1", session_id="ses_42"))
    results = index.search("auth")
    assert results[0]["session_id"] == "ses_42"


def test_search_finds_by_narrative(index):
    index.add(make_obs(
        id="obs_1",
        title="unrelated title",
        narrative="The agent validated JWT tokens in the middleware",
    ))
    results = index.search("jwt")
    assert any(r["obs_id"] == "obs_1" for r in results)


def test_search_finds_by_concept(index):
    index.add(make_obs(id="obs_1", concepts=["kubernetes", "deployment"]))
    results = index.search("kubernetes")
    assert len(results) == 1


def test_search_finds_by_file(index):
    index.add(make_obs(id="obs_1", title="unrelated", files=["src/auth.ts"]))
    results = index.search("auth")
    assert any(r["obs_id"] == "obs_1" for r in results)


def test_search_finds_by_fact(index):
    index.add(make_obs(id="obs_1", facts=["redis connection added"]))
    results = index.search("redis")
    assert any(r["obs_id"] == "obs_1" for r in results)


# ---------------------------------------------------------------------------
# Search — misses
# ---------------------------------------------------------------------------

def test_search_returns_empty_for_no_match(index):
    index.add(make_obs())
    assert index.search("database") == []


def test_search_returns_empty_for_empty_query(index):
    index.add(make_obs())
    assert index.search("") == []


def test_search_on_empty_index_returns_empty(index):
    assert index.search("auth") == []


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def test_scores_are_positive(index):
    index.add(make_obs(id="obs_1"))
    results = index.search("auth")
    assert results[0]["score"] > 0


def test_exact_match_scores_higher_than_prefix_match(index):
    index.add(make_obs(
        id="obs_exact",
        title="redis cache",
        narrative="Set up redis caching layer",
        concepts=["redis"],
        facts=["Added redis"],
        files=["src/redis.ts"],
    ))
    index.add(make_obs(
        id="obs_prefix",
        title="redistool handler",
        narrative="Set up redistool for ops",
        concepts=["redistool"],
        facts=["Added redistool"],
        files=["src/redistool.ts"],
    ))
    results = index.search("redis")
    exact = next(r for r in results if r["obs_id"] == "obs_exact")
    prefix = next(r for r in results if r["obs_id"] == "obs_prefix")
    assert exact["score"] >= prefix["score"]


def test_multi_term_match_scores_higher_than_single(index):
    index.add(make_obs(
        id="obs_both",
        title="redis cache layer",
        narrative="Set up redis and cache layer",
        concepts=["redis", "cache"],
        facts=["Added caching"],
        files=["src/cache.ts"],
    ))
    index.add(make_obs(
        id="obs_one",
        title="redis connection",
        narrative="Set up redis connection only",
        concepts=["redis"],
        facts=["Added redis"],
        files=["src/redis.ts"],
    ))
    results = index.search("redis cache")
    assert results[0]["obs_id"] == "obs_both"
    assert results[0]["score"] > results[1]["score"]


def test_results_sorted_descending_by_score(index):
    for i in range(5):
        index.add(make_obs(id=f"obs_{i}", title=f"auth feature {i}"))
    results = index.search("auth")
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# Limit
# ---------------------------------------------------------------------------

def test_limit_caps_results(index):
    for i in range(30):
        index.add(make_obs(id=f"obs_{i}", title=f"auth feature {i}"))
    assert len(index.search("auth", limit=5)) == 5


def test_limit_default_is_20(index):
    for i in range(25):
        index.add(make_obs(id=f"obs_{i}", title=f"auth feature {i}"))
    assert len(index.search("auth")) == 20


def test_limit_larger_than_results_returns_all(index):
    index.add(make_obs(id="obs_1"))
    results = index.search("auth", limit=100)
    assert len(results) == 1


# ---------------------------------------------------------------------------
# Upsert
# ---------------------------------------------------------------------------

def test_upsert_does_not_grow_size(index):
    obs = make_obs(id="obs_1")
    index.add(obs)
    index.add(obs)
    assert index.size == 1


def test_upsert_updates_content(index):
    index.add(make_obs(id="obs_1", title="old title about redis"))
    assert len(index.search("redis")) == 1
    assert len(index.search("postgres")) == 0

    index.add(make_obs(
        id="obs_1",
        title="new title about postgres",
        narrative="switched to postgres",
        concepts=["postgres"],
        facts=[],
        files=[],
    ))
    assert index.size == 1
    assert len(index.search("postgres")) == 1
    assert len(index.search("redis")) == 0


# ---------------------------------------------------------------------------
# Clear
# ---------------------------------------------------------------------------

def test_clear_resets_size(index):
    index.add(make_obs())
    index.clear()
    assert index.size == 0


def test_clear_empties_search(index):
    index.add(make_obs())
    index.clear()
    assert index.search("auth") == []


# ---------------------------------------------------------------------------
# Serialize / deserialize
# ---------------------------------------------------------------------------

def test_serialize_returns_string(index):
    index.add(make_obs())
    assert isinstance(index.serialize(), str)


def test_deserialize_empty_string_returns_empty_index(index):
    restored = BM25Index.deserialize("")
    assert restored.size == 0


def test_serialize_deserialize_round_trip(index):
    index.add(make_obs(id="obs_1", title="auth middleware handler"))
    index.add(make_obs(id="obs_2", title="redis cache layer"))

    restored = BM25Index.deserialize(index.serialize())

    assert restored.size == 2
    auth_results = restored.search("auth")
    assert any(r["obs_id"] == "obs_1" for r in auth_results)
    redis_results = restored.search("redis")
    assert any(r["obs_id"] == "obs_2" for r in redis_results)


def test_deserialize_preserves_scores(index):
    index.add(make_obs(id="obs_1"))
    original_score = index.search("auth")[0]["score"]

    restored = BM25Index.deserialize(index.serialize())
    restored_score = restored.search("auth")[0]["score"]

    assert abs(original_score - restored_score) < 1e-6


# ---------------------------------------------------------------------------
# restore_from
# ---------------------------------------------------------------------------

def test_restore_from_copies_entries(index):
    index.add(make_obs(id="obs_1"))
    other = BM25Index()
    other.restore_from(index)

    assert other.size == 1
    assert len(other.search("auth")) == 1


def test_restore_from_is_independent_copy(index):
    index.add(make_obs(id="obs_1"))
    other = BM25Index()
    other.restore_from(index)

    index.clear()

    assert other.size == 1
