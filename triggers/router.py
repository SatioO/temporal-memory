from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Awaitable, Callable, Generic, Optional, TypeVar, overload

from schema.base import to_primitive

T = TypeVar("T")
P = TypeVar("P")
Qs = TypeVar("Qs", default=dict[str, str])  # query params


# --- HTTP types ---

@dataclass
class Request(Generic[T, Qs]):
    body: T
    params: dict[str, str] = field(default_factory=dict)          # SDK metadata (method, path, etc.)
    query_params: Qs = field(default_factory=dict)                # e.g. ?session_id=123 — typed via decorator
    path_params: dict[str, str] = field(default_factory=dict)    # e.g. /sessions/:id
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class ApiSuccess(Generic[T]):
    data: T


@dataclass
class Response(Generic[T]):
    status_code: int
    body: T

    def to_dict(self) -> dict:
        return {
            "status_code": self.status_code,
            "body": to_primitive(self.body),
        }


# --- Error contract ---

class ErrorCode(str, Enum):
    SESSION_NOT_FOUND = "session_not_found"
    INVALID_PAYLOAD = "invalid_payload"
    INTERNAL_ERROR = "internal_error"
    UNAUTHORIZED = "unauthorized"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"


_STATUS_MAP: dict[ErrorCode, int] = {
    ErrorCode.SESSION_NOT_FOUND: 404,
    ErrorCode.INVALID_PAYLOAD:   400,
    ErrorCode.INTERNAL_ERROR:    500,
    ErrorCode.UNAUTHORIZED:      401,
    ErrorCode.NOT_FOUND:         404,
    ErrorCode.CONFLICT:          409,
}


@dataclass(frozen=True)
class ApiError:
    code: ErrorCode
    message: str
    details: Optional[dict] = None

    def to_dict(self) -> dict:
        return to_primitive(self)


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
Handler = Callable[[Request], Awaitable[Response]]
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
class RouteConfig(Generic[T, Qs]):
    path: str
    method: str
    function_id: str
    handler: Callable[[Request[T, Qs]], Awaitable[Response]]
    payload_type: Optional[type[T]]
    params_type: Optional[type[Qs]]


class ApiRouter:
    def __init__(self, prefix: str, middleware: list[Middleware] | None = None):
        self.middleware = middleware if middleware is not None else []
        self.prefix = prefix
        self.routes: list[RouteConfig] = []

    @overload
    def post(self, path: str, function_id: str, payload_type: type[P]) -> Callable[[Callable[[Request[P, dict[str, str]]], Awaitable[Response]]], Callable[[Request[P, dict[str, str]]], Awaitable[Response]]]: ...
    @overload
    def post(self, path: str, function_id: str, payload_type: None = None) -> Callable[[Handler], Handler]: ...

    def post(self, path: str, function_id: str, payload_type=None):
        def decorator(handler):
            self.routes.append(RouteConfig(
                path=f"{self.prefix}/{path}",
                method="POST",
                function_id=function_id,
                handler=handler,
                payload_type=payload_type,
                params_type=None,
            ))
            return handler
        return decorator

    @overload
    def get(self, path: str, function_id: str, params_type: type[Qs]) -> Callable[[Callable[[Request[None, Qs]], Awaitable[Response]]], Callable[[Request[None, Qs]], Awaitable[Response]]]: ...
    @overload
    def get(self, path: str, function_id: str, params_type: None = None) -> Callable[[Handler], Handler]: ...

    def get(self, path: str, function_id: str, params_type=None):
        def decorator(handler):
            self.routes.append(RouteConfig(
                path=f"{self.prefix}/{path}",
                method="GET",
                function_id=function_id,
                handler=handler,
                payload_type=None,
                params_type=params_type,
            ))
            return handler
        return decorator
