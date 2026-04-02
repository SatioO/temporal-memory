#!/usr/bin/env python3
import os
import sys
from datetime import datetime, timezone

from shared import REST_URL, fetch, log, auth_headers, read_json_stdin

sys.path.insert(0, os.path.dirname(__file__))


def main() -> None:
    log("[graphmind] TaskCompleted hook triggered ✓")

    data = read_json_stdin() or {}
    session_id = data.get("session_id") or "unknown"
    project = data.get("cwd") or os.getcwd()

    try:
        fetch(
            url=f"{REST_URL}/graphmind/context",
            method="POST",
            headers=auth_headers(),
            body={
                "hook_type": "task_completed",
                "session_id": session_id,
                "project": project,
                "cwd": project,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "task_id": data.get("task_id"),
                    "task_subject": data.get("task_subject"),
                    "task_description": data.get("task_description")[:2000] if isinstance(data.get("task_description"), str) else "",
                    "teammate_name": data.get("teammate_name"),
                    "team_name": data.get("team_name")
                },
            },
            timeout=5,
        )

    except Exception as err:
        log(f"[graphmind] API call failed: {err}")


if __name__ == "__main__":
    main()
