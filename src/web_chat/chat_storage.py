"""Persist agent chat sessions under ``~/.babka/chats/<workspace_key>/`` (per workspace).

Override the root with env ``BABKA_HOME`` (defaults to ``Path.home() / ".babka"``).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from azure.ai.inference.models import AssistantMessage, SystemMessage, UserMessage

from .chat_event import ChatEvent
from ..ui.ui_utils import build_messages, normalize_mode

FORMAT_VERSION = 1


def babka_user_data_root() -> Path:
    raw = os.environ.get("BABKA_HOME", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return (Path.home() / ".babka").resolve()


def _workspace_key(workspace: Path) -> str:
    p = workspace.resolve().as_posix().encode("utf-8")
    return hashlib.sha256(p).hexdigest()[:16]


def chats_dir(workspace: Path) -> Path:
    return babka_user_data_root() / "chats" / _workspace_key(workspace)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_chats_dir(workspace: Path) -> Path:
    root = chats_dir(workspace)
    root.mkdir(parents=True, exist_ok=True)
    return root


def chat_file_path(workspace: Path, chat_id: str) -> Path:
    safe = chat_id.replace("/", "").replace("\\", "").replace("..", "")
    if not safe:
        raise ValueError("Invalid chat id")
    return ensure_chats_dir(workspace) / f"{safe}.json"


def archived_chat_file_path(workspace: Path, chat_id: str) -> Path:
    safe = chat_id.replace("/", "").replace("\\", "").replace("..", "")
    if not safe:
        raise ValueError("Invalid chat id")
    root = chats_dir(workspace) / "archive"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{safe}.json"


def resolve_chat_file(workspace: Path, chat_id: str) -> tuple[Path, bool] | None:
    """Return ``(path, is_archived)`` if a chat JSON exists, else ``None``."""

    active = chat_file_path(workspace, chat_id)
    if active.is_file():
        return active, False
    archived = archived_chat_file_path(workspace, chat_id)
    if archived.is_file():
        return archived, True
    return None


def list_saved_chats(workspace: Path) -> list[tuple[str, float, str]]:
    """Return `(chat_id, mtime, title)` sorted by mtime descending (newest first)."""
    root = chats_dir(workspace)
    if not root.is_dir():
        return []
    rows: list[tuple[str, float, str]] = []
    for path in root.glob("*.json"):
        try:
            st = path.stat()
        except OSError:
            continue
        chat_id = path.stem
        title = chat_id
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("title"), str) and data["title"].strip():
                title = data["title"].strip()
        except (OSError, json.JSONDecodeError, TypeError):
            pass
        rows.append((chat_id, st.st_mtime, title))
    rows.sort(key=lambda x: x[1], reverse=True)
    return rows


def list_archived_chats(workspace: Path) -> list[tuple[str, float, str]]:
    """Return `(chat_id, mtime, title)` for chats in the archive subfolder."""

    root = chats_dir(workspace) / "archive"
    if not root.is_dir():
        return []
    rows: list[tuple[str, float, str]] = []
    for path in root.glob("*.json"):
        try:
            st = path.stat()
        except OSError:
            continue
        chat_id = path.stem
        title = chat_id
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and isinstance(data.get("title"), str) and data["title"].strip():
                title = data["title"].strip()
        except (OSError, json.JSONDecodeError, TypeError):
            pass
        rows.append((chat_id, st.st_mtime, title))
    rows.sort(key=lambda x: x[1], reverse=True)
    return rows


def move_chat_to_archive(workspace: Path, chat_id: str) -> None:
    """Move ``<id>.json`` from active chats to ``chats/archive/``."""

    src = chat_file_path(workspace, chat_id)
    if not src.is_file():
        raise FileNotFoundError(src)
    dst = archived_chat_file_path(workspace, chat_id)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))


def move_chat_from_archive(workspace: Path, chat_id: str) -> None:
    """Move ``<id>.json`` from archive back to active ``chats/``."""

    src = archived_chat_file_path(workspace, chat_id)
    if not src.is_file():
        raise FileNotFoundError(src)
    dst = chat_file_path(workspace, chat_id)
    ensure_chats_dir(workspace)
    shutil.move(str(src), str(dst))


def read_last_chat_id(workspace: Path) -> str | None:
    path = chats_dir(workspace) / "last_chat.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    cid = data.get("chat_id")
    return cid if isinstance(cid, str) and cid.strip() else None


def write_last_chat_id(workspace: Path, chat_id: str) -> None:
    path = chats_dir(workspace) / "last_chat.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"chat_id": chat_id}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def serialize_message(msg: Any) -> dict[str, Any]:
    if isinstance(msg, SystemMessage):
        return {"role": "system", "content": msg.content}
    if isinstance(msg, UserMessage):
        return {"role": "user", "content": msg.content}
    if isinstance(msg, AssistantMessage):
        return {"role": "assistant", "content": msg.content}
    raise TypeError(f"Unsupported message type for serialization: {type(msg)!r}")


def deserialize_messages(items: list[dict[str, Any]]) -> list[Any]:
    out: list[Any] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("Message entry must be an object")
        role = item.get("role")
        content = item.get("content")
        if not isinstance(role, str) or not isinstance(content, str):
            raise ValueError("Each message needs string role and content")
        if role == "system":
            out.append(SystemMessage(content))
        elif role == "user":
            out.append(UserMessage(content))
        elif role == "assistant":
            out.append(AssistantMessage(content=content))
        else:
            raise ValueError(f"Unknown message role: {role!r}")
    return out


def chat_events_to_json(events: list[ChatEvent]) -> list[dict[str, Any]]:
    return [asdict(e) for e in events]


def chat_events_from_json(items: list[dict[str, Any]]) -> list[ChatEvent]:
    out: list[ChatEvent] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        step_v = raw.get("step")
        step = step_v if isinstance(step_v, int) else None
        total_v = raw.get("total")
        total = total_v if isinstance(total_v, int) else None
        def _opt_int(key: str) -> int | None:
            v = raw.get(key)
            if isinstance(v, bool) or v is None:
                return None
            if isinstance(v, int):
                return v
            if isinstance(v, float):
                return int(v)
            return None

        out.append(
            ChatEvent(
                kind=str(raw.get("kind", "message")),
                title=str(raw.get("title", "")),
                body=str(raw.get("body", "")),
                tone=str(raw.get("tone", "meta")),
                step=step,
                total=total,
                block_id=str(raw.get("block_id", "")),
                collapsible=bool(raw.get("collapsible", False)),
                group_id=str(raw.get("group_id", "")),
                usage_prompt_tokens=_opt_int("usage_prompt_tokens"),
                usage_completion_tokens=_opt_int("usage_completion_tokens"),
                usage_total_tokens=_opt_int("usage_total_tokens"),
            )
        )
    return out


def derive_title(messages: list[Any], chat_events: list[ChatEvent]) -> str:
    for ev in chat_events:
        if ev.kind == "message" and ev.tone == "user" and ev.body.strip():
            line = ev.body.strip().split("\n", 1)[0].strip()
            if len(line) > 48:
                line = line[:45] + "…"
            return line or "Chat"
    for msg in messages:
        if isinstance(msg, UserMessage) and msg.content.strip():
            line = msg.content.strip().split("\n", 1)[0].strip()
            if len(line) > 48:
                line = line[:45] + "…"
            return line or "Chat"
    return "New chat"


def save_chat_session(
    workspace: Path,
    *,
    chat_id: str,
    mode: str,
    messages: list[Any],
    chat_events: list[ChatEvent],
    collapsed_blocks: set[str],
    next_block_id: int,
    title: str | None = None,
    usage_totals: dict[str, int] | None = None,
    stored_in_archive: bool = False,
) -> None:
    """Write the full chat state under the user ``.babka`` chats tree (active or archive)."""
    mode_norm = normalize_mode(mode)
    t = (title or "").strip() or derive_title(messages, chat_events)
    path = archived_chat_file_path(workspace, chat_id) if stored_in_archive else chat_file_path(workspace, chat_id)
    created = _utc_now_iso()
    try:
        if path.is_file():
            prev = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(prev, dict) and isinstance(prev.get("created_at"), str):
                created = prev["created_at"]
    except (OSError, json.JSONDecodeError, TypeError):
        pass

    ut = usage_totals or {}
    prompt_tok = int(ut.get("prompt_tokens", 0)) if isinstance(ut.get("prompt_tokens"), (int, float)) else 0
    completion_tok = int(ut.get("completion_tokens", 0)) if isinstance(ut.get("completion_tokens"), (int, float)) else 0
    total_tok = int(ut.get("total_tokens", 0)) if isinstance(ut.get("total_tokens"), (int, float)) else 0

    payload = {
        "version": FORMAT_VERSION,
        "id": chat_id,
        "title": t,
        "created_at": created,
        "updated_at": _utc_now_iso(),
        "mode": mode_norm,
        "messages": [serialize_message(m) for m in messages],
        "chat_events": chat_events_to_json(chat_events),
        "collapsed_blocks": sorted(collapsed_blocks),
        "next_block_id": next_block_id,
        "usage_totals": {
            "prompt_tokens": prompt_tok,
            "completion_tokens": completion_tok,
            "total_tokens": total_tok,
        },
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_chat_session(workspace: Path, chat_id: str) -> dict[str, Any]:
    resolved = resolve_chat_file(workspace, chat_id)
    if resolved is None:
        raise FileNotFoundError(chat_file_path(workspace, chat_id))
    path, stored_in_archive = resolved
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Invalid chat file")
    ver = data.get("version", 1)
    if ver != FORMAT_VERSION:
        raise ValueError(f"Unsupported chat format version: {ver}")

    mode = normalize_mode(str(data.get("mode", "agent")))
    raw_messages = data.get("messages")
    if not isinstance(raw_messages, list):
        raise ValueError("Invalid messages in chat file")
    messages = deserialize_messages([m for m in raw_messages if isinstance(m, dict)])
    if not messages:
        messages = build_messages(mode)

    raw_events = data.get("chat_events", [])
    if not isinstance(raw_events, list):
        raw_events = []
    chat_events = chat_events_from_json([e for e in raw_events if isinstance(e, dict)])

    collapsed = data.get("collapsed_blocks", [])
    collapsed_blocks: set[str] = set(collapsed) if isinstance(collapsed, list) else set()

    nb = data.get("next_block_id", 1)
    next_block_id = int(nb) if isinstance(nb, (int, float)) else 1

    title = data.get("title")
    title_str = str(title).strip() if isinstance(title, str) else ""

    ut_raw = data.get("usage_totals")
    if isinstance(ut_raw, dict):
        pr = ut_raw.get("prompt_tokens", 0)
        co = ut_raw.get("completion_tokens", 0)
        to = ut_raw.get("total_tokens", 0)
        usage_totals = {
            "prompt_tokens": int(pr) if isinstance(pr, (int, float)) else 0,
            "completion_tokens": int(co) if isinstance(co, (int, float)) else 0,
            "total_tokens": int(to) if isinstance(to, (int, float)) else 0,
        }
    else:
        usage_totals = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    return {
        "chat_id": chat_id,
        "mode": mode,
        "messages": messages,
        "chat_events": chat_events,
        "collapsed_blocks": collapsed_blocks,
        "next_block_id": max(1, next_block_id),
        "title": title_str or derive_title(messages, chat_events),
        "usage_totals": usage_totals,
        "stored_in_archive": stored_in_archive,
    }


def new_chat_id() -> str:
    return str(uuid.uuid4())


def fresh_session_state(mode: str) -> dict[str, Any]:
    """Default in-memory state for a new chat (no file yet)."""
    m = normalize_mode(mode)
    return {
        "chat_id": new_chat_id(),
        "mode": m,
        "messages": build_messages(m),
        "chat_events": [],
        "collapsed_blocks": set(),
        "next_block_id": 1,
        "title": "New chat",
        "usage_totals": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "stored_in_archive": False,
    }
