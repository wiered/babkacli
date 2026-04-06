"""Interactive GitHub Models agent for the workspace."""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
from pathlib import Path
from typing import Any

from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import AssistantMessage, SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv

if __package__ in {None, ""}:
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[1]))

    from src.system_prompts.prompts import build_system_prompt_for_mode
    from src.utils.commands import CommandExecutionError, parse_and_dispatch_agent_response
    from src.utils.json_parser import AgentResponseParseError
else:
    from .system_prompts.prompts import build_system_prompt_for_mode
    from .utils.commands import CommandExecutionError, parse_and_dispatch_agent_response
    from .utils.json_parser import AgentResponseParseError

ENDPOINT = "https://models.github.ai/inference"
DEFAULT_MODEL = os.getenv("GITHUB_MODEL", "openai/gpt-4.1-mini")
DEFAULT_MAX_STEPS = 8


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_workspace() -> Path:
    return _repo_root() / "test_project"


def _ensure_workspace(workspace: Path) -> Path:
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace.resolve()


def _get_token() -> str:
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if not token:
        raise RuntimeError("Set GITHUB_TOKEN (or GH_TOKEN) in the environment.")
    return token


def _format_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def _build_client() -> ChatCompletionsClient:
    return ChatCompletionsClient(
        endpoint=ENDPOINT,
        credential=AzureKeyCredential(_get_token()),
    )


def _build_messages() -> list[Any]:
    return [SystemMessage(build_system_prompt_for_mode("agent"))]


def _call_model(
    client: ChatCompletionsClient,
    *,
    messages: list[Any],
    model: str,
) -> str:
    response = client.complete(
        messages=messages,
        model=model,
        temperature=0.2,
        response_format="json_object",
    )

    message = response.choices[0].message
    content = message.content if message and message.content else ""
    return content.strip()


def _execute_agent_turn(
    client: ChatCompletionsClient,
    *,
    messages: list[Any],
    model: str,
    max_steps: int,
) -> str:
    """Run one user turn until the agent returns `done` or hits the step limit."""

    for step in range(1, max_steps + 1):
        raw_response = _call_model(client, messages=messages, model=model)
        messages.append(AssistantMessage(content=raw_response))

        try:
            outcome = parse_and_dispatch_agent_response(raw_response)
        except (AgentResponseParseError, CommandExecutionError, ValueError) as exc:
            repair_message = (
                "Invalid command response from the assistant: "
                f"{exc}. Return only a JSON object with a supported command."
            )
            messages.append(UserMessage(repair_message))
            if step == max_steps:
                return repair_message
            continue

        print(_format_json({"command": outcome.command, **outcome.data}))

        if outcome.command == "done":
            return str(outcome.data["result"])

        messages.append(
            UserMessage(
                "Command result:\n"
                + _format_json({"command": outcome.command, **outcome.data})
            )
        )

    return "Agent stopped after reaching the maximum number of steps."


def run_repl(*, workspace: Path, model: str, max_steps: int) -> int:
    os.chdir(workspace)

    client = _build_client()
    messages = _build_messages()

    print(f"Workspace: {workspace}")
    print("Type a task in natural language. Type 'exit' or 'quit' to stop.")

    while True:
        try:
            user_text = input("BabkaCLI> ").strip()
        except EOFError:
            print()
            return 0

        if not user_text:
            continue
        if user_text.lower() in {"/exit", "exit", "quit"}:
            return 0
        if user_text.lower() in {"/md"}:
            text = """
Напиши полноценно форматированный markdown документ с демонстрацией
всех форматирований доступных в result для теста отображения markdown в клиенте
            """
            messages.append(UserMessage(text))
            result = _execute_agent_turn(
                client,
                messages=messages,
                model=model,
                max_steps=max_steps,
            )
            continue

        messages.append(UserMessage(user_text))
        result = _execute_agent_turn(
            client,
            messages=messages,
            model=model,
            max_steps=max_steps,
        )
        print(result)


def _split_ui_cli(argv: list[str]) -> tuple[str, list[str]]:
    """Return (mode, rest). First token `ui` or `cli` selects mode; else terminal agent (cli)."""

    if argv and argv[0] == "ui":
        return "ui", argv[1:]
    if argv and argv[0] == "cli":
        return "cli", argv[1:]
    return "cli", argv


def _print_root_help() -> None:
    print(
        textwrap.dedent(
            """\
            usage: babkacli [{cli|ui}] [options]

            Single entrypoint: terminal agent (cli) or desktop UI (ui). If you omit the
            subcommand, the terminal agent runs (same as `babkacli cli`).

            Terminal agent:
              babkacli [cli] [--workspace DIR] [--model NAME] [--max-steps N] [--once TASK]

            Desktop UI:
              babkacli ui [--workspace DIR] [--model NAME] [--max-steps N]

            For full options: babkacli cli --help   |   babkacli ui --help
            """
        ).rstrip()
    )


def build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="babkacli cli",
        description="Interactive GitHub Models agent that can inspect and edit the workspace.",
    )
    parser.add_argument(
        "--workspace",
        default=str(_default_workspace()),
        help="Workspace directory to use. Defaults to ./test_project.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="GitHub Models model name. Defaults to openai/gpt-5.",
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=DEFAULT_MAX_STEPS,
        help="Maximum command turns per user message.",
    )
    parser.add_argument(
        "--once",
        metavar="TASK",
        help="Run a single user task and print the result.",
    )
    return parser


def _run_ui(argv: list[str]) -> int:
    from src.ui import ui as ui_entry

    return ui_entry.main(argv)


def _run_once(*, task: str, workspace: Path, model: str, max_steps: int) -> int:
    os.chdir(workspace)

    client = _build_client()
    messages = _build_messages()
    messages.append(UserMessage(task))

    result = _execute_agent_turn(
        client,
        messages=messages,
        model=model,
        max_steps=max_steps,
    )
    print(result)
    return 0


def main(argv: list[str] | None = None) -> int:
    load_dotenv()

    argv = sys.argv[1:] if argv is None else list(argv)

    if argv in (["-h"], ["--help"]):
        _print_root_help()
        return 0

    mode, rest = _split_ui_cli(argv)
    if mode == "ui":
        return _run_ui(rest)

    parser = build_cli_parser()
    args = parser.parse_args(rest)

    workspace = _ensure_workspace(Path(args.workspace))
    model = args.model
    max_steps = max(1, args.max_steps)

    try:
        if args.once:
            return _run_once(
                task=args.once,
                workspace=workspace,
                model=model,
                max_steps=max_steps,
            )
        return run_repl(workspace=workspace, model=model, max_steps=max_steps)
    except RuntimeError as exc:
        parser.exit(status=1, message=f"error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
