"""Terminal widget for the BabkaCode."""

from __future__ import annotations

import argparse
import html
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import AssistantMessage, SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
from PySide6.QtCore import QDir, QModelIndex, QObject, QProcess, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QAction, QFont, QFontDatabase, QKeySequence, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileSystemModel,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QTextBrowser,
    QPlainTextEdit,
    QToolBar,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

if __package__ in {None, ""}:
    from ..system_prompts.prompts import build_system_prompt_for_mode
    from ..toolcall.json_parser import AgentResponseParseError, parse_agent_response
else:
    from ..system_prompts.prompts import build_system_prompt_for_mode
    from ..toolcall.json_parser import AgentResponseParseError, parse_agent_response
    from ..ui.ui_utils import (
        normalize_mode,
        build_client,
        allowed_commands_for_mode,
        call_model,
        dispatch_workspace_command,
        format_json,
        WorkspaceCommandError
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
                raw_response, usage = call_model(client, messages=messages, model=self._model)
                messages.append(AssistantMessage(content=raw_response))
                self.assistant_response.emit(step, raw_response, usage)

                try:
                    parsed = parse_agent_response(
                        raw_response,
                        allowed_commands=allowed_commands,
                    )
                    outcome = dispatch_workspace_command(
                        workspace,
                        parsed.command,
                        parsed.arguments,
                    )
                except (AgentResponseParseError, WorkspaceCommandError, ValueError) as exc:
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

            self.finished.emit("Agent stopped after reaching the maximum number of steps.", messages)
        except Exception as exc:  # noqa: BLE001 - surface any unexpected backend issue to the UI
            self.error.emit(str(exc))