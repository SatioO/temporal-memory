from dataclasses import dataclass
from typing import Any

from functions.context import ContextPayload
from functions.file_context import FileContextPayload
from functions.remember import ForgetPayload, RememberPayload
from schema import CompressedObservation
from schema.base import Model
from schema.domain import HookPayload
from state.kv import StateKV
from state.schema import KV
from triggers.router import ApiException, ApiRouter, ErrorCode, Middleware, Request, Response


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
        return Response(status_code=200, body=result)

    @router.post("summarize", "api::summarize", SummarizePayload)
    async def handle_summarize(req: Request[SummarizePayload]) -> Response:
        result = await sdk.trigger_async({
            "function_id": "mem::summarize",
            "payload": req.body.to_dict(),
        })
        return Response(status_code=200, body=result)

    @router.post("context", "api::context", ContextPayload)
    async def handle_context(req: Request[ContextPayload]) -> Response:
        result = await sdk.trigger_async({
            "function_id": "mem::context",
            "payload": req.body.to_dict(),
        })
        return Response(status_code=200, body=result)

    @router.get("observations", "api::observations")
    async def handle_observations(req: Request[None, dict[str, str]]) -> Response:
        session_id = req.path_params.get("session_id")
        if not session_id:
            raise ApiException(ErrorCode.INVALID_PAYLOAD,
                               "session_id is required")

        observations = await kv.list(KV.observations(session_id), CompressedObservation)
        return Response(status_code=200, body={"observations": observations or []})

    @router.post("remember", "api::remember", RememberPayload)
    async def handle_remember(req: Request[RememberPayload]) -> Response:
        result = await sdk.trigger_async({
            "function_id": "mem::remember",
            "payload": req.body.to_dict(),
        })
        return Response(status_code=201, body=result)

    @router.post("forget", "api::forget", ForgetPayload)
    async def handle_remember(req: Request[ForgetPayload]) -> Response:
        result = await sdk.trigger_async({
            "function_id": "mem::forget",
            "payload": req.body.to_dict(),
        })
        return Response(status_code=200, body=result)

    @router.post("file_context", "api::file_context", FileContextPayload)
    async def handle_file_context(req: Request[FileContextPayload]) -> Response:
        result = await sdk.trigger_async({
            "function_id": "mem::file_context",
            "payload": req.body.to_dict(),
        })
        return Response(status_code=200, body=result)

    return router
