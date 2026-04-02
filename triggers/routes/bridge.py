from dataclasses import dataclass
from typing import Any

from functions.context import ContextPayload
from schema.base import Model
from schema.domain import HookPayload
from state.kv import StateKV
from state.schema import KV
from triggers.router import ApiRouter, Middleware, Request, Response


@dataclass(frozen=True)
class SummarizePayload(Model):
    session_id: str


@dataclass(frozen=True)
class ObservationsPayload(Model):
    session_id: str


def bridge_router(sdk: Any, kv: StateKV, middleware: list[Middleware] = None) -> ApiRouter:
    router = ApiRouter(prefix="graphmind", middleware=middleware)

    @router.post("observe", "api::observe", HookPayload)
    async def handle_observe(req: Request[HookPayload]) -> Response:
        result = await sdk.trigger_async({
            "function_id": "mem::observe",
            "payload": req.body.to_dict(),
        })
        return Response(status_code=200, body=result)

    @router.post("compress", "api::compress", HookPayload)
    async def handle_compress(req: Request[HookPayload]) -> Response:
        result = await sdk.trigger_async({
            "function_id": "mem::compress",
            "payload": req.body.to_dict(),
        })
        return {"status_code": 200, "body": result}

    @router.post("summarize", "api::summarize", SummarizePayload)
    async def handle_summarize(req: Request[SummarizePayload]) -> Response:
        result = await sdk.trigger_async({
            "function_id": "mem::summarize",
            "payload": req.body.to_dict(),
        })
        return {"status_code": 200, "body": result}

    @router.post("context", "api::context", ContextPayload)
    async def handle_context(req: Request[ContextPayload]) -> Response:
        result = await sdk.trigger_async({
            "function_id": "mem::context",
            "payload": req.body.to_dict(),
        })
        return {"status_code": 200, "body": result}

    return router
