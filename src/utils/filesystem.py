"""Filesystem traversal, directory skip rules, and lightweight file typing."""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path
from typing import Iterator

DEFAULT_SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        ".venv",
        "venv",
        "node_modules",
        ".mypy_cache",
        ".pytest_cache",
        ".tox",
        "dist",
        "build",
        ".eggs",
    }
)


def should_skip_dir(name: str) -> bool:
    if name in DEFAULT_SKIP_DIR_NAMES:
        return True
    return name.endswith(".egg-info")


def iter_files_under(root: Path) -> Iterator[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not should_skip_dir(d)]
        for name in filenames:
            yield Path(dirpath) / name


def is_probably_binary(sample: bytes) -> bool:
    if not sample:
        return False
    if b"\x00" in sample[:8192]:
        return True
    return False


def findfiles_path_matches(relpath: Path, pattern: str) -> bool:
    posix = relpath.as_posix()
    glob_chars = frozenset("*?[]")
    if any(c in pattern for c in glob_chars):
        if "/" in pattern or pattern.startswith("**"):
            return fnmatch.fnmatch(posix, pattern)
        return fnmatch.fnmatch(relpath.name, pattern)
    return pattern in relpath.name
