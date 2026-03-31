from triggers.router import ApiException, ErrorCode, Handler, Middleware, Request, Response


def make_auth_middleware(secret: str) -> Middleware:
    async def auth(req: Request, next: Handler) -> Response:
        if req.headers.get("x-api-key") != secret:
            raise ApiException(ErrorCode.UNAUTHORIZED, "Invalid or missing API key")
        return await next(req)
    return auth
