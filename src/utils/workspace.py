"""Workspace root and safe path resolution."""

from __future__ import annotations

from pathlib import Path

from ..toolcall.errors import CommandExecutionError


def workspace_root() -> Path:
    return Path.cwd().resolve()


def resolve_within_workspace(path: str | Path) -> Path:
    root = workspace_root()
    resolved = (root / Path(path)).resolve()
    if root not in resolved.parents and resolved != root:
        raise CommandExecutionError(f"Path escapes workspace root: {path}")
    return resolved
