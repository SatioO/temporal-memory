from dataclasses import dataclass
from typing import Any, Optional

try:
    from iii import TriggerRequest
except ModuleNotFoundError:
    class TriggerRequest:  # type: ignore[no-redef]
        def __init__(self, function_id: str, payload: Any):
            self.function_id = function_id
            self.payload = payload

from schema.base import Model
from schema.domain import HookPayload
from triggers.router import ApiRouter, ApiSuccess, Middleware, Request, Response


@dataclass(frozen=True)
class SummarizePayload(Model):
    session_id: str


def bridge_router(sdk: Any, middleware: list[Middleware] = None) -> ApiRouter:
    router = ApiRouter(prefix="graphmind", middleware=middleware)

    @router.post("observe", "api::observe", HookPayload)
    async def handle_observe(req: Request[HookPayload]) -> Response:
        result = await sdk.trigger_async(TriggerRequest(
            function_id="mem::observe",
            payload=req.body.to_dict(),
        ))
        return Response(status_code=201, body=ApiSuccess(data=result))

    @router.post("summarize", "api::summarize", SummarizePayload)
    async def handle_summarize(req: Request[SummarizePayload]) -> Response:
        result = await sdk.trigger_async(TriggerRequest(
            function_id="mem::summarize",
            payload=req.body.to_dict(),
        ))
        return Response(status_code=200, body=ApiSuccess(data=result))

    @router.post("claude-bridge/sync", "api::claude-bridge::sync", None)
    async def handle_claude_bridge_sync(req: Request) -> Response:
        result = await sdk.trigger_async(TriggerRequest(
            function_id="mem::claude-bridge::sync",
            payload={},
        ))
        return Response(status_code=200, body=ApiSuccess(data=result))

    return router
