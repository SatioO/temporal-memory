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
async def test_logging_middleware_passes_through(caplog):
    import logging
    req = Request(body={})
    with caplog.at_level(logging.DEBUG, logger="graphmind"):
        response = await logging_middleware(req, ok_handler)
    assert response.status_code == 200
    assert len(caplog.records) == 2
