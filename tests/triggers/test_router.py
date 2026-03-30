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
