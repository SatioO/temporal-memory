#!/usr/bin/env python3
from shared import REST_URL, fetch, log, auth_headers, read_json_stdin
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


def main() -> None:
    log("[graphmind] Stop hook triggered ✓")

    data = read_json_stdin() or {}
    session_id = data.get("session_id") or "unknown"

    try:
        fetch(
            url=f"{REST_URL}/graphmind/summarize",
            method="POST",
            headers=auth_headers(),
            body={"session_id": session_id},
            timeout=10,
        )

    except Exception as err:
        log(f"[graphmind] API call failed: {err}")


if __name__ == "__main__":
    main()
