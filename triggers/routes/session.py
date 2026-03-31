import asyncio
from datetime import datetime, timezone
from typing import Any, Optional
from pydantic import BaseModel
from state.kv import StateKV

from schema import Session, SessionStatus
from state.schema import KV
from triggers.router import (
    ApiException, ApiRouter, ErrorCode,
    Middleware, Request, Response,
)


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


class _ContextHandlerParams(BaseModel):
    session_id: str
    project: str
    budget: Optional[int] = None


class _ContextResult(BaseModel):
    context: str


def session_router(kv: StateKV, sdk: Any, middleware: list[Middleware] = None) -> ApiRouter:
    router = ApiRouter(prefix="graphmind/session", middleware=middleware)

    @router.post("start", "api::session::start", SessionStartPayload)
    async def handle_session_start(req: Request[SessionStartPayload]) -> Response:
        payload = req.body
        session = Session(
            id=payload.session_id,
            project=payload.project,
            cwd=payload.cwd,
            model=payload.model,
            started_at=datetime.now(timezone.utc).isoformat(),
            status=SessionStatus.ACTIVE,
            observation_count=0,
        )

        _, context_result_raw = await asyncio.gather(
            kv.set(KV.sessions, payload.session_id, session.model_dump()),
            sdk.trigger_async({
                "function_id": "mem::context",
                "payload": _ContextHandlerParams(
                    session_id=payload.session_id,
                    project=payload.project)
            })
        )

        parsed_context = _ContextResult(**context_result_raw)
        return Response(
            status_code=200,
            body=SessionStartResponse(
                session=session, context=parsed_context.context),
        )

    @router.post("end", "api::session::end", SessionEndPayload)
    async def handle_session_end(req: Request[SessionEndPayload]) -> Response:
        payload = req.body
        raw = await kv.get(KV.sessions, payload.session_id)

        if raw is None:
            raise ApiException(ErrorCode.SESSION_NOT_FOUND,
                               f"Session '{payload.session_id}' not found")

        session = Session.model_validate(raw)
        modified = session.model_copy(update={
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "status": SessionStatus.COMPLETED,
        })
        await kv.set(KV.sessions, payload.session_id, modified.model_dump())

        return Response(status_code=200, body=SessionEndResponse(success=True))

    return router
