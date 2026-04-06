"""Tests for `.babka/chats` persistence."""

from __future__ import annotations

from azure.ai.inference.models import UserMessage

from src.ui.chat_storage import (
    fresh_session_state,
    load_chat_session,
    save_chat_session,
)


def test_chat_roundtrip_preserves_messages_and_events(tmp_path):
    s = fresh_session_state("agent")
    s["chat_events"] = []  # start clean
    s["messages"].append(UserMessage("hello"))

    cid = s["chat_id"]
    save_chat_session(
        tmp_path,
        chat_id=cid,
        mode=s["mode"],
        messages=s["messages"],
        chat_events=s["chat_events"],
        collapsed_blocks=s["collapsed_blocks"],
        next_block_id=s["next_block_id"],
    )

    loaded = load_chat_session(tmp_path, cid)
    assert loaded["chat_id"] == cid
    assert len(loaded["messages"]) == 2
    assert isinstance(loaded["messages"][1], UserMessage)
    assert loaded["messages"][1].content == "hello"
