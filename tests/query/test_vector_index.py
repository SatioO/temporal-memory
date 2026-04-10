import pytest
import numpy as np
from query.vector_index import VectorIndex


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def index() -> VectorIndex:
    return VectorIndex()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def vec(*values: float) -> np.ndarray:
    return np.array(values, dtype=np.float32)


# ---------------------------------------------------------------------------
# Basic state
# ---------------------------------------------------------------------------

def test_starts_empty(index):
    assert index.size == 0


def test_add_increments_size(index):
    index.add("obs_1", "ses_1", vec(0.1, 0.2, 0.3))
    assert index.size == 1


def test_add_multiple(index):
    index.add("obs_1", "ses_1", vec(1, 0, 0))
    index.add("obs_2", "ses_1", vec(0, 1, 0))
    assert index.size == 2


def test_remove_decrements_size(index):
    index.add("obs_1", "ses_1", vec(0.1, 0.2, 0.3))
    index.remove("obs_1")
    assert index.size == 0


def test_remove_nonexistent_is_noop(index):
    index.add("obs_1", "ses_1", vec(1, 0, 0))
    index.remove("obs_missing")
    assert index.size == 1


# ---------------------------------------------------------------------------
# Search — empty
# ---------------------------------------------------------------------------

def test_search_empty_index_returns_empty(index):
    assert index.search(vec(1, 0, 0)) == []


def test_search_after_remove_all_returns_empty(index):
    index.add("obs_1", "ses_1", vec(1, 0, 0))
    index.remove("obs_1")
    assert index.search(vec(1, 0, 0)) == []


# ---------------------------------------------------------------------------
# Search — cosine similarity ordering
# ---------------------------------------------------------------------------

def test_identical_vector_scores_one(index):
    index.add("obs_1", "ses_1", vec(1, 0, 0))
    results = index.search(vec(1, 0, 0))
    assert pytest.approx(results[0]["score"], abs=1e-5) == 1.0


def test_orthogonal_vector_scores_zero(index):
    index.add("obs_1", "ses_1", vec(1, 0, 0))
    results = index.search(vec(0, 1, 0))
    assert pytest.approx(results[0]["score"], abs=1e-5) == 0.0


def test_results_sorted_by_cosine_similarity(index):
    index.add("obs_close",  "ses_1", vec(1, 0, 0))
    index.add("obs_far",    "ses_1", vec(0, 1, 0))
    index.add("obs_medium", "ses_1", vec(0.7, 0.7, 0))

    results = index.search(vec(1, 0, 0))

    assert results[0]["obs_id"] == "obs_close"
    assert pytest.approx(results[0]["score"], abs=1e-5) == 1.0
    assert results[1]["obs_id"] == "obs_medium"
    assert results[2]["obs_id"] == "obs_far"
    assert pytest.approx(results[2]["score"], abs=1e-5) == 0.0


def test_scores_are_between_neg1_and_1(index):
    for i in range(5):
        index.add(f"obs_{i}", "ses_1", vec(float(i), float(i + 1), 0.5))
    results = index.search(vec(1, 1, 0))
    for r in results:
        assert -1.0 <= r["score"] <= 1.0 + 1e-6


# ---------------------------------------------------------------------------
# Search — result shape
# ---------------------------------------------------------------------------

def test_result_contains_obs_id_session_id_score(index):
    index.add("obs_1", "ses_42", vec(1, 0, 0))
    result = index.search(vec(1, 0, 0))[0]
    assert result["obs_id"] == "obs_1"
    assert result["session_id"] == "ses_42"
    assert isinstance(result["score"], float)


# ---------------------------------------------------------------------------
# Limit
# ---------------------------------------------------------------------------

def test_limit_caps_results(index):
    for i in range(10):
        index.add(f"obs_{i}", "ses_1", vec(float(i) * 0.1, 0.5, 0.5))
    results = index.search(vec(0.9, 0.5, 0.5), limit=3)
    assert len(results) == 3


def test_limit_default_is_20(index):
    for i in range(25):
        index.add(f"obs_{i}", "ses_1", vec(float(i) * 0.01, 1.0, 0.0))
    assert len(index.search(vec(0.0, 1.0, 0.0))) == 20


def test_limit_larger_than_size_returns_all(index):
    index.add("obs_1", "ses_1", vec(1, 0, 0))
    index.add("obs_2", "ses_1", vec(0, 1, 0))
    assert len(index.search(vec(1, 0, 0), limit=100)) == 2


# ---------------------------------------------------------------------------
# Zero / degenerate vectors
# ---------------------------------------------------------------------------

def test_zero_query_vector_returns_zero_scores(index):
    index.add("obs_1", "ses_1", vec(1, 0, 0))
    results = index.search(vec(0, 0, 0))
    assert results[0]["score"] == 0.0


def test_zero_stored_vector_returns_zero_score(index):
    index.add("obs_zero", "ses_1", vec(0, 0, 0))
    results = index.search(vec(1, 0, 0))
    assert results[0]["score"] == 0.0


# ---------------------------------------------------------------------------
# Clear
# ---------------------------------------------------------------------------

def test_clear_resets_size(index):
    index.add("obs_1", "ses_1", vec(1, 0, 0))
    index.add("obs_2", "ses_1", vec(0, 1, 0))
    index.clear()
    assert index.size == 0


def test_clear_empties_search(index):
    index.add("obs_1", "ses_1", vec(1, 0, 0))
    index.clear()
    assert index.search(vec(1, 0, 0)) == []


# ---------------------------------------------------------------------------
# Serialize / deserialize
# ---------------------------------------------------------------------------

def test_serialize_returns_string(index):
    index.add("obs_1", "ses_1", vec(0.1, 0.2, 0.3))
    assert isinstance(index.serialize(), str)


def test_deserialize_empty_string_returns_empty_index():
    restored = VectorIndex.deserialize("")
    assert restored.size == 0


def test_deserialize_invalid_json_returns_empty_index():
    restored = VectorIndex.deserialize("not json at all")
    assert restored.size == 0


def test_serialize_deserialize_round_trip_preserves_size(index):
    index.add("obs_1", "ses_1", vec(0.1, 0.2, 0.3))
    index.add("obs_2", "ses_2", vec(0.4, 0.5, 0.6))

    restored = VectorIndex.deserialize(index.serialize())
    assert restored.size == 2


def test_serialize_deserialize_round_trip_preserves_session_id(index):
    index.add("obs_1", "ses_99", vec(1, 0, 0))

    restored = VectorIndex.deserialize(index.serialize())
    results = restored.search(vec(1, 0, 0), limit=1)
    assert results[0]["obs_id"] == "obs_1"
    assert results[0]["session_id"] == "ses_99"


def test_serialize_deserialize_preserves_search_order(index):
    index.add("obs_close",  "ses_1", vec(1, 0, 0))
    index.add("obs_far",    "ses_1", vec(0, 1, 0))
    index.add("obs_medium", "ses_1", vec(0.7, 0.7, 0))

    restored = VectorIndex.deserialize(index.serialize())
    results = restored.search(vec(1, 0, 0))

    assert results[0]["obs_id"] == "obs_close"
    assert results[1]["obs_id"] == "obs_medium"
    assert results[2]["obs_id"] == "obs_far"


# ---------------------------------------------------------------------------
# restore_from
# ---------------------------------------------------------------------------

def test_restore_from_copies_entries(index):
    index.add("obs_1", "ses_1", vec(1, 0, 0))
    other = VectorIndex()
    other.restore_from(index)

    assert other.size == 1
    assert other.search(vec(1, 0, 0))[0]["obs_id"] == "obs_1"


def test_restore_from_is_independent_copy(index):
    index.add("obs_1", "ses_1", vec(1, 0, 0))
    other = VectorIndex()
    other.restore_from(index)

    index.clear()

    assert other.size == 1
