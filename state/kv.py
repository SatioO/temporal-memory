from typing import Optional, TypeVar
from iii import IIIClient, TriggerRequest

T = TypeVar("T")


class StateKV:
    def __init__(self, sdk: IIIClient) -> None:
        self.sdk = sdk

    async def get(self, scope: str, key: str, type: type[T]) -> Optional[T]:
        result = await self.sdk.trigger_async(TriggerRequest(function_id="state::get", payload={"scope": scope, "key": key}))
        if result is None:
            return None
        if isinstance(result, dict) and hasattr(type, "from_dict"):
            return type.from_dict(result)
        return result

    async def set(self, scope: str, key: str, value: T) -> T:
        return await self.sdk.trigger_async(TriggerRequest(function_id="state::set", payload={"scope": scope, "key": key, "value": value}))

    async def delete(self, scope: str, key: str) -> None:
        return await self.sdk.trigger_async(TriggerRequest(function_id="state::delete", payload={"scope": scope, "key": key}))

    def _deserialize_list(self, results, type: type[T]) -> list[T]:
        if not results:
            return []
        if not hasattr(type, "from_dict"):
            return results
        out = []
        for r in results:
            if not isinstance(r, dict):
                out.append(r)
                continue
            try:
                out.append(type.from_dict(r))
            except (TypeError, KeyError, ValueError):
                pass
        return out

    async def get_group(self, scope: str, type: type[T]) -> list[T]:
        results = await self.sdk.trigger_async(TriggerRequest(function_id="state::list", payload={"scope": scope}))
        return self._deserialize_list(results, type)

    async def list(self, scope: str, type: type[T]) -> list[T]:
        results = await self.sdk.trigger_async(TriggerRequest(function_id='state::list', payload={"scope": scope}))
        return self._deserialize_list(results, type)
