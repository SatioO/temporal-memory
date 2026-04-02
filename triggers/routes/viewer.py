import os

from triggers.router import ApiRouter, Middleware, Request, Response


def viewer_router(middleware: list[Middleware] = None) -> ApiRouter:
    router = ApiRouter(prefix="graphmind", middleware=middleware)

    _html_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "viewer", "index.html"
    )

    @router.get("viewer", "api::viewer::index")
    async def handle_viewer(_req: Request) -> Response:
        with open(_html_path, "r", encoding="utf-8") as f:
            html = f.read()
        return Response(status_code=200, body=html)

    return router
