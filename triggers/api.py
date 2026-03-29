from datetime import datetime, timezone
from typing import Optional, Union
from iii import ApiRequest, IIIClient, RegisterFunctionInput, RegisterTriggerInput, Logger, ApiResponse, TriggerRequest
from pydantic import BaseModel

from functions.context import ContextHandlerParams, ContextResult
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
    context: str


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
    async def handle_session_start(req_raw: ApiRequest[SessionStartPayload]) -> ApiResponse[SessionStartResponse]:
        logger = Logger()

        req = ApiRequest(**req_raw)
        if not req.body:
            raise ValueError("Request body missing")

        payload = SessionStartPayload(**req.body)
        print(f"[graphmind] Created Payload: {payload.session_id}")

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

        context_result = await sdk.trigger_async(
            TriggerRequest(
                function_id="mem::context",
                payload=ContextHandlerParams(
                    session_id=payload.session_id,
                    project=payload.project
                )
            )
        )

        parsed_context = ContextResult(**context_result)

        return ApiResponse(
            statusCode=200,
            body=SessionStartResponse(
                session=session,
                context=parsed_context.context
            ).model_dump(),
        )

    async def handle_session_end(req_raw: ApiRequest[SessionEndPayload]) -> ApiResponse[SessionEndResponse]:
        logger = Logger()

        req = ApiRequest(**req_raw)
        if not req.body:
            raise ValueError("Request body missing")

        payload = SessionEndPayload(**req.body)
        print(f"[graphmind] Created Payload: {payload.session_id}")

        raw = await kv.get(KV.sessions, payload.session_id)

        if raw is None:
            return ApiResponse(
                statusCode=404,
                body=SessionEndResponse(success=False).model_dump()
            )

        session = Session.model_validate(raw)
        modified_session = session.model_copy(update={
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "status": SessionStatus.COMPLETED
        })

        await kv.set(KV.sessions, payload.session_id, modified_session.model_dump())

        return ApiResponse(
            statusCode=200,
            body=SessionEndResponse(success=True).model_dump()
        )

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
