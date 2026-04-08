from __future__ import annotations

from .ui_utils import allowed_commands_for_mode as _allowed_commands_for_mode
from .ui_utils import build_messages as _build_messages

__all__ = [
    "main",
    "_allowed_commands_for_mode",
    "_build_messages",
]


def __getattr__(name: str):
    if name == "main":
        from .ui import main as main_fn

        return main_fn
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
