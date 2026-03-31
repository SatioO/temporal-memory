
from typing import Awaitable, Callable
from schema import MemoryProvider
from providers.circuit_breaker import CircuitBreaker


class ResilientProvider(MemoryProvider):
    def __init__(self, inner: MemoryProvider):
        self.inner = inner
        self.name = f"resilient({inner.name})"
        self.circuit_breaker = CircuitBreaker()

    async def compress(self, system_prompt: str, user_prompt: str) -> str:
        return await self._call(lambda: self.inner.compress(system_prompt, user_prompt))

    async def summarize(self, system_prompt: str, user_prompt: str) -> str:
        return await self._call(lambda: self.inner.summarize(system_prompt, user_prompt))

    async def _call(self, fn: Callable[[], Awaitable[str]]) -> str:
        if not self.circuit_breaker.is_allowed:
            raise Exception("circuit_breaker_open")

        try:
            result = await fn()
            self.circuit_breaker.record_success()
            return result

        except Exception as err:
            self.circuit_breaker.record_failures()
            raise err
