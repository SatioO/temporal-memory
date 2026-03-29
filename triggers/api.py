from datetime import datetime, timezone
from typing import Optional, Union
from iii import ApiRequest, IIIClient, RegisterFunctionInput, RegisterTriggerInput, Logger, ApiResponse, TriggerRequest
from pydantic import BaseModel

from functions.context import ContextHandlerParams
from schema import Session, SessionStatus
from providers.resilient import ResilientProvider
from state.kv import StateKV
from state.schema import KV


class SessionStartPayload(BaseModel):
    session_id: str
    project: str
    cwd: str
    model: Optional[str] = None


class SessionStartResponse(BaseModel):
    session: Session


class SessionEndPayload(BaseModel):
    session_id: str


class SessionEndResponse(BaseModel):
    success: bool


def register_api_triggers(
    sdk: IIIClient,
    kv: StateKV,
    secret: Optional[str] = None,
    provider: Optional[Union[ResilientProvider, dict]] = None
):
    async def handle_session_start(req: ApiRequest[SessionStartPayload]) -> ApiResponse[SessionStartResponse]:
        logger = Logger()

        parsed_req = ApiRequest[SessionStartPayload](**req)
        payload = SessionStartPayload(**parsed_req.body)

        session = Session(
            id=payload.session_id,
            project=payload.project,
            cwd=payload.cwd,
            model=payload.model,
            started_at=datetime.now(timezone.utc).isoformat(),
            status=SessionStatus.ACTIVE,
            observation_count=0
        )

        await kv.set(KV.sessions, payload.session_id, session.model_dump())
        logger.debug(f"[graphmind] Created session: {payload.session_id}")

        context_response = await sdk.trigger_async(
            TriggerRequest(
                function_id="mem::context",
                payload=ContextHandlerParams(
                    session_id=payload.session_id,
                    project=payload.project
                )
            )
        )

        print(context_response)

        # parsed = ContextResponse(**context_response)

        return ApiResponse(
            statusCode=200,
            body=SessionStartResponse(session=session).model_dump(),
        )

    async def handle_session_end(req: ApiRequest[SessionEndPayload]) -> ApiResponse[SessionEndResponse]:
        parsed_req = ApiRequest[SessionEndPayload](**req)
        body = SessionEndPayload(**parsed_req.body)

        raw = await kv.get(KV.sessions, body.session_id)
        if raw is None:
            return ApiResponse(statusCode=404, body={"success": False})

        session = Session.model_validate(raw)
        modified_session = session.model_copy(update={
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "status": SessionStatus.COMPLETED
        })

        await kv.set(KV.sessions, body.session_id, modified_session.model_dump())

        return ApiResponse(statusCode=200, body={"success": True})

    sdk.register_function(
        RegisterFunctionInput(id="api::session::start"),
        handle_session_start,
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

    sdk.register_function(
        RegisterFunctionInput(id="api::session::end"),
        handle_session_end,
    )

    sdk.register_trigger(
        RegisterTriggerInput(
            type="http",
            function_id="api::session::end",
            config={
                "api_path": "graphmind/session/end",
                "http_method": "POST"
            }
        )
    )
