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
