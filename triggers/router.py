from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Awaitable, Callable, Generic, Optional, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


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
    def __init__(self, prefix: str, middleware: list[Middleware] | None = None):
        self.middleware = middleware if middleware is not None else []
        self.prefix = prefix
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
