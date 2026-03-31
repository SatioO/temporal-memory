import asyncio
import dataclasses
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

try:
    from iii import TriggerRequest
except ModuleNotFoundError:
    class TriggerRequest:  # type: ignore[no-redef]
        def __init__(self, function_id: str, payload: Any):
            self.function_id = function_id
            self.payload = payload

from schema import Session, SessionStatus
from schema.base import Model
from state.schema import KV
from triggers.router import (
    ApiException, ApiRouter, ApiSuccess, ErrorCode,
    Middleware, Request, Response,
)

if TYPE_CHECKING:
    from state.kv import StateKV


@dataclass(frozen=True)
class SessionStartPayload(Model):
    session_id: str
    project: str
    cwd: str
    model: Optional[str] = None


@dataclass(frozen=True)
class SessionStartResponse(Model):
    session: Session
    context: str


@dataclass(frozen=True)
class SessionEndPayload(Model):
    session_id: str


@dataclass(frozen=True)
class SessionEndResponse(Model):
    success: bool


@dataclass(frozen=True)
class _ContextHandlerParams(Model):
    session_id: str
    project: str
    budget: Optional[int] = None


@dataclass(frozen=True)
class _ContextResult(Model):
    context: str


def session_router(kv: "StateKV", sdk: Any, middleware: list[Middleware] = None) -> ApiRouter:
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
            kv.set(KV.sessions, payload.session_id, session.to_dict()),
            sdk.trigger_async(TriggerRequest(
                function_id="mem::context",
                payload=_ContextHandlerParams(
                    session_id=payload.session_id,
                    project=payload.project,
                ).to_dict(),
            ))
        )

        parsed_context = _ContextResult.from_dict(context_result_raw)
        return Response(
            status_code=200,
            body=ApiSuccess(data=SessionStartResponse(session=session, context=parsed_context.context)),
        )

    @router.post("end", "api::session::end", SessionEndPayload)
    async def handle_session_end(req: Request[SessionEndPayload]) -> Response:
        payload = req.body
        raw = await kv.get(KV.sessions, payload.session_id)

        if raw is None:
            raise ApiException(ErrorCode.SESSION_NOT_FOUND, f"Session '{payload.session_id}' not found")

        session = Session.from_dict(raw)
        modified = dataclasses.replace(
            session,
            ended_at=datetime.now(timezone.utc).isoformat(),
            status=SessionStatus.COMPLETED,
        )
        await kv.set(KV.sessions, payload.session_id, modified.to_dict())

        return Response(status_code=200, body=ApiSuccess(data=SessionEndResponse(success=True)))

    return router
