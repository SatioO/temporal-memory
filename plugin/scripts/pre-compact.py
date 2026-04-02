#!/usr/bin/env python3
from shared import REST_URL, fetch, log, auth_headers, read_json_stdin, is_ok
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))


def main() -> None:
    log("[graphmind] PreCompact hook triggered ✓")

    data = read_json_stdin() or {}
    session_id = data.get("session_id") or "unknown"
    project = data.get("cwd") or os.getcwd()

    try:
        res = fetch(
            url=f"{REST_URL}/graphmind/context",
            method="POST",
            headers=auth_headers(),
            body={
                "session_id": session_id,
                "project": project,
                "budget": 1500,
            },
            timeout=5,
        )

        if is_ok(res):
            result = res.get("json") or {}
            context = result.get("context")
            if context:
                sys.stdout.write(context)

    except Exception as err:
        log(f"[graphmind] API call failed: {err}")


if __name__ == "__main__":
    main()
