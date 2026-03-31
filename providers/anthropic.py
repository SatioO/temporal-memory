from typing import Final
from schema import MemoryProvider
from anthropic import Anthropic
from logger import get_logger

logger = get_logger("context")


class AnthropicProvider(MemoryProvider):
    name: Final[str] = "anthropic"

    def __init__(self, api_key: str, model: str, max_tokens: int):
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    async def compress(self, system_prompt: str, user_prompt: str) -> str:
        logger.info("Anthropic provider in action: compress")
        return await self._call(system_prompt, user_prompt)

    async def summarize(self, system_prompt: str, user_prompt: str) -> str:
        logger.info("Anthropic provider in action: summarize")
        return await self._call(system_prompt, user_prompt)

    async def _call(self, system_prompt: str, user_prompt: str):
        response = self.client.messages.create(
            max_tokens=self.max_tokens,
            messages=[
                {
                    "role": "user",
                    "content": user_prompt,
                }
            ],
            system=system_prompt,
            model=self.model,
        )

        text_block = next(
            (b for b in response.content if b.type == "text"),
            None
        )

        return text_block.text if text_block else ""
