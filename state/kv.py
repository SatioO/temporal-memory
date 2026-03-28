from typing import Any, TypeVar
from iii import IIIClient, TriggerRequest

T = TypeVar("T")


class StateKV:
    def __init__(self, sdk: IIIClient) -> None:
        self.sdk = sdk

    async def get(self, scope: str, key: str) -> Any | None:
        return await self.sdk.trigger_async(TriggerRequest(function_id="state::get", payload={"scope": scope, "key": key}))

    async def set(self, scope: str, key: str, value: Any) -> Any:
        return await self.sdk.trigger_async(TriggerRequest(function_id="state::set", payload={"scope": scope, "key": key, "value": value}))

    async def delete(self, scope: str, key: str) -> None:
        return await self.sdk.trigger_async(TriggerRequest(function_id="state::delete", payload={"scope": scope, "key": key}))

    async def get_group(self, scope: str) -> list[Any]:
        return await self.sdk.trigger_async(TriggerRequest(function_id="state::list", payload={"scope": scope}))
