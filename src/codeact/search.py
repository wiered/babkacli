from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..utils.filesystem import (
    findfiles_path_matches,
    is_probably_binary,
    iter_files_under,
    should_skip_dir,
)
from ..utils.workspace import workspace_root
from .utils import resolve as resolve_universal
from .errors import CodeActSearchError


def resolve(path: str | Path) -> Path:
    return resolve_universal(path, CodeActSearchError)


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

        start = resolve(path)
        if not start.exists():
            raise CodeActSearchError(f"Path does not exist: {path}")
        if not start.is_dir():
            raise CodeActSearchError(f"Path is not a directory: {path}")

        root = workspace_root()
        matches: list[dict[str, Any]] = []
        truncated = False

        for file_path in iter_files_under(start):
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
            if is_probably_binary(raw):
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

        start = resolve(path)
        if not start.exists():
            raise CodeActSearchError(f"Path does not exist: {path}")
        if not start.is_dir():
            raise CodeActSearchError(f"Path is not a directory: {path}")

        root = workspace_root()
        files: list[str] = []

        for file_path in iter_files_under(start):
            try:
                rel = file_path.resolve().relative_to(root)
            except ValueError:
                continue
            if findfiles_path_matches(rel, pattern):
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

        target = resolve(path)
        if not target.exists():
            raise CodeActSearchError(f"Path does not exist: {path}")
        if not target.is_dir():
            raise CodeActSearchError(f"Path is not a directory: {path}")

        root = workspace_root()
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
                if entry.is_dir() and should_skip_dir(entry.name):
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
