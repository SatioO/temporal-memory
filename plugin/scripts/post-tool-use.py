#!/usr/bin/env python3
import json
import re
from typing import Any
from shared import REST_URL, fetch, log, auth_headers, read_json_stdin
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))


_DEFAULT_SIGNIFICANT_TOOLS = {"Write", "Edit", "Bash", "Task", "NotebookEdit"}
_DEFAULT_TRIVIAL_BASH_PREFIXES = (
    "ls", "pwd", "echo", "cat", "head", "tail",
    "which", "type", "git status", "git log", "git diff",
)

def _load_config() -> tuple[set[str], tuple[str, ...]]:
    tools_env = os.environ.get("GRAPHMIND_TRACK_TOOLS", "")
    skip_env = os.environ.get("GRAPHMIND_SKIP_BASH", "")
    tools = set(t.strip() for t in tools_env.split(",") if t.strip()) or _DEFAULT_SIGNIFICANT_TOOLS
    skips = tuple(p.strip() for p in skip_env.split(",") if p.strip()) or _DEFAULT_TRIVIAL_BASH_PREFIXES
    return tools, skips


def should_log_tool(tool_name: str, tool_input: dict, sig_tools: set[str], skip_prefixes: tuple[str, ...]) -> bool:
    if tool_name not in sig_tools:
        return False
    if tool_name == "Bash":
        command = (tool_input.get("command") or "").strip()
        if any(command.startswith(p) for p in skip_prefixes):
            return False
    return True


def infer_content_purpose(content: str, file_path: str) -> str:
    ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
    file_name = file_path.split("/")[-1].lower()

    # TypeScript / JavaScript
    if ext in ("ts", "tsx", "js", "jsx", "mjs", "cjs"):
        m = re.search(
            r"export\s+(?:default\s+)?(function|class|const|interface|type|enum)\s+(\w+)",
            content,
        )
        if m:
            return f"defines {m.group(1)} {m.group(2)}"
        m = re.search(
            r"(?:function|const)\s+(\w+).*(?:return|=>)\s*[(<]", content)
        if m:
            return f"component {m.group(1)}"
        if "describe(" in content or "it(" in content or "test(" in content:
            return "tests"
        if "router." in content or "app.get(" in content or "app.post(" in content:
            return "routes"

    # Python
    elif ext == "py":
        m = re.search(r"class\s+(\w+)", content)
        if m:
            return f"defines class {m.group(1)}"
        m = re.search(r"def\s+(\w+)", content)
        if m:
            return f"defines function {m.group(1)}"
        if "def test_" in content or "import pytest" in content:
            return "tests"
        if "@router." in content or "@app." in content:
            return "routes"

    # Rust
    elif ext == "rs":
        m = re.search(r"pub\s+(?:async\s+)?fn\s+(\w+)", content)
        if m:
            return f"defines fn {m.group(1)}"
        m = re.search(r"(?:pub\s+)?struct\s+(\w+)", content)
        if m:
            return f"defines struct {m.group(1)}"
        m = re.search(r"(?:pub\s+)?enum\s+(\w+)", content)
        if m:
            return f"defines enum {m.group(1)}"
        if "#[test]" in content or "#[cfg(test)]" in content:
            return "tests"

    # Go
    elif ext == "go":
        m = re.search(r"type\s+(\w+)\s+struct", content)
        if m:
            return f"defines struct {m.group(1)}"
        m = re.search(r"func\s+(\w+)", content)
        if m:
            return f"defines func {m.group(1)}"
        if "func Test" in content:
            return "tests"

    # CSS / SCSS / Less
    elif ext in ("css", "scss", "less", "sass"):
        selectors = re.findall(
            r"^\s*([.#][\w-]+|[\w-]+)\s*\{", content, re.MULTILINE)
        if selectors:
            return f"styles {', '.join(selectors[:3])}"
        return "styles"

    # HTML / templates
    elif ext in ("html", "htm", "svelte", "vue"):
        m = re.search(r"<title>(.+?)</title>", content, re.IGNORECASE)
        if m:
            return f"page: {m.group(1)[:50]}"
        m = re.search(r"<h1[^>]*>(.+?)</h1>", content, re.IGNORECASE)
        if m:
            return f"page: {m.group(1)[:50]}"
        return "template"

    # SQL
    elif ext == "sql":
        m = re.search(r"CREATE\s+(?:TABLE|VIEW|INDEX)\s+(\w+)",
                      content, re.IGNORECASE)
        if m:
            return f"schema: {m.group(0)[:60]}"
        m = re.search(r"(INSERT|UPDATE|DELETE|SELECT)", content, re.IGNORECASE)
        if m:
            return f"{m.group(1).lower()} query"
        return "SQL"

    # Shell
    elif ext in ("sh", "bash", "zsh", "fish"):
        m = re.search(r"^(?:function\s+)?(\w+)\s*\(\)", content, re.MULTILINE)
        if m:
            return f"script: {m.group(1)}"
        return "shell script"

    # Dockerfile
    elif ext == "dockerfile" or file_name == "dockerfile":
        m = re.search(r"^FROM\s+(\S+)", content, re.MULTILINE)
        if m:
            return f"Docker image from {m.group(1)}"
        return "Dockerfile"

    # Markdown / docs
    elif ext in ("md", "mdx", "rst", "txt"):
        m = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if m:
            return f"doc: {m.group(1)[:50]}"
        return "docs"

    # Config / data
    elif ext in ("json", "yaml", "yml", "toml", "ini", "cfg", "env"):
        if "package" in file_name:
            return "package config"
        if "docker" in file_name or "compose" in file_name:
            return "Docker config"
        if file_name.startswith(".env"):
            return "env config"
        return "config file"

    # Jupyter
    elif ext == "ipynb":
        return "notebook"

    # GraphQL
    elif ext in ("graphql", "gql"):
        m = re.search(r"(type|query|mutation|subscription)\s+(\w+)", content)
        if m:
            return f"GraphQL {m.group(1)} {m.group(2)}"
        return "GraphQL schema"

    # Protobuf
    elif ext == "proto":
        m = re.search(r"message\s+(\w+)", content)
        if m:
            return f"proto message {m.group(1)}"
        return "protobuf schema"

    line_count = content.count("\n") + 1
    return f"{line_count} lines"


def summarize_edit(old_str: str, new_str: str, file_path: str) -> str:
    old_lines = old_str.count("\n") + 1 if old_str else 0
    new_lines = new_str.count("\n") + 1 if new_str else 0

    if not old_str.strip():
        purpose = infer_content_purpose(new_str, file_path)
        return f"added {new_lines} lines ({purpose})"

    if not new_str.strip():
        return f"removed {old_lines} lines"

    old_tokens = re.findall(r"\w+", old_str)
    new_tokens = re.findall(r"\w+", new_str)
    old_set = set(old_tokens)
    new_set = set(new_tokens)

    added = [t for t in new_tokens if t not in old_set and len(t) > 2]
    removed = [t for t in old_tokens if t not in new_set and len(t) > 2]

    if added and removed:
        return f"changed: {', '.join(removed[:2])} → {', '.join(added[:2])}"
    if added:
        return f"added: {', '.join(added[:3])}"
    if removed:
        return f"removed: {', '.join(removed[:3])}"

    diff = new_lines - old_lines
    if diff > 0:
        return f"expanded by {diff} lines"
    if diff < 0:
        return f"reduced by {-diff} lines"
    return f"modified {old_lines} lines"


def format_tool_summary(tool_name: str, tool_input: dict, tool_response: dict) -> str:
    if tool_name == "Write":
        file_path = tool_input.get("file_path", "unknown")
        content = tool_input.get("content", "")
        purpose = infer_content_purpose(content, file_path)
        file_name = file_path.split("/")[-1] or file_path
        return f"Wrote {file_name} ({purpose})"

    if tool_name == "Edit":
        file_path = tool_input.get("file_path", "unknown")
        file_name = file_path.split("/")[-1] or file_path
        change_summary = summarize_edit(
            tool_input.get("old_string", ""),
            tool_input.get("new_string", ""),
            file_path,
        )
        return f"Edited {file_name}: {change_summary}"

    if tool_name == "Bash":
        command = (tool_input.get("command") or "")[:100]
        success = not tool_response.get("error")
        cmd_parts = re.split(r"[;&|]", command)[0].strip()
        if any(pm in command for pm in ("npm", "pnpm", "yarn", "bun")):
            m = re.search(r"(install|build|test|run|dev|start)", command)
            action = m.group(0) if m else "command"
            return f"Package {action}: {'success' if success else 'failed'}"
        if "git commit" in command:
            m = re.search(r'-m\s*["\']([^"\']+)["\']', command)
            msg = m.group(1) if m else ""
            return f"Git commit: {msg[:50]}{'...' if len(msg) > 50 else ''}"
        if "git push" in command:
            return f"Git push: {'success' if success else 'failed'}"
        if any(c in command for c in ("curl", "wget", "fetch")):
            m = re.search(r"https?://[^\s\"']+", command)
            domain = m.group(0).split("/")[2] if m else "API"
            return f"HTTP request to {domain}: {'success' if success else 'failed'}"
        if any(c in command for c in ("docker", "flyctl", "fly ")):
            return f"Deploy: {cmd_parts[:60]} ({'success' if success else 'failed'})"
        return f"Ran: {cmd_parts[:60]} ({'success' if success else 'failed'})"

    if tool_name == "Task":
        desc = tool_input.get("description", "unknown")
        agent_type = tool_input.get("subagent_type", "")
        return f"Agent task ({agent_type}): {desc}"

    if tool_name == "NotebookEdit":
        notebook_path = tool_input.get("notebook_path", "unknown")
        file_name = notebook_path.split("/")[-1] or notebook_path
        edit_mode = tool_input.get("edit_mode", "replace")
        cell_type = tool_input.get("cell_type", "code")
        return f"Notebook {edit_mode} {cell_type} cell in {file_name}"

    return f"Used {tool_name}"


def truncate(value: Any, max_len: int):
    # String case
    if isinstance(value, str) and len(value) > max_len:
        return value[:max_len] + "\n[...truncated]"

    # Object (dict/list/etc.) case
    if isinstance(value, (dict, list)):
        try:
            s = json.dumps(value)
            if len(s) > max_len:
                return s[:max_len] + "...[truncated]"
            return value
        except (TypeError, ValueError):
            return value

    return value


def _slim_input(tool_name: str, tool_input: dict) -> dict:
    """Return a token-efficient subset of tool_input."""
    limit = int(os.environ.get("GRAPHMIND_INPUT_LIMIT", "500"))
    if tool_name == "Write":
        return {"file_path": tool_input.get("file_path"), "content": truncate(tool_input.get("content", ""), limit)}
    if tool_name == "Edit":
        return {
            "file_path": tool_input.get("file_path"),
            "old_string": truncate(tool_input.get("old_string", ""), limit // 2),
            "new_string": truncate(tool_input.get("new_string", ""), limit // 2),
        }
    if tool_name == "Bash":
        return {"command": truncate(tool_input.get("command", ""), limit)}
    return {k: truncate(v, limit) for k, v in tool_input.items()}


def main() -> None:
    log("PostToolUse hook triggered ✓")

    hook_input = read_json_stdin()
    if hook_input is None:
        log(f"API call failed hook_input: {hook_input}")
        return

    sig_tools, skip_prefixes = _load_config()

    tool_name = hook_input.get("tool_name") or ""
    tool_input = hook_input.get("tool_input") or {}
    command = tool_input.get("command") or ""
    session_id = hook_input.get("session_id", "unknown")
    project = hook_input.get("cwd", os.getcwd())

    # Skip observing graphmind API calls to avoid recursive loops
    if REST_URL and REST_URL in command:
        return

    if not should_log_tool(tool_name, tool_input, sig_tools, skip_prefixes):
        return

    tool_response = hook_input.get("tool_response") or {}
    summary = format_tool_summary(tool_name, tool_input, tool_response)
    print(f"[graphmind] summary: {summary}")

    try:
        fetch(
            url=f"{REST_URL}/graphmind/observe",
            method="POST",
            headers=auth_headers(),
            body={
                "hook_type": "post_tool_use",
                "session_id": session_id,
                "project": project,
                "cwd": project,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "tool_name": tool_name,
                    "summary": summary,
                    "tool_input": _slim_input(tool_name, tool_input),
                },
            },
        )

    except Exception as err:
        log(f"API call failed: {err}")


if __name__ == "__main__":
    main()
