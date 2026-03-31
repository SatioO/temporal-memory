from dataclasses import dataclass
import json
from typing import Any, Optional
from schema import Model


COMPRESSION_SYSTEM_PROMPT = """You are a memory compression engine for an AI coding agent. Your job is to extract the essential information from a tool usage observation and compress it into structured data.
    
    Output EXACTLY this JSON format with no additional text:

    {
      "type": "one of: file_read, file_write, file_edit, command_run, search, web_fetch, conversation, error, decision, discovery, subagent, notification, task, other",
      "title": "Short descriptive title (max 80 chars)",
      "subtitle": "One-line context (optional)",
      "facts": [
        "Specific factual detail 1",
        "Specific factual detail 2"
      ],
      "narrative": "2-3 sentence summary of what happened and why it matters",
      "concepts": [
        "technical concept or pattern"
      ],
      "files": [
        "path/to/file"
      ],
      "importance": 1
    }

    Rules:
    - Be concise but preserve ALL technically relevant details
    - File paths must be exact
    - Importance: 1-3 for routine reads, 4-6 for edits/commands, 7-9 for architectural decisions, 10 for breaking changes
    - Concepts should be reusable search terms (e.g., "React hooks", "SQL migration", "auth middleware")
    - Strip any secrets, tokens, or credentials from the output
    - Output must be valid JSON (no trailing commas, proper quoting)
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
