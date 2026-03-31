from typing import Any
from pydantic import BaseModel

from schema.domain import HookPayload
from triggers.router import ApiRouter, Middleware, Request, Response


class SummarizePayload(BaseModel):
    session_id: str


def bridge_router(sdk: Any, middleware: list[Middleware] = None) -> ApiRouter:
    router = ApiRouter(prefix="graphmind", middleware=middleware)

    @router.post("observe", "api::observe", HookPayload)
    async def handle_observe(req: Request[HookPayload]) -> Response:
        result = await sdk.trigger_async({
            "function_id": "mem::observe",
            "payload": req.body,
        })
        return Response(status_code=201, body=result)

    @router.post("summarize", "api::summarize", SummarizePayload)
    async def handle_summarize(req: Request[SummarizePayload]) -> Response:
        result = await sdk.trigger_async({
            "function_id": "mem::summarize",
            "payload": req.body,
        })
        return Response(status_code=201, body=result)

    @router.post("claude-bridge/sync", "api::claude-bridge-sync", None)
    async def handle_claude_bridge_sync(_: Request) -> Response:
        result = await sdk.trigger_async({
            "function_id": "mem::claude-bridge-sync",
            "payload": {},
        })
        return Response(status_code=200, body=result)

    return router
