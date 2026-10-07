"""Bridge to the local readdocs MCP server using its installed Python SDK."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

DEFAULT_SERVER = "G:/programming/py/git/readthedocs-mcp-server"
READ_ONLY_TOOLS = frozenset(
    {
        "list_indexed_sources",
        "list_documentation_pages",
        "search",
        "search_in_file",
        "search_entities",
        "lookup_symbol",
        "related_symbols",
        "get_entity",
        "list_class_methods",
        "get_entity_context",
        "get_symbol_graph_stats",
        "fetch",
    }
)


def request(
    operation: str, tool: str | None = None, arguments: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Run a bounded MCP session; keep SDK dependencies in the server environment."""
    from ..toolcall.errors import CommandExecutionError

    root = Path(os.getenv("READDOCS_MCP_SERVER", DEFAULT_SERVER)).resolve()
    python = (
        root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    )
    if not python.is_file():
        raise CommandExecutionError(
            f"MCP Python not found: {python}. Set READDOCS_MCP_SERVER to the installed server directory."
        )
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["READTHEDOCS_MCP_TRANSPORT"] = "stdio"
    try:
        completed = subprocess.run(
            [str(python), str(Path(__file__).resolve())],
            cwd=root,
            env=env,
            input=json.dumps(
                {"operation": operation, "tool": tool, "arguments": arguments or {}}
            ),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
            check=False,
        )
        if completed.returncode:
            raise CommandExecutionError(
                f"MCP request failed: {completed.stderr.strip()}"
            )
        return json.loads(completed.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
        raise CommandExecutionError(f"MCP request failed: {exc}") from exc


async def _serve_request(payload: dict[str, Any]) -> dict[str, Any]:
    from datetime import timedelta

    # These imports run only under the server's Python, which owns the SDK.
    from mcp import ClientSession, StdioServerParameters  # ty: ignore[unresolved-import]
    from mcp.client.stdio import stdio_client  # ty: ignore[unresolved-import]

    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "readdocsserver"],
        cwd=os.getcwd(),
        env=dict(os.environ),
    )
    async with stdio_client(parameters) as (reader, writer):
        async with ClientSession(
            reader, writer, read_timeout_seconds=timedelta(seconds=570)
        ) as session:
            await session.initialize()
            if payload["operation"] == "list":
                tools = []
                cursor = None
                while True:
                    page = await session.list_tools(cursor=cursor)
                    tools.extend(
                        tool.model_dump(mode="json", exclude_none=True)
                        for tool in page.tools
                    )
                    cursor = page.nextCursor
                    if not cursor:
                        break
                return {"server": "readdocs", "tools": tools}
            result = await session.call_tool(payload["tool"], payload["arguments"])
            return {
                "server": "readdocs",
                "tool": payload["tool"],
                **result.model_dump(mode="json", exclude_none=True),
            }


if __name__ == "__main__":
    import asyncio

    try:
        print(
            json.dumps(
                asyncio.run(_serve_request(json.load(sys.stdin))), ensure_ascii=False
            )
        )
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
