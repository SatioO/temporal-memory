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
    except (json.JSONDecodeError, EOFError):
        print("[graphmind] Failed to read hook input", file=sys.stderr)
        return None


def log(msg: Any) -> None:
    if isinstance(msg, (dict, list)):
        print(f"[graphmind] {json.dumps(msg, ensure_ascii=False)}")
    else:
        print(f"[graphmind] {msg}")


def auth_headers() -> Dict[str, str]:
    h = {"Content-Type": "application/json"}
    if SECRET:
        h["Authorization"] = f"Bearer {SECRET}"
    return h


def is_ok(res: Dict[str, Any]) -> bool:
    return 200 <= res.get("status", 0) < 300


def read_transcript(transcript_path: str) -> list:
    """Read a JSONL transcript file and return list of message dicts.

    Claude Code transcript format nests messages:
      {type: "user", message: {role: "user", content: "..."}, uuid: "...", ...}
    Also supports flat format for testing:
      {role: "user", content: "..."}
    """
    if not transcript_path or not os.path.isfile(transcript_path):
        return []

    messages = []
    try:
        with open(transcript_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    # Claude Code nested format: {type: "user", message: {role, content}}
                    if entry.get("type") in ("user", "assistant") and not entry.get("isSidechain"):
                        msg = entry.get("message", {})
                        if isinstance(msg, dict) and msg.get("role"):
                            messages.append(msg)
                    # Flat format (testing / future compatibility)
                    elif "role" in entry and "content" in entry:
                        messages.append(entry)
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    return messages


def debug_log(config: dict, *args):
    """Log to stderr if debug mode is enabled."""
    if config.get("debug"):
        print("[Hindsight]", *args, file=sys.stderr)
