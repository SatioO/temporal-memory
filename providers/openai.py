from typing import Final
from schema import MemoryProvider
from logger import get_logger
from openai import AsyncOpenAI

logger = get_logger("provider::openai")


class OpenAIProvider(MemoryProvider):
    name: Final[str] = "openai"

    def __init__(self, api_key: str, model: str, max_tokens: int):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    async def summarize(self, system_prompt: str, user_prompt: str) -> str:
        logger.info("provider::openai::summarize")
        return await self._call(system_prompt, user_prompt)

    async def compress(self, system_prompt: str, user_prompt: str) -> str:
        logger.info("provider::openai::compress")
        return await self._call(system_prompt, user_prompt)

    async def _call(self, system_prompt: str, user_prompt: str):
        response = await self.client.chat.completions.create(
            max_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=self.model,
        )

        return response.choices[0].message.content or ""
