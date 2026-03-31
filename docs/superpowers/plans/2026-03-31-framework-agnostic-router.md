# Framework-Agnostic Router Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flat, `iii`-coupled `triggers/api.py` with a framework-agnostic router + adapter pattern that supports ~100 endpoints across grouped routes, per-group middleware, and a standardized typed error contract.

**Architecture:** An `ApiRouter` class (no SDK imports) collects decorated route handlers per domain group. An `AbstractAdapter` defines the registration contract; `IIIAdapter` is the only file that imports from `iii`. Swapping to Fastify or another framework = write a new adapter, touch nothing else. All handlers speak `Request[T]` / `Response[T]` / `ApiException` — never raw SDK types.

**Tech Stack:** Python 3.13, Pydantic v2, pytest, `iii-sdk`, `asyncio`

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `triggers/router.py` | Core types: `Request`, `Response`, `ApiSuccess`, `ApiError`, `ErrorCode`, `ApiException`, `RouteConfig`, `ApiRouter`, `Handler`, `Middleware` |
| Create | `triggers/adapters/__init__.py` | Re-exports |
| Create | `triggers/adapters/base.py` | `AbstractAdapter` ABC |
| Create | `triggers/adapters/iii.py` | `IIIAdapter` — only file importing `iii` SDK |
| Create | `triggers/middleware/__init__.py` | Re-exports |
| Create | `triggers/middleware/logging.py` | `logging_middleware` |
| Create | `triggers/middleware/auth.py` | `make_auth_middleware(secret)` |
| Create | `triggers/routes/__init__.py` | Re-exports |
| Create | `triggers/routes/session.py` | `session_router(kv, sdk, middleware)` — start + end handlers |
| Create | `triggers/routes/bridge.py` | `bridge_router(sdk, middleware)` — observe + summarize + claude-bridge-sync |
| Modify | `triggers/api.py` | Assembly only: create adapter, collect routers, call `adapter.register()` |
| Create | `tests/__init__.py` | Test package root |
| Create | `tests/triggers/__init__.py` | Test subpackage |
| Create | `tests/triggers/test_router.py` | Unit tests for `ApiRouter`, `ApiException`, middleware chain |
| Create | `tests/triggers/test_middleware.py` | Unit tests for auth and logging middleware |
| Create | `tests/triggers/test_routes_session.py` | Unit tests for session route handlers |
| Create | `tests/triggers/test_iii_adapter.py` | Unit tests for `IIIAdapter` registration and wrapping |

---

## Task 1: Core types in `triggers/router.py`

**Files:**
- Create: `triggers/router.py`
- Create: `tests/__init__.py`
- Create: `tests/triggers/__init__.py`
- Create: `tests/triggers/test_router.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/triggers/test_router.py
import pytest
from triggers.router import (
    ApiRouter, ApiException, ApiError, ApiSuccess,
    ErrorCode, Request, Response, build_middleware_chain
)
from pydantic import BaseModel


class SamplePayload(BaseModel):
    name: str


class SampleResponse(BaseModel):
    greeting: str


# --- ApiRouter ---

def test_router_registers_route():
    router = ApiRouter(prefix="test")

    @router.post("hello", "test::hello", SamplePayload)
    async def handler(req: Request[SamplePayload]) -> Response:
        return Response(status_code=200, body=ApiSuccess(data=SampleResponse(greeting=f"hi {req.body.name}")))

    assert len(router.routes) == 1
    route = router.routes[0]
    assert route.path == "test/hello"
    assert route.function_id == "test::hello"
    assert route.method == "POST"
    assert route.payload_type is SamplePayload


def test_router_stores_middleware():
    async def mw(req, next): return await next(req)
    router = ApiRouter(prefix="test", middleware=[mw])
    assert router.middleware == [mw]


def test_router_no_payload_route():
    router = ApiRouter(prefix="test")

    @router.post("ping", "test::ping", None)
    async def handler(req: Request) -> Response:
        return Response(status_code=200, body=ApiSuccess(data={}))

    assert router.routes[0].payload_type is None


# --- ApiException ---

def test_api_exception_carries_code_and_message():
    exc = ApiException(ErrorCode.SESSION_NOT_FOUND, "not found")
    assert exc.code == ErrorCode.SESSION_NOT_FOUND
    assert exc.message == "not found"
    assert exc.details is None
    assert exc.status_code == 404


def test_api_exception_with_details():
    exc = ApiException(ErrorCode.INVALID_PAYLOAD, "bad input", details={"field": "session_id"})
    assert exc.details == {"field": "session_id"}


def test_api_exception_to_error():
    exc = ApiException(ErrorCode.INTERNAL_ERROR, "oops")
    error = exc.to_error()
    assert isinstance(error, ApiError)
    assert error.code == ErrorCode.INTERNAL_ERROR
    assert error.message == "oops"


# --- Middleware chain ---

@pytest.mark.asyncio
async def test_middleware_chain_calls_handler():
    async def handler(req):
        return Response(status_code=200, body=ApiSuccess(data={"ok": True}))

    req = Request(body={})
    chain = build_middleware_chain([], handler)
    result = await chain(req)
    assert result.status_code == 200


@pytest.mark.asyncio
async def test_middleware_chain_runs_in_order():
    order = []

    async def mw1(req, next):
        order.append("mw1_before")
        res = await next(req)
        order.append("mw1_after")
        return res

    async def mw2(req, next):
        order.append("mw2_before")
        res = await next(req)
        order.append("mw2_after")
        return res

    async def handler(req):
        order.append("handler")
        return Response(status_code=200, body=ApiSuccess(data={}))

    chain = build_middleware_chain([mw1, mw2], handler)
    await chain(Request(body={}))
    assert order == ["mw1_before", "mw2_before", "handler", "mw2_after", "mw1_after"]


@pytest.mark.asyncio
async def test_middleware_can_short_circuit():
    from triggers.router import ApiException, ErrorCode

    async def blocking_mw(req, next):
        raise ApiException(ErrorCode.UNAUTHORIZED, "blocked")

    async def handler(req):
        return Response(status_code=200, body=ApiSuccess(data={}))

    chain = build_middleware_chain([blocking_mw], handler)
    with pytest.raises(ApiException) as exc_info:
        await chain(Request(body={}))
    assert exc_info.value.code == ErrorCode.UNAUTHORIZED
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /path/to/worktree && python -m pytest tests/triggers/test_router.py -v
```
Expected: `ModuleNotFoundError: No module named 'triggers.router'`

- [ ] **Step 3: Implement `triggers/router.py`**

```python
# triggers/router.py
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Generic, Optional, TypeVar
from pydantic import BaseModel

T = TypeVar("T")
U = TypeVar("U")


# --- HTTP types ---

class Request(BaseModel, Generic[T]):
    body: T
    headers: dict[str, str] = {}
    params: dict[str, str] = {}


class ApiSuccess(BaseModel, Generic[T]):
    data: T


class Response(BaseModel, Generic[T]):
    status_code: int
    body: T


# --- Error contract ---

class ErrorCode(str, Enum):
    SESSION_NOT_FOUND  = "session_not_found"
    INVALID_PAYLOAD    = "invalid_payload"
    INTERNAL_ERROR     = "internal_error"
    UNAUTHORIZED       = "unauthorized"
    NOT_FOUND          = "not_found"
    CONFLICT           = "conflict"


_STATUS_MAP: dict[ErrorCode, int] = {
    ErrorCode.SESSION_NOT_FOUND: 404,
    ErrorCode.INVALID_PAYLOAD:   400,
    ErrorCode.INTERNAL_ERROR:    500,
    ErrorCode.UNAUTHORIZED:      401,
    ErrorCode.NOT_FOUND:         404,
    ErrorCode.CONFLICT:          409,
}


class ApiError(BaseModel):
    code: ErrorCode
    message: str
    details: Optional[dict] = None


class ApiException(Exception):
    def __init__(self, code: ErrorCode, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details
        self.status_code = _STATUS_MAP.get(code, 500)

    def to_error(self) -> ApiError:
        return ApiError(code=self.code, message=self.message, details=self.details)


# --- Middleware ---

Handler    = Callable[[Request], Awaitable[Response]]
Middleware = Callable[[Request, Handler], Awaitable[Response]]


def build_middleware_chain(middleware: list[Middleware], handler: Handler) -> Handler:
    async def execute(index: int, req: Request) -> Response:
        if index >= len(middleware):
            return await handler(req)

        async def next_handler(req: Request) -> Response:
            return await execute(index + 1, req)

        return await middleware[index](req, next_handler)

    async def chain(req: Request) -> Response:
        return await execute(0, req)

    return chain


# --- Router ---

@dataclass
class RouteConfig:
    path: str
    method: str
    function_id: str
    handler: Handler
    payload_type: Optional[type[BaseModel]]


class ApiRouter:
    def __init__(self, prefix: str, middleware: list[Middleware] = []):
        self.prefix = prefix
        self.middleware = middleware
        self.routes: list[RouteConfig] = []

    def post(self, path: str, function_id: str, payload_type: Optional[type[BaseModel]]):
        def decorator(handler: Handler) -> Handler:
            self.routes.append(RouteConfig(
                path=f"{self.prefix}/{path}",
                method="POST",
                function_id=function_id,
                handler=handler,
                payload_type=payload_type,
            ))
            return handler
        return decorator
```

- [ ] **Step 4: Create empty `__init__.py` files**

```bash
touch tests/__init__.py tests/triggers/__init__.py
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
python -m pytest tests/triggers/test_router.py -v
```
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add triggers/router.py tests/__init__.py tests/triggers/__init__.py tests/triggers/test_router.py
git commit -m "feat: add ApiRouter, typed error contract, and middleware chain"
```

---

## Task 2: `AbstractAdapter` and `IIIAdapter`

**Files:**
- Create: `triggers/adapters/__init__.py`
- Create: `triggers/adapters/base.py`
- Create: `triggers/adapters/iii.py`
- Create: `tests/triggers/test_iii_adapter.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/triggers/test_iii_adapter.py
import pytest
from unittest.mock import AsyncMock, MagicMock, call
from pydantic import BaseModel

from triggers.router import ApiRouter, ApiException, ApiSuccess, ErrorCode, Request, Response
from triggers.adapters.iii import IIIAdapter


class Payload(BaseModel):
    value: str


class Result(BaseModel):
    echo: str


def make_router() -> ApiRouter:
    router = ApiRouter(prefix="test")

    @router.post("echo", "test::echo", Payload)
    async def handle_echo(req: Request[Payload]) -> Response:
        return Response(status_code=200, body=ApiSuccess(data=Result(echo=req.body.value)))

    return router


def make_no_payload_router() -> ApiRouter:
    router = ApiRouter(prefix="test")

    @router.post("ping", "test::ping", None)
    async def handle_ping(req: Request) -> Response:
        return Response(status_code=200, body=ApiSuccess(data={"pong": True}))

    return router


def test_iii_adapter_registers_function_and_trigger():
    sdk = MagicMock()
    adapter = IIIAdapter()
    adapter.register(sdk, [make_router()])

    assert sdk.register_function.call_count == 1
    assert sdk.register_trigger.call_count == 1

    trigger_call = sdk.register_trigger.call_args[0][0]
    assert trigger_call.config["api_path"] == "test/echo"
    assert trigger_call.config["http_method"] == "POST"
    assert trigger_call.function_id == "test::echo"


def test_iii_adapter_registers_multiple_routers():
    sdk = MagicMock()
    adapter = IIIAdapter()
    adapter.register(sdk, [make_router(), make_no_payload_router()])

    assert sdk.register_function.call_count == 2
    assert sdk.register_trigger.call_count == 2


@pytest.mark.asyncio
async def test_iii_adapter_wrapped_handler_success():
    sdk = MagicMock()
    adapter = IIIAdapter()
    adapter.register(sdk, [make_router()])

    wrapped = sdk.register_function.call_args[0][1]
    # Simulate iii calling the wrapped handler with raw dict
    raw_req = {"body": {"value": "hello"}, "headers": {}}
    result = await wrapped(raw_req)

    assert result["status_code"] == 200
    assert result["body"]["data"]["echo"] == "hello"


@pytest.mark.asyncio
async def test_iii_adapter_wrapped_handler_api_exception():
    sdk = MagicMock()
    router = ApiRouter(prefix="test")

    @router.post("fail", "test::fail", Payload)
    async def handle_fail(req: Request[Payload]) -> Response:
        raise ApiException(ErrorCode.SESSION_NOT_FOUND, "not found")

    adapter = IIIAdapter()
    adapter.register(sdk, [router])

    wrapped = sdk.register_function.call_args[0][1]
    result = await wrapped({"body": {"value": "x"}, "headers": {}})

    assert result["status_code"] == 404
    assert result["body"]["code"] == "session_not_found"
    assert result["body"]["message"] == "not found"


@pytest.mark.asyncio
async def test_iii_adapter_wrapped_handler_unhandled_exception():
    sdk = MagicMock()
    router = ApiRouter(prefix="test")

    @router.post("crash", "test::crash", Payload)
    async def handle_crash(req: Request[Payload]) -> Response:
        raise RuntimeError("boom")

    adapter = IIIAdapter()
    adapter.register(sdk, [router])

    wrapped = sdk.register_function.call_args[0][1]
    result = await wrapped({"body": {"value": "x"}, "headers": {}})

    assert result["status_code"] == 500
    assert result["body"]["code"] == "internal_error"


@pytest.mark.asyncio
async def test_iii_adapter_runs_middleware():
    sdk = MagicMock()
    called = []

    async def tracking_mw(req, next):
        called.append("mw")
        return await next(req)

    router = ApiRouter(prefix="test", middleware=[tracking_mw])

    @router.post("mw-test", "test::mw", Payload)
    async def handle(req: Request[Payload]) -> Response:
        return Response(status_code=200, body=ApiSuccess(data={}))

    adapter = IIIAdapter()
    adapter.register(sdk, [router])

    wrapped = sdk.register_function.call_args[0][1]
    await wrapped({"body": {"value": "x"}, "headers": {}})

    assert "mw" in called
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/triggers/test_iii_adapter.py -v
```
Expected: `ModuleNotFoundError: No module named 'triggers.adapters'`

- [ ] **Step 3: Implement `triggers/adapters/base.py`**

```python
# triggers/adapters/base.py
from abc import ABC, abstractmethod
from triggers.router import ApiRouter


class AbstractAdapter(ABC):
    @abstractmethod
    def register(self, sdk, routers: list[ApiRouter]) -> None:
        """Register all routes from all routers with the underlying framework/SDK."""
        ...
```

- [ ] **Step 4: Implement `triggers/adapters/iii.py`**

```python
# triggers/adapters/iii.py
from iii import IIIClient, RegisterFunctionInput, RegisterTriggerInput

from triggers.adapters.base import AbstractAdapter
from triggers.router import (
    ApiError, ApiException, ApiRouter, ErrorCode,
    Request, build_middleware_chain,
)


class IIIAdapter(AbstractAdapter):
    def register(self, sdk: IIIClient, routers: list[ApiRouter]) -> None:
        for router in routers:
            for route in router.routes:
                wrapped = self._wrap(route, router.middleware)
                sdk.register_function(RegisterFunctionInput(id=route.function_id), wrapped)
                sdk.register_trigger(RegisterTriggerInput(
                    type="http",
                    function_id=route.function_id,
                    config={
                        "api_path": route.path,
                        "http_method": route.method,
                    }
                ))

    def _wrap(self, route, middleware):
        chain = build_middleware_chain(middleware, route.handler)

        async def handler(req_raw: dict) -> dict:
            try:
                body = req_raw.get("body", {}) or {}
                headers = req_raw.get("headers", {}) or {}

                if route.payload_type is not None:
                    parsed_body = route.payload_type(**body)
                else:
                    parsed_body = body

                req = Request(body=parsed_body, headers=headers)
                response = await chain(req)
                return response.model_dump()

            except ApiException as e:
                return {"status_code": e.status_code, "body": e.to_error().model_dump()}
            except Exception as e:
                error = ApiError(code=ErrorCode.INTERNAL_ERROR, message=str(e))
                return {"status_code": 500, "body": error.model_dump()}

        return handler
```

- [ ] **Step 5: Create `triggers/adapters/__init__.py`**

```python
# triggers/adapters/__init__.py
from triggers.adapters.iii import IIIAdapter

__all__ = ["IIIAdapter"]
```

- [ ] **Step 6: Run tests to confirm they pass**

```bash
python -m pytest tests/triggers/test_iii_adapter.py -v
```
Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add triggers/adapters/ tests/triggers/test_iii_adapter.py
git commit -m "feat: add AbstractAdapter and IIIAdapter with error boundary"
```

---

## Task 3: Middleware — logging and auth

**Files:**
- Create: `triggers/middleware/__init__.py`
- Create: `triggers/middleware/logging.py`
- Create: `triggers/middleware/auth.py`
- Create: `tests/triggers/test_middleware.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/triggers/test_middleware.py
import pytest
from triggers.router import ApiException, ApiSuccess, ErrorCode, Request, Response
from triggers.middleware.auth import make_auth_middleware
from triggers.middleware.logging import logging_middleware


async def ok_handler(req: Request) -> Response:
    return Response(status_code=200, body=ApiSuccess(data={"ok": True}))


# --- Auth middleware ---

@pytest.mark.asyncio
async def test_auth_middleware_passes_with_valid_key():
    auth = make_auth_middleware("secret123")
    req = Request(body={}, headers={"x-api-key": "secret123"})
    response = await auth(req, ok_handler)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_auth_middleware_rejects_missing_key():
    auth = make_auth_middleware("secret123")
    req = Request(body={}, headers={})
    with pytest.raises(ApiException) as exc_info:
        await auth(req, ok_handler)
    assert exc_info.value.code == ErrorCode.UNAUTHORIZED


@pytest.mark.asyncio
async def test_auth_middleware_rejects_wrong_key():
    auth = make_auth_middleware("secret123")
    req = Request(body={}, headers={"x-api-key": "wrong"})
    with pytest.raises(ApiException) as exc_info:
        await auth(req, ok_handler)
    assert exc_info.value.code == ErrorCode.UNAUTHORIZED


# --- Logging middleware ---

@pytest.mark.asyncio
async def test_logging_middleware_passes_through(capfd):
    req = Request(body={})
    response = await logging_middleware(req, ok_handler)
    assert response.status_code == 200
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/triggers/test_middleware.py -v
```
Expected: `ModuleNotFoundError: No module named 'triggers.middleware'`

- [ ] **Step 3: Implement `triggers/middleware/auth.py`**

```python
# triggers/middleware/auth.py
from triggers.router import ApiException, ErrorCode, Handler, Middleware, Request, Response


def make_auth_middleware(secret: str) -> Middleware:
    async def auth(req: Request, next: Handler) -> Response:
        if req.headers.get("x-api-key") != secret:
            raise ApiException(ErrorCode.UNAUTHORIZED, "Invalid or missing API key")
        return await next(req)
    return auth
```

- [ ] **Step 4: Implement `triggers/middleware/logging.py`**

```python
# triggers/middleware/logging.py
import logging

from triggers.router import Handler, Middleware, Request, Response

_logger = logging.getLogger("graphmind")


async def logging_middleware(req: Request, next: Handler) -> Response:
    _logger.debug(f"[graphmind] → {req.params.get('method', 'POST')} {req.params.get('path', '')}")
    response = await next(req)
    _logger.debug(f"[graphmind] ← {response.status_code}")
    return response
```

- [ ] **Step 5: Create `triggers/middleware/__init__.py`**

```python
# triggers/middleware/__init__.py
from triggers.middleware.auth import make_auth_middleware
from triggers.middleware.logging import logging_middleware

__all__ = ["make_auth_middleware", "logging_middleware"]
```

- [ ] **Step 6: Run tests to confirm they pass**

```bash
python -m pytest tests/triggers/test_middleware.py -v
```
Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add triggers/middleware/ tests/triggers/test_middleware.py
git commit -m "feat: add logging and auth middleware"
```

---

## Task 4: Session routes

**Files:**
- Create: `triggers/routes/__init__.py`
- Create: `triggers/routes/session.py`
- Create: `tests/triggers/test_routes_session.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/triggers/test_routes_session.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from triggers.routes.session import session_router
from triggers.router import ApiException, ApiSuccess, ErrorCode, Request
from triggers.adapters.iii import IIIAdapter


def make_kv(session_data=None):
    kv = MagicMock()
    kv.set = AsyncMock(return_value=None)
    kv.get = AsyncMock(return_value=session_data)
    return kv


def make_sdk(context_result=None):
    sdk = MagicMock()
    sdk.trigger_async = AsyncMock(return_value=context_result or {"context": "test context"})
    return sdk


@pytest.mark.asyncio
async def test_session_start_creates_session_and_returns_context():
    kv = make_kv()
    sdk = make_sdk({"context": "some context"})

    router = session_router(kv, sdk)
    adapter = IIIAdapter()
    mock_sdk = MagicMock()
    adapter.register(mock_sdk, [router])

    # Find start handler
    start_wrapped = None
    for reg_call in mock_sdk.register_function.call_args_list:
        func_input = reg_call[0][0]
        if func_input.id == "api::session::start":
            start_wrapped = reg_call[0][1]

    assert start_wrapped is not None
    result = await start_wrapped({
        "body": {
            "session_id": "s1",
            "project": "my-project",
            "cwd": "/home/user",
            "model": "claude-sonnet-4-6"
        },
        "headers": {}
    })

    assert result["status_code"] == 200
    assert result["body"]["data"]["session"]["id"] == "s1"
    assert result["body"]["data"]["context"] == "some context"
    kv.set.assert_called_once()


@pytest.mark.asyncio
async def test_session_end_returns_404_when_session_missing():
    kv = make_kv(session_data=None)
    sdk = make_sdk()

    router = session_router(kv, sdk)
    adapter = IIIAdapter()
    mock_sdk = MagicMock()
    adapter.register(mock_sdk, [router])

    end_wrapped = None
    for reg_call in mock_sdk.register_function.call_args_list:
        func_input = reg_call[0][0]
        if func_input.id == "api::session::end":
            end_wrapped = reg_call[0][1]

    result = await end_wrapped({"body": {"session_id": "missing"}, "headers": {}})

    assert result["status_code"] == 404
    assert result["body"]["code"] == "session_not_found"


@pytest.mark.asyncio
async def test_session_end_marks_session_completed():
    from schema.domain import Session, SessionStatus
    from datetime import datetime, timezone

    existing = Session(
        id="s1", project="p", cwd="/",
        started_at=datetime.now(timezone.utc).isoformat(),
        status=SessionStatus.ACTIVE,
        observation_count=0
    )
    kv = make_kv(session_data=existing.model_dump())
    sdk = make_sdk()

    router = session_router(kv, sdk)
    adapter = IIIAdapter()
    mock_sdk = MagicMock()
    adapter.register(mock_sdk, [router])

    end_wrapped = None
    for reg_call in mock_sdk.register_function.call_args_list:
        func_input = reg_call[0][0]
        if func_input.id == "api::session::end":
            end_wrapped = reg_call[0][1]

    result = await end_wrapped({"body": {"session_id": "s1"}, "headers": {}})

    assert result["status_code"] == 200
    assert result["body"]["data"]["success"] is True
    kv.set.assert_called_once()
    saved = kv.set.call_args[0][2]
    assert saved["status"] == SessionStatus.COMPLETED
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python -m pytest tests/triggers/test_routes_session.py -v
```
Expected: `ModuleNotFoundError: No module named 'triggers.routes'`

- [ ] **Step 3: Implement `triggers/routes/session.py`**

```python
# triggers/routes/session.py
import asyncio
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel

from functions.context import ContextHandlerParams, ContextResult
from schema import Session, SessionStatus
from state.kv import StateKV
from state.schema import KV
from triggers.router import (
    ApiException, ApiRouter, ApiSuccess, ErrorCode,
    Middleware, Request, Response,
)


class SessionStartPayload(BaseModel):
    session_id: str
    project: str
    cwd: str
    model: Optional[str] = None


class SessionStartResponse(BaseModel):
    session: Session
    context: str


class SessionEndPayload(BaseModel):
    session_id: str


class SessionEndResponse(BaseModel):
    success: bool


def session_router(kv: StateKV, sdk, middleware: list[Middleware] = []) -> ApiRouter:
    from iii import TriggerRequest  # imported here to keep handlers free of iii

    router = ApiRouter(prefix="graphmind/session", middleware=middleware)

    @router.post("start", "api::session::start", SessionStartPayload)
    async def handle_session_start(req: Request[SessionStartPayload]) -> Response:
        payload = req.body
        session = Session(
            id=payload.session_id,
            project=payload.project,
            cwd=payload.cwd,
            model=payload.model,
            started_at=datetime.now(timezone.utc).isoformat(),
            status=SessionStatus.ACTIVE,
            observation_count=0,
        )

        _, context_result_raw = await asyncio.gather(
            kv.set(KV.sessions, payload.session_id, session.model_dump()),
            sdk.trigger_async(TriggerRequest(
                function_id="mem::context",
                payload=ContextHandlerParams(
                    session_id=payload.session_id,
                    project=payload.project,
                )
            ))
        )

        parsed_context = ContextResult(**context_result_raw)
        return Response(
            status_code=200,
            body=ApiSuccess(data=SessionStartResponse(session=session, context=parsed_context.context)),
        )

    @router.post("end", "api::session::end", SessionEndPayload)
    async def handle_session_end(req: Request[SessionEndPayload]) -> Response:
        payload = req.body
        raw = await kv.get(KV.sessions, payload.session_id)

        if raw is None:
            raise ApiException(ErrorCode.SESSION_NOT_FOUND, f"Session '{payload.session_id}' not found")

        session = Session.model_validate(raw)
        modified = session.model_copy(update={
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "status": SessionStatus.COMPLETED,
        })
        await kv.set(KV.sessions, payload.session_id, modified.model_dump())

        return Response(status_code=200, body=ApiSuccess(data=SessionEndResponse(success=True)))

    return router
```

- [ ] **Step 4: Create `triggers/routes/__init__.py`** (session only — bridge added in Task 5)

```python
# triggers/routes/__init__.py
from triggers.routes.session import session_router

__all__ = ["session_router"]
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
python -m pytest tests/triggers/test_routes_session.py -v
```
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add triggers/routes/ tests/triggers/test_routes_session.py
git commit -m "feat: add session routes (start, end) using ApiRouter"
```

---

## Task 5: Bridge routes (observe, summarize, claude-bridge-sync)

**Files:**
- Create: `triggers/routes/bridge.py`

- [ ] **Step 1: Implement `triggers/routes/bridge.py`**

No new test file needed — the `IIIAdapter` tests already cover the wrapping; bridge handlers are thin pass-throughs to existing `mem::*` functions.

```python
# triggers/routes/bridge.py
from typing import List
from pydantic import BaseModel

from schema.domain import HookPayload
from triggers.router import ApiRouter, ApiSuccess, Middleware, Request, Response


class SummarizePayload(BaseModel):
    session_id: str


def bridge_router(sdk, middleware: List[Middleware] = []) -> ApiRouter:
    from iii import TriggerRequest

    router = ApiRouter(prefix="graphmind", middleware=middleware)

    @router.post("observe", "api::observe", HookPayload)
    async def handle_observe(req: Request[HookPayload]) -> Response:
        result = await sdk.trigger_async(TriggerRequest(
            function_id="mem::observe",
            payload=req.body,
        ))
        return Response(status_code=201, body=ApiSuccess(data=result))

    @router.post("summarize", "api::summarize", SummarizePayload)
    async def handle_summarize(req: Request[SummarizePayload]) -> Response:
        result = await sdk.trigger_async(TriggerRequest(
            function_id="mem::summarize",
            payload=req.body,
        ))
        return Response(status_code=200, body=ApiSuccess(data=result))

    @router.post("claude-bridge/sync", "api::claude-bridge::sync", None)
    async def handle_claude_bridge_sync(req: Request) -> Response:
        result = await sdk.trigger_async(TriggerRequest(
            function_id="mem::claude-bridge::sync",
            payload={},
        ))
        return Response(status_code=200, body=ApiSuccess(data=result))

    return router
```

- [ ] **Step 2: Update `triggers/routes/__init__.py` to add `bridge_router`**

```python
# triggers/routes/__init__.py
from triggers.routes.session import session_router
from triggers.routes.bridge import bridge_router

__all__ = ["session_router", "bridge_router"]
```

- [ ] **Step 3: Run all existing tests to confirm nothing broke**

```bash
python -m pytest tests/ -v
```
Expected: all tests pass

- [ ] **Step 4: Commit**

```bash
git add triggers/routes/bridge.py triggers/routes/__init__.py
git commit -m "feat: add bridge routes (observe, summarize, claude-bridge-sync)"
```

---

## Task 6: Rewire `triggers/api.py` as assembly point

**Files:**
- Modify: `triggers/api.py`

- [ ] **Step 1: Replace `triggers/api.py`**

```python
# triggers/api.py
from typing import Optional, Union

from iii import IIIClient

from providers.resilient import ResilientProvider
from state.kv import StateKV
from triggers.adapters.iii import IIIAdapter
from triggers.middleware import logging_middleware, make_auth_middleware
from triggers.routes.bridge import bridge_router
from triggers.routes.session import session_router


def register_api_triggers(
    sdk: IIIClient,
    kv: StateKV,
    secret: Optional[str] = None,
    provider: Optional[Union[ResilientProvider, dict]] = None,
) -> None:
    middleware = [logging_middleware]
    if secret:
        middleware.append(make_auth_middleware(secret))

    adapter = IIIAdapter()
    adapter.register(sdk, [
        session_router(kv, sdk, middleware=middleware),
        bridge_router(sdk, middleware=middleware),
    ])
```

- [ ] **Step 2: Run all tests**

```bash
python -m pytest tests/ -v
```
Expected: all tests pass

- [ ] **Step 3: Commit**

```bash
git add triggers/api.py
git commit -m "refactor: rewire api.py as clean assembly point using adapter + routers"
```

---

## Task 7: Final integration check

- [ ] **Step 1: Run full test suite**

```bash
python -m pytest tests/ -v --tb=short
```
Expected: all tests pass, no warnings

- [ ] **Step 2: Verify `main.py` still calls `register_api_triggers` correctly**

`main.py` calls `register_api_triggers(sdk, kv)` — signature unchanged, no modification needed.

- [ ] **Step 3: Final commit**

```bash
git add .
git commit -m "feat: framework-agnostic router complete — ApiRouter, IIIAdapter, typed errors, middleware"
```
