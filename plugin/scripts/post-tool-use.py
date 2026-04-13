#!/usr/bin/env python3
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
from shared import REST_URL, fetch, log, auth_headers, read_json_stdin


MAX_LEN = 2000


def truncate(value, max_len=MAX_LEN):
    if isinstance(value, str) and len(value) > max_len:
        return value[:max_len] + "…"
    return value


def main() -> None:
    log("PostToolUse hook triggered ✓")

    data = read_json_stdin() or {}
    session_id = data.get("session_id") or "unknown"
    project = data.get("cwd") or os.getcwd()

    tool_input = data.get("tool_input") or {}
    command = tool_input.get("command") or ""

    # Skip observing graphmind API calls to avoid recursive loops
    if REST_URL and REST_URL in command:
        return

    tool_response = data.get("tool_response") or {}
    safe_response = {
        k: truncate(v) for k, v in tool_response.items()
    }

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
                    "tool_name": data.get("tool_name"),
                    "tool_input": tool_input,
                    "tool_response": safe_response,
                },
            },
            timeout=10,
        )

    except Exception as err:
        log(f"API call failed: {err}")


if __name__ == "__main__":
    main()
