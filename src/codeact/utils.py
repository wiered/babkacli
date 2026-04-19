from ..toolcall.errors import CommandExecutionError
from ..utils.workspace import resolve_within_workspace
from pathlib import Path


def resolve(path: str | Path, error_class: type[RuntimeError]) -> Path:
    try:
        return resolve_within_workspace(path)
    except CommandExecutionError as exc:
        raise error_class(str(exc)) from exc
