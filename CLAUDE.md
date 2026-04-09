# graphmind — Agent Instructions

## Architecture

graphmind is a persistent memory system for AI coding agents, built on iii-engine's three primitives (Worker/Function/Trigger). Everything goes through `sdk.register_function` / `sdk.trigger_async` — never bypass iii-engine with standalone SQLite or in-process alternatives.

- **Engine**: iii-sdk (WebSocket to iii-engine on port 49134)
- **State**: File-based SQLite via iii-engine's StateModule
- **Language**: Python 3.13, async/await throughout
- **Package manager**: `uv` — always use `uv run`, `uv add`, `uv sync` (never `pip`)
- **Test**: pytest + pytest-asyncio (`uv run pytest`)
- **MCP server**: FastMCP, streamable-http on port 8000 (`mcp_tools/server.py`)

## Project Layout

```
functions/       # one file per iii function (observe, remember, search, …)
schema/          # domain.py (dataclasses), config.py (AppConfig), base.py (Model)
state/           # schema.py (KV keys, generate_id), kv.py (StateKV), search/vector indexes
prompts/         # system prompts and prompt builders (compression, summary, consolidation)
providers/       # LLM provider adapters (anthropic, openai, gemini, openrouter, agent-sdk)
triggers/        # REST API routes (routes/), adapters/, middleware/
mcp_tools/       # FastMCP tool registration (server.py)
plugin/          # hooks, scripts, skills for Claude Code integration
config.py        # AppConfig.from_env() entry point
main.py          # worker entry point — registers all functions, starts mcp.run()
```

## Consistency Rules

**When adding a new iii function:**
1. `functions/<name>.py` — implement `register_<name>_function(sdk, kv, ...)`
2. `main.py` — call `register_<name>_function(...)` in `main()`

**When adding a REST endpoint:**
1. `triggers/routes/<router>.py` — add `@router.get/post(...)` handler
2. `triggers/api.py` — include the router in `register_api_triggers`
3. `main.py` — update the endpoint count in the log line

**When adding a new KV scope:**
1. `state/schema.py` — add the key to the `KV` class
2. `schema/domain.py` — add the corresponding `@dataclass(frozen=True)` type

**When adding new schema types:**
1. `schema/domain.py` — define the `@dataclass(frozen=True)` class inheriting `Model`
2. `schema/__init__.py` — export from `__all__`

**When adding MCP tools:**
1. `mcp_tools/server.py` — add the tool inside `register_mcp_function`

## Code Patterns

### Function Registration

```python
from iii import IIIClient, TriggerRequest
from state.kv import StateKV
from state.schema import KV
from logger import get_logger

logger = get_logger("your_function")

def register_your_function(sdk: IIIClient, kv: StateKV):
    async def handle(raw_data: dict):
        # validate inputs
        # do work via kv.get / kv.set / kv.list
        return {"success": True, ...}

    sdk.register_function({"id": "mem::your-function"}, handle)
```

### Triggering Another Function

```python
# Always use TriggerRequest — never pass a plain dict
result = await sdk.trigger_async(TriggerRequest(
    function_id="mem::other-function",
    payload={"key": value},
))
```

### REST Endpoint Registration

```python
router = ApiRouter(prefix="graphmind/your-path", middleware=middleware)

@router.post("action", "api::your::action", PayloadType)
async def handle(req: Request[PayloadType]) -> Response:
    result = await sdk.trigger_async(TriggerRequest(
        function_id="mem::your-function",
        payload=req.body.to_dict(),   # whitelist fields — never pass raw body
    ))
    return Response(status_code=200, body=result)
```

### MCP Tool Handler

```python
@mcp.tool
async def your_tool(param: str, kv: StateKV = Depends(get_kv)) -> str:
    """Tool description shown to the LLM."""
    result = await sdk.trigger_async(TriggerRequest(
        function_id="mem::your-function",
        payload={"param": param},
    ))
    return json.dumps(result, indent=2)
```

### Dataclass Mutations (frozen=True)

All domain types use `frozen=True`. Never assign fields directly — use `dataclasses.replace()`:

```python
import dataclasses

# WRONG — raises FrozenInstanceError
existing.strength = 0.9

# CORRECT
updated = dataclasses.replace(existing, strength=0.9, updated_at=now)
await kv.set(KV.memories, updated.id, updated)
```

### KV Usage

```python
# Read one
item = await kv.get(KV.memories, item_id, Memory)

# Read all
items = await kv.list(KV.memories, Memory)

# Write
await kv.set(KV.memories, item.id, item)

# Delete
await kv.delete(KV.memories, item_id)
```

### Timestamps

```python
from datetime import datetime, timezone

now = datetime.now(timezone.utc).isoformat()  # capture once, reuse
```

### Parallel IO

```python
import asyncio

results = await asyncio.gather(
    kv.get(KV.sessions, sid, Session),
    kv.list(KV.memories, Memory),
)
```

## Recurring Bugs — Always Check

| Bug | Wrong | Right |
|-----|-------|-------|
| Frozen dataclass mutation | `obj.field = x` | `dataclasses.replace(obj, field=x)` |
| datetime module vs class | `datetime.fromisoformat(...)` | `datetime.datetime.fromisoformat(...)` |
| iii trigger payload | `sdk.trigger_async({"function_id": ...})` | `sdk.trigger_async(TriggerRequest(...))` |
| Folder name conflict | `mcp/` (conflicts with installed `mcp` package) | `mcp_tools/` |
| List length | `items.length` | `len(items)` |
| Type annotation vs assignment | `self.x = Dict[str, int] = {}` | `self.x: Dict[str, int] = {}` |
| Module name "lib" | `lib_utils`, `libhelper` | no "lib" prefix anywhere |

## KV Namespaces

Defined in `state/schema.py`:

```python
class KV:
    sessions   = "mem:sessions"
    profiles   = "mem:profiles"
    memories   = "mem:memories"
    summaries  = "mem:summaries"
    semantic   = "mem:semantic"
    claude_bridge = "mem:claude-bridge"

    @staticmethod
    def observations(session_id: str) -> str: ...

    @staticmethod
    def embeddings(obs_id: str) -> str: ...
```

## Testing

```bash
uv run pytest                        # all tests
uv run pytest tests/functions/       # function tests only
uv run pytest -s                     # with stdout (logs visible)
uv run pytest -k "test_search"       # filter by name
```

- Test files go in `tests/` mirroring the source layout (`tests/functions/`, etc.)
- Use `@pytest_asyncio.fixture` for async fixtures (not `@pytest.fixture`)
- Mock pattern: `MockKV` / `MockSDK` classes (see `tests/functions/test_smart_search.py`)
- Logs don't print by default — run with `-s` or set `log_cli = true` in `pyproject.toml`

## Running

```bash
uv run python main.py        # start the worker + MCP server
```

Key env vars (see `schema/config.py` for full list):

| Variable | Default | Purpose |
|----------|---------|---------|
| `III_ENGINE_URL` | `ws://localhost:49134` | iii-engine WebSocket |
| `III_REST_PORT` | `3111` | REST API port |
| `ANTHROPIC_API_KEY` | — | enables Anthropic provider |
| `CONSOLIDATION_ENABLED` | `false` | enables consolidation pipeline |
| `CONSOLIDATION_DECAY_DAYS` | `30` | memory decay period |
| `CLAUDE_MEMORY_BRIDGE` | `false` | sync to MEMORY.md |
| `CLAUDE_PROJECT_PATH` | — | project path for bridge |
