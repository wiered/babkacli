"""Helpers for parsing JSON responses from the AI agent."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


class AgentResponseParseError(ValueError):
    """Raised when an agent response cannot be parsed as a command JSON object."""


@dataclass(slots=True)
class ParsedAgentCommand:
    """Normalized command extracted from the agent response."""

    command: str
    arguments: dict[str, Any]


def _strip_code_fence(text: str) -> str:
    """Remove a single fenced markdown block if the agent wrapped JSON in it."""

    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if len(lines) >= 2 and lines[0].startswith("```"):
        content = lines[1:]
        if content and content[-1].strip().startswith("```"):
            content = content[:-1]
        return "\n".join(content).strip()

    return stripped


def _extract_json_object(text: str) -> str:
    """Extract the first balanced JSON object from a raw assistant response."""

    candidate = _strip_code_fence(text)
    if not candidate:
        raise AgentResponseParseError("Empty agent response.")

    start = candidate.find("{")
    if start == -1:
        raise AgentResponseParseError("No JSON object found in agent response.")

    depth = 0
    in_string = False
    escape = False
    end = None

    for index in range(start, len(candidate)):
        char = candidate[index]

        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                end = index + 1
                break

    if end is None:
        raise AgentResponseParseError("Unbalanced JSON object in agent response.")

    return candidate[start:end]


def parse_agent_response(
    raw_response: str,
    *,
    allowed_commands: set[str] | None = None,
) -> ParsedAgentCommand:
    """
    Parse an AI agent response into a normalized command.

    The expected JSON shape is:
    {"command":"ls","path":"."}

    Extra keys are preserved in the returned arguments mapping.
    """

    json_text = _extract_json_object(raw_response)

    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise AgentResponseParseError(
            f"Invalid JSON agent response: {exc.msg}"
        ) from exc

    if not isinstance(payload, dict):
        raise AgentResponseParseError("Agent response must be a JSON object.")

    command = payload.get("command")
    if not isinstance(command, str) or not command.strip():
        raise AgentResponseParseError(
            "Agent response must include a non-empty string 'command'."
        )

    normalized_command = command.strip()
    if allowed_commands is not None and normalized_command not in allowed_commands:
        allowed = ", ".join(sorted(allowed_commands))
        raise AgentResponseParseError(
            f"Unsupported command '{normalized_command}'. Allowed commands: {allowed}."
        )

    arguments = {key: value for key, value in payload.items() if key != "command"}
    return ParsedAgentCommand(command=normalized_command, arguments=arguments)


def parse_agent_response_as_dict(
    raw_response: str,
    *,
    allowed_commands: set[str] | None = None,
) -> dict[str, Any]:
    """Compatibility helper that returns a plain dictionary."""

    parsed = parse_agent_response(raw_response, allowed_commands=allowed_commands)
    return {"command": parsed.command, **parsed.arguments}
