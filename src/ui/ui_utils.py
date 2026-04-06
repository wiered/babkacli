import json
import os
import sys
import subprocess
from importlib import resources
from typing import Any
from pathlib import Path
from dataclasses import dataclass

from PySide6.QtGui import QFont, QFontDatabase
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage
from azure.core.credentials import AzureKeyCredential

from ..system_prompts.prompts import build_system_prompt_for_mode

ENDPOINT = "https://models.github.ai/inference"
SUPPORTED_MODES = ("ask", "agent")
ALLOWED_COMMANDS_BY_MODE: dict[str, set[str]] = {
    "ask": {"done", "ls", "readfiles"},
    "agent": {"createFiles", "createFolders", "done", "ls", "readfiles", "runpy", "writefile"},
}


class WorkspaceCommandError(RuntimeError):
    """Raised when a workspace command cannot be executed safely."""


@dataclass(slots=True)
class CommandOutcome:
    """Normalized result returned by a workspace command."""

    command: str
    data: dict[str, Any]


@dataclass(slots=True)
class ChatEvent:
    """A rendered item in the agent chat history."""

    kind: str
    title: str = ""
    body: str = ""
    tone: str = "meta"
    step: int | None = None
    total: int | None = None
    block_id: str = ""
    collapsible: bool = False
    group_id: str = ""



def _get_token() -> str:
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if not token:
        raise RuntimeError("Set GITHUB_TOKEN (or GH_TOKEN) in the environment.")
    return token

def _resolve_within_workspace(workspace: Path, path: str | Path) -> Path:
    root = workspace.resolve()
    resolved = (root / Path(path)).resolve()
    if root not in resolved.parents and resolved != root:
        raise WorkspaceCommandError(f"Path escapes workspace root: {path}")
    return resolved

def _python_interpreter(workspace: Path) -> Path:
    for parent in [workspace, *workspace.parents]:
        candidate = parent / ".venv" / "Scripts" / "python.exe"
        if candidate.exists():
            return candidate
    return Path(sys.executable)

def _run_python(workspace: Path, path: str, args: list[str] | None = None) -> dict[str, Any]:
    target = _resolve_within_workspace(workspace, path)
    if not target.exists():
        raise WorkspaceCommandError(f"File does not exist: {path}")
    if not target.is_file():
        raise WorkspaceCommandError(f"Path is not a file: {path}")
    if target.suffix.lower() != ".py":
        raise WorkspaceCommandError(f"Path is not a Python file: {path}")

    command_args = [str(_python_interpreter(workspace)), str(target)]
    if args:
        if not all(isinstance(item, str) for item in args):
            raise WorkspaceCommandError("'args' must be a list of strings.")
        command_args.extend(args)

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    completed = subprocess.run(
        command_args,
        cwd=workspace.resolve(),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    return {
        "path": str(target.relative_to(workspace.resolve())),
        "interpreter": str(Path(command_args[0])),
        "args": command_args[2:],
        "returncode": completed.returncode,
        "stdout": completed.stdout or "",
        "stderr": completed.stderr or "",
    }

def _list_directory(workspace: Path, path: str = ".") -> dict[str, Any]:
    target = _resolve_within_workspace(workspace, path)
    if not target.exists():
        raise WorkspaceCommandError(f"Path does not exist: {path}")
    if not target.is_dir():
        raise WorkspaceCommandError(f"Path is not a directory: {path}")

    entries = []
    for entry in sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
        entries.append(
            {
                "name": entry.name,
                "path": str(entry.relative_to(workspace.resolve())),
                "type": "dir" if entry.is_dir() else "file",
            }
        )

    return {"path": str(target.relative_to(workspace.resolve())), "entries": entries}

def _read_files(workspace: Path, paths: list[str]) -> dict[str, Any]:
    if not paths:
        raise WorkspaceCommandError("'paths' must be a non-empty list.")

    files = []
    for raw_path in paths:
        target = _resolve_within_workspace(workspace, raw_path)
        if not target.exists():
            raise WorkspaceCommandError(f"File does not exist: {raw_path}")
        if not target.is_file():
            raise WorkspaceCommandError(f"Path is not a file: {raw_path}")
        files.append(
            {
                "path": str(target.relative_to(workspace.resolve())),
                "content": target.read_text(encoding="utf-8"),
            }
        )
    return {"files": files}

def _write_file(workspace: Path, path: str, content: str) -> dict[str, Any]:
    target = _resolve_within_workspace(workspace, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {
        "path": str(target.relative_to(workspace.resolve())),
        "written": True,
        "bytes": len(content.encode("utf-8")),
    }

def _create_folders(workspace: Path, paths: list[str]) -> dict[str, Any]:
    if not paths:
        raise WorkspaceCommandError("'paths' must be a non-empty list.")
    if not all(isinstance(item, str) and item.strip() for item in paths):
        raise WorkspaceCommandError("'paths' must contain non-empty strings.")

    created = []
    for raw_path in paths:
        target = _resolve_within_workspace(workspace, raw_path)
        target.mkdir(parents=True, exist_ok=True)
        created.append(
            {
                "path": str(target.relative_to(workspace.resolve())),
                "created": True,
            }
        )
    return {"folders": created}

def _create_files(workspace: Path, files: list[dict[str, Any]]) -> dict[str, Any]:
    if not files:
        raise WorkspaceCommandError("'files' must be a non-empty list.")

    created = []
    for item in files:
        if not isinstance(item, dict):
            raise WorkspaceCommandError("'files' must contain objects with 'path' and optional 'content'.")

        raw_path = item.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise WorkspaceCommandError("Each file must include a non-empty string 'path'.")

        content = item.get("content", "")
        if not isinstance(content, str):
            raise WorkspaceCommandError("Each file 'content' must be a string when provided.")

        target = _resolve_within_workspace(workspace, raw_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        created.append(
            {
                "path": str(target.relative_to(workspace.resolve())),
                "written": True,
                "bytes": len(content.encode("utf-8")),
            }
        )
    return {"files": created}

def normalize_mode(mode: str) -> str:
    normalized = mode.strip().lower()
    if normalized not in SUPPORTED_MODES:
        raise ValueError(f"Unsupported mode: {mode}")
    return normalized

def build_client() -> ChatCompletionsClient:
    return ChatCompletionsClient(
        endpoint=ENDPOINT,
        credential=AzureKeyCredential(_get_token()),
    )

def allowed_commands_for_mode(mode: str) -> set[str]:
    normalized = normalize_mode(mode)
    return set(ALLOWED_COMMANDS_BY_MODE[normalized])

def call_model(
    client: ChatCompletionsClient,
    *,
    messages: list[Any],
    model: str,
) -> str:
    response = client.complete(
        messages=messages,
        model=model,
        temperature=0.2,
        response_format="json_object",
    )

    message = response.choices[0].message
    content = message.content if message and message.content else ""
    return content.strip()

def dispatch_workspace_command(workspace: Path, command: str, arguments: dict[str, Any]) -> CommandOutcome:
    if command == "ls":
        data = _list_directory(workspace, **arguments)
    elif command == "readfiles":
        data = _read_files(workspace, **arguments)
    elif command == "createFolders":
        data = _create_folders(workspace, **arguments)
    elif command == "createFiles":
        data = _create_files(workspace, **arguments)
    elif command == "writefile":
        data = _write_file(workspace, **arguments)
    elif command == "runpy":
        data = _run_python(workspace, **arguments)
    elif command == "done":
        result = arguments.get("result")
        if not isinstance(result, str) or not result.strip():
            raise WorkspaceCommandError("'result' must be a non-empty string.")
        data = {"result": result}
    else:
        allowed = ", ".join(["createFiles", "createFolders", "done", "ls", "readfiles", "runpy", "writefile"])
        raise WorkspaceCommandError(f"Unsupported command '{command}'. Allowed: {allowed}.")

    return CommandOutcome(command=command, data=data)

def format_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)

def build_messages(mode: str) -> list[Any]:
    return [SystemMessage(build_system_prompt_for_mode(mode))]

# Bitmap / GDI-era faces that Qt on Windows may report as the system fixed font but
# DirectWrite cannot load via CreateFontFaceFromHDC (see qt.qpa.fonts warnings).
_LEGACY_FIXEDSYS_STYLE_FAMILIES: frozenset[str] = frozenset(
    name.casefold()
    for name in (
        "Fixedsys",
        "Terminal",
        "System",
        "Modern",
        "Small Fonts",
        "MS Sans Serif",
    )
)


def _resolve_safe_monospace_fallback(requested: str | None) -> str | None:
    if not requested:
        return None
    if requested.casefold() not in _LEGACY_FIXEDSYS_STYLE_FAMILIES:
        return requested
    db = QFontDatabase()
    for name in ("Consolas", "Cascadia Mono", "Cascadia Code", "Lucida Console", "Courier New"):
        if db.hasFamily(name):
            return name
    return "Courier New"


_BUNDLED_JETBRAINS_TTF = "JetBrainsMonoNerdFont-Regular.ttf"
_bundled_jetbrains_attempted: bool = False
_bundled_jetbrains_family: str | None = None


def _load_bundled_jetbrains_nerd_font_family() -> str | None:
    """Register the bundled TTF once and return its Qt family name, or None if unavailable."""
    global _bundled_jetbrains_attempted, _bundled_jetbrains_family
    if _bundled_jetbrains_attempted:
        return _bundled_jetbrains_family
    _bundled_jetbrains_attempted = True
    fonts_dir = Path(__file__).resolve().parent / "fonts"
    path = fonts_dir / _BUNDLED_JETBRAINS_TTF
    fid: int
    if path.is_file():
        fid = QFontDatabase.addApplicationFont(str(path))
    else:
        try:
            data = resources.files("src.ui").joinpath("fonts", _BUNDLED_JETBRAINS_TTF).read_bytes()
        except (OSError, TypeError, ValueError):
            _bundled_jetbrains_family = None
            return None
        fid = QFontDatabase.addApplicationFontFromData(data)
    if fid < 0:
        _bundled_jetbrains_family = None
        return None
    names = QFontDatabase.applicationFontFamilies(fid)
    if not names:
        _bundled_jetbrains_family = None
        return None
    _bundled_jetbrains_family = names[0]
    return _bundled_jetbrains_family


def ensure_bundled_jetbrains_nerd_font() -> str | None:
    """Register bundled JetBrains Mono from TTF if present (requires QGuiApplication)."""
    return _load_bundled_jetbrains_nerd_font_family()


def monospace_font_stack_css() -> str:
    """CSS font-family list without generic `monospace` (on Windows/Qt it often resolves to Fixedsys)."""
    ensure_bundled_jetbrains_nerd_font()
    primary = _bundled_jetbrains_family or "JetBrainsMono Nerd Font"
    return f"'{primary}', Consolas, 'Courier New'"


def build_nerd_font(point_size: int, *, fallback_family: str | None = None) -> QFont:
    safe_fallback = _resolve_safe_monospace_fallback(fallback_family)
    bundled = _load_bundled_jetbrains_nerd_font_family()
    if bundled:
        font = QFont(bundled, point_size)
    else:
        font = QFont("JetBrainsMono Nerd Font", point_size)
        if safe_fallback and font.family() != "JetBrainsMono Nerd Font":
            font = QFont(safe_fallback, point_size)
    font.setFixedPitch(True)
    font.setStyleStrategy(
        QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.NoFontMerging
    )
    return font
