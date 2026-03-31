from typing import Callable

try:
    from iii import IIIClient, RegisterFunctionInput, RegisterTriggerInput
except ModuleNotFoundError:
    # Stubs for environments where the iii SDK is not installed (e.g. tests).
    IIIClient = None  # type: ignore[assignment,misc]

    class RegisterFunctionInput:  # type: ignore[no-redef]
        def __init__(self, id: str):
            self.id = id

    class RegisterTriggerInput:  # type: ignore[no-redef]
        def __init__(self, type: str, function_id: str, config: dict):
            self.type = type
            self.function_id = function_id
            self.config = config

from triggers.adapters.base import AbstractAdapter
from triggers.router import (
    ApiError, ApiException, ApiRouter, ErrorCode,
    Middleware, Request, RouteConfig, build_middleware_chain,
)


class IIIAdapter(AbstractAdapter):
    def register(self, sdk: IIIClient, routers: list[ApiRouter]) -> None:
        for router in routers:
            for route in router.routes:
                wrapped = self._wrap(route, router.middleware)
                sdk.register_function(RegisterFunctionInput(
                    id=route.function_id), wrapped)
                sdk.register_trigger(RegisterTriggerInput(
                    type="http",
                    function_id=route.function_id,
                    config={
                        "api_path": route.path,
                        "http_method": route.method,
                    }
                ))

    def _wrap(self, route: RouteConfig, middleware: list[Middleware]) -> Callable:
        chain = build_middleware_chain(middleware, route.handler)

        async def handler(req_raw: dict) -> dict:
            try:
                body = req_raw.get("body", {}) or {}
                headers = req_raw.get("headers", {}) or {}

                if route.payload_type is not None:
                    parsed_body = route.payload_type(**body)
                else:
                    parsed_body = body

                req = Request(body=parsed_body, headers=headers)
                response = await chain(req)
                return response.model_dump()

            except ApiException as e:
                return {"status_code": e.status_code, "body": e.to_error().model_dump()}
            except Exception as e:
                error = ApiError(code=ErrorCode.INTERNAL_ERROR, message=str(e))
                return {"status_code": 500, "body": error.model_dump()}

        return handler
