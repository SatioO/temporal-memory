from typing import Awaitable, Callable, List
from model import MemoryProvider


class FallbackChain(MemoryProvider):
    def __init__(self, providers: List[MemoryProvider]):
        self.name = f"fallback({"->".join([provider.name for provider in providers])})"

    async def compress(self, system_prompt: str, user_prompt: str) -> str:
        return await self.tryAll(lambda: self.compress(system_prompt, user_prompt))

    async def summarize(self, system_prompt: str, user_prompt: str) -> str:
        return await self.tryAll(lambda: self.summarize(system_prompt, user_prompt))

    async def tryAll(self, fn: Callable[[MemoryProvider],  Awaitable[str]]) -> str:
        last_error: Exception | None = None

        for provider in self.providers:
            try:
                return await fn(provider)
            except Exception as err:
                last_error = err if isinstance(
                    err, Exception) else Exception(str(err))

        raise last_error or Exception("No providers available")
