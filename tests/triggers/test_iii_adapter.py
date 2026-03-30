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
