"""Workspace root and safe path resolution."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from collections.abc import Iterator
from pathlib import Path

from ..toolcall.errors import CommandExecutionError

_workspace_override: ContextVar[Path | None] = ContextVar("babka_workspace_root", default=None)


def workspace_root() -> Path:
    override = _workspace_override.get()
    if override is not None:
        return override.resolve()
    return Path.cwd().resolve()


@contextmanager
def use_workspace_root(root: Path) -> Iterator[None]:
    """Temporarily treat ``root`` as the workspace for toolcall path resolution."""

    token = _workspace_override.set(Path(root).resolve())
    try:
        yield
    finally:
        _workspace_override.reset(token)


def resolve_within_workspace(path: str | Path) -> Path:
    root = workspace_root()
    resolved = (root / Path(path)).resolve()
    if root not in resolved.parents and resolved != root:
        raise CommandExecutionError(f"Path escapes workspace root: {path}")
    return resolved
