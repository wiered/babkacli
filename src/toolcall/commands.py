"""Command handlers for JSON instructions produced by the AI agent."""

from __future__ import annotations

import ast
from dataclasses import dataclass
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from ..utils.workspace import resolve_within_workspace, workspace_root
from .errors import CommandExecutionError
from .json_parser import ParsedAgentCommand


@dataclass(slots=True)
class CommandOutcome:
    """Normalized result returned by a command handler."""

    command: str
    data: dict[str, Any]


def ls(path: str = ".", *, paths: list[str] | None = None) -> dict[str, Any]:
    """List one directory, or multiple directories in one call."""

    if paths is not None:
        if path != ".":
            raise CommandExecutionError("Use either 'path' or 'paths', not both.")
        if not isinstance(paths, list) or not paths:
            raise CommandExecutionError("'paths' must be a non-empty list.")
        if not all(isinstance(item, str) and item.strip() for item in paths):
            raise CommandExecutionError("'paths' must contain non-empty strings.")
        return {"directories": [ls(path=item) for item in paths]}

    target = resolve_within_workspace(path)
    if not target.exists():
        raise CommandExecutionError(f"Path does not exist: {path}")
    if not target.is_dir():
        raise CommandExecutionError(f"Path is not a directory: {path}")

    entries = []
    for entry in sorted(
        target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())
    ):
        entries.append(
            {
                "name": entry.name,
                "path": str(entry.relative_to(workspace_root())),
                "type": "dir" if entry.is_dir() else "file",
            }
        )
    return {"path": str(target.relative_to(workspace_root())), "entries": entries}


def readfiles(paths: list[str]) -> dict[str, Any]:
    """Read multiple files in one call."""

    if not paths:
        raise CommandExecutionError("'paths' must be a non-empty list.")

    files = []
    for raw_path in paths:
        target = resolve_within_workspace(raw_path)
        if not target.exists():
            raise CommandExecutionError(f"File does not exist: {raw_path}")
        if not target.is_file():
            raise CommandExecutionError(f"Path is not a file: {raw_path}")
        files.append(
            {
                "path": str(target.relative_to(workspace_root())),
                "content": target.read_text(encoding="utf-8"),
            }
        )
    return {"files": files}


def writefile(path: str, content: str) -> dict[str, Any]:
    """Create or overwrite a file inside the workspace."""

    target = resolve_within_workspace(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {
        "path": str(target.relative_to(workspace_root())),
        "written": True,
        "bytes": len(content.encode("utf-8")),
    }


def createFolders(paths: list[str]) -> dict[str, Any]:
    """Create multiple directories inside the workspace."""

    if not paths:
        raise CommandExecutionError("'paths' must be a non-empty list.")
    if not all(isinstance(item, str) and item.strip() for item in paths):
        raise CommandExecutionError("'paths' must contain non-empty strings.")

    created = []
    for raw_path in paths:
        target = resolve_within_workspace(raw_path)
        target.mkdir(parents=True, exist_ok=True)
        created.append(
            {
                "path": str(target.relative_to(workspace_root())),
                "created": True,
            }
        )

    return {"folders": created}


def createFiles(files: list[dict[str, Any]]) -> dict[str, Any]:
    """Create or overwrite multiple files inside the workspace."""

    if not files:
        raise CommandExecutionError("'files' must be a non-empty list.")

    created = []
    for item in files:
        if not isinstance(item, dict):
            raise CommandExecutionError(
                "'files' must contain objects with 'path' and optional 'content'."
            )

        raw_path = item.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise CommandExecutionError(
                "Each file must include a non-empty string 'path'."
            )

        content = item.get("content", "")
        if not isinstance(content, str):
            raise CommandExecutionError(
                "Each file 'content' must be a string when provided."
            )

        target = resolve_within_workspace(raw_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        created.append(
            {
                "path": str(target.relative_to(workspace_root())),
                "written": True,
                "bytes": len(content.encode("utf-8")),
            }
        )

    return {"files": created}


def _python_interpreter() -> Path:
    """Return the preferred Python interpreter for workspace scripts."""

    root = workspace_root()
    for parent in [root, *root.parents]:
        candidate = parent / ".venv" / "Scripts" / "python.exe"
        if candidate.exists():
            return candidate
    return Path(sys.executable)


def _resolve_codeact_source(
    code: str | None,
    code_lines: list[Any] | None,
) -> str:
    """Prefer ``code_lines`` (no string escaping) over a single ``code`` string."""

    if code_lines is not None:
        if not isinstance(code_lines, list):
            raise CommandExecutionError("'code_lines' must be a JSON array of strings.")
        if code_lines:
            if not all(isinstance(line, str) for line in code_lines):
                raise CommandExecutionError("'code_lines' must contain only strings.")
            joined = "\n".join(code_lines)
            if joined.strip():
                return joined

    if isinstance(code, str) and code.strip():
        return code

    raise CommandExecutionError(
        "Provide non-empty 'code' (string) or 'code_lines' (non-empty array of strings, one source line per element)."
    )


def _codeact_is_print_call(expr: ast.expr) -> bool:
    """True if ``expr`` is a call to the builtin ``print`` (by name)."""

    return (
        isinstance(expr, ast.Call)
        and isinstance(expr.func, ast.Name)
        and expr.func.id == "print"
    )


def _codeact_wrap_top_level_expr_prints(source: str) -> str:
    """
    Turn bare top-level expressions into ``print(repr(...))`` so API return values reach stdout.

    Skips a leading module docstring (a string literal as the first statement).
    Does not wrap ``print(...)`` — wrapping would emit ``print(repr(print(...)))`` and append ``None``.
    """

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source

    new_body: list[ast.stmt] = []
    for i, node in enumerate(tree.body):
        if isinstance(node, ast.Expr):
            if (
                i == 0
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                new_body.append(node)
                continue
            if _codeact_is_print_call(node.value):
                new_body.append(node)
                continue
            new_body.append(
                ast.Expr(
                    value=ast.Call(
                        func=ast.Name(id="print", ctx=ast.Load()),
                        args=[
                            ast.Call(
                                func=ast.Name(id="repr", ctx=ast.Load()),
                                args=[node.value],
                                keywords=[],
                            )
                        ],
                        keywords=[],
                    )
                )
            )
        else:
            new_body.append(node)

    tree.body = new_body
    return ast.unparse(tree)


def codeact(
    code: str | None = None, code_lines: list[Any] | None = None
) -> dict[str, Any]:
    """
    CodeAct-style action: run an arbitrary Python program in the workspace.

    The JSON ``command`` field is only transport; the payload is real Python you can compose
    (variables, control flow, stdlib) while ``ca`` exposes workspace-bound ``.files`` and ``.search``.
    Observation for the next turn is ``returncode``, ``stdout``, and ``stderr`` (tracebacks on failure).
    User source is passed on stdin so large scripts are not limited by OS command-line length.
    """

    source = _codeact_wrap_top_level_expr_prints(
        _resolve_codeact_source(code, code_lines)
    )

    root = workspace_root()
    interp = _python_interpreter()
    bootstrap = "\n".join(
        [
            "import sys",
            f"sys.path.insert(0, {str(root)!r})",
            "from src.codeact.codeact import CodeAct",
            "ca = CodeAct()",
            "exec(compile(sys.stdin.read(), '<codeact>', 'exec'))",
        ]
    )

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    completed = subprocess.run(
        [str(interp), "-c", bootstrap],
        cwd=root,
        env=env,
        input=source,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    return {
        "interpreter": str(interp),
        "returncode": completed.returncode,
        "stdout": completed.stdout or "",
        "stderr": completed.stderr or "",
    }


def runpy(path: str, args: list[str] | None = None) -> dict[str, Any]:
    """Run a Python file inside the workspace and capture its output."""

    target = resolve_within_workspace(path)
    if not target.exists():
        raise CommandExecutionError(f"File does not exist: {path}")
    if not target.is_file():
        raise CommandExecutionError(f"Path is not a file: {path}")
    if target.suffix.lower() != ".py":
        raise CommandExecutionError(f"Path is not a Python file: {path}")

    command_args = [str(_python_interpreter()), str(target)]
    if args:
        if not all(isinstance(item, str) for item in args):
            raise CommandExecutionError("'args' must be a list of strings.")
        command_args.extend(args)

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    completed = subprocess.run(
        command_args,
        cwd=workspace_root(),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    return {
        "path": str(target.relative_to(workspace_root())),
        "interpreter": str(Path(command_args[0])),
        "args": command_args[2:],
        "returncode": completed.returncode,
        "stdout": completed.stdout or "",
        "stderr": completed.stderr or "",
    }


def mcp_list_tools(arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Discover actual tool descriptions and JSON schemas from readdocs."""
    from ..utils.mcp_client import request

    if arguments is not None and (not isinstance(arguments, dict) or arguments):
        raise CommandExecutionError("'mcp_list_tools' accepts only empty 'arguments'.")
    return request("list")


def mcp_call(tool: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Call a tool on the configured readdocs server."""
    from ..utils.mcp_client import request

    if not isinstance(tool, str) or not tool.strip():
        raise CommandExecutionError("'tool' must be a non-empty string.")
    if arguments is not None and not isinstance(arguments, dict):
        raise CommandExecutionError("'arguments' must be a JSON object.")
    return request("call", tool, arguments)


def mcp_read(tool: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Allow only known read-only documentation tools in ask mode."""
    from ..utils.mcp_client import READ_ONLY_TOOLS

    if not isinstance(tool, str) or tool not in READ_ONLY_TOOLS:
        raise CommandExecutionError("This MCP tool is not allowed in read-only mode.")
    return mcp_call(tool, arguments)


def done(result: str) -> dict[str, Any]:
    """Return the final result for the user."""

    if not isinstance(result, str) or not result.strip():
        raise CommandExecutionError("'result' must be a non-empty string.")
    return {"result": result}


COMMAND_HANDLERS: dict[str, Callable[..., dict[str, Any]]] = {
    "mcp_list_tools": mcp_list_tools,
    "mcp_call": mcp_call,
    "mcp_read": mcp_read,
    "codeact": codeact,
    "createFiles": createFiles,
    "createFolders": createFolders,
    "ls": ls,
    "readfiles": readfiles,
    "writefile": writefile,
    "runpy": runpy,
    "done": done,
}

AVAILABLE_COMMANDS = frozenset(COMMAND_HANDLERS)


def dispatch_command(command: ParsedAgentCommand) -> CommandOutcome:
    """Execute a parsed agent command and return a normalized outcome."""

    handler = COMMAND_HANDLERS.get(command.command)
    if handler is None:
        allowed = ", ".join(sorted(AVAILABLE_COMMANDS))
        raise CommandExecutionError(
            f"Unsupported command '{command.command}'. Allowed: {allowed}."
        )

    try:
        data = handler(**command.arguments)
    except TypeError as exc:
        raise CommandExecutionError(
            f"Invalid arguments for command '{command.command}': {exc}"
        ) from exc

    return CommandOutcome(command=command.command, data=data)


def parse_and_dispatch_agent_response(raw_response: str) -> CommandOutcome:
    """Parse a raw agent response and execute the referenced command."""

    from .json_parser import parse_agent_response

    parsed = parse_agent_response(
        raw_response, allowed_commands=set(AVAILABLE_COMMANDS)
    )
    return dispatch_command(parsed)
