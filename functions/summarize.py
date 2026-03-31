from state.schema import KV
from state.kv import StateKV
from schema.domain import CompressedObservation, MemoryProvider
from schema.base import Model
from prompts.summary import SUMMARY_SYSTEM_PROMPT, build_summary_prompt
from dataclasses import dataclass
from typing import Optional

from iii import IIIClient
from logger import get_logger

logger = get_logger("summarize")


@dataclass(frozen=True)
class SummarizationParams(Model):
    session_id: str


@dataclass(frozen=True)
class SummarizationResult(Model):
    success: bool
    error: Optional[str] = None


def register_summarize_function(sdk: IIIClient, kv: StateKV, provider: MemoryProvider):

    async def handle_summarize(raw_data: dict):
        data = SummarizationParams.from_dict(raw_data)

        session = kv.get(KV.sessions, data.session_id)
        if not session:
            logger.warning("session not found (session_id: %s)",
                           data.session_id)
            return SummarizationResult(success=False, error="session_not_found").to_dict()

        raw_observations = await kv.list(KV.observations(data.session_id))
        compressed = [
            CompressedObservation.from_dict(obs)
            for obs in raw_observations
            if obs.get("title")
        ]

        if len(compressed) == 0:
            logger.warning(
                "no observations to summarize (session_id: %s)", data.session_id)
            return SummarizationResult(success=False, error="no_observations").to_dict()

        try:
            prompt = build_summary_prompt(compressed)
            response = provider.summarize(SUMMARY_SYSTEM_PROMPT, prompt)
            logger.debug("summarize response: %s", response)

        # TODO: write next logic
        except Exception:
            pass

    sdk.register_function({
        "id": "mem::summarize",
        "description": "Generate end-of-session summary"
    }, handle_summarize)
