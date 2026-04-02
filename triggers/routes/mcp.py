from typing import Any

from mcp_tools.server import MCPRequestPayload
from triggers.router import (
    ApiRouter, Middleware, Request, Response,
)


def mcp_router(sdk: Any, middleware: list[Middleware] = None) -> ApiRouter:
    router = ApiRouter(prefix="graphmind/mcp", middleware=middleware)

    @router.get("tools", "api::tools::list")
    async def handle_mcp_list(req: Request) -> Response:
        print("handle_mcp_list called")
        result = await sdk.trigger_async({
            "function_id": "mcp::tools::list",
            "payload": {}
        })

        return Response(status_code=200, body=result)

    @router.post("call", "api::tools::call", MCPRequestPayload)
    async def handle_mcp_call(req: Request[MCPRequestPayload]) -> Response:
        print("handle_mcp_call called")
        result = await sdk.trigger_async({
            "function_id": "mcp::tools::call",
            "payload": req.body.to_dict(),
        })

        return Response(status_code=200, body=result)

    return router
