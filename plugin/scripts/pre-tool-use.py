#!/usr/bin/env python3
from shared import REST_URL, fetch, log, auth_headers, read_json_stdin, is_ok
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


def main() -> None:
    log("[graphmind] PreToolUse hook triggered ✓")

    data = read_json_stdin() or {}
    session_id = data.get("session_id") or "unknown"

    print(f"[graphmind] PreToolUse data: {data}")

    tool_name = data.get("tool_name")

    if not tool_name:
        return

    file_tools = {"Edit", "Write", "Read", "Glob", "Grep"}
    if tool_name not in file_tools:
        return

    tool_input = data.get("tool_input") or {}
    files = []

    for key in ["file_path", "path", "file", "pattern"]:
        val = tool_input.get(key)
        if isinstance(val, str) and val:
            files.append(val)

    if not files:
        return

    try:
        res = fetch(
            url=f"{REST_URL}/graphmind/file_context",
            method="POST",
            headers=auth_headers(),
            body={
                "session_id": session_id,
                "files": files
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
                "error": "pre_tool_use hook failed",
                "status": res.get("status"),
                "details": res.get("error"),
            })

    except Exception as err:
        log(f"[graphmind] API call failed: {err}")


if __name__ == "__main__":
    main()
