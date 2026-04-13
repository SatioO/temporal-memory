#!/usr/bin/env python3
from datetime import datetime, timezone

from shared import REST_URL, fetch, log, auth_headers, read_json_stdin, is_ok
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


def main() -> None:
    log("SubagentStart hook triggered ✓")

    data = read_json_stdin() or {}
    session_id = data.get("session_id") or "unknown"
    project = data.get("cwd") or os.getcwd()

    log(
        f"SubagentStart hook: session_id={session_id}, cwd={project}")

    try:
        res = fetch(
            url=f"{REST_URL}/graphmind/observe",
            method="POST",
            headers=auth_headers(),
            body={
                "hook_type": "subagent_start",
                "session_id": session_id,
                "project": project,
                "cwd": project,
                "timestamp":  datetime.now(timezone.utc).isoformat(),
                "data": {
                    "agent_id": data.agent_id,
                    "agent_type": data.agent_type
                }
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
                "error": "subagent session start failed",
                "status": res.get("status"),
                "details": res.get("error"),
            })

    except Exception as err:
        log(f"SubagentStart hook failed: {err}")


if __name__ == "__main__":
    main()
