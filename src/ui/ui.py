"""Minimal PySide6 workspace UI for the Babka agent."""

from __future__ import annotations

import argparse
import os

import sys
from pathlib import Path

from dotenv import load_dotenv
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

if __package__ in {None, ""}:
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from src.ui.agent_studio_window import AgentStudioWindow
    from src.ui.title_bar import build_app_icon
    from src.ui.ui_utils import ensure_bundled_jetbrains_nerd_font
    from src.ui.design_tokens import (
        BG_BASE,
        BG_SURFACE,
        BG_ELEVATED,
        TEXT_PRIMARY,
        TEXT_DISABLED,
        ACCENT,
        FONT_UI_QT,
        FONT_UI_QT_FB,
    )
else:
    from ..ui.agent_studio_window import AgentStudioWindow
    from ..ui.title_bar import build_app_icon
    from ..ui.ui_utils import ensure_bundled_jetbrains_nerd_font
    from ..ui.design_tokens import (
        BG_BASE,
        BG_SURFACE,
        BG_ELEVATED,
        TEXT_PRIMARY,
        TEXT_DISABLED,
        ACCENT,
        FONT_UI_QT,
        FONT_UI_QT_FB,
    )

load_dotenv()
DEFAULT_MODEL = os.getenv("GITHUB_MODEL", "openai/gpt-4o")
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
        help="GitHub Models model name. Defaults to openai/gpt-4o.",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=DEFAULT_MAX_STEPS,
        help="Maximum command turns per user message.",
    )
    return parser


def _apply_dark_palette(app: QApplication) -> None:
    """Apply a Fusion dark palette matching the design tokens."""
    palette = QPalette()

    bg_base = QColor(BG_BASE)
    bg_surface = QColor(BG_SURFACE)
    bg_elev = QColor(BG_ELEVATED)
    fg_primary = QColor(TEXT_PRIMARY)
    fg_dis = QColor(TEXT_DISABLED)
    accent = QColor(ACCENT)

    palette.setColor(QPalette.ColorRole.Window, bg_surface)
    palette.setColor(QPalette.ColorRole.WindowText, fg_primary)
    palette.setColor(QPalette.ColorRole.Base, bg_elev)
    palette.setColor(QPalette.ColorRole.AlternateBase, bg_base)
    palette.setColor(QPalette.ColorRole.ToolTipBase, bg_elev)
    palette.setColor(QPalette.ColorRole.ToolTipText, fg_primary)
    palette.setColor(QPalette.ColorRole.Text, fg_primary)
    palette.setColor(QPalette.ColorRole.Button, bg_elev)
    palette.setColor(QPalette.ColorRole.ButtonText, fg_primary)
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Link, accent)
    palette.setColor(QPalette.ColorRole.Highlight, accent)
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, fg_dis
    )
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, fg_dis)
    palette.setColor(
        QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, fg_dis
    )

    app.setPalette(palette)


def main(argv: list[str] | None = None) -> int:
    load_dotenv()

    parser = build_parser()
    args = parser.parse_args(argv)

    workspace = _ensure_workspace(Path(args.workspace))
    model = args.model
    max_steps = max(1, args.max_steps)

    app = QApplication.instance() or QApplication(
        sys.argv[:1] if argv is None else [sys.argv[0], *argv]
    )

    # Dark scheme hint keeps DWM/WebView2 borders dark on Windows
    QGuiApplication.styleHints().setColorScheme(Qt.ColorScheme.Dark)
    app.setApplicationName("BabkaCode")
    app.setOrganizationName("babkacli")
    app.setWindowIcon(build_app_icon())

    ensure_bundled_jetbrains_nerd_font()

    # UI font: try Geist (if installed), fall back through Segoe UI chain
    for family in ("Geist", FONT_UI_QT, FONT_UI_QT_FB):
        font = QFont(family, 10)
        if font.exactMatch():
            app.setFont(font)
            break
    else:
        app.setFont(QFont("Segoe UI", 11))

    # Fusion style + dark palette for native Qt widgets not covered by QSS
    app.setStyle("Fusion")
    _apply_dark_palette(app)

    window = AgentStudioWindow(workspace=workspace, model=model, max_steps=max_steps)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
