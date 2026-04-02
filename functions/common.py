import asyncio
from typing import Any, Callable, Coroutine, Optional

_locks: dict[str, asyncio.Lock] = {}


async def with_keyed_lock(key: str, fn: Callable[[], Coroutine[Any, Any, Any]]):
    if key not in _locks:
        _locks[key] = asyncio.Lock()
    async with _locks[key]:
        return await fn()
