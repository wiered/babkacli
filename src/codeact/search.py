from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path
from typing import Any


class CodeActSearchError(RuntimeError):
    """Raised when a CodeAct search operation cannot be executed safely."""


_DEFAULT_SKIP_DIRS = frozenset(
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


def _skip_dir(name: str) -> bool:
    if name in _DEFAULT_SKIP_DIRS:
        return True
    return name.endswith(".egg-info")


def _workspace_root() -> Path:
    return Path.cwd().resolve()


def _resolve(path: str | Path) -> Path:
    root = _workspace_root()
    resolved = (root / Path(path)).resolve()
    if root not in resolved.parents and resolved != root:
        raise CodeActSearchError(f"Path escapes workspace root: {path}")
    return resolved


def _is_probably_binary(sample: bytes) -> bool:
    if not sample:
        return False
    if b"\x00" in sample[:8192]:
        return True
    return False


def _walk_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not _skip_dir(d)]
        for name in filenames:
            out.append(Path(dirpath) / name)
    return out


def _findfiles_match(relpath: Path, pattern: str) -> bool:
    posix = relpath.as_posix()
    glob_chars = frozenset("*?[]")
    if any(c in pattern for c in glob_chars):
        if "/" in pattern or pattern.startswith("**"):
            return fnmatch.fnmatch(posix, pattern)
        return fnmatch.fnmatch(relpath.name, pattern)
    return pattern in relpath.name


class CodeActSearch:
    def search(
        self,
        pattern: str,
        path: str = ".",
        *,
        max_matches: int = 500,
        max_file_bytes: int = 2 * 1024 * 1024,
    ) -> dict[str, Any]:
        """
        Search file contents for a regular expression (grep-like).

        Skips common vendor/cache directories and files that look binary.
        """
        if not isinstance(pattern, str) or not pattern.strip():
            raise CodeActSearchError("'pattern' must be a non-empty string.")

        try:
            regex = re.compile(pattern)
        except re.error as exc:
            raise CodeActSearchError(f"Invalid regular expression: {exc}") from exc

        start = _resolve(path)
        if not start.exists():
            raise CodeActSearchError(f"Path does not exist: {path}")
        if not start.is_dir():
            raise CodeActSearchError(f"Path is not a directory: {path}")

        root = _workspace_root()
        matches: list[dict[str, Any]] = []
        truncated = False

        for file_path in _walk_files(start):
            if truncated:
                break
            try:
                rel = file_path.resolve().relative_to(root)
            except ValueError:
                continue
            try:
                raw = file_path.read_bytes()
            except OSError:
                continue
            if len(raw) > max_file_bytes:
                continue
            if _is_probably_binary(raw):
                continue
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                if regex.search(line):
                    matches.append(
                        {
                            "path": rel.as_posix(),
                            "line": lineno,
                            "text": line,
                        }
                    )
                    if len(matches) >= max_matches:
                        truncated = True
                        break

        return {
            "pattern": pattern,
            "path": str(start.relative_to(root)),
            "matches": matches,
            "truncated": truncated,
        }

    def findfiles(self, pattern: str, path: str = ".") -> dict[str, Any]:
        """
        Find files whose path or basename matches a pattern.

        If the pattern contains glob characters (* ? [ ]), ``fnmatch`` is used.
        Patterns with ``/`` or leading ``**`` are matched against the path
        relative to the workspace; otherwise the basename is matched.

        Without glob characters, any file whose basename contains the pattern
        as a substring is listed.
        """
        if not isinstance(pattern, str) or not pattern.strip():
            raise CodeActSearchError("'pattern' must be a non-empty string.")

        start = _resolve(path)
        if not start.exists():
            raise CodeActSearchError(f"Path does not exist: {path}")
        if not start.is_dir():
            raise CodeActSearchError(f"Path is not a directory: {path}")

        root = _workspace_root()
        files: list[str] = []

        for file_path in _walk_files(start):
            try:
                rel = file_path.resolve().relative_to(root)
            except ValueError:
                continue
            if _findfiles_match(rel, pattern):
                files.append(rel.as_posix())

        files.sort()
        return {
            "pattern": pattern,
            "path": str(start.relative_to(root)),
            "files": files,
        }

    def readfolder(
        self,
        path: str = ".",
        *,
        max_depth: int = 8,
        max_entries: int = 400,
    ) -> dict[str, Any]:
        """
        Return a nested directory tree for workspace navigation.

        Stops at ``max_depth`` and caps total nodes (files + dirs) at ``max_entries``.
        """
        if max_depth < 0:
            raise CodeActSearchError("max_depth must be non-negative.")
        if max_entries < 1:
            raise CodeActSearchError("max_entries must be at least 1.")

        target = _resolve(path)
        if not target.exists():
            raise CodeActSearchError(f"Path does not exist: {path}")
        if not target.is_dir():
            raise CodeActSearchError(f"Path is not a directory: {path}")

        root = _workspace_root()
        rel_root = target.relative_to(root)
        count = 0
        truncated = False

        def build(p: Path, depth: int) -> dict[str, Any] | None:
            nonlocal count, truncated
            if count >= max_entries:
                truncated = True
                return None

            rel = p.relative_to(root)
            disp = rel.as_posix() if rel != Path(".") else "."
            if p == target:
                name = "." if target == root else target.name
            else:
                name = p.name

            node: dict[str, Any] = {
                "name": name,
                "type": "dir" if p.is_dir() else "file",
                "path": disp,
            }
            count += 1

            if not p.is_dir():
                return node

            if depth >= max_depth:
                node["children"] = []
                return node

            children: list[dict[str, Any]] = []
            try:
                entries = sorted(p.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
            except OSError:
                node["children"] = []
                return node

            for entry in entries:
                if entry.is_dir() and _skip_dir(entry.name):
                    continue
                if count >= max_entries:
                    truncated = True
                    break
                child = build(entry, depth + 1)
                if child is not None:
                    children.append(child)

            node["children"] = children
            return node

        tree = build(target, 0)
        assert tree is not None
        return {
            "path": str(rel_root) if str(rel_root) != "." else ".",
            "max_depth": max_depth,
            "tree": tree,
            "truncated": truncated,
        }
