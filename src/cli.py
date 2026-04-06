"""Small CLI for manually testing the agent command protocol."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .utils.commands import CommandExecutionError, parse_and_dispatch_agent_response


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_workspace() -> Path:
    return _repo_root() / "test_project"


def _ensure_workspace(workspace: Path) -> Path:
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace.resolve()


def _format_result(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def run_once(raw_response: str) -> dict[str, Any]:
    """Parse and execute a single agent response."""

    outcome = parse_and_dispatch_agent_response(raw_response)
    return {"command": outcome.command, **outcome.data}


def run_repl(*, workspace: Path) -> int:
    """Run an interactive prompt that evaluates one JSON command per line."""

    os.chdir(workspace)
    print(f"Workspace: {workspace}")
    print("Paste one JSON command per line. Type 'exit' to quit.")

    while True:
        try:
            raw = input("test_project> ").strip()
        except EOFError:
            print()
            return 0

        if not raw:
            continue
        if raw.lower() in {"exit", "quit"}:
            return 0

        try:
            result = run_once(raw)
        except (CommandExecutionError, ValueError) as exc:
            print(f"error: {exc}")
            continue

        print(_format_result(result))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="babkacli",
        description="Small CLI for testing the agent command protocol in test_project.",
    )
    parser.add_argument(
        "--workspace",
        default=str(_default_workspace()),
        help="Workspace directory to use. Defaults to ./test_project.",
    )
    parser.add_argument(
        "--once",
        metavar="JSON",
        help="Execute a single JSON command and print the result.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv()

    parser = build_parser()
    args = parser.parse_args(argv)

    workspace = _ensure_workspace(Path(args.workspace))
    os.chdir(workspace)

    if args.once:
        try:
            result = run_once(args.once)
        except (CommandExecutionError, ValueError) as exc:
            parser.exit(status=1, message=f"error: {exc}\n")
        print(_format_result(result))
        return 0

    return run_repl(workspace=workspace)


if __name__ == "__main__":
    raise SystemExit(main())
