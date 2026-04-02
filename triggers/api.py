# triggers/api.py
from typing import Optional, Union

from providers.resilient import ResilientProvider
from state.kv import StateKV
from triggers.adapters.iii import IIIAdapter
from triggers.middleware import logging_middleware, make_auth_middleware
from triggers.routes.bridge import bridge_router
from triggers.routes.mcp import mcp_router
from triggers.routes.session import session_router


def register_api_triggers(
    sdk,
    kv: StateKV,
    secret: Optional[str] = None,
    provider: Optional[Union[ResilientProvider, dict]] = None,
) -> None:
    middleware = [logging_middleware]
    # if secret:
    #     middleware.append(make_auth_middleware(secret))

    adapter = IIIAdapter()
    adapter.register(sdk, [
        session_router(kv, sdk, middleware=middleware),
        bridge_router(sdk, middleware=middleware),
        mcp_router(sdk, middleware=middleware)
    ])
