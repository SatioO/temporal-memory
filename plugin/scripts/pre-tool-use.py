#!/usr/bin/env python3
from shared import REST_URL, fetch, log, auth_headers, read_json_stdin, is_ok
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


def main() -> None:
    log("[graphmind] PreToolUse hook triggered ✓")

    data = read_json_stdin() or {}

    tool_name = data.get("tool_name")
    if not tool_name:
        return

    if tool_name not in {"Edit", "Write", "Read", "Glob", "Grep"}:
        return

    tool_input = data.get("tool_input", {})

    files = []
    file_keys = ["path", "file"] if tool_name == "Grep" else [
        "file_path",
        "path",
        "file",
        "pattern",
    ]

    for key in file_keys:
        val = tool_input.get(key)
        if isinstance(val, str) and len(val) > 0:
            files.append(val)

    if not files:
        return

    terms = []
    if tool_name in {"Grep", "Glob"}:
        pattern = tool_input.get("pattern")
        if isinstance(pattern, str) and len(pattern) > 0:
            terms.append(pattern)

    session_id = data.get("session_id") or "unknown"

    try:
        res = fetch(
            url=f"{REST_URL}/graphmind/file_context",
            method="POST",
            headers=auth_headers(),
            body={
                "session_id": session_id,
                "files": files,
                "terms": terms,
                "tool_name": tool_name
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
