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
    except json.JSONDecodeError:
        return None


def log(msg: Any) -> None:
    if isinstance(msg, (dict, list)):
        print(json.dumps(msg, ensure_ascii=False))
    else:
        print(msg)


def auth_headers() -> Dict[str, str]:
    h = {"Content-Type": "application/json"}
    if SECRET:
        h["Authorization"] = f"Bearer {SECRET}"
    return h


def is_ok(res: Dict[str, Any]) -> bool:
    return 200 <= res.get("status", 0) < 300
