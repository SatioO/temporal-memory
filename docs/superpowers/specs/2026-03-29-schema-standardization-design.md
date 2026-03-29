# Schema Standardization Design

**Date:** 2026-03-29
**Status:** Approved
**Branch:** context-schema

---

## Problem

`schema.py` mixes four different model definition styles with no organizing principle:

- `@dataclass` for domain objects and configs
- `TypedDict` for internal function params
- Pydantic `BaseModel` for HTTP request/response bodies (in `triggers/api.py`)
- No distinction between models that cross system boundaries and those that stay internal

This mixing has produced concrete bugs and will become harder to maintain as the project grows.

---

## Design

### Four-Layer Model Architecture

Each layer has exactly one tool and one rule for deciding which tool to use.

| Layer | Tool | Rule |
|---|---|---|
| **L1 — HTTP I/O** | Pydantic `BaseModel` | Any model that is an HTTP request body or response body |
| **L2 — Domain/KV** | Pydantic `BaseModel` | Any model stored in or retrieved from KV, or shared across modules |
| **L3 — Internal params** | `@dataclass` | Params and return types for internal function handlers that stay within the process |
| **L4 — Config** | `@dataclass` | Startup configuration loaded from env/files, validated once at boot |

ABCs (provider interfaces) and `str+Enum` (status/state values) are not affected.

**The boundary rule:** If a model crosses a system boundary (HTTP or KV storage), it belongs to L1 or L2 and uses Pydantic. If it stays inside the process, it belongs to L3 or L4 and uses `@dataclass`.

---

### Model Assignments

**L2 → Pydantic BaseModel** (currently `@dataclass` in `schema.py`):
- `Session`
- `ProjectProfile`
- `ProjectTopConcepts`
- `ProjectTopFiles`
- `ContextBlock`
- `CircuitBreakerSnapshot`

**L4 → @dataclass** (stay, no change):
- `ProviderConfig`
- `AgentMemoryConfig`
- `EmbeddingConfig`
- `FallbackConfig`
- `TeamConfig`
- `CloudBridgeConfig`
- `OtelConfigSettings`

**L1 → Pydantic BaseModel** (already correct, stay in `triggers/api.py`):
- `SessionStartPayload`
- `SessionStartResponse`
- `SessionEndPayload`
- `SessionEndResponse`

**L3 → @dataclass** (currently `TypedDict` in `functions/context.py`):
- `ContextHandlerParams`
- `ContextResponse`

---

### File Organization

Split the current flat `schema.py` into two files that reflect the layer distinction:

```
schema/
  __init__.py       # re-exports for backwards compatibility
  domain.py         # L2 models — Pydantic BaseModel
  config.py         # L4 models — @dataclass
```

L1 models stay co-located with their trigger file (`triggers/api.py`).
L3 models stay co-located with their function file (`functions/context.py`).

Co-location keeps each file self-contained: a trigger file defines the shapes it accepts and returns, a function file defines the params it works with.

---

### Bug Fixes

The following bugs are fixed as a direct consequence of this migration:

1. **`ContextBlock.type`** — currently `type = Literal["summary", "observation", "memory"],` (assignment with trailing comma, not a type annotation). Fix: `type: Literal["summary", "observation", "memory"]`

2. **`EmbeddingConfig.provider`** — `Optional["str"]` (str quoted unnecessarily). Fix: `Optional[str]`

3. **`ContextHandlerParams.budget`** — `TypedDict` with `Optional[int]` field but no `total=False`, making `budget` technically required. Fix: move to `@dataclass` with `budget: Optional[int] = None`

4. **`Session` inside `SessionStartResponse(BaseModel)`** — Pydantic cannot natively validate/serialize a `@dataclass` field. Fix: convert `Session` to Pydantic `BaseModel` (L2)

5. **`handle_session_end` dict mutation** — `{**session, "ended_at": ..., "status": ...}` is an untyped dict spread used because `Session` is a dataclass. Fix: use `session.model_copy(update={"ended_at": ..., "status": ...})` once `Session` is a Pydantic model

---

### Data Flow

```
HTTP Request
    │
    ▼
L1 (Pydantic) ── validates, parses ──► L2 (Pydantic) ── stored in KV ──► L2 (Pydantic)
                                            │
                                            ▼
                                       L3 (dataclass) ── internal processing
                                            │
                                            ▼
                                       L2 (Pydantic) ── returned in HTTP response
```

---

### What Does Not Change

- `EmbeddingProvider` and `MemoryProvider` remain ABCs — they define interfaces, not data shapes
- `SessionStatus` and `CircuitBreakerState` remain `str+Enum`
- `state/schema.py` (KV key constants) is not affected
- `state/kv.py` (StateKV client) is not affected
- Serialization/deserialization to/from the `iii` KV store is handled by the SDK and does not require changes

---

### Adding New Models (Going Forward)

When adding a new model, apply the boundary rule:

1. Will it be in an HTTP request or response body? → L1, Pydantic, co-locate in the trigger file
2. Will it be stored in KV or shared across modules? → L2, Pydantic, add to `schema/domain.py`
3. Is it a param or return type for an internal handler? → L3, dataclass, co-locate in the function file
4. Is it startup configuration? → L4, dataclass, add to `schema/config.py`
