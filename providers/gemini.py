from typing import Final
from schema import MemoryProvider
from logger import get_logger
from google import genai
from google.genai import types

logger = get_logger("provider::gemini")


class GeminiProvider(MemoryProvider):
    name: Final[str] = "gemini"

    def __init__(self, api_key: str, model: str, max_tokens: int):
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    async def summarize(self, system_prompt: str, user_prompt: str) -> str:
        logger.info("provider::gemini::summarize")
        return await self._call(system_prompt, user_prompt)

    async def compress(self, system_prompt: str, user_prompt: str) -> str:
        logger.info("provider::gemini::compress")
        return await self._call(system_prompt, user_prompt)

    async def _call(self, system_prompt: str, user_prompt: str) -> str:
        response = await self.client.aio.models.generate_content(
            model=self.model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=self.max_tokens,
            ),
        )
        return response.text or ""
