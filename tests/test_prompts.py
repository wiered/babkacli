from src.system_prompts.prompts import (
    COMMAND_PROMPTS,
    build_system_prompt,
    build_system_prompt_for_mode,
)


def test_build_system_prompt_for_ask_omits_writefile():
    prompt = build_system_prompt("ask")

    assert COMMAND_PROMPTS["ls"] in prompt
    assert COMMAND_PROMPTS["readfiles"] in prompt
    assert COMMAND_PROMPTS["done"] in prompt
    assert COMMAND_PROMPTS["writefile"] not in prompt
    assert COMMAND_PROMPTS["createFolders"] not in prompt
    assert COMMAND_PROMPTS["createFiles"] not in prompt
    assert COMMAND_PROMPTS["codeact"] not in prompt


def test_build_system_prompt_for_agent_includes_writefile():
    prompt = build_system_prompt("agent")

    assert COMMAND_PROMPTS["createFolders"] in prompt
    assert COMMAND_PROMPTS["createFiles"] in prompt
    assert COMMAND_PROMPTS["writefile"] in prompt
    assert COMMAND_PROMPTS["runpy"] in prompt
    assert COMMAND_PROMPTS["codeact"] in prompt


def test_build_system_prompt_for_mode_normalizes_input():
    assert build_system_prompt_for_mode(" AGENT ") == build_system_prompt("agent")
