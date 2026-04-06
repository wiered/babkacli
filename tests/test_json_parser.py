import pytest

from src.utils.json_parser import (
    AgentResponseParseError,
    ParsedAgentCommand,
    parse_agent_response,
    parse_agent_response_as_dict,
)


def test_parse_agent_response_strips_code_fence_and_keeps_extra_fields():
    raw = """```json
    {"command": "ls", "path": ".", "extra": 1}
    ```"""

    parsed = parse_agent_response(raw, allowed_commands={"ls"})

    assert parsed == ParsedAgentCommand(command="ls", arguments={"path": ".", "extra": 1})


def test_parse_agent_response_rejects_unsupported_command():
    with pytest.raises(AgentResponseParseError, match="Unsupported command 'writefile'"):
        parse_agent_response('{"command": "writefile"}', allowed_commands={"ls"})


def test_parse_agent_response_as_dict_returns_plain_mapping():
    result = parse_agent_response_as_dict('{"command": "done", "result": "ok"}')

    assert result == {"command": "done", "result": "ok"}
