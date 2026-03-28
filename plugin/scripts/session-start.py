#!/usr/bin/env python3

import json
import sys


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
