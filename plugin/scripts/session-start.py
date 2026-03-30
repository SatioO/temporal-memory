#!/usr/bin/env python3
import os
import sys
import json
import urllib.request
import urllib.error
from typing import Any, Dict, Optional

REST_URL = os.getenv("GRAPHMIND_URL") or "http://localhost:3111"
SECRET = os.getenv("GRAPHMIND_SECRET") or ""


def fetch(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    body: Optional[Any] = None,
    timeout: int = 10,
) -> Dict[str, Any]:
    """Minimal HTTP client using stdlib."""

    req = urllib.request.Request(url, method=method, headers=headers or {})

    if body is not None:
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
            req.add_header("Content-Type", "application/json")
        elif isinstance(body, str):
            body = body.encode()

        req.data = body

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()

            return {
                "status": resp.status,
                "headers": dict(resp.headers),
                "body": raw,
                "json": safe_json(raw),
            }

    except urllib.error.HTTPError as e:
        return {
            "status": e.code,
            "headers": dict(e.headers or {}),
            "body": e.read().decode() if e.fp else "",
            "json": None,
            "error": str(e),
        }

    except urllib.error.URLError as e:
        return {
            "status": 0,
            "headers": {},
            "body": "",
            "json": None,
            "error": str(e),
        }


def safe_json(raw: str) -> Optional[Any]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def read_json_stdin() -> Optional[Dict[str, Any]]:
    if sys.stdin.isatty():
        return None

    try:
        return json.load(sys.stdin)
    except json.JSONDecodeError:
        return None


def log(msg: Any) -> None:
    """Consistent logging (stdout safe)."""
    if isinstance(msg, (dict, list)):
        print(json.dumps(msg, ensure_ascii=False))
    else:
        print(msg)


def auth_headers():
    h = {"Content-Type": "application/json"}
    if (SECRET):
        h["Authorization"] = f"Bearer {SECRET}"
    return h


def is_ok(res):
    return 200 <= res.get("status", 0) < 300


def main() -> None:
    log("[graphmind] SessionStart hook triggered ✓")

    data = read_json_stdin() or {}
    session_id = data.get("session_id") or "unknown"
    project = data.get("cwd") or os.getcwd()

    log(
        f"[graphmind] SessionStart hook: session_id={session_id}, cwd={project}")

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
