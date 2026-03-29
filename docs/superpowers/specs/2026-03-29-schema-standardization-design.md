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

ABCs (provider interfaces) and `str+Enum` (status/state values) follow separate rules described below.

**The boundary rule:** If a model crosses a system boundary (HTTP or KV storage), it belongs to L1 or L2 and uses Pydantic. If it stays inside the process, it belongs to L3 or L4 and uses `@dataclass`.

---

### Model Assignments

**L2 → Pydantic BaseModel** (currently `@dataclass` in `schema.py`, move to `schema/domain.py`):
- `Session`
- `ProjectProfile`
- `ProjectTopConcepts`
- `ProjectTopFiles`
- `ContextBlock`
- `CircuitBreakerSnapshot`

**Enums** (stay as `str+Enum`, move to `schema/domain.py` alongside the models that use them):
- `SessionStatus`
- `CircuitBreakerState`

**ABCs** (stay as ABCs, move to `schema/domain.py`):
- `EmbeddingProvider`
- `MemoryProvider`

**L4 → @dataclass** (stay, move to `schema/config.py`):
- `ProviderConfig`
- `AgentMemoryConfig`
- `EmbeddingConfig`
- `FallbackConfig`
- `TeamConfig`
- `CloudBridgeConfig`
- `OtelConfigSettings`

**Type aliases** (move to `schema/config.py` alongside the L4 models that reference them):
- `ProviderType = Literal[...]`

**L1 → Pydantic BaseModel** (already correct, stay co-located in `triggers/api.py`):
- `SessionStartPayload`
- `SessionStartResponse`
- `SessionEndPayload`
- `SessionEndResponse`

**L3 → @dataclass** (currently `TypedDict`, stay co-located in `functions/context.py`):
- `ContextHandlerParams`
- `ContextResponse` — intentionally L3 because it is only returned from the internal handler and consumed within the same process. After conversion to `@dataclass`, the handler body must be updated to return `ContextResponse(context=...)` rather than a plain dict literal. The caller in `triggers/api.py` currently discards the return value entirely (`print(context_response)`), so no import of `ContextResponse` into `triggers/api.py` is needed — the commented-out `# parsed = ContextResponse(**context_response)` stays commented out. If `ContextResponse` ever crosses the module boundary and is used in an HTTP response, it must be promoted to L2 in `schema/domain.py`.

---

### File Organization

Split the current flat `schema.py` into two files:

```
schema/
  __init__.py       # re-exports all public names for backwards compatibility
  domain.py         # L2 models (Pydantic BaseModel) + Enums + ABCs
  config.py         # L4 models (@dataclass) + ProviderType alias
```

`__init__.py` re-exports everything from both `domain.py` and `config.py` so existing `from schema import Session, SessionStatus` imports continue to work without changes at callsites.

**Relationship to `config.py` (root):** The existing root-level `config.py` contains config *construction logic* (`load_config()`, `load_team_config()`, etc.). The new `schema/config.py` contains only the config *data shapes* (`@dataclass` definitions). These are distinct responsibilities. `config.py` imports from `schema/config.py`; `schema/config.py` does not import from `config.py`.

L1 models stay co-located with their trigger file (`triggers/api.py`).
L3 models stay co-located with their function file (`functions/context.py`).

Co-location keeps each file self-contained: a trigger file defines the shapes it accepts and returns, a function file defines the params it works with.

---

### Bug Fixes

The following bugs are fixed as part of this migration. Apply them in order — Bug Fix 5 depends on Bug Fix 4.

1. **`ContextBlock.type`** — currently `type = Literal["summary", "observation", "memory"],` (class variable assignment with trailing comma, not a type annotation). Fix: `type: Literal["summary", "observation", "memory"]`. **Breaking callsite change:** once `ContextBlock` becomes a Pydantic model with `type` as a proper field, any code constructing a `ContextBlock` must pass `type` explicitly. Note: in the current codebase `blocks: List[ContextBlock] = []` is initialized in `handle_context` but never populated — there are no active `ContextBlock(...)` constructor calls. The callsite audit is a precautionary check, not a known-count fix.

2. **`EmbeddingConfig.provider`** — `Optional["str"]` (str is quoted unnecessarily). Fix: `Optional[str]`.

3. **`ContextHandlerParams.budget` and dict-style access in `handle_context`** — two issues from the same TypedDict-to-dataclass conversion:
   - `TypedDict` with an `Optional[int]` field but no `total=False`, making `budget` technically required at runtime.
   - `handle_context` accesses params via `data.get("budget", token_budget)` (dict-style). After conversion to `@dataclass` this raises `TypeError`.

   Fix: move to `@dataclass` with `budget: Optional[int] = None`, change all dict-style `data["field"]` and `data.get("field", default)` accesses in `handle_context` to attribute-style (`data.field`, `data.budget if data.budget is not None else token_budget`), and update the handler to return `ContextResponse(context=...)` instead of a plain dict literal.

4. **`Session` inside `SessionStartResponse(BaseModel)`** — the `iii` KV store deserializes stored objects as plain dicts, not typed instances. When `Session` is a `@dataclass`, Pydantic will not coerce an incoming dict into a `Session` instance automatically, leading to untyped dict access propagating through the codebase (e.g., `s["project"]` in `functions/context.py`). Fix: convert `Session` to Pydantic `BaseModel` (L2) so Pydantic handles coercion at every boundary. **Apply this before Bug Fix 5**, which depends on `Session` being a Pydantic model.

5. **`handle_session_end` dict mutation, null-check ordering, and wrong response shape** — three bugs in one block (depends on Bug Fix 4):
   - `{**session, "ended_at": ..., "status": ...}` spreads `session` before the null check, so if `session` is `None` the spread raises `TypeError` before the guard is reached.
   - The mutation produces an untyped dict instead of a typed object.
   - The return body is `{"session": modified_session}` but `SessionEndResponse` only has `success: bool` — the key `session` does not exist on the declared response type.

   Note on KV deserialization: `StateKV.get` returns whatever the `iii` SDK gives back, which is a plain dict at runtime. Even after `Session` becomes a Pydantic `BaseModel`, `kv.get` does not automatically coerce the result. A `Session.model_validate(raw)` call is required after `kv.get` to produce a typed `Session` instance before calling `model_copy`. The same pattern applies everywhere a domain model is read from KV.

   Fix: move the null check first, coerce the raw KV result with `model_validate`, use `model_copy`, and correct the return body:
   ```python
   raw = await kv.get(KV.sessions, body.session_id)
   if raw is None:
       return ApiResponse(statusCode=404, body={"success": False})
   session = Session.model_validate(raw)
   modified_session = session.model_copy(update={
       "ended_at": datetime.now(timezone.utc).isoformat(),
       "status": SessionStatus.COMPLETED
   })
   await kv.set(KV.sessions, body.session_id, modified_session)
   return ApiResponse(statusCode=200, body={"success": True})
   ```

   The `model_validate` pattern applies to all L2 models read back from KV — this is the standard coercion point at the storage boundary.

6. **`SessionStartPayload` missing `model` field** — `handle_session_start` passes `model=payload.model` to the `Session(...)` constructor, but `SessionStartPayload` declares only `session_id`, `project`, and `cwd`. This raises `AttributeError` on every session start call. Fix: add `model: Optional[str] = None` to `SessionStartPayload`.

---

### Data Flow

```
HTTP Request
    │
    ▼
L1 (Pydantic) ── validates, parses
    │
    ├──► L2 (Pydantic) ── stored in KV
    │
    ├──► L3 (dataclass) ── dispatched as internal trigger (fire-and-read)
    │        result consumed within L1 handler, not propagated to HTTP response
    │
    └──► L1 (Pydantic) ── HTTP response assembled from L2 data already in scope
```

In `handle_session_start`, the `Session` (L2) is constructed and stored, the context trigger (L3) is called for side-effects, and the HTTP response wraps the already-in-scope `Session` — the L3 result does not feed the response.

---

### What Does Not Change

- `EmbeddingProvider` and `MemoryProvider` remain ABCs — they move to `schema/domain.py` but their interface is unchanged
- `SessionStatus` and `CircuitBreakerState` remain `str+Enum` — they move to `schema/domain.py`
- `state/schema.py` (KV key constants) is not affected
- `state/kv.py` (StateKV client) is not affected
- Root-level `config.py` (config construction logic) is not affected — it will import from `schema/config.py` instead of `schema.py`
- The `iii` SDK handles serialization (write) to the KV store without changes. On reads, the SDK returns plain dicts — `Session.model_validate(raw)` (and equivalent for other L2 models) must be applied at every KV read callsite to coerce the result to a typed instance. `StateKV` itself does not change.

---

### Adding New Models (Going Forward)

When adding a new model, apply the boundary rule:

1. Will it be in an HTTP request or response body? → L1, Pydantic, co-locate in the trigger file
2. Will it be stored in KV or shared across modules? → L2, Pydantic, add to `schema/domain.py`
3. Is it a param or return type for an internal handler? → L3, dataclass, co-locate in the function file
4. Is it startup configuration? → L4, dataclass, add to `schema/config.py`
5. If a model starts in L3 and later needs to cross a module boundary or appear in an HTTP response, promote it to L2.
