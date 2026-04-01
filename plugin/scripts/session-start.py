#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from shared import REST_URL, fetch, log, auth_headers, read_json_stdin, is_ok


def main() -> None:
    log("[graphmind] SessionStart hook triggered ✓")

    data = read_json_stdin() or {}
    session_id = data.get("session_id") or "unknown"
    project = data.get("cwd") or os.getcwd()

    log(f"[graphmind] SessionStart hook: session_id={session_id}, cwd={project}")

    try:
        res = fetch(
            url=f"{REST_URL}/graphmind/session/start",
            method="POST",
            headers=auth_headers(),
            body={
                "session_id": session_id,
                "project": project,
                "cwd": project,
            },
            timeout=5,
        )

        if is_ok(res):
            result = res.get("json") or {}
            context = result.get("context")
            if context:
                sys.stdout.write(context)
        else:
            log({
                "error": "session start failed",
                "status": res.get("status"),
                "details": res.get("error"),
            })

    except Exception as err:
        log(f"[graphmind] Claude bridge sync failed: {err}")


if __name__ == "__main__":
    main()
