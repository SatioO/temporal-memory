#!/usr/bin/env python3
import json
from typing import Any
from shared import REST_URL, fetch, log, auth_headers, read_json_stdin
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))


def truncate(value: Any, max_len: int):
    # String case
    if isinstance(value, str) and len(value) > max_len:
        return value[:max_len] + "\n[...truncated]"

    # Object (dict/list/etc.) case
    if isinstance(value, (dict, list)):
        try:
            s = json.dumps(value)
            if len(s) > max_len:
                return s[:max_len] + "...[truncated]"
            return value
        except (TypeError, ValueError):
            return value

    return value


def main() -> None:
    log("PostToolUse hook triggered ✓")

    hook_input = read_json_stdin()
    if hook_input is None:
        log(f"API call failed hook_input: {hook_input}")
        return

    tool_input = hook_input.get("tool_input") or {}
    command = tool_input.get("command") or ""
    session_id = hook_input.get("session_id", "unknown")
    project = hook_input.get("cwd", os.getcwd())

    # Skip observing graphmind API calls to avoid recursive loops
    if REST_URL and REST_URL in command:
        return

    tool_response = hook_input.get("tool_response") or {}

    try:
        fetch(
            url=f"{REST_URL}/graphmind/observe",
            method="POST",
            headers=auth_headers(),
            body={
                "hook_type": "post_tool_use",
                "session_id": session_id,
                "project": project,
                "cwd": project,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "tool_name": hook_input.get("tool_name"),
                    "tool_input": tool_input,
                    "tool_response": truncate(tool_response, 8e3),
                },
            },
        )

    except Exception as err:
        log(f"API call failed: {err}")


if __name__ == "__main__":
    main()
