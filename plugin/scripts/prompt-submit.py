#!/usr/bin/env python3
from shared import REST_URL, fetch, log, auth_headers, read_json_stdin
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))


def main() -> None:
    log("[graphmind] PromptSubmit hook triggered ✓")

    hook_input = read_json_stdin()
    if hook_input is None:
        log(f"[graphmind] API call failed hook_input: {hook_input}")
        return

    project = hook_input.get("cwd", os.getcwd())
    session_id = hook_input.get("session_id", "unknown")

    try:
        fetch(
            url=f"{REST_URL}/graphmind/observe",
            method="POST",
            headers=auth_headers(),
            body={
                "hook_type": "prompt_submit",
                "session_id": session_id,
                "project": project,
                "cwd": project,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {"prompt": hook_input.get("prompt")},
            },
            timeout=5,
        )

    except Exception as err:
        log(f"[graphmind] API call failed: {err}")


if __name__ == "__main__":
    main()
