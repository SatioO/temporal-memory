#!/usr/bin/env python3

import json
import sys
import urllib.request
import urllib.error


def fetch(url, method="GET", headers=None, body=None, timeout=10):
    """Fetch data from an API without third-party libraries.

    Returns a dict with keys: status (int), headers (dict), body (str), json (dict|None).
    Raises urllib.error.URLError on network errors, urllib.error.HTTPError on HTTP errors.
    """
    req = urllib.request.Request(url, method=method, headers=headers or {})
    if body is not None:
        if isinstance(body, dict):
            body = json.dumps(body).encode()
            req.add_header("Content-Type", "application/json")
        elif isinstance(body, str):
            body = body.encode()
        req.data = body

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = None
        return {
            "status": resp.status,
            "headers": dict(resp.headers),
            "body": raw,
            "json": parsed,
        }


def read_json_stdin():
    try:
        return json.load(sys.stdin)
    except json.JSONDecodeError:
        return None


def main():
    print('[graphmind] SessionStart hook triggered ✓')
    data = read_json_stdin()
    print(data)


if __name__ == "__main__":
    main()
