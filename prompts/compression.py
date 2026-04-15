from dataclasses import dataclass
import json
from typing import Any, Optional
from schema import Model


COMPRESSION_SYSTEM_PROMPT = """You are a memory compression engine for an AI coding agent.

Convert a tool interaction into a dense, structured memory. Every token counts — be ruthlessly concise while preserving all technically critical information.

────────────────────────────
OUTPUT FORMAT (STRICT JSON)

{
  "type": "file_read|file_write|file_edit|command_run|search|web_fetch|conversation|error|decision|discovery|subagent|notification|task|other",
  "title": "Action + outcome, max 80 chars",
  "subtitle": "Optional extra context, max 60 chars",
  "facts": [
    "One concrete technical fact per entry, max 100 chars each, max 5 facts"
  ],
  "narrative": "What happened and why it matters. Max 200 chars. 2 sentences max.",
  "concepts": [
    "search term, max 35 chars each, max 3 concepts"
  ],
  "files": [
    "exact/file/path"
  ],
  "importance": 1
}

────────────────────────────
RULES

title      : verb-first, specific — "Fix BM25 tokenizer crash on empty input" not "Code fix"
facts      : extract NEW, surprising, or non-obvious findings only; skip obvious outcomes
narrative  : state what changed + why it matters; omit anything already in facts
concepts   : reusable search terms only (e.g. "BM25", "frozen dataclass", "async deadlock")
files      : exact paths, deduplicated; omit files only read without modification
importance : 1-3 reads/low-impact · 4-6 edits/commands · 7-9 arch decisions · 10 breaking changes

Do NOT include secrets, tokens, or credentials.
Output ONLY valid JSON. No explanations, no extra text.
"""


@dataclass(frozen=True)
class Observation(Model):
    hook_type: str
    tool_name: Optional[str]
    tool_input: Optional[Any]
    tool_output: Optional[Any]
    user_prompt: Optional[str]
    timestamp: str


def build_compression_prompt(observation: Observation) -> str:
    parts = [
        f"Timestamp: {observation.timestamp}",
        f"Hook: {observation.hook_type}"
    ]

    if observation.tool_name:
        parts.append(f"Tool: {observation.tool_name}")

    if observation.tool_input:
        if isinstance(observation.tool_input, str):
            input_str = observation.tool_input
        else:
            input_str = json.dumps(observation.tool_input, indent=2)

        parts.append(f"Input:\n{truncate(input_str, 4000)}")

    if observation.tool_output:
        if isinstance(observation.tool_output, str):
            output_str = observation.tool_output
        else:
            output_str = json.dumps(observation.tool_output, indent=2)

        parts.append(f"Output:\n{truncate(output_str, 4000)}")

    if observation.user_prompt:
        parts.append(
            f"User Prompt: \n{truncate(observation.user_prompt, 2000)}")

    return "\n\n".join(parts)


def truncate(s: str, max_len: int) -> str:
    return s[:max_len] + "\n[...truncated]" if len(s) > max_len else s
