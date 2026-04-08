import json
import os
from importlib import resources
from typing import Any
from pathlib import Path
from dataclasses import dataclass

from PySide6.QtGui import QFont, QFontDatabase
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage
from azure.core.credentials import AzureKeyCredential

from ..system_prompts.prompts import build_system_prompt_for_mode

ENDPOINT = "https://models.github.ai/inference"
SUPPORTED_MODES = ("ask", "agent")
ALLOWED_COMMANDS_BY_MODE: dict[str, set[str]] = {
    "ask": {"done", "ls", "readfiles"},
    "agent": {
        "codeact",
        "createFiles",
        "createFolders",
        "done",
        "ls",
        "readfiles",
        "runpy",
        "writefile",
    },
}


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


def _get_token() -> str:
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if not token:
        raise RuntimeError("Set GITHUB_TOKEN (or GH_TOKEN) in the environment.")
    return token


def normalize_mode(mode: str) -> str:
    normalized = mode.strip().lower()
    if normalized not in SUPPORTED_MODES:
        raise ValueError(f"Unsupported mode: {mode}")
    return normalized


def build_client() -> ChatCompletionsClient:
    return ChatCompletionsClient(
        endpoint=ENDPOINT,
        credential=AzureKeyCredential(_get_token()),
    )


def allowed_commands_for_mode(mode: str) -> set[str]:
    normalized = normalize_mode(mode)
    return set(ALLOWED_COMMANDS_BY_MODE[normalized])


def extract_completion_usage(response: Any) -> dict[str, int] | None:
    """Pull token counts from an Azure ``ChatCompletions`` response when present."""

    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    out: dict[str, int] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        raw = getattr(usage, key, None)
        if isinstance(raw, int) and raw >= 0:
            out[key] = raw
    return out or None


def call_model(
    client: ChatCompletionsClient,
    *,
    messages: list[Any],
    model: str,
) -> tuple[str, dict[str, int] | None]:
    response = client.complete(
        messages=messages,
        model=model,
        temperature=0.2,
        response_format="json_object",
    )

    message = response.choices[0].message
    content = message.content if message and message.content else ""
    return content.strip(), extract_completion_usage(response)


def format_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


def build_messages(mode: str) -> list[Any]:
    return [SystemMessage(build_system_prompt_for_mode(mode))]


# Bitmap / GDI-era faces that Qt on Windows may report as the system fixed font but
# DirectWrite cannot load via CreateFontFaceFromHDC (see qt.qpa.fonts warnings).
_LEGACY_FIXEDSYS_STYLE_FAMILIES: frozenset[str] = frozenset(
    name.casefold()
    for name in (
        "Fixedsys",
        "Terminal",
        "System",
        "Modern",
        "Small Fonts",
        "MS Sans Serif",
    )
)


def _resolve_safe_monospace_fallback(requested: str | None) -> str | None:
    if not requested:
        return None
    if requested.casefold() not in _LEGACY_FIXEDSYS_STYLE_FAMILIES:
        return requested
    db = QFontDatabase()
    for name in ("Consolas", "Cascadia Mono", "Cascadia Code", "Lucida Console", "Courier New"):
        if db.hasFamily(name):
            return name
    return "Courier New"


_BUNDLED_JETBRAINS_TTF = "JetBrainsMonoNerdFont-Regular.ttf"
_bundled_jetbrains_attempted: bool = False
_bundled_jetbrains_family: str | None = None


def _load_bundled_jetbrains_nerd_font_family() -> str | None:
    """Register the bundled TTF once and return its Qt family name, or None if unavailable."""
    global _bundled_jetbrains_attempted, _bundled_jetbrains_family
    if _bundled_jetbrains_attempted:
        return _bundled_jetbrains_family
    _bundled_jetbrains_attempted = True
    fonts_dir = Path(__file__).resolve().parent / "fonts"
    path = fonts_dir / _BUNDLED_JETBRAINS_TTF
    fid: int
    if path.is_file():
        fid = QFontDatabase.addApplicationFont(str(path))
    else:
        try:
            data = resources.files("src.ui").joinpath("fonts", _BUNDLED_JETBRAINS_TTF).read_bytes()
        except (OSError, TypeError, ValueError):
            _bundled_jetbrains_family = None
            return None
        fid = QFontDatabase.addApplicationFontFromData(data)
    if fid < 0:
        _bundled_jetbrains_family = None
        return None
    names = QFontDatabase.applicationFontFamilies(fid)
    if not names:
        _bundled_jetbrains_family = None
        return None
    _bundled_jetbrains_family = names[0]
    return _bundled_jetbrains_family


def ensure_bundled_jetbrains_nerd_font() -> str | None:
    """Register bundled JetBrains Mono from TTF if present (requires QGuiApplication)."""
    return _load_bundled_jetbrains_nerd_font_family()


def monospace_font_stack_css() -> str:
    """CSS font-family list without generic `monospace` (on Windows/Qt it often resolves to Fixedsys)."""
    ensure_bundled_jetbrains_nerd_font()
    primary = _bundled_jetbrains_family or "JetBrainsMono Nerd Font"
    return f"'{primary}', Consolas, 'Courier New'"


def build_nerd_font(point_size: int, *, fallback_family: str | None = None) -> QFont:
    safe_fallback = _resolve_safe_monospace_fallback(fallback_family)
    bundled = _load_bundled_jetbrains_nerd_font_family()
    if bundled:
        font = QFont(bundled, point_size)
    else:
        font = QFont("JetBrainsMono Nerd Font", point_size)
        if safe_fallback and font.family() != "JetBrainsMono Nerd Font":
            font = QFont(safe_fallback, point_size)
    font.setFixedPitch(True)
    font.setStyleStrategy(
        QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.NoFontMerging
    )
    return font
