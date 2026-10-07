from src.system_prompts.prompts import (
    COMMAND_PROMPTS,
    build_system_prompt,
    build_system_prompt_for_mode,
)


def test_mcp_discovery_and_call_are_distinct_in_both_modes():
    for mode, command in (("ask", "mcp_read"), ("agent", "mcp_call")):
        prompt = build_system_prompt(mode)
        assert "never include a 'tool' field" in prompt
        assert "Discovery and calling are separate turns" in prompt
        assert (
            f'{{"command":"{command}","tool":"list_indexed_sources","arguments":{{}}}}'
            in prompt
        )


def test_build_system_prompt_for_ask_omits_writefile():
    prompt = build_system_prompt("ask")

    assert "Verify edits:" in prompt
    assert "CodeAct filesystem rule:" in prompt
    assert COMMAND_PROMPTS["ls"] in prompt
    assert COMMAND_PROMPTS["readfiles"] in prompt
    assert COMMAND_PROMPTS["done"] in prompt
    assert COMMAND_PROMPTS["writefile"] not in prompt
    assert COMMAND_PROMPTS["createFolders"] not in prompt
    assert COMMAND_PROMPTS["createFiles"] not in prompt
    assert COMMAND_PROMPTS["codeact"] not in prompt
    assert "Gather only what you need" in prompt
    assert "finish with `done`" in prompt
    assert "prefer `ls` + `readfiles`" not in prompt
    assert "Ask mode is read-only" in prompt
    assert "Do not use `writefile`" in prompt
    assert "`runpy`" in prompt and "`codeact`" in prompt


def test_build_system_prompt_for_agent_includes_writefile():
    prompt = build_system_prompt("agent")

    assert COMMAND_PROMPTS["createFolders"] in prompt
    assert COMMAND_PROMPTS["createFiles"] in prompt
    assert COMMAND_PROMPTS["writefile"] in prompt
    assert COMMAND_PROMPTS["runpy"] in prompt
    assert COMMAND_PROMPTS["codeact"] in prompt
    assert "Do not use **`open`**" in prompt
    assert "prefer `ls` + `readfiles`" in prompt
    assert "use `codeact` when batching logic" in prompt
    assert "Agent mode: you may use every command listed below" in prompt


def test_build_system_prompt_for_mode_normalizes_input():
    assert build_system_prompt_for_mode(" AGENT ") == build_system_prompt("agent")


def test_documentation_search_routing_and_recovery_in_both_modes():
    for mode in ("ask", "agent"):
        prompt = build_system_prompt(mode)
        assert (
            '"tool":"search","arguments":{"query":"health check","source_base":'
            in prompt
        )
        assert '"tool":"search_in_file","arguments":{"page_url":' in prompt
        assert "Changing source_base does not fix missing page_url" in prompt
        assert "search only those sources" in prompt
        assert "do not report documentation absent based on failed calls" in prompt
