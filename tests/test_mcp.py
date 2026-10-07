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


def test_discovery_with_tool_returns_repair_hint_without_contacting_server(monkeypatch):
    def unexpected(*args):
        pytest.fail("Must not contact MCP for a malformed discovery command")

    monkeypatch.setattr(mcp_client, "request", unexpected)
    with pytest.raises(CommandExecutionError) as error:
        parse_and_dispatch_agent_response(
            '{"command":"mcp_list_tools","tool":"list_indexed_sources","arguments":{}}'
        )
    message = str(error.value)
    assert '{"command":"mcp_list_tools"}' in message
    assert "'mcp_read' in ask mode" in message
    assert "'mcp_call' in agent mode" in message


def test_invalid_arguments_are_rejected():
    with pytest.raises(CommandExecutionError, match="JSON object"):
        mcp_call("search", [])  # ty: ignore[invalid-argument-type] - test malformed input


@pytest.mark.parametrize("command", ["mcp_read", "mcp_call"])
def test_page_search_without_url_guides_source_search(monkeypatch, command):
    def unexpected(*args):
        pytest.fail("Malformed page search must not contact the server")

    monkeypatch.setattr(mcp_client, "request", unexpected)
    with pytest.raises(CommandExecutionError, match="call tool 'search'"):
        parse_and_dispatch_agent_response(
            '{"command":"' + command + '","tool":"search_in_file",'
            '"arguments":{"source_base":"http://127.0.0.1:18763/","query":"FastAPI health check"}}'
        )


def test_page_search_forwards_discovered_url(monkeypatch):
    calls = []
    monkeypatch.setattr(mcp_client, "request", lambda *args: calls.append(args) or {})
    arguments = {"page_url": "http://127.0.0.1:18763/health", "query": "health"}
    mcp_read("search_in_file", arguments)
    assert calls == [("call", "search_in_file", arguments)]


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
