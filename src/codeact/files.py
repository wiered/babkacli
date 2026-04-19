from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from ..utils.workspace import workspace_root
from .errors import CodeActFilesError
from .utils import resolve as resolve_universal


def resolve(path: str | Path) -> Path:
    return resolve_universal(path, CodeActFilesError)


class CodeActFiles:
    def ls(self, path: str = ".", ignore: list[str] | None = None) -> dict[str, Any]:
        """
        List files and directories under a path.

        Directories whose basenames appear in ``ignore`` are omitted.
        """
        target = resolve(path)
        if not target.exists():
            raise CodeActFilesError(f"Path does not exist: {path}")
        if not target.is_dir():
            raise CodeActFilesError(f"Path is not a directory: {path}")

        root = workspace_root()
        ignore_set = frozenset(ignore) if ignore else frozenset()

        entries: list[dict[str, Any]] = []
        for entry in sorted(
            target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())
        ):
            if entry.is_dir() and entry.name in ignore_set:
                continue
            entries.append(
                {
                    "name": entry.name,
                    "path": str(entry.relative_to(root)),
                    "type": "dir" if entry.is_dir() else "file",
                }
            )
        return {"path": str(target.relative_to(root)), "entries": entries}

    def read(self, path: str) -> dict[str, Any]:
        """Read a single file inside the workspace."""
        target = resolve(path)
        if not target.exists():
            raise CodeActFilesError(f"File does not exist: {path}")
        if not target.is_file():
            raise CodeActFilesError(f"Path is not a file: {path}")
        root = workspace_root()
        return {
            "path": str(target.relative_to(root)),
            "content": target.read_text(encoding="utf-8"),
        }

    def readfiles(self, paths: list[str]) -> dict[str, Any]:
        """Read multiple files; same shape as the JSON ``readfiles`` command."""
        if not paths:
            raise CodeActFilesError("'paths' must be a non-empty list.")
        return {"files": [self.read(p) for p in paths]}

    def write(self, path: str, content: str) -> dict[str, Any]:
        """Create or overwrite a single file inside the workspace."""
        target = resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        root = workspace_root()
        return {
            "path": str(target.relative_to(root)),
            "written": True,
            "bytes": len(content.encode("utf-8")),
        }

    def create(
        self,
        path: str,
        content: str = "",
        *,
        is_directory: bool = False,
    ) -> dict[str, Any]:
        """
        Create a single file or directory inside the workspace.

        For a file, parent directories are created as needed. For a directory,
        ``content`` must be empty.
        """
        if is_directory and content:
            raise CodeActFilesError("Cannot create a directory with non-empty content.")

        target = resolve(path)
        root = workspace_root()

        if is_directory:
            target.mkdir(parents=True, exist_ok=True)
            return {"path": str(target.relative_to(root)), "created": True}

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {
            "path": str(target.relative_to(root)),
            "written": True,
            "bytes": len(content.encode("utf-8")),
        }

    def delete(self, path: str) -> dict[str, Any]:
        """Remove a single file, symlink, or directory tree inside the workspace."""
        target = resolve(path)
        root = workspace_root()
        if target == root:
            raise CodeActFilesError("Cannot delete workspace root.")

        if not target.exists() and not target.is_symlink():
            raise CodeActFilesError(f"Path does not exist: {path}")

        if target.is_symlink():
            target.unlink()
        elif target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()

        return {"path": str(target.relative_to(root)), "deleted": True}
