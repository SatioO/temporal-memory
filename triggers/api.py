from datetime import datetime, timezone
import os
from typing import Optional, TypedDict, Union
from iii import ApiRequest, IIIClient, RegisterFunctionInput, RegisterTriggerInput, Logger, ApiResponse

from model import Session
from providers.resilient import ResilientProvider
from state.kv import StateKV
from state.schema import KV
from triggers.utils import bind_handler


class SessionStartPayload(TypedDict):
    session_id: str
    project: str
    cwd: str


async def handle_session_start(req: ApiRequest[SessionStartPayload], kv: StateKV):
    logger = Logger()

    data = req["body"]
    session_id = data.get("session_id")

    if session_id is None:
        return ApiResponse(
            status_code=400,
            body={
                "message": "session_id is required"
            },
        )

    session = Session(
        id=session_id,
        project=data.get("project", os.getcwd()),
        cwd=data.get("cwd"),
        model=data.get("model"),
        started_at=datetime.now(timezone.utc).isoformat(),
        status="active",
        observation_count=0
    )

    await kv.set(KV["sessions"], session_id, session)

    return ApiResponse(
        status_code=200,
        body={
            "app_name": "[graphmind]",
            "message": "Hello request received! Processing in background.",
            "status": "processing",
        },
    )


def register_api_triggers(
    sdk: IIIClient,
    kv: StateKV,
    secret: Optional[str] = None,
    provider: Optional[Union[ResilientProvider, dict]] = None
):

    sdk.register_function(
        RegisterFunctionInput(id="api::session::start"),
        bind_handler(handle_session_start, kv=kv),
    )

    sdk.register_trigger(
        RegisterTriggerInput(
            type="http",
            function_id="api::session::start",
            config={
                "api_path": "graphmind/session/start",
                "http_method": "POST"
            }
        )
    )
