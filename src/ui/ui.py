"""Minimal PySide6 workspace UI for the Babka agent."""

from __future__ import annotations

import argparse
import os

import sys
from pathlib import Path

from dotenv import load_dotenv
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

if __package__ in {None, ""}:
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from src.ui.agent_studio_window import AgentStudioWindow
    from src.ui.title_bar import build_app_icon
    from src.ui.ui_utils import ensure_bundled_jetbrains_nerd_font
else:
    from ..ui.agent_studio_window import AgentStudioWindow
    from ..ui.title_bar import build_app_icon
    from ..ui.ui_utils import ensure_bundled_jetbrains_nerd_font

DEFAULT_MODEL = os.getenv("GITHUB_MODEL", "openai/gpt-4.1-mini")
DEFAULT_MAX_STEPS = 8

def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]

def _default_workspace() -> Path:
    return _repo_root() / "test_project"

def _ensure_workspace(workspace: Path) -> Path:
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace.resolve()

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="babkacli ui",
        description="Minimal PySide6 UI for the workspace agent.",
    )
    parser.add_argument(
        "--workspace",
        default=str(_default_workspace()),
        help="Workspace directory to use. Defaults to ./test_project.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="GitHub Models model name. Defaults to openai/gpt-4.1-mini.",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=DEFAULT_MAX_STEPS,
        help="Maximum command turns per user message.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv()

    parser = build_parser()
    args = parser.parse_args(argv)

    workspace = _ensure_workspace(Path(args.workspace))
    model = args.model
    max_steps = max(1, args.max_steps)

    app = QApplication.instance() or QApplication(sys.argv[:1] if argv is None else [sys.argv[0], *argv])
    app.setApplicationName("BabkaCode")
    app.setOrganizationName("babkacli")
    app.setWindowIcon(build_app_icon())

    ensure_bundled_jetbrains_nerd_font()

    font = QFont("Segoe UI", 11)
    app.setFont(font)

    window = AgentStudioWindow(workspace=workspace, model=model, max_steps=max_steps)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
