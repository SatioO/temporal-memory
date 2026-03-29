# Schema Standardization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the mixed model definition styles in `schema.py` with a four-layer architecture: Pydantic BaseModel at system boundaries (HTTP + KV), `@dataclass` internally; split into `schema/domain.py` and `schema/config.py`.

**Architecture:** Create a `schema/` package with `domain.py` (L2 Pydantic models + Enums + ABCs) and `config.py` (L4 @dataclass models). A re-exporting `__init__.py` keeps all existing `from schema import ...` calls working unchanged. Fix 6 bugs discovered during design — apply in order, as Bug Fix 5 depends on Bug Fix 4.

**Tech Stack:** Python 3.13, Pydantic v2 (`BaseModel`, `model_validate`, `model_copy`, `model_dump`), `dataclasses`, `pytest`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `schema/` | Create (directory) | New package replacing `schema.py` |
| `schema/__init__.py` | Create | Re-exports everything from `domain.py` and `config.py` |
| `schema/domain.py` | Create | L2 Pydantic models + Enums + ABCs |
| `schema/config.py` | Create | L4 @dataclass models + `ProviderType` alias |
| `schema.py` | Delete | Replaced by `schema/` package |
| `functions/context.py` | Modify | Convert TypedDict → @dataclass; fix dict-style access; fix Bug Fix 3 |
| `triggers/api.py` | Modify | Fix Bug Fixes 5 & 6 |
| `tests/test_schema_domain.py` | Create | Tests for L2 Pydantic models |
| `tests/test_schema_config.py` | Create | Tests for L4 @dataclass models |
| `tests/test_context.py` | Create | Tests for ContextHandlerParams / ContextResponse |
| `tests/test_api_triggers.py` | Create | Tests for handle_session_end and SessionStartPayload |

---

## Task 1: Add pytest

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add pytest dev dependency**

```toml
[project]
name = "graphmind"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "anthropic>=0.86.0",
    "iii-sdk>=0.10.0",
    "pydantic>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
]
```

- [ ] **Step 2: Install**

```bash
uv sync --extra dev
```

Expected: resolves and installs pytest.

- [ ] **Step 3: Create tests directory with empty conftest**

Create `tests/__init__.py` (empty file) and `tests/conftest.py` (empty file).

- [ ] **Step 4: Verify pytest runs**

```bash
uv run pytest tests/ -v
```

Expected: `no tests ran` — not an error, just empty.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock tests/
git commit -m "chore: add pytest dev dependency"
```

---

## Task 2: Write failing tests for `schema/config.py`

**Files:**
- Create: `tests/test_schema_config.py`

The tests import from `schema.config` which doesn't exist yet — they must fail with `ModuleNotFoundError`.

- [ ] **Step 1: Write the tests**

Create `tests/test_schema_config.py`:

```python
from schema.config import (
    ProviderType,
    ProviderConfig,
    AgentMemoryConfig,
    EmbeddingConfig,
    FallbackConfig,
    TeamConfig,
    CloudBridgeConfig,
    OtelConfigSettings,
)


def test_provider_config_is_dataclass():
    cfg = ProviderConfig(provider="anthropic", model="claude-3-5-sonnet-20241022", max_tokens=8096)
    assert cfg.provider == "anthropic"
    assert cfg.model == "claude-3-5-sonnet-20241022"
    assert cfg.max_tokens == 8096


def test_embedding_config_provider_is_not_quoted():
    # Bug Fix 2: Optional[str] not Optional["str"]
    cfg = EmbeddingConfig(provider=None, bm25_weight=0.5, vector_weight=0.5)
    assert cfg.provider is None
    cfg2 = EmbeddingConfig(provider="openai", bm25_weight=0.3, vector_weight=0.7)
    assert cfg2.provider == "openai"


def test_fallback_config_providers_list():
    cfg = FallbackConfig(providers=["anthropic", "openrouter"])
    assert cfg.providers == ["anthropic", "openrouter"]


def test_team_config():
    cfg = TeamConfig(team_id="t1", user_id="u1", mode="shared")
    assert cfg.mode == "shared"


def test_cloud_bridge_config():
    cfg = CloudBridgeConfig(
        enabled=True,
        project_path="/tmp/proj",
        memory_file_path="/tmp/mem.md",
        line_budget=200,
    )
    assert cfg.enabled is True


def test_otel_config_defaults():
    cfg = OtelConfigSettings()
    assert cfg.service_name == "graphmind"
    assert cfg.metrics_export_interval_ms == 30000
```

- [ ] **Step 2: Run to confirm they fail**

```bash
uv run pytest tests/test_schema_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'schema.config'`

---

## Task 3: Write failing tests for `schema/domain.py`

**Files:**
- Create: `tests/test_schema_domain.py`

- [ ] **Step 1: Write the tests**

Create `tests/test_schema_domain.py`:

```python
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
```

- [ ] **Step 2: Run to confirm they fail**

```bash
uv run pytest tests/test_schema_domain.py -v
```

Expected: `ModuleNotFoundError: No module named 'schema.domain'`

---

## Task 4: Create `schema/` package

This task creates `schema/config.py`, `schema/domain.py`, and `schema/__init__.py`, then deletes `schema.py`. Python's package resolution means `schema/` takes precedence over `schema.py` once `schema/__init__.py` exists — but to avoid confusion, delete `schema.py` in the same commit.

**Files:**
- Create: `schema/__init__.py`
- Create: `schema/domain.py`
- Create: `schema/config.py`
- Delete: `schema.py`

- [ ] **Step 1: Create `schema/config.py`**

```python
from dataclasses import dataclass, field
from typing import List, Literal, Optional

ProviderType = Literal["agent-sdk", "anthropic", "gemini", "openrouter"]


@dataclass
class ProviderConfig:
    provider: ProviderType
    model: str
    max_tokens: int


@dataclass
class AgentMemoryConfig:
    engine_url: str
    rest_port: int
    streams_port: int
    provider: str
    token_budget: int
    max_observations_per_session: int
    compression_model: str
    data_dir: str


@dataclass
class EmbeddingConfig:
    provider: Optional[str]
    bm25_weight: float
    vector_weight: float


@dataclass
class FallbackConfig:
    providers: List[ProviderType]


@dataclass
class TeamConfig:
    team_id: str
    user_id: str
    mode: Literal["shared", "private"]


@dataclass
class CloudBridgeConfig:
    enabled: bool
    project_path: str
    memory_file_path: str
    line_budget: int


@dataclass
class OtelConfigSettings:
    service_name: str = "graphmind"
    service_version: str = "0.6.0"
    metrics_export_interval_ms: int = 30000
```

- [ ] **Step 2: Create `schema/domain.py`**

```python
from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel


class SessionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class CircuitBreakerState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half-open"


class Session(BaseModel):
    id: str
    project: str
    cwd: str
    started_at: str
    ended_at: Optional[str] = None
    status: SessionStatus = SessionStatus.ACTIVE
    observation_count: int = 0
    model: Optional[str] = None
    tags: Optional[str] = None


class ProjectTopConcepts(BaseModel):
    concept: str
    frequency: str


class ProjectTopFiles(BaseModel):
    file: str
    frequency: str


class ProjectProfile(BaseModel):
    project: str
    updated_at: str
    top_concepts: List[ProjectTopConcepts]
    top_files: List[ProjectTopFiles]
    conventions: List[str]
    common_errors: List[str]
    recent_activity: List[str]
    session_count: int
    total_observations: int
    summary: Optional[str] = None


class ContextBlock(BaseModel):
    type: Literal["summary", "observation", "memory"]
    content: str
    tokens: int
    recency: int


class CircuitBreakerSnapshot(BaseModel):
    state: CircuitBreakerState
    failures: int
    last_failure_at: Optional[float]
    opened_at: Optional[float]


class EmbeddingProvider(ABC):
    name: str
    dimensions: int

    @abstractmethod
    async def embed(self, text: str):
        pass

    @abstractmethod
    async def embed_batch(self, texts: List[str]):
        pass


class MemoryProvider(ABC):
    name: str

    @abstractmethod
    async def compress(self, system_prompt: str, user_prompt: str) -> str:
        pass

    @abstractmethod
    async def summarize(self, system_prompt: str, user_prompt: str) -> str:
        pass
```

- [ ] **Step 3: Create `schema/__init__.py`**

```python
from schema.config import (
    AgentMemoryConfig,
    CloudBridgeConfig,
    EmbeddingConfig,
    FallbackConfig,
    OtelConfigSettings,
    ProviderConfig,
    ProviderType,
    TeamConfig,
)
from schema.domain import (
    CircuitBreakerSnapshot,
    CircuitBreakerState,
    ContextBlock,
    EmbeddingProvider,
    MemoryProvider,
    ProjectProfile,
    ProjectTopConcepts,
    ProjectTopFiles,
    Session,
    SessionStatus,
)

__all__ = [
    # domain
    "CircuitBreakerSnapshot",
    "CircuitBreakerState",
    "ContextBlock",
    "EmbeddingProvider",
    "MemoryProvider",
    "ProjectProfile",
    "ProjectTopConcepts",
    "ProjectTopFiles",
    "Session",
    "SessionStatus",
    # config
    "AgentMemoryConfig",
    "CloudBridgeConfig",
    "EmbeddingConfig",
    "FallbackConfig",
    "OtelConfigSettings",
    "ProviderConfig",
    "ProviderType",
    "TeamConfig",
]
```

- [ ] **Step 4: Delete `schema.py`**

```bash
git rm schema.py
```

- [ ] **Step 5: Run all schema tests**

```bash
uv run pytest tests/test_schema_config.py tests/test_schema_domain.py -v
```

Expected: all pass.

- [ ] **Step 6: Verify existing `from schema import ...` still works**

```bash
uv run python -c "from schema import Session, SessionStatus, ProviderConfig, EmbeddingConfig, MemoryProvider, CircuitBreakerSnapshot; print('OK')"
```

Expected: `OK`

- [ ] **Step 6b: Verify `config.py` (root) still loads cleanly**

```bash
uv run python -c "import config; print('config OK')"
```

Expected: `config OK`. Note: `config.py` imports from `schema` — this verifies the re-export path is complete. If this fails, check that all symbols imported in `config.py` line 7 are present in `schema/__init__.py`.

- [ ] **Step 7: Commit**

```bash
git add schema/ tests/test_schema_config.py tests/test_schema_domain.py
git commit -m "refactor: split schema.py into schema/domain.py and schema/config.py"
```

---

## Task 5: Fix `functions/context.py` (Bug Fix 3)

Convert `ContextHandlerParams` and `ContextResponse` from `TypedDict` to `@dataclass`, fix all dict-style accesses on `data`, and fix the return statement.

**Files:**
- Create: `tests/test_context.py`
- Modify: `functions/context.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_context.py`:

```python
from dataclasses import fields
from functions.context import ContextHandlerParams, ContextResponse


def test_context_handler_params_is_dataclass():
    params = ContextHandlerParams(session_id="s1", project="proj")
    assert params.session_id == "s1"
    assert params.project == "proj"
    assert params.budget is None  # Optional with default None


def test_context_handler_params_with_budget():
    params = ContextHandlerParams(session_id="s1", project="proj", budget=500)
    assert params.budget == 500


def test_context_handler_params_attribute_not_dict():
    params = ContextHandlerParams(session_id="s1", project="proj")
    # Must use attribute access, not dict access
    assert params.project == "proj"
    assert params.session_id == "s1"


def test_context_response_is_dataclass():
    resp = ContextResponse(context="some context")
    assert resp.context == "some context"
```

- [ ] **Step 2: Run to confirm they fail**

```bash
uv run pytest tests/test_context.py -v
```

Expected: `TypeError: ContextHandlerParams() takes no arguments` — calling a TypedDict with keyword args raises TypeError, not ImportError. The tests will fail before reaching the assertions.

- [ ] **Step 3: Rewrite `functions/context.py`**

```python
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional
from iii import IIIClient

from schema import ContextBlock, ProjectProfile, Session
from state.kv import StateKV
from state.schema import KV


@dataclass
class ContextResponse:
    context: str


@dataclass
class ContextHandlerParams:
    session_id: str
    project: str
    budget: Optional[int] = None


def register_context_function(sdk: IIIClient, kv: StateKV, token_budget: int) -> None:
    async def handle_context(data: ContextHandlerParams):
        budget = data.budget if data.budget is not None else token_budget
        blocks: List[ContextBlock] = []
        print(f"recieved: {data}")

        profile: ProjectProfile = await kv.get(KV.profiles, data.project)
        if profile is not None:
            print(f"[graphmind] found profile: {profile}")

        # TODO: This needs more rethinking as it is getting all the sessions from cache than getting project specific sessions
        raw_sessions = await kv.list(KV.sessions)
        all_sessions: List[Session] = [Session.model_validate(s) for s in raw_sessions] if raw_sessions else []
        print(f"[graphmind] found sessions: {all_sessions}")

        sessions = sorted(
            [
                s for s in all_sessions
                if s.project == data.project and s.id != data.session_id
            ],
            key=lambda s: datetime.fromisoformat(s.started_at),
            reverse=True
        )[:10]

        print(f"[graphmind] filtered sessions: {sessions}")

        return ContextResponse(context="12345")

    sdk.register_function({"id": "mem::context"}, handle_context)
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_context.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add functions/context.py tests/test_context.py
git commit -m "refactor: convert ContextHandlerParams and ContextResponse from TypedDict to dataclass"
```

---

## Task 6: Fix `triggers/api.py` (Bug Fixes 5 & 6)

Fix `SessionStartPayload` missing `model` field (Bug Fix 6), `handle_session_end` null-check ordering / dict mutation / wrong response shape (Bug Fix 5), and add `model_dump()` to the KV write in `handle_session_start`.

**Files:**
- Create: `tests/test_api_triggers.py`
- Modify: `triggers/api.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_api_triggers.py`:

```python
from triggers.api import SessionStartPayload, SessionEndPayload, SessionEndResponse, SessionStartResponse
from schema import Session, SessionStatus


def test_session_start_payload_has_model_field():
    # Bug Fix 6: model field must exist on SessionStartPayload
    payload = SessionStartPayload(session_id="s1", project="proj", cwd="/tmp", model="claude-sonnet-4-6")
    assert payload.model == "claude-sonnet-4-6"


def test_session_start_payload_model_optional():
    payload = SessionStartPayload(session_id="s1", project="proj", cwd="/tmp")
    assert payload.model is None


def test_session_end_response_shape():
    # Bug Fix 5: SessionEndResponse only has success field
    resp = SessionEndResponse(success=True)
    assert resp.success is True
    assert not hasattr(resp, "session")


def test_session_start_response_shape():
    s = Session(id="s1", project="proj", cwd="/tmp", started_at="2026-03-29T00:00:00+00:00")
    resp = SessionStartResponse(session=s)
    assert resp.session.id == "s1"
```

- [ ] **Step 2: Run to confirm Bug Fix 6 test fails**

```bash
uv run pytest tests/test_api_triggers.py -v
```

Expected: `test_session_start_payload_has_model_field` fails with `ValidationError` (field not found).

- [ ] **Step 3: Update `triggers/api.py`**

Apply all three changes: add `model` to `SessionStartPayload`, fix `handle_session_start` KV write with `model_dump()`, rewrite `handle_session_end` with null-check-first + `model_validate` + `model_copy` + correct return shape.

```python
from datetime import datetime, timezone
from typing import Optional, Union
from iii import ApiRequest, IIIClient, RegisterFunctionInput, RegisterTriggerInput, Logger, ApiResponse, TriggerRequest
from pydantic import BaseModel

from functions.context import ContextHandlerParams
from schema import Session, SessionStatus
from providers.resilient import ResilientProvider
from state.kv import StateKV
from state.schema import KV


class SessionStartPayload(BaseModel):
    session_id: str
    project: str
    cwd: str
    model: Optional[str] = None


class SessionStartResponse(BaseModel):
    session: Session


class SessionEndPayload(BaseModel):
    session_id: str


class SessionEndResponse(BaseModel):
    success: bool


def register_api_triggers(
    sdk: IIIClient,
    kv: StateKV,
    secret: Optional[str] = None,
    provider: Optional[Union[ResilientProvider, dict]] = None
):
    async def handle_session_start(req: ApiRequest[SessionStartPayload]) -> ApiResponse[SessionStartResponse]:
        logger = Logger()

        parsed_req = ApiRequest[SessionStartPayload](**req)
        payload = SessionStartPayload(**parsed_req.body)

        session = Session(
            id=payload.session_id,
            project=payload.project,
            cwd=payload.cwd,
            model=payload.model,
            started_at=datetime.now(timezone.utc).isoformat(),
            status=SessionStatus.ACTIVE,
            observation_count=0
        )

        await kv.set(KV.sessions, payload.session_id, session.model_dump())
        logger.debug(f"[graphmind] Created session: {payload.session_id}")

        context_response = await sdk.trigger_async(
            TriggerRequest(
                function_id="mem::context",
                payload=ContextHandlerParams(
                    session_id=payload.session_id,
                    project=payload.project
                )
            )
        )

        print(context_response)

        # parsed = ContextResponse(**context_response)

        return ApiResponse(
            statusCode=200,
            body=SessionStartResponse(session=session).model_dump(),
        )

    async def handle_session_end(req: ApiRequest[SessionEndPayload]) -> ApiResponse[SessionEndResponse]:
        parsed_req = ApiRequest[SessionEndPayload](**req)
        body = SessionEndPayload(**parsed_req.body)

        raw = await kv.get(KV.sessions, body.session_id)
        if raw is None:
            return ApiResponse(statusCode=404, body={"success": False})

        session = Session.model_validate(raw)
        modified_session = session.model_copy(update={
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "status": SessionStatus.COMPLETED
        })

        await kv.set(KV.sessions, body.session_id, modified_session.model_dump())

        return ApiResponse(statusCode=200, body={"success": True})

    sdk.register_function(
        RegisterFunctionInput(id="api::session::start"),
        handle_session_start,
    )

    sdk.register_trigger(
        RegisterTriggerInput(
            type="http",
            function_id="api::session::start",
            config={
                "api_path": "graphmind/session/start",
                "http_method": "POST"
            }
        )
    )

    sdk.register_function(
        RegisterFunctionInput(id="api::session::end"),
        handle_session_end,
    )

    sdk.register_trigger(
        RegisterTriggerInput(
            type="http",
            function_id="api::session::end",
            config={
                "api_path": "graphmind/session/end",
                "http_method": "POST"
            }
        )
    )
```

- [ ] **Step 4: Run all tests**

```bash
uv run pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 5: Audit for any remaining `from schema import` that reference the old flat module path**

```bash
grep -r "from schema import" --include="*.py" .
```

Verify all import sites still work (they should, since `schema/__init__.py` re-exports everything).

- [ ] **Step 6: Commit**

```bash
git add triggers/api.py tests/test_api_triggers.py
git commit -m "fix: add model field to SessionStartPayload, fix handle_session_end null-check and response shape"
```

---

## Final Verification

- [ ] Run full test suite one last time:

```bash
uv run pytest tests/ -v
```

Expected: all tests pass, no warnings about missing imports.

- [ ] Verify the package imports a clean module tree:

```bash
uv run python -c "
from schema import Session, SessionStatus, ContextBlock, ProjectProfile
from schema import ProviderConfig, EmbeddingConfig, TeamConfig
from schema import MemoryProvider, EmbeddingProvider
print('All imports OK')
"
```

Expected: `All imports OK`
