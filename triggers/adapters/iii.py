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
                params = req_raw.get("params", {}) or {}
                query_params_raw = req_raw.get("query_params", {}) or {}
                path_params = req_raw.get("path_params", {}) or {}

                parsed_body = route.payload_type.from_dict(body) if route.payload_type else body
                parsed_query = route.params_type.from_dict(query_params_raw) if route.params_type else query_params_raw

                req = Request(
                    body=parsed_body,
                    params=params,
                    query_params=parsed_query,
                    path_params=path_params,
                    headers=headers,
                )
                response = await chain(req)
                return response.to_dict()

            except ApiException as e:
                return {"status_code": e.status_code, "body": e.to_error().to_dict()}
            except Exception as e:
                error = ApiError(code=ErrorCode.INTERNAL_ERROR, message=str(e))
                return {"status_code": 500, "body": error.to_dict()}

        return handler
