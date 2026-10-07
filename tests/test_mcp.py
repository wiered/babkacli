import subprocess

import pytest

from src.toolcall.commands import (
    mcp_call,
    mcp_list_tools,
    mcp_read,
    parse_and_dispatch_agent_response,
)
from src.toolcall.errors import CommandExecutionError
from src.utils import mcp_client


def test_discovery_and_call_forward_arguments(monkeypatch):
    calls = []

    def request(*args):
        calls.append(args)
        return {"content": [{"type": "text", "text": "ok"}]}

    monkeypatch.setattr(mcp_client, "request", request)
    mcp_list_tools()
    result = mcp_read("search", {"query": "LayoutView"})
    assert calls == [("list",), ("call", "search", {"query": "LayoutView"})]
    assert result["content"][0]["text"] == "ok"


def test_read_only_blocks_indexing_before_contacting_server(monkeypatch):
    def unexpected(*args):
        pytest.fail("Must not contact MCP for a denied tool")

    monkeypatch.setattr(mcp_client, "request", unexpected)
    with pytest.raises(CommandExecutionError, match="read-only"):
        mcp_read("index_readthedocs", {"seed_url": "https://example.com"})


def test_discovery_accepts_empty_arguments_through_dispatch(monkeypatch):
    monkeypatch.setattr(mcp_client, "request", lambda operation: {"tools": []})
    outcome = parse_and_dispatch_agent_response(
        '{"command":"mcp_list_tools","arguments":{}}'
    )
    assert outcome.command == "mcp_list_tools"
    assert outcome.data == {"tools": []}


def test_discovery_rejects_nonempty_arguments():
    with pytest.raises(CommandExecutionError, match="only empty"):
        mcp_list_tools({"unexpected": True})


def test_invalid_arguments_are_rejected():
    with pytest.raises(CommandExecutionError, match="JSON object"):
        mcp_call("search", [])  # ty: ignore[invalid-argument-type] - test malformed input


def test_timeout_becomes_command_error(monkeypatch, tmp_path):
    python = tmp_path / ".venv" / "Scripts" / "python.exe"
    python.parent.mkdir(parents=True)
    python.touch()
    monkeypatch.setenv("READDOCS_MCP_SERVER", str(tmp_path))

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("mcp", 600)

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(CommandExecutionError, match="MCP request failed"):
        mcp_list_tools()
