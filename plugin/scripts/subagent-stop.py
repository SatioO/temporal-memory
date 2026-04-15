#!/usr/bin/env python3
from datetime import datetime, timezone

from shared import REST_URL, fetch, log, auth_headers, read_json_stdin
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


def main() -> None:
    log("SubagentStop hook triggered ✓")

    data = read_json_stdin() or {}
    session_id = data.get("session_id") or "unknown"
    project = data.get("cwd") or os.getcwd()

    last_msg = data.get("last_assistant_message").slice(
        0, 4e3) if isinstance(data.get("last_assistant_message"), str) else ""

    try:
        fetch(
            url=f"{REST_URL}/graphmind/observe",
            method="POST",
            headers=auth_headers(),
            body={
                "hook_type": "subagent_stop",
                "session_id": session_id,
                "project": project,
                "cwd": project,
                "timestamp":  datetime.now(timezone.utc).isoformat(),
                "data": {
                    "agent_id": data.get("agent_id"),
                    "agent_type": data.get("agent_type"),
                    "last_message": last_msg
                }
            },
            timeout=10,
        )

    except Exception as err:
        log(f"API call failed: {err}")


if __name__ == "__main__":
    main()
