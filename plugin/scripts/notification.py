#!/usr/bin/env python3
from shared import REST_URL, fetch, log, auth_headers, read_json_stdin
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))


def main() -> None:
    log("[graphmind] Notification hook triggered ✓")

    data = read_json_stdin() or {}
    session_id = data.get("session_id") or "unknown"
    project = data.get("cwd") or os.getcwd()

    try:
        fetch(
            url=f"{REST_URL}/graphmind/observe",
            method="POST",
            headers=auth_headers(),
            body={
                "hook_type": "notification",
                "session_id": session_id,
                "project": project,
                "cwd": project,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "notification_type": data.get("notification_type"),
                    "title": data.get("title"),
                    "message": data.get("message"),
                },
            },
            timeout=5,
        )

    except Exception as err:
        log(f"[graphmind] API call failed: {err}")


if __name__ == "__main__":
    main()
