import html
import re
from pathlib import Path

if __package__ in {None, ""}:
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from src.web_chat.chat_event import ChatEvent
    from src.ui.ui_utils import monospace_font_stack_css
else:
    from .chat_event import ChatEvent
    from ..ui.ui_utils import monospace_font_stack_css


# ── Copy store (populated each render, read by clipboard handler) ──────────────
_copy_blocks: dict[str, str] = {}

# ── Dark palette ──────────────────────────────────────────────────────────────
_BG = "#14161c"
_SURFACE = "#1a1d25"
_SURFACE_ALT = "#0e1015"
_SURFACE_USER = "rgba(99, 102, 241, 0.10)"
_SURFACE_TOOL = "#1a1d25"
_SURFACE_CODE = "#0e1015"
_BORDER = "rgba(255, 255, 255, 0.08)"
_BORDER_STRONG = "rgba(255, 255, 255, 0.14)"
_TEXT = "#e2e4ea"
_TEXT_SOFT = "#8b8fa3"
_TEXT_MUTED = "#525669"
_TEXT_CODE = "#c8ccd8"
_ACCENT = "#6366f1"
_ACCENT_MUTED = "rgba(99, 102, 241, 0.12)"
_SUCCESS = "#34d399"
_ERROR = "#f87171"
_ERROR_BG = "rgba(248, 113, 113, 0.08)"
_WARNING = "#fbbf24"

_FONT_UI = '"Geist", "Inter", "Segoe UI Variable", "Segoe UI", system-ui, sans-serif'


def get_copy_block(block_id: str) -> str | None:
    """Return the raw code content for a given block ID, or None."""
    return _copy_blocks.get(block_id)


def _usage_caption_html(event: ChatEvent, *, mono_css: str) -> str:
    if (
        event.usage_prompt_tokens is None
        and event.usage_completion_tokens is None
        and event.usage_total_tokens is None
    ):
        return ""
    parts: list[str] = []
    if event.usage_prompt_tokens is not None:
        parts.append(f"in {event.usage_prompt_tokens}")
    if event.usage_completion_tokens is not None:
        parts.append(f"out {event.usage_completion_tokens}")
    if event.usage_total_tokens is not None:
        parts.append(f"Σ {event.usage_total_tokens}")
    cap = " · ".join(parts)
    return (
        f'<div style="font-size:10px;color:{_TEXT_MUTED};margin:0 0 4px 0;'
        f' font-family:{mono_css};">{html.escape(cap)}</div>'
    )


# ── Markdown → HTML ────────────────────────────────────────────────────────────


def _md_to_html(text: str, *, mono: str, copy_store: dict[str, str]) -> str:
    """Convert a subset of Markdown to HTML for the dark chat view."""

    lines = text.split("\n")
    out: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # ── fenced code block ```...``` ────────────────────────────
        if line.strip().startswith("```"):
            lang = line.strip()[3:].strip()
            code_lines: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            raw_code = "\n".join(code_lines)

            block_id = f"cb_{len(copy_store)}"
            copy_store[block_id] = raw_code

            code_body = html.escape(raw_code)
            lang_label = html.escape(lang) if lang else ""
            lang_cell = (
                (
                    f'<span style="font-family:{mono}; font-size:10px; color:{_TEXT_MUTED}; letter-spacing:0.06em; text-transform:uppercase;">'
                    f"{lang_label}</span>"
                )
                if lang_label
                else "<span></span>"
            )
            copy_link = (
                f'<a href="copy:{block_id}" '
                f'style="font-size:10px; color:{_TEXT_MUTED}; text-decoration:none; '
                f"padding:2px 8px; border-radius:4px; border:1px solid {_BORDER}; "
                f'background:rgba(255,255,255,0.04);">copy</a>'
            )
            out.append(
                f'<div style="background:{_SURFACE_CODE}; border:1px solid {_BORDER}; '
                f'border-radius:8px; margin:8px 0 12px 0; overflow:hidden;">'
                f'<div style="display:flex; align-items:center; justify-content:space-between; '
                f'padding:7px 12px; border-bottom:1px solid {_BORDER};">'
                f"{lang_cell}{copy_link}"
                f"</div>"
                f'<div style="padding:12px 14px 14px 14px;">'
                f'<pre style="margin:0; font-family:{mono}; font-size:12px; color:{_TEXT_CODE}; '
                f'white-space:pre-wrap; word-break:break-word; line-height:1.6;">{code_body}</pre>'
                f"</div>"
                f"</div>"
            )
            i += 1
            continue

        # ── horizontal rule ────────────────────────────────────────
        if re.fullmatch(r"[-*_]{3,}", line.strip()):
            out.append(
                f'<hr style="border:none; border-top:1px solid {_BORDER}; margin:12px 0;">'
            )
            i += 1
            continue

        # ── headings ───────────────────────────────────────────────
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            level = len(m.group(1))
            size_map = {
                1: "18px",
                2: "16px",
                3: "14px",
                4: "13.5px",
                5: "13px",
                6: "12.5px",
            }
            size = size_map.get(level, "13.5px")
            content = _inline_md(m.group(2), mono=mono)
            out.append(
                f'<div style="font-size:{size}; font-weight:700; color:{_TEXT}; '
                f'margin:12px 0 5px 0;">{content}</div>'
            )
            i += 1
            continue

        # ── unordered list ─────────────────────────────────────────
        if re.match(r"^[-*+]\s+", line):
            out.append(f'<ul style="margin:6px 0 6px 18px; padding:0; color:{_TEXT};">')
            while i < len(lines) and re.match(r"^[-*+]\s+", lines[i]):
                item = _inline_md(re.sub(r"^[-*+]\s+", "", lines[i]), mono=mono)
                out.append(f'<li style="margin:3px 0;">{item}</li>')
                i += 1
            out.append("</ul>")
            continue

        # ── ordered list ───────────────────────────────────────────
        if re.match(r"^\d+\.\s+", line):
            out.append(f'<ol style="margin:6px 0 6px 18px; padding:0; color:{_TEXT};">')
            while i < len(lines) and re.match(r"^\d+\.\s+", lines[i]):
                item = _inline_md(re.sub(r"^\d+\.\s+", "", lines[i]), mono=mono)
                out.append(f'<li style="margin:3px 0;">{item}</li>')
                i += 1
            out.append("</ol>")
            continue

        # ── blank line ─────────────────────────────────────────────
        if not line.strip():
            out.append('<div style="height:8px;"></div>')
            i += 1
            continue

        # ── normal paragraph line ──────────────────────────────────
        out.append(f'<div style="margin:0;">{_inline_md(line, mono=mono)}</div>')
        i += 1

    return "\n".join(out)


def _inline_md(text: str, *, mono: str) -> str:
    """Apply inline Markdown (bold, italic, code, links) to a single line."""
    result: list[str] = []

    pattern = re.compile(
        r"(`[^`]+`)"
        r"|(\*\*[^*]+\*\*)"
        r"|(__[^_]+__)"
        r"|(\*[^*]+\*)"
        r"|(_[^_]+_)"
        r"|(\[([^\]]+)\]\(([^)]+)\))"
    )

    last = 0
    for m in pattern.finditer(text):
        result.append(html.escape(text[last : m.start()]))
        last = m.end()

        raw = m.group(0)
        if raw.startswith("`"):
            inner = html.escape(raw[1:-1])
            result.append(
                f'<code style="font-family:{mono}; font-size:11.5px; '
                f"background:{_SURFACE_ALT}; color:{_TEXT_CODE}; "
                f"border:1px solid {_BORDER}; "
                f'padding:1px 6px; border-radius:4px;">{inner}</code>'
            )
        elif raw.startswith("**") or raw.startswith("__"):
            inner = html.escape(raw[2:-2])
            result.append(f'<strong style="color:{_TEXT};">{inner}</strong>')
        elif raw.startswith("*") or raw.startswith("_"):
            inner = html.escape(raw[1:-1])
            result.append(f'<em style="color:{_TEXT_SOFT};">{inner}</em>')
        elif raw.startswith("["):
            link_text = html.escape(m.group(7))
            link_url = html.escape(m.group(8))
            result.append(
                f'<a href="{link_url}" style="color:{_ACCENT};">{link_text}</a>'
            )

    result.append(html.escape(text[last:]))
    return "".join(result)


# ── HTML renderer ──────────────────────────────────────────────────────────────


def render_chat_history(
    chat_events: list[ChatEvent], collapsed_blocks: set[str]
) -> list[str]:
    global _copy_blocks
    _mono = monospace_font_stack_css()

    copy_store: dict[str, str] = {}

    html_parts = [
        f"""<html>
<head>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&display=swap');
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    padding: 20px 20px 16px 20px;
    background:
      linear-gradient(rgba(255, 0, 255, 0.14), rgba(255, 0, 255, 0.14)),
      {_BG};
    color: {_TEXT};
    font-family: {_FONT_UI};
    font-size: 13.5px;
    line-height: 1.65;
    border: 3px solid #ff00ff;
  }}

  code {{
    font-family: {_mono};
    font-size: 11.5px;
    background: {_SURFACE_ALT};
    color: {_TEXT_CODE};
    border: 1px solid {_BORDER};
    padding: 1px 6px;
    border-radius: 4px;
  }}

  a {{ color: {_ACCENT}; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}

  pre {{
    margin: 0;
    font-family: {_mono};
    font-size: 12px;
    white-space: pre-wrap;
    word-break: break-word;
    line-height: 1.6;
    color: {_TEXT_CODE};
  }}

  strong {{ color: {_TEXT}; }}
  em {{ color: {_TEXT_SOFT}; font-style: italic; }}

  .msg-body {{
    white-space: pre-wrap;
    line-height: 1.65;
  }}

  .label {{
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 4px;
  }}

  .dim {{ color: {_TEXT_SOFT}; font-size: 12px; }}

  /* ── step / duration divider ── */
  .step-divider {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 20px 0 12px 0;
    color: {_TEXT_MUTED};
    font-size: 11px;
  }}
  .step-divider::before,
  .step-divider::after {{
    content: "";
    flex: 1;
    height: 1px;
    background: {_BORDER};
  }}
  .step-divider-text {{
    white-space: nowrap;
    padding: 0 4px;
    color: {_TEXT_MUTED};
    font-size: 11px;
  }}

  /* ── tool run row ── */
  a.tool-run-row {{
    display: flex;
    align-items: center;
    gap: 6px;
    color: inherit;
    text-decoration: none;
    padding: 4px 0;
    cursor: pointer;
  }}
  a.tool-run-row:hover .tool-run-cmd {{
    color: {_TEXT};
  }}
  .tool-run-label {{
    color: {_TEXT_MUTED};
    font-size: 11.5px;
  }}
  .tool-run-cmd {{
    font-family: {_mono};
    font-size: 11.5px;
    color: {_TEXT_SOFT};
  }}
  .tool-run-arrow {{
    color: {_TEXT_MUTED};
    font-size: 10px;
    margin-left: 2px;
  }}

  /* ── tool block expanded content ── */
  .tool-content {{
    margin: 6px 0 0 0;
    padding: 10px 14px;
    background: {_SURFACE};
    border-left: 2px solid {_BORDER_STRONG};
    border-radius: 0 6px 6px 0;
  }}

  /* ── error block ── */
  .error-block {{
    margin: 8px 0 12px 0;
    padding: 12px 16px;
    background: {_ERROR_BG};
    border-left: 3px solid {_ERROR};
    border-radius: 0 8px 8px 0;
  }}

  /* ── assistant result ── */
  .assistant-result {{
    line-height: 1.7;
    color: {_TEXT};
  }}

  /* ── toggle link (non-tool blocks) ── */
  .toggle-link {{
    color: {_TEXT_MUTED};
    font-size: 11px;
    text-decoration: none;
    margin-left: 8px;
  }}
  .toggle-link:hover {{ color: {_TEXT_SOFT}; }}
</style>
</head>
<body>
"""
    ]

    for event in chat_events:
        if event.group_id and event.group_id in collapsed_blocks:
            continue

        # ── Work group header ──────────────────────────────────────────────────
        if event.kind == "group_header":
            collapsed = event.block_id in collapsed_blocks
            arrow = "&rsaquo;" if collapsed else "&#10549;"
            html_parts.append(f"""
<div id="chat-block-{html.escape(event.block_id)}" class="step-divider" style="margin: 20px 0 16px 0;">
  <a href="toggle:{html.escape(event.block_id)}"
     style="color:{_TEXT_SOFT}; text-decoration:none; white-space:nowrap; padding:0 6px; cursor:pointer; font-size:11.5px;">
    {html.escape(event.title)}&nbsp;<span id="chat-arrow-{html.escape(event.block_id)}">{arrow}</span>
  </a>
</div>
""")
            continue

        # ── Chat messages ──────────────────────────────────────────────────────
        if event.kind == "message":
            if event.tone == "user":
                user_text = event.body.replace("\r\n", "\n").replace("\r", "\n").strip()
                body_html = html.escape(user_text).replace("\n", "<br>")
                html_parts.append(f"""
<div style="margin: 12px 0 18px 0; display: flex; flex-direction: column; align-items: flex-end;">
  <div style="max-width: 72%; background: rgba(99, 102, 241, 0.10);
       border: 1px solid rgba(99, 102, 241, 0.20);
       border-radius: 14px 14px 4px 14px;
       padding: 12px 16px; color: {_TEXT}; font-size: 13.5px;
       line-height: 1.6; word-wrap: break-word; overflow-wrap: break-word;">{body_html}</div>
</div>
""")

            elif event.tone == "assistant":
                md_html = _md_to_html(event.body, mono=_mono, copy_store=copy_store)
                html_parts.append(f"""
<div class="assistant-result" style="margin: 8px 0 18px 0;">
{md_html}
</div>
""")

            elif event.tone == "error":
                body_html = html.escape(event.body).replace("\n", "<br>")
                html_parts.append(f"""
<div class="error-block">
  <div class="label" style="color: {_ERROR}; margin-bottom: 6px;">{html.escape(event.title)}</div>
  <div class="msg-body" style="color: rgba(248, 113, 113, 0.85);">{body_html}</div>
</div>
""")

            else:  # meta / system
                html_parts.append(f"""
<div class="step-divider" style="margin:16px 0 12px 0;">
  <span class="step-divider-text">{html.escape(event.body)}</span>
</div>
""")
            continue

        # ── Step indicator ─────────────────────────────────────────────────────
        if event.kind == "step":
            step_label = (
                html.escape(event.title)
                if event.title
                else f"{event.step}\u202f/\u202f{event.total}"
            )
            html_parts.append(f"""
<div class="step-divider" style="margin: 22px 0 14px 0;">
  <span class="step-divider-text">{step_label}&rsaquo;</span>
</div>
""")
            continue

        # ── Tool / code block ──────────────────────────────────────────────────
        if event.kind == "block":
            collapsed = event.block_id in collapsed_blocks
            title_esc = html.escape(event.title)
            bid_esc = html.escape(event.block_id)

            if event.tone == "tool":
                arrow = "&rsaquo;" if collapsed else "&#10549;"
                row = (
                    f'<a class="tool-run-row" href="toggle:{bid_esc}">'
                    f'<span class="tool-run-label">Ran</span> '
                    f'<span class="tool-run-cmd">{title_esc.replace("Tool: ", "")}</span>'
                    f'<span class="tool-run-arrow" id="chat-arrow-{bid_esc}">&nbsp;{arrow}</span>'
                    f"</a>"
                )
                html_parts.append(f"""
<div id="chat-block-{bid_esc}" style="margin: 4px 0 8px 0;">
  {row}
  <div id="chat-content-{bid_esc}" class="tool-content" style="{"" if not collapsed else "display:none;"}">
    <pre>{html.escape(event.body)}</pre>
  </div>
</div>
""")

            elif event.tone == "error":
                toggle_icon = "&rsaquo;" if collapsed else "&#10549;"
                content_html = f'<pre style="color: rgba(248, 113, 113, 0.85); margin: 0;">{html.escape(event.body)}</pre>'
                html_parts.append(f"""
<div id="chat-block-{bid_esc}" class="error-block" style="margin: 6px 0 10px 0;">
  <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:6px;">
    <span class="label" style="color: {_ERROR};">{title_esc}</span>
    <a class="toggle-link" href="toggle:{bid_esc}"><span id="chat-arrow-{bid_esc}">{toggle_icon}</span></a>
  </div>
  <div id="chat-content-{bid_esc}" style="{"" if not collapsed else "display:none;"}">{content_html}</div>
</div>
""")

            else:  # assistant / meta blocks
                toggle_icon = "&rsaquo;" if collapsed else "&#10549;"
                content_html = (
                    f'<pre style="color: {_TEXT_CODE};">{html.escape(event.body)}</pre>'
                )
                label_color = _SUCCESS if event.tone == "assistant" else _TEXT_SOFT
                usage_html = _usage_caption_html(event, mono_css=_mono)
                html_parts.append(f"""
<div id="chat-block-{bid_esc}" style="margin: 4px 0 10px 0;">
  <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">
    <a class="toggle-link" style="color:{label_color}; font-size:10px; font-weight:700;
       letter-spacing:0.08em; text-transform:uppercase;"
       href="toggle:{bid_esc}">{title_esc}&nbsp;<span id="chat-arrow-{bid_esc}">{toggle_icon}</span></a>
  </div>
  {usage_html}
  <div id="chat-content-{bid_esc}" style="{"" if not collapsed else "display:none;"}">{content_html}</div>
</div>
""")

    html_parts.append("</body></html>")

    _copy_blocks.clear()
    _copy_blocks.update(copy_store)

    return html_parts
