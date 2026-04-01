import dataclasses
import json
from datetime import datetime, timezone
from dataclasses import dataclass
from iii import IIIClient

from eval.quality import score_summary
from eval.self_correct import SummarizationValidationResult, summarize_with_retry
from state.schema import KV
from state.kv import StateKV
from schema.domain import CompressedObservation, MemoryProvider, SessionSummary
from schema.base import Model
from prompts.summary import SUMMARY_SYSTEM_PROMPT, build_summary_prompt
from logger import get_logger

logger = get_logger("summarize")


@dataclass(frozen=True)
class SummarizationParams(Model):
    session_id: str


def register_summarize_function(sdk: IIIClient, kv: StateKV, provider: MemoryProvider):

    async def handle_summarize(raw_data: dict):
        data = SummarizationParams.from_dict(raw_data)

        session = await kv.get(KV.sessions, data.session_id)
        if not session:
            logger.warning("session not found (session_id: %s)",
                           data.session_id)
            return {"success": False, "error": "session_not_found"}

        raw_observations = await kv.list(KV.observations(data.session_id))
        observations = [
            CompressedObservation.from_dict(obs)
            for obs in raw_observations
            if obs.get("title")
        ]

        if len(observations) == 0:
            logger.warning(
                "no observations to summarize (session_id: %s)", data.session_id)
            return {"success": False, "error": "no_observations"}

        prompt = build_summary_prompt(observations)

        try:
            def validator(response: str) -> SummarizationValidationResult:
                try:
                    output = json.loads(response)
                except Exception:
                    return SummarizationValidationResult(
                        valid=False,
                        errors=["invalid_JSON"]
                    )

                errors = []

                required_fields = ["title", "narrative",
                                   "decisions", "concepts", "files"]

                for field in required_fields:
                    if field not in output:
                        errors.append(f"missing_field: {field}")

                if "title" in output:
                    if not isinstance(output["title"], str) or not (1 <= len(output["title"]) <= 100):
                        errors.append("invalid_title")

                if "narrative" in output:
                    if not isinstance(output["narrative"], str) or len(output["narrative"]) <= 20:
                        errors.append("Invalid narrative")

                if "decisions" in output:
                    if not isinstance(output["decisions"], list) or not all(isinstance(c, str) for c in output["decisions"]):
                        errors.append("invalid_decisions")

                if "concepts" in output:
                    if not isinstance(output["concepts"], list) or not all(isinstance(c, str) for c in output["concepts"]):
                        errors.append("invalid_concepts")

                if "files" in output:
                    if not isinstance(output["files"], list) or not all(isinstance(f, str) for f in output["files"]):
                        errors.append("invalid_files")

                if errors:
                    return SummarizationValidationResult(
                        valid=False,
                        errors=errors
                    )

                return SummarizationValidationResult(
                    valid=True,
                    errors=[]
                )

            raw_summary = await summarize_with_retry(provider, SUMMARY_SYSTEM_PROMPT, prompt, validator, 1)

            try:
                parsed_summary = json.loads(raw_summary.response)

                summary = SessionSummary(
                    session_id=data.session_id,
                    project=session.get("project"),
                    created_at=datetime.now(timezone.utc).isoformat(),
                    title=parsed_summary["title"],
                    narrative=parsed_summary["narrative"],
                    key_decisions=parsed_summary["decisions"],
                    files_modified=parsed_summary["files"],
                    concepts=parsed_summary["concepts"],
                    observation_count=len(observations)
                )

                quality_score = score_summary(summary)
                summary = dataclasses.replace(
                    summary, confidence=quality_score/100)

                await kv.set(KV.summaries, data.session_id, summary)
                logger.info("Observation compressed", {
                    "session_id": data.session_id,
                    "title": summary.title,
                    "decisions": summary.key_decisions,
                    "quality_score": quality_score,
                })

                return {"success": True, "summary": summary, "quality_score": quality_score}
            except Exception as err:
                logger.warning("Failed to parse summary (session_id: %s, error: %s)", {
                    "session_id": data.session_id,
                    "error": err
                })
                return {"success": False, "error": "summarization_parsing_failed"}
        except Exception as err:
            logger.warning("summarization_failed (session_id: %s), error: %s",
                           data.session_id,  err)
            return {"success": False, "error": "summarization_failed"}

    sdk.register_function({
        "id": "mem::summarize",
        "description": "Generate end-of-session summary"
    }, handle_summarize)
