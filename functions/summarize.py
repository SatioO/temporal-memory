from typing import Optional
from iii import IIIClient
from pydantic import BaseModel

from prompts.summary import SUMMARY_SYSTEM_PROMPT, build_summary_prompt
from schema.config import ProviderConfig
from schema.domain import CompressedObservation, MemoryProvider
from state.kv import StateKV
from state.schema import KV


class SummarizationParams(BaseModel):
    session_id: str


class SummarizationResult(BaseModel):
    success: bool
    error: Optional[str]


def register_summarize_function(sdk: IIIClient, kv: StateKV, provider: MemoryProvider):

    async def handle_summarize(data_raw: SummarizationParams):
        data = SummarizationParams(**data_raw)

        session = kv.get(KV.sessions, data.session_id)
        if not session:
            print(
                f"[graphmind] session not found. (session_id: {data.session_id})")
            return SummarizationResult(success=False, error="session_not_found")

        # TODO: handle observations here
        raw_observations = await kv.list(KV.observations(data.session_id))
        compressed = [CompressedObservation(
            **observation) for observation in raw_observations if observation.get("title")]

        if len(compressed) == 0:
            print(
                f"[graphmind] No observations to summarize. (session_id: {data.session_id})")
            return SummarizationResult(success=False, error="no_observations")

        try:
            prompt = build_summary_prompt(compressed)
            response = provider.summarize(SUMMARY_SYSTEM_PROMPT, prompt)
            print(response)


        # TODO: write next logic
        except:
            pass

    sdk.register_function({
        "id": "mem::summarize",
        "description": "Generate end-of-session summary"
    }, handle_summarize)
