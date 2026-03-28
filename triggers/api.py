from typing import Optional, TypedDict, Union
from iii import ApiRequest, IIIClient, RegisterFunctionInput, RegisterTriggerInput, Logger, ApiResponse

from providers.resilient import ResilientProvider
from state.kv import StateKV


class SessionStartPayload(TypedDict):
    session_id: str
    project: str
    cwd: str


def handle_session_start(req: ApiRequest[SessionStartPayload]):
    logger = Logger()

    return ApiResponse(
        status_code=200,
        body={
            "message": "Hello request received! Processing in background.",
            "status": "processing",
            "appName": "graphmind",
        },
    )


def handle_liveness():
    return {
        "status_code": 200,
        "body": {"status": "ok", "service": "graphmind"},
    }


def hello_api(data) -> ApiResponse:
    logger = Logger()
    print(data)
    app_name = "III App"

    logger.info("Hello API called", {"appName": app_name})

    return ApiResponse(
        status_code=200,
        body={
            "message": "Hello request received! Processing in background.",
            "status": "processing",
            "appName": app_name,
        },
    )


def register_api_triggers(
    sdk: IIIClient,
    kv: StateKV,
    secret: Optional[str] = None,
    provider: Optional[Union[ResilientProvider, dict]] = None
):

    sdk.register_function({"id": "hello::api"}, hello_api)
    sdk.register_trigger({
        "type": "http",
        "function_id": "hello::api",
        "config": {"api_path": "hello", "http_method": "GET"},
    })

    sdk.register_function(
        RegisterFunctionInput(id="api::session::start"),
        handle_session_start
    )

    sdk.register_trigger(
        RegisterTriggerInput(
            type="http",
            function_id="api::session::start",
            config={
                "api_path": "graphmind/session/start",
                "http_method": "POST"
            }
        )
    )
