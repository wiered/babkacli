"""Terminal widget for the BabkaCode."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from azure.ai.inference.models import AssistantMessage, UserMessage
from PySide6.QtCore import QObject, Signal

if __package__ in {None, ""}:
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[2]))

    from src.toolcall.commands import CommandExecutionError, dispatch_command
    from src.toolcall.json_parser import AgentResponseParseError, parse_agent_response
    from src.utils.workspace import use_workspace_root
    from src.ui.ui_utils import (
        allowed_commands_for_mode,
        build_client,
        call_model,
        format_json,
        normalize_mode,
    )
else:
    from ..toolcall.commands import CommandExecutionError, dispatch_command
    from ..toolcall.json_parser import AgentResponseParseError, parse_agent_response
    from ..utils.workspace import use_workspace_root
    from ..ui.ui_utils import (
        allowed_commands_for_mode,
        build_client,
        call_model,
        format_json,
        normalize_mode,
    )


class AgentWorker(QObject):
    """Run one user request against the agent in a background thread."""

    step_started = Signal(int, int)
    assistant_response = Signal(int, str, object)
    repair_requested = Signal(int, str)
    command_executed = Signal(int, str, object)
    finished = Signal(str, object)
    error = Signal(str)

    def __init__(
        self,
        *,
        workspace: Path,
        model: str,
        mode: str,
        max_steps: int,
        messages: list[Any],
    ) -> None:
        super().__init__()
        self._workspace = workspace
        self._model = model
        self._mode = normalize_mode(mode)
        self._max_steps = max_steps
        self._messages = list(messages)

    def run(self) -> None:
        try:
            client = build_client()
            workspace = self._workspace
            messages = self._messages
            allowed_commands = allowed_commands_for_mode(self._mode)

            for step in range(1, self._max_steps + 1):
                self.step_started.emit(step, self._max_steps)
                raw_response, usage = call_model(
                    client, messages=messages, model=self._model
                )
                messages.append(AssistantMessage(content=raw_response))
                self.assistant_response.emit(step, raw_response, usage)

                try:
                    parsed = parse_agent_response(
                        raw_response,
                        allowed_commands=allowed_commands,
                    )
                    with use_workspace_root(workspace):
                        outcome = dispatch_command(parsed)
                except (
                    AgentResponseParseError,
                    CommandExecutionError,
                    ValueError,
                ) as exc:
                    repair_message = (
                        "Invalid command response from the assistant: "
                        f"{exc}. Return only a JSON object with a supported command."
                    )
                    self.repair_requested.emit(step, repair_message)
                    messages.append(UserMessage(repair_message))
                    if step == self._max_steps:
                        self.finished.emit(repair_message, messages)
                        return
                    continue

                self.command_executed.emit(step, outcome.command, outcome.data)

                if outcome.command == "done":
                    self.finished.emit(str(outcome.data["result"]), messages)
                    return

                messages.append(
                    UserMessage(
                        "Command result:\n"
                        + format_json({"command": outcome.command, **outcome.data})
                    )
                )

            self.finished.emit(
                "Agent stopped after reaching the maximum number of steps.", messages
            )
        except Exception as exc:  # noqa: BLE001 - surface any unexpected backend issue to the UI
            self.error.emit(str(exc))
