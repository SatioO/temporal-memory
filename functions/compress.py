from dataclasses import dataclass
import dataclasses
import json
from iii import IIIClient, TriggerRequest

from eval.quality import score_compression
from eval.self_correct import compress_with_retry, CompressionValidationResult
from functions.search import get_search_index
from prompts.compression import COMPRESSION_SYSTEM_PROMPT, Observation, build_compression_prompt
from schema import CompressedObservation, Model, RawObservation, MemoryProvider
from state.kv import StateKV
from logger import get_logger
from state.schema import KV, STREAM

logger = get_logger("compress")

ALLOWED_TYPES = {
    "file_read", "file_write", "file_edit", "command_run", "search",
    "web_fetch", "conversation", "error", "decision", "discovery",
    "subagent", "notification", "task", "other"
}


@dataclass(frozen=True)
class CompressParams(Model):
    observation_id: str
    session_id: str
    raw: RawObservation


def register_compress_function(sdk: IIIClient, kv: StateKV, provider: MemoryProvider):
    async def handle_compress(raw_data: dict):
        data = CompressParams.from_dict(raw_data)
        prompt = build_compression_prompt(Observation(
            hook_type=data.raw.hook_type,
            tool_name=data.raw.tool_name,
            tool_input=data.raw.tool_input,
            tool_output=data.raw.tool_output,
            user_prompt=data.raw.user_prompt,
            timestamp=data.raw.timestamp,
        ))

        def validator(response: str) -> CompressionValidationResult:
            try:
                output = json.loads(response)
            except Exception:
                return CompressionValidationResult(
                    valid=False,
                    errors=["invalid_JSON"]
                )

            errors = []

            required_fields = [
                "type", "title", "facts", "narrative",
                "concepts", "files", "importance"
            ]

            for field in required_fields:
                if field not in output:
                    errors.append(f"missing_field: {field}")

            if "type" in output and output["type"] not in ALLOWED_TYPES:
                errors.append("invalid_type")

            if "title" in output:
                if not isinstance(output["title"], str) or len(output["title"]) > 80:
                    errors.append("invalid_title")

            if "facts" in output:
                if not isinstance(output["facts"], list) or not all(isinstance(f, str) for f in output["facts"]):
                    errors.append("invalid_facts")

            if "narrative" in output:
                if not isinstance(output["narrative"], str):
                    errors.append("invalid_narrative")

            if "concepts" in output:
                if not isinstance(output["concepts"], list) or not all(isinstance(c, str) for c in output["concepts"]):
                    errors.append("invalid_concepts")

            if "files" in output:
                if not isinstance(output["files"], list) or not all(isinstance(f, str) for f in output["files"]):
                    errors.append("invalid_files")

            if "importance" in output:
                if not isinstance(output["importance"], int) or not (1 <= output["importance"] <= 10):
                    errors.append("invalid_importance")

            if errors:
                return CompressionValidationResult(
                    valid=False,
                    errors=errors
                )

            return CompressionValidationResult(
                valid=True,
                errors=[]
            )

        try:
            compression_result = await compress_with_retry(provider, COMPRESSION_SYSTEM_PROMPT, prompt, validator, 1)
            try:
                parsed_json = json.loads(compression_result.response)
            except Exception:
                logger.warning("Failed to parse compression result", {
                    "obs_id": data.observation_id,
                    "retried": compression_result.retried,
                })
                return {"success": False, "error": "compression_parsing_failed"}

            compressed = CompressedObservation(
                id=data.observation_id,
                session_id=data.session_id,
                timestamp=data.raw.timestamp,
                type=parsed_json["type"],
                title=parsed_json["title"],
                facts=parsed_json["facts"],
                narrative=parsed_json["narrative"],
                concepts=parsed_json["concepts"],
                files=parsed_json["files"],
                importance=parsed_json["importance"],
                subtitle=parsed_json.get("subtitle"),
            )
            quality_score = score_compression(compressed)
            compressed = dataclasses.replace(
                compressed, confidence=quality_score/100)

            logger.info(
                f"compression_result: {parsed_json}, score: {quality_score}")

            get_search_index().add(compressed)

            await kv.set(
                KV.observations(data.session_id),
                data.observation_id,
                compressed,
            )

            await sdk.trigger_async(TriggerRequest(
                function_id="stream::set",
                payload={
                    "stream_name": STREAM.name,
                    "group_id": data.session_id,
                    "item_id": data.observation_id,
                    "data": {"type": "compressed", "observation": compressed.to_dict()},
                }
            ))

            await sdk.trigger_async(TriggerRequest(
                function_id="stream::set",
                payload={
                    "stream_name": STREAM.name,
                    "group_id": STREAM.viewer_group,
                    "item_id": data.observation_id,
                    "data": {"type": "compressed", "observation": compressed.to_dict(), "session_id": data.session_id},
                }
            ))

            logger.info("Observation compressed", {
                "obs_id": data.observation_id,
                "type": compressed.type,
                "importance": compressed.importance,
                "quality_score": quality_score,
                "retried": compression_result.retried,
            })

            return {"success": True, "quality_score": quality_score}
        except Exception as err:
            logger.warning("compression failed (session_id: %s, observation_id: %s), error: %s",
                           data.session_id, data.observation_id, err)
            return {"success": False, "error": "compression_failed"}

    sdk.register_function({
        "id": "mem::compress",
        "description": "Compress a raw observation using LLM",
    }, handle_compress)
