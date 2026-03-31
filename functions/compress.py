from dataclasses import dataclass
import json
from iii import IIIClient

from eval.self_correct import compress_with_retry, CompressionValidationResult
from prompts.compression import COMPRESSION_SYSTEM_PROMPT, Observation, build_compression_prompt, Observation
from schema import Model, RawObservation, MemoryProvider
from state.kv import StateKV
from logger import get_logger

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
    async def handle_compress(raw_data: CompressParams):
        data: CompressParams = CompressParams.from_dict(raw_data)
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
                    errors=["Invalid JSON"]
                )

            errors = []

            required_fields = [
                "type", "title", "facts", "narrative",
                "concepts", "files", "importance"
            ]

            for field in required_fields:
                if field not in output:
                    errors.append(f"Missing field: {field}")

            if "type" in output and output["type"] not in ALLOWED_TYPES:
                errors.append("Invalid type")

            if "title" in output:
                if not isinstance(output["title"], str) or len(output["title"]) > 80:
                    errors.append("Invalid title")

            if "facts" in output:
                if not isinstance(output["facts"], list) or not all(isinstance(f, str) for f in output["facts"]):
                    errors.append("Invalid facts")

            if "narrative" in output:
                if not isinstance(output["narrative"], str):
                    errors.append("Invalid narrative")

            if "concepts" in output:
                if not isinstance(output["concepts"], list) or not all(isinstance(c, str) for c in output["concepts"]):
                    errors.append("Invalid concepts")

            if "files" in output:
                if not isinstance(output["files"], list) or not all(isinstance(f, str) for f in output["files"]):
                    errors.append("Invalid files")

            if "importance" in output:
                if not isinstance(output["importance"], int) or not (1 <= output["importance"] <= 10):
                    errors.append("Invalid importance")

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
            compression_result = await compress_with_retry(provider, COMPRESSION_SYSTEM_PROMPT, prompt, validator, 0)
            try:
                result = json.loads(compression_result.response)
            except json.JSONDecodeError:
                result = None

            if not result:
                logger.warning("Failed to parse compression result", {
                    "obs_id": data.observation_id,
                    "retried": compression_result.retried,
                })
                return {"success": False, "error": "compression_parsing_failed"}

            logger.info(f"compression_result: {compression_result.response}")

            return {"success": True}
        except Exception as err:
            logger.warning("compression failed (session_id: %s, observation_id: %s), error: %s",
                           data.session_id, data.observation_id, err)
            return {"success": False, "error": "compression_failed"}

    sdk.register_function({
        "id": "mem::compress",
        "description": "Compress a raw observation using LLM",
    }, handle_compress)
