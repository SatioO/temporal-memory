#!/usr/bin/env python3
from shared import REST_URL, fetch, log, auth_headers, read_json_stdin, is_ok
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


def main() -> None:
    log("SessionStart hook triggered ✓")

    hook_input = read_json_stdin()
    if hook_input is None:
        log(f"API call failed hook_input: {hook_input}")
        return

    session_id = hook_input.get("session_id", "unknown")
    project = hook_input.get("cwd", os.getcwd())

    log(
        f"SessionStart hook: session_id={session_id}, cwd={project}")

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
        log(f"Claude bridge sync failed: {err}")


if __name__ == "__main__":
    main()
