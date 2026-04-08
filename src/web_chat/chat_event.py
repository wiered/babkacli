from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ChatEvent:
    """A rendered item in the agent chat history."""

    kind: str
    title: str = ""
    body: str = ""
    tone: str = "meta"
    step: int | None = None
    total: int | None = None
    block_id: str = ""
    collapsible: bool = False
    group_id: str = ""
    usage_prompt_tokens: int | None = None
    usage_completion_tokens: int | None = None
    usage_total_tokens: int | None = None
