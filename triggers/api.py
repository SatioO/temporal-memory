import asyncio
from datetime import datetime, timezone
from typing import Optional, Union
from iii import ApiRequest, IIIClient, RegisterFunctionInput, RegisterTriggerInput, Logger, ApiResponse, TriggerRequest
from pydantic import BaseModel

from functions.claude_bridge import ClaudeBridgeSyncResult
from functions.context import ContextHandlerParams, ContextResult
from schema import Session, SessionStatus
from providers.resilient import ResilientProvider
from schema.domain import HookPayload
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


class SummarizePayload(BaseModel):
    session_id: str


def register_api_triggers(
    sdk: IIIClient,
    kv: StateKV,
    # TODO: handle authentication for requests
    secret: Optional[str] = None,
    provider: Optional[Union[ResilientProvider, dict]] = None
):
    logger = Logger()

    async def handle_observe(req_raw: ApiRequest[HookPayload]) -> ApiResponse:
        req = ApiRequest(**req_raw)
        payload = HookPayload(**req.body)

        try:
            result = await sdk.trigger_async(TriggerRequest(
                function_id="mem::observe",
                payload=payload
            ))
            return ApiResponse(statusCode=201, body=result)
        except Exception as err:
            return ApiResponse(statusCode=500, body={"success": False, "error": str(err)})

    async def handle_summarize(req_raw: ApiRequest[SummarizePayload]) -> ApiResponse:
        req = ApiRequest(**req_raw)
        payload = SummarizePayload(**req.body)

        try:
            result = await sdk.trigger_async(TriggerRequest(
                function_id="mem::summarize",
                payload=payload
            ))
            return ApiResponse(statusCode=200, body=result)
        except Exception as err:
            return ApiResponse(statusCode=500, body={"success": False, "error": str(err)})

    async def handle_claude_bridge_sync(req_raw: ApiRequest) -> ApiResponse[ClaudeBridgeSyncResult]:
        try:
            result = await sdk.trigger_async(TriggerRequest(
                function_id="mem::claude-bridge::sync",
                payload={}
            ))
            return ApiResponse(statusCode=200, body=result)
        except Exception as err:
            return ApiResponse(statusCode=500, body=ClaudeBridgeSyncResult(success=False, error=str(err)))

    async def handle_session_start(req_raw: ApiRequest[SessionStartPayload]) -> ApiResponse[SessionStartResponse]:
        req = ApiRequest(**req_raw)
        payload = SessionStartPayload(**req.body)

        session = Session(
            id=payload.session_id,
            project=payload.project,
            cwd=payload.cwd,
            model=payload.model,
            started_at=datetime.now(timezone.utc).isoformat(),
            status=SessionStatus.ACTIVE,
            observation_count=0
        )

        _, context_result_raw = await asyncio.gather(
            kv.set(KV.sessions, payload.session_id, session.model_dump()),
            sdk.trigger_async(TriggerRequest(
                function_id="mem::context",
                payload=ContextHandlerParams(
                    session_id=payload.session_id,
                    project=payload.project
                )
            ))
        )

        logger.debug(f"[graphmind] Created session: {payload.session_id}")
        parsed_context = ContextResult(**context_result_raw)

        return ApiResponse(
            statusCode=200,
            body=SessionStartResponse(
                session=session,
                context=parsed_context.context
            ).model_dump(),
        )

    async def handle_session_end(req_raw: ApiRequest[SessionEndPayload]) -> ApiResponse[SessionEndResponse]:
        req = ApiRequest(**req_raw)
        payload = SessionEndPayload(**req.body)

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
        logger.debug(f"[graphmind] Ended session: {payload.session_id}")

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

    sdk.register_function(
        RegisterFunctionInput(id="api::claude-bridge::sync"),
        handle_claude_bridge_sync,
    )

    sdk.register_trigger(
        RegisterTriggerInput(
            type="http",
            function_id="api::claude-bridge::sync",
            config={
                "api_path": "graphmind/claude-bridge/sync",
                "http_method": "POST"
            }
        )
    )

    sdk.register_function(
        RegisterFunctionInput(id="api::summarize"),
        handle_summarize,
    )

    sdk.register_trigger(
        RegisterTriggerInput(
            type="http",
            function_id="api::summarize",
            config={
                "api_path": "graphmind/summarize",
                "http_method": "POST"
            }
        )
    )

    sdk.register_function(
        RegisterFunctionInput(id="api::observe"),
        handle_observe,
    )

    sdk.register_trigger(
        RegisterTriggerInput(
            type="http",
            function_id="api::observe",
            config={
                "api_path": "graphmind/observe",
                "http_method": "POST"
            }
        )
    )
