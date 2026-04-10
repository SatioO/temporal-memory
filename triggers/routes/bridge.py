from dataclasses import dataclass
from typing import Any

from iii import TriggerRequest
from functions.auto_forget import AutoForgetPayload
from functions.consolidate import ConsolidatePayload
from functions.context import ContextPayload
from functions.enrich import EnrichPayload
from functions.file_context import FileContextPayload
from functions.remember import ForgetPayload, RememberPayload
from functions.search import SearchPayload
from functions.smart_search import SmartSearchPayload
from functions.timeline import TimelinePayload
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
        result = await sdk.trigger_async(TriggerRequest(
            function_id="mem::observe",
            payload=req.body.to_dict(),
        ))
        return Response(status_code=200, body=result)

    @router.post("consolidate", "api::consolidate", ConsolidatePayload)
    async def handle_consolidate(req: Request[ConsolidatePayload]) -> Response:
        result = await sdk.trigger_async(TriggerRequest(
            function_id="mem::consolidate",
            payload=req.body.to_dict(),
        ))
        return Response(status_code=200, body=result)

    @router.post("compress", "api::compress", HookPayload)
    async def handle_compress(req: Request[HookPayload]) -> Response:
        result = await sdk.trigger_async(TriggerRequest(
            function_id="mem::compress",
            payload=req.body.to_dict(),
        ))
        return Response(status_code=200, body=result)

    @router.post("summarize", "api::summarize", SummarizePayload)
    async def handle_summarize(req: Request[SummarizePayload]) -> Response:
        result = await sdk.trigger_async(TriggerRequest(
            function_id="mem::summarize",
            payload=req.body.to_dict(),
        ))
        return Response(status_code=200, body=result)

    @router.post("context", "api::context", ContextPayload)
    async def handle_context(req: Request[ContextPayload]) -> Response:
        result = await sdk.trigger_async(TriggerRequest(
            function_id="mem::context",
            payload=req.body.to_dict(),
        ))
        return Response(status_code=200, body=result)

    @router.get("observations", "api::observations")
    async def handle_observations(req: Request[None, dict[str, str]]) -> Response:
        session_id = req.query_params.get("session_id")
        if not session_id:
            raise ApiException(ErrorCode.INVALID_PAYLOAD,
                               "session_id is required")

        observations = await kv.list(KV.observations(session_id), CompressedObservation)
        return Response(status_code=200, body={"observations": observations or []})

    @router.post("remember", "api::remember", RememberPayload)
    async def handle_remember(req: Request[RememberPayload]) -> Response:
        result = await sdk.trigger_async(TriggerRequest(
            function_id="mem::remember",
            payload=req.body.to_dict(),
        ))
        return Response(status_code=201, body=result)

    @router.post("forget", "api::forget", ForgetPayload)
    async def handle_forget(req: Request[ForgetPayload]) -> Response:
        result = await sdk.trigger_async(TriggerRequest(
            function_id="mem::forget",
            payload=req.body.to_dict(),
        ))
        return Response(status_code=200, body=result)

    @router.post("enrich", "api::enrich", EnrichPayload)
    async def handle_enrich(req: Request[EnrichPayload]) -> Response:
        body = req.body
        if not body.files or not all(isinstance(f, str) for f in body.files):
            raise ApiException(ErrorCode.INVALID_PAYLOAD,
                               "files (string[]) must be a non-empty array of strings")
        if body.terms is not None and not all(isinstance(t, str) for t in body.terms):
            raise ApiException(ErrorCode.INVALID_PAYLOAD,
                               "terms must be an array of strings")

        result = await sdk.trigger_async(TriggerRequest(
            function_id="mem::enrich",
            payload=req.body.to_dict(),
        ))
        return Response(status_code=200, body=result)

    @router.post("file_context", "api::file_context", FileContextPayload)
    async def handle_file_context(req: Request[FileContextPayload]) -> Response:
        result = await sdk.trigger_async(TriggerRequest(
            function_id="mem::file_context",
            payload=req.body.to_dict(),
        ))
        return Response(status_code=200, body=result)

    @router.post("search", "api::search", SearchPayload)
    async def handle_search(req: Request[SearchPayload]) -> Response:
        result = await sdk.trigger_async(TriggerRequest(
            function_id="mem::search",
            payload=req.body.to_dict(),
        ))
        return Response(status_code=200, body=result)

    @router.post("smart_search", "api::smart_search", SmartSearchPayload)
    async def handle_smart_search(req: Request[SmartSearchPayload]) -> Response:
        result = await sdk.trigger_async(TriggerRequest(
            function_id="mem::smart-search",
            payload=req.body.to_dict(),
        ))
        return Response(status_code=200, body=result)

    @router.post("timeline", "api::timeline", TimelinePayload)
    async def handle_timeline(req: Request[TimelinePayload]) -> Response:
        result = await sdk.trigger_async(TriggerRequest(
            function_id="mem::timeline",
            payload=req.body.to_dict(),
        ))
        return Response(status_code=200, body=result)

    @router.post("auto_forget", "api::auto_forget", AutoForgetPayload)
    async def handle_auto_forget(req: Request[AutoForgetPayload]) -> Response:
        result = await sdk.trigger_async(TriggerRequest(
            function_id="mem::auto_forget",
            payload=req.body.to_dict(),
        ))
        return Response(status_code=200, body=result)

    return router
