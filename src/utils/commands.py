"""Command handlers for JSON instructions produced by the AI agent."""

from __future__ import annotations

from dataclasses import dataclass
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from ..toolcall.json_parser import ParsedAgentCommand


class CommandExecutionError(RuntimeError):
    """Raised when a command cannot be executed safely."""


@dataclass(slots=True)
class CommandOutcome:
    """Normalized result returned by a command handler."""

    command: str
    data: dict[str, Any]


def workspace_root() -> Path:
    return Path.cwd().resolve()


def resolve_within_workspace(path: str | Path) -> Path:
    root = workspace_root()
    resolved = (root / Path(path)).resolve()
    if root not in resolved.parents and resolved != root:
        raise CommandExecutionError(f"Path escapes workspace root: {path}")
    return resolved


def ls(path: str = ".") -> dict[str, Any]:
    """List files and directories under a path."""

    target = resolve_within_workspace(path)
    if not target.exists():
        raise CommandExecutionError(f"Path does not exist: {path}")
    if not target.is_dir():
        raise CommandExecutionError(f"Path is not a directory: {path}")

    entries = []
    for entry in sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
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
            raise CommandExecutionError("'files' must contain objects with 'path' and optional 'content'.")

        raw_path = item.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise CommandExecutionError("Each file must include a non-empty string 'path'.")

        content = item.get("content", "")
        if not isinstance(content, str):
            raise CommandExecutionError("Each file 'content' must be a string when provided.")

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
    venv_python = root / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return venv_python
    return Path(sys.executable)


def codeact(code: str) -> dict[str, Any]:
    """Run Python source in the workspace; ``CodeAct`` is pre-imported in the child process."""

    if not isinstance(code, str) or not code.strip():
        raise CommandExecutionError("'code' must be a non-empty string.")

    root = workspace_root()
    interp = _python_interpreter()
    bootstrap = "\n".join(
        [
            "import sys",
            f"sys.path.insert(0, {str(root)!r})",
            "from src.codeact.codeact import CodeAct",
            f"exec(compile({code!r}, '<codeact>', 'exec'))",
        ]
    )

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    completed = subprocess.run(
        [str(interp), "-c", bootstrap],
        cwd=root,
        env=env,
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


def done(result: str) -> dict[str, Any]:
    """Return the final result for the user."""

    if not isinstance(result, str) or not result.strip():
        raise CommandExecutionError("'result' must be a non-empty string.")
    return {"result": result}


COMMAND_HANDLERS: dict[str, Callable[..., dict[str, Any]]] = {
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
        raise CommandExecutionError(f"Unsupported command '{command.command}'. Allowed: {allowed}.")

    try:
        data = handler(**command.arguments)
    except TypeError as exc:
        raise CommandExecutionError(
            f"Invalid arguments for command '{command.command}': {exc}"
        ) from exc

    return CommandOutcome(command=command.command, data=data)


def parse_and_dispatch_agent_response(raw_response: str) -> CommandOutcome:
    """Parse a raw agent response and execute the referenced command."""

    from ..toolcall.json_parser import parse_agent_response

    parsed = parse_agent_response(raw_response, allowed_commands=set(AVAILABLE_COMMANDS))
    return dispatch_command(parsed)
