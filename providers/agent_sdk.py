from typing import Final
from schema import MemoryProvider
from logger import get_logger
from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

logger = get_logger("provider::agent-sdk")


class AgentSDKProvider(MemoryProvider):
    name: Final[str] = "agent-sdk"

    def __init__(self, model: str, max_tokens: int):
        self.model = model
        self.max_tokens = max_tokens

    async def summarize(self, system_prompt: str, user_prompt: str) -> str:
        logger.info("provider::agent-sdk::summarize")
        return await self._call(system_prompt, user_prompt)

    async def compress(self, system_prompt: str, user_prompt: str) -> str:
        logger.info("provider::agent-sdk::compress")
        return await self._call(system_prompt, user_prompt)

    async def _call(self, system_prompt: str, user_prompt: str) -> str:
        async for message in query(
            prompt=user_prompt,
            options=ClaudeAgentOptions(
                system_prompt=system_prompt,
                model=self.model,
                allowed_tools=[],
                max_turns=1,
            ),
        ):
            if isinstance(message, ResultMessage):
                return message.result or ""
        return ""
