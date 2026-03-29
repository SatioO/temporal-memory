from schema.domain import (
    SessionStatus,
    CircuitBreakerState,
    Session,
    ProjectProfile,
    ProjectTopConcepts,
    ProjectTopFiles,
    ContextBlock,
    CircuitBreakerSnapshot,
    EmbeddingProvider,
    MemoryProvider,
)


def test_session_is_pydantic():
    from pydantic import BaseModel
    assert issubclass(Session, BaseModel)


def test_session_instantiation():
    s = Session(
        id="s1",
        project="myproject",
        cwd="/tmp",
        started_at="2026-03-29T00:00:00+00:00",
    )
    assert s.id == "s1"
    assert s.status == SessionStatus.ACTIVE
    assert s.observation_count == 0
    assert s.ended_at is None
    assert s.model is None
    assert s.tags is None


def test_session_model_validate_from_dict():
    # KV store returns plain dicts — model_validate must coerce them
    raw = {
        "id": "s1",
        "project": "proj",
        "cwd": "/tmp",
        "started_at": "2026-03-29T00:00:00+00:00",
        "status": "active",
        "observation_count": 3,
    }
    s = Session.model_validate(raw)
    assert s.id == "s1"
    assert s.status == SessionStatus.ACTIVE
    assert s.observation_count == 3


def test_session_model_dump():
    s = Session(
        id="s1",
        project="proj",
        cwd="/tmp",
        started_at="2026-03-29T00:00:00+00:00",
    )
    d = s.model_dump()
    assert isinstance(d, dict)
    assert d["id"] == "s1"
    assert d["status"] == "active"


def test_session_model_copy_update():
    s = Session(
        id="s1",
        project="proj",
        cwd="/tmp",
        started_at="2026-03-29T00:00:00+00:00",
    )
    s2 = s.model_copy(update={"status": SessionStatus.COMPLETED, "ended_at": "2026-03-29T01:00:00+00:00"})
    assert s2.status == SessionStatus.COMPLETED
    assert s.status == SessionStatus.ACTIVE  # original unchanged


def test_context_block_type_is_field_not_class_var():
    # Bug Fix 1: type must be a proper field annotation, not a class variable
    b = ContextBlock(type="summary", content="hello", tokens=10, recency=1)
    assert b.type == "summary"
    assert b.content == "hello"


def test_project_profile():
    p = ProjectProfile(
        project="proj",
        updated_at="2026-03-29",
        top_concepts=[],
        top_files=[],
        conventions=[],
        common_errors=[],
        recent_activity=[],
        session_count=0,
        total_observations=0,
    )
    assert p.project == "proj"
    assert p.summary is None


def test_circuit_breaker_snapshot():
    snap = CircuitBreakerSnapshot(
        state=CircuitBreakerState.CLOSED,
        failures=0,
        last_failure_at=None,
        opened_at=None,
    )
    assert snap.state == CircuitBreakerState.CLOSED


def test_embedding_provider_is_abc():
    import abc
    assert issubclass(EmbeddingProvider, abc.ABC)


def test_memory_provider_is_abc():
    import abc
    assert issubclass(MemoryProvider, abc.ABC)
