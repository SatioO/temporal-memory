"""Tests for plugin/scripts/post-tool-use.py"""
import importlib
import sys
import types
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers — inject a fake `shared` module so the script can be imported
# ---------------------------------------------------------------------------

def _load_module():
    fake_shared = types.ModuleType("shared")
    fake_shared.REST_URL = "http://localhost:3111"
    fake_shared.fetch = MagicMock()
    fake_shared.log = MagicMock()
    fake_shared.auth_headers = MagicMock(return_value={})
    fake_shared.read_json_stdin = MagicMock()
    sys.modules.setdefault("shared", fake_shared)

    import importlib.util, os
    spec = importlib.util.spec_from_file_location(
        "post_tool_use",
        os.path.join(os.path.dirname(__file__), "../../plugin/scripts/post-tool-use.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PTU = _load_module()
SIG = PTU._DEFAULT_SIGNIFICANT_TOOLS
SKIP = PTU._DEFAULT_TRIVIAL_BASH_PREFIXES


# ---------------------------------------------------------------------------
# should_log_tool
# ---------------------------------------------------------------------------

class TestShouldLogTool:
    def test_significant_tools_pass(self):
        for tool in ("Write", "Edit", "Bash", "Task", "NotebookEdit"):
            assert PTU.should_log_tool(tool, {"command": "uv run pytest"}, SIG, SKIP)

    def test_insignificant_tool_skipped(self):
        assert not PTU.should_log_tool("Read", {}, SIG, SKIP)
        assert not PTU.should_log_tool("Glob", {}, SIG, SKIP)
        assert not PTU.should_log_tool("Unknown", {}, SIG, SKIP)

    def test_trivial_bash_skipped(self):
        for cmd in ("ls -la", "pwd", "echo hello", "git status", "git log --oneline", "git diff HEAD"):
            assert not PTU.should_log_tool("Bash", {"command": cmd}, SIG, SKIP)

    def test_significant_bash_passes(self):
        for cmd in ("uv run pytest", "git commit -m 'fix'", "docker build .", "npm install"):
            assert PTU.should_log_tool("Bash", {"command": cmd}, SIG, SKIP)

    def test_custom_sig_tools_via_env(self, monkeypatch):
        monkeypatch.setenv("GRAPHMIND_TRACK_TOOLS", "Read,Grep")
        tools, skips = PTU._load_config()
        assert tools == {"Read", "Grep"}
        assert PTU.should_log_tool("Read", {}, tools, skips)
        assert not PTU.should_log_tool("Write", {}, tools, skips)

    def test_custom_skip_bash_via_env(self, monkeypatch):
        monkeypatch.setenv("GRAPHMIND_SKIP_BASH", "uv,docker")
        _, skips = PTU._load_config()
        assert not PTU.should_log_tool("Bash", {"command": "uv run pytest"}, SIG, skips)
        assert PTU.should_log_tool("Bash", {"command": "git commit -m x"}, SIG, skips)


# ---------------------------------------------------------------------------
# infer_content_purpose
# ---------------------------------------------------------------------------

class TestInferContentPurpose:
    def test_python_class(self):
        assert PTU.infer_content_purpose("class MyModel:\n    pass", "models.py") == "defines class MyModel"

    def test_python_function(self):
        assert PTU.infer_content_purpose("def compute():\n    return 1", "utils.py") == "defines function compute"

    def test_python_tests(self):
        # "def" check fires first — def test_foo → "defines function test_foo"
        assert PTU.infer_content_purpose("import pytest\ndef test_foo(): pass", "test_foo.py") == "defines function test_foo"
        # Only reaches "tests" branch when there's no class/def
        assert PTU.infer_content_purpose("import pytest", "conftest.py") == "tests"

    def test_python_routes(self):
        # "def" check fires first when both are present
        assert PTU.infer_content_purpose("@router.get('/ping')\nasync def ping(): pass", "routes.py") == "defines function ping"
        # Only reaches "routes" branch when there's no class/def
        assert PTU.infer_content_purpose("@router.get('/ping')", "routes.py") == "routes"

    def test_ts_export_function(self):
        r = PTU.infer_content_purpose("export function fetchUser(id: string) {}", "api.ts")
        assert r == "defines function fetchUser"

    def test_ts_export_class(self):
        r = PTU.infer_content_purpose("export class AuthService {}", "auth.ts")
        assert r == "defines class AuthService"

    def test_ts_tests(self):
        r = PTU.infer_content_purpose("describe('foo', () => { it('works', () => {}) })", "foo.test.ts")
        assert r == "tests"

    def test_rust_fn(self):
        r = PTU.infer_content_purpose("pub async fn handle_request() {}", "handler.rs")
        assert r == "defines fn handle_request"

    def test_rust_struct(self):
        r = PTU.infer_content_purpose("pub struct Config { pub port: u16 }", "config.rs")
        assert r == "defines struct Config"

    def test_rust_tests(self):
        r = PTU.infer_content_purpose("#[test]\nfn it_works() {}", "lib.rs")
        assert r == "tests"

    def test_go_struct(self):
        r = PTU.infer_content_purpose("type Server struct { Port int }", "server.go")
        assert r == "defines struct Server"

    def test_go_func(self):
        r = PTU.infer_content_purpose("func main() {}", "main.go")
        assert r == "defines func main"

    def test_css_selectors(self):
        r = PTU.infer_content_purpose(".btn { color: red; }\n#header { font-size: 16px; }", "styles.css")
        assert "styles" in r

    def test_html_title(self):
        r = PTU.infer_content_purpose("<html><head><title>Home</title></head></html>", "index.html")
        assert r == "page: Home"

    def test_sql_create(self):
        r = PTU.infer_content_purpose("CREATE TABLE users (id INT PRIMARY KEY)", "schema.sql")
        assert "schema" in r or "CREATE" in r

    def test_json_package(self):
        r = PTU.infer_content_purpose('{"name": "myapp"}', "package.json")
        assert r == "package config"

    def test_dockerfile(self):
        r = PTU.infer_content_purpose("FROM python:3.13\nRUN pip install uv", "Dockerfile")
        assert "python:3.13" in r

    def test_markdown(self):
        r = PTU.infer_content_purpose("# My Project\nSome text", "README.md")
        assert r == "doc: My Project"

    def test_unknown_ext_falls_back_to_line_count(self):
        r = PTU.infer_content_purpose("line1\nline2\nline3", "file.xyz")
        assert r == "3 lines"


# ---------------------------------------------------------------------------
# summarize_edit
# ---------------------------------------------------------------------------

class TestSummarizeEdit:
    def test_pure_addition(self):
        r = PTU.summarize_edit("", "def foo():\n    pass", "util.py")
        assert r.startswith("added")

    def test_pure_deletion(self):
        r = PTU.summarize_edit("def foo():\n    pass", "", "util.py")
        assert r.startswith("removed")

    def test_token_change(self):
        r = PTU.summarize_edit("old_function(x)", "new_function(x)", "util.py")
        assert "old_function" in r or "new_function" in r

    def test_line_expansion(self):
        r = PTU.summarize_edit("x = 1", "x = 1\ny = 2\nz = 3", "util.py")
        assert "expanded" in r

    def test_line_reduction(self):
        r = PTU.summarize_edit("x = 1\ny = 2\nz = 3", "x = 1", "util.py")
        assert "reduced" in r

    def test_same_size_modification(self):
        r = PTU.summarize_edit("foo = bar", "baz = qux", "util.py")
        assert r  # just ensure it returns something


# ---------------------------------------------------------------------------
# format_tool_summary
# ---------------------------------------------------------------------------

class TestFormatToolSummary:
    def test_write(self):
        r = PTU.format_tool_summary("Write", {"file_path": "/src/auth.py", "content": "class Auth: pass"}, {})
        assert "auth.py" in r
        assert "defines class Auth" in r

    def test_edit(self):
        r = PTU.format_tool_summary(
            "Edit",
            {"file_path": "/src/util.py", "old_string": "def foo():", "new_string": "def bar():"},
            {},
        )
        assert "util.py" in r

    def test_bash_git_commit(self):
        r = PTU.format_tool_summary("Bash", {"command": "git commit -m 'fix auth bug'"}, {})
        assert "fix auth bug" in r

    def test_bash_git_push_success(self):
        r = PTU.format_tool_summary("Bash", {"command": "git push origin main"}, {})
        assert "push" in r.lower()

    def test_bash_npm(self):
        r = PTU.format_tool_summary("Bash", {"command": "npm install express"}, {})
        assert "install" in r.lower() or "Package" in r

    def test_bash_generic(self):
        r = PTU.format_tool_summary("Bash", {"command": "uv run pytest"}, {})
        assert "uv run pytest" in r or "Ran" in r

    def test_bash_failure(self):
        r = PTU.format_tool_summary("Bash", {"command": "uv run pytest"}, {"error": "exit 1"})
        assert "failed" in r

    def test_task(self):
        r = PTU.format_tool_summary("Task", {"description": "explore codebase", "subagent_type": "Explore"}, {})
        assert "Explore" in r
        assert "explore codebase" in r

    def test_notebook_edit(self):
        r = PTU.format_tool_summary(
            "NotebookEdit",
            {"notebook_path": "/nb/analysis.ipynb", "edit_mode": "insert", "cell_type": "code"},
            {},
        )
        assert "analysis.ipynb" in r
        assert "insert" in r

    def test_unknown_tool(self):
        r = PTU.format_tool_summary("Grep", {}, {})
        assert "Grep" in r


# ---------------------------------------------------------------------------
# truncate
# ---------------------------------------------------------------------------

class TestTruncate:
    def test_string_under_limit(self):
        assert PTU.truncate("hello", 100) == "hello"

    def test_string_over_limit(self):
        r = PTU.truncate("x" * 200, 50)
        assert len(r) <= 70  # truncated + marker
        assert "truncated" in r

    def test_dict_under_limit(self):
        d = {"a": 1}
        assert PTU.truncate(d, 1000) == d

    def test_dict_over_limit(self):
        big = {"key": "v" * 2000}
        r = PTU.truncate(big, 100)
        assert isinstance(r, str)
        assert "truncated" in r

    def test_non_string_passthrough(self):
        assert PTU.truncate(42, 10) == 42
        assert PTU.truncate(None, 10) is None


# ---------------------------------------------------------------------------
# _slim_input
# ---------------------------------------------------------------------------

class TestSlimInput:
    def test_write_truncates_content(self, monkeypatch):
        monkeypatch.setenv("GRAPHMIND_INPUT_LIMIT", "10")
        r = PTU._slim_input("Write", {"file_path": "foo.py", "content": "x" * 100})
        assert r["file_path"] == "foo.py"
        assert "truncated" in r["content"]

    def test_edit_splits_limit(self, monkeypatch):
        monkeypatch.setenv("GRAPHMIND_INPUT_LIMIT", "20")
        r = PTU._slim_input("Edit", {"file_path": "f.py", "old_string": "a" * 50, "new_string": "b" * 50})
        assert "truncated" in r["old_string"]
        assert "truncated" in r["new_string"]

    def test_bash_truncates_command(self, monkeypatch):
        monkeypatch.setenv("GRAPHMIND_INPUT_LIMIT", "10")
        r = PTU._slim_input("Bash", {"command": "c" * 100})
        assert "truncated" in r["command"]

    def test_write_preserves_short_content(self, monkeypatch):
        monkeypatch.setenv("GRAPHMIND_INPUT_LIMIT", "500")
        r = PTU._slim_input("Write", {"file_path": "f.py", "content": "short"})
        assert r["content"] == "short"

    def test_generic_tool_slim(self, monkeypatch):
        monkeypatch.setenv("GRAPHMIND_INPUT_LIMIT", "10")
        r = PTU._slim_input("Task", {"description": "d" * 100, "subagent_type": "Explore"})
        assert "truncated" in r["description"]


# ---------------------------------------------------------------------------
# _load_config defaults
# ---------------------------------------------------------------------------

class TestLoadConfig:
    def test_defaults_when_no_env(self, monkeypatch):
        monkeypatch.delenv("GRAPHMIND_TRACK_TOOLS", raising=False)
        monkeypatch.delenv("GRAPHMIND_SKIP_BASH", raising=False)
        tools, skips = PTU._load_config()
        assert tools == PTU._DEFAULT_SIGNIFICANT_TOOLS
        assert skips == PTU._DEFAULT_TRIVIAL_BASH_PREFIXES

    def test_override_tools(self, monkeypatch):
        monkeypatch.setenv("GRAPHMIND_TRACK_TOOLS", "Write, Edit")
        tools, _ = PTU._load_config()
        assert tools == {"Write", "Edit"}

    def test_override_skip(self, monkeypatch):
        monkeypatch.setenv("GRAPHMIND_SKIP_BASH", "ls, pwd, echo")
        _, skips = PTU._load_config()
        assert "ls" in skips and "pwd" in skips
