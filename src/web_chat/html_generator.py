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
        f'<div style="font-size:10px;color:#4a4a52;margin:0 0 4px 0;'
        f' font-family:{mono_css};">{html.escape(cap)}</div>'
    )


# ── Markdown → HTML ────────────────────────────────────────────────────────────

def _md_to_html(text: str, *, mono: str, copy_store: dict[str, str]) -> str:
    """Convert a subset of Markdown to HTML for the chat web view."""

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

            # Store for clipboard
            block_id = f"cb_{len(copy_store)}"
            copy_store[block_id] = raw_code

            code_body = html.escape(raw_code)
            lang_label = html.escape(lang) if lang else ""
            lang_cell = (
                f'<span style="font-family:{mono}; font-size:10px; color:#5a5a64;">'
                f'{lang_label}</span>'
            ) if lang_label else "<span></span>"
            copy_link = (
                f'<a href="copy:{block_id}" style="font-size:10px; color:#4a4a52;'
                f' text-decoration:none;">copy</a>'
            )
            out.append(
                f'<table cellpadding="0" cellspacing="0"'
                f' style="width:100%; border-collapse:separate; border-spacing:0;'
                f' background:#111114; border:1px solid #2a2a2e;'
                f' border-radius:8px; margin:6px 0 10px 0;">'
                f'<tr>'
                f'<td style="padding:5px 12px 4px 12px;'
                f' border-radius:8px 0 0 0;">{lang_cell}</td>'
                f'<td style="padding:5px 12px 4px 12px; text-align:right;'
                f' border-radius:0 8px 0 0;">{copy_link}</td>'
                f'</tr>'
                f'<tr>'
                f'<td colspan="2" style="border-top:1px solid #2a2a2e;'
                f' padding:8px 14px 12px 14px;'
                f' border-radius:0 0 8px 8px;">'
                f'<pre style="margin:0; font-family:{mono}; font-size:12px;'
                f' color:#b0b0b8; white-space:pre-wrap; word-break:break-word;'
                f' line-height:1.55;">{code_body}</pre>'
                f'</td></tr>'
                f'</table>'
            )
            i += 1
            continue

        # ── horizontal rule ────────────────────────────────────────
        if re.fullmatch(r"[-*_]{3,}", line.strip()):
            out.append('<hr style="border:none; border-top:1px solid #2a2a2e; margin:10px 0;">')
            i += 1
            continue

        # ── headings ───────────────────────────────────────────────
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            level = len(m.group(1))
            size_map = {1: "18px", 2: "16px", 3: "14px", 4: "13.5px", 5: "13px", 6: "12.5px"}
            size = size_map.get(level, "13.5px")
            content = _inline_md(m.group(2), mono=mono)
            out.append(
                f'<div style="font-size:{size}; font-weight:700; color:#e0e0e0;'
                f' margin:10px 0 4px 0;">{content}</div>'
            )
            i += 1
            continue

        # ── unordered list ─────────────────────────────────────────
        if re.match(r"^[-*+]\s+", line):
            out.append('<ul style="margin:4px 0 4px 18px; padding:0;">')
            while i < len(lines) and re.match(r"^[-*+]\s+", lines[i]):
                item = _inline_md(re.sub(r"^[-*+]\s+", "", lines[i]), mono=mono)
                out.append(f'<li style="margin:1px 0;">{item}</li>')
                i += 1
            out.append("</ul>")
            continue

        # ── ordered list ───────────────────────────────────────────
        if re.match(r"^\d+\.\s+", line):
            out.append('<ol style="margin:4px 0 4px 18px; padding:0;">')
            while i < len(lines) and re.match(r"^\d+\.\s+", lines[i]):
                item = _inline_md(re.sub(r"^\d+\.\s+", "", lines[i]), mono=mono)
                out.append(f'<li style="margin:1px 0;">{item}</li>')
                i += 1
            out.append("</ol>")
            continue

        # ── blank line ─────────────────────────────────────────────
        if not line.strip():
            out.append('<div style="height:6px;"></div>')
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
        r"(`[^`]+`)"                   # inline code
        r"|(\*\*[^*]+\*\*)"            # bold **...**
        r"|(__[^_]+__)"                # bold __...__
        r"|(\*[^*]+\*)"                # italic *...*
        r"|(_[^_]+_)"                  # italic _..._
        r"|(\[([^\]]+)\]\(([^)]+)\))"  # link [text](url)
    )

    last = 0
    for m in pattern.finditer(text):
        result.append(html.escape(text[last:m.start()]))
        last = m.end()

        raw = m.group(0)
        if raw.startswith("`"):
            inner = html.escape(raw[1:-1])
            result.append(
                f'<code style="font-family:{mono}; font-size:12px;'
                f' background:#222226; color:#d4d4d8;'
                f' border:1px solid #2a2a2e;'
                f' padding:1px 5px; border-radius:4px;">{inner}</code>'
            )
        elif raw.startswith("**") or raw.startswith("__"):
            inner = html.escape(raw[2:-2])
            result.append(f"<strong>{inner}</strong>")
        elif raw.startswith("*") or raw.startswith("_"):
            inner = html.escape(raw[1:-1])
            result.append(f"<em>{inner}</em>")
        elif raw.startswith("["):
            link_text = html.escape(m.group(7))
            link_url  = html.escape(m.group(8))
            result.append(f'<a href="{link_url}" style="color:#60a5fa;">{link_text}</a>')

    result.append(html.escape(text[last:]))
    return "".join(result)


# ── HTML renderer ──────────────────────────────────────────────────────────────

def render_chat_history(chat_events: list[ChatEvent], collapsed_blocks: set[str]) -> list[str]:
    global _copy_blocks
    _mono = monospace_font_stack_css()

    # Rebuild copy store from scratch on every render
    copy_store: dict[str, str] = {}

    html_parts = [
        f"""<html>
<head>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    padding: 20px 20px 16px 20px;
    background: #161618;
    color: #d0d0d0;
    font-family: "Segoe UI Variable", "Segoe UI", system-ui, -apple-system, sans-serif;
    font-size: 13.5px;
    line-height: 1.65;
  }}

  code {{
    font-family: {_mono};
    font-size: 12px;
    background: #222226;
    color: #d4d4d8;
    border: 1px solid #2a2a2e;
    padding: 1px 5px;
    border-radius: 4px;
  }}

  a {{ color: #60a5fa; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}

  pre {{
    margin: 6px 0 0 0;
    font-family: {_mono};
    font-size: 12px;
    white-space: pre-wrap;
    word-break: break-word;
    line-height: 1.55;
    color: #b0b0b8;
  }}

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

  .dim {{ color: #4a4a52; font-size: 12px; }}

  /* ── step / duration divider ── */
  .step-divider {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 20px 0 12px 0;
    color: #3a3a40;
    font-size: 12px;
  }}
  .step-divider::before,
  .step-divider::after {{
    content: "";
    flex: 1;
    height: 1px;
    background: #2a2a2e;
  }}
  .step-divider-text {{
    white-space: nowrap;
    padding: 0 2px;
    color: #4a4a52;
  }}

  /* ── tool run row — entire row is a link ── */
  a.tool-run-row {{
    display: block;
    color: inherit;
    text-decoration: none;
    padding: 2px 0;
    cursor: pointer;
  }}
  a.tool-run-row:hover .tool-run-cmd {{
    color: #d0d0d0;
  }}
  a.tool-run-row:hover .tool-run-arrow {{
    color: #8a8a96;
  }}
  .tool-run-label {{
    color: #4a4a52;
    font-size: 12.5px;
  }}
  .tool-run-cmd {{
    font-family: {_mono};
    font-size: 12px;
    color: #8a8a96;
  }}
  .tool-run-arrow {{
    color: #3a3a40;
    font-size: 10px;
    margin-left: 4px;
  }}

  /* ── tool block expanded content ── */
  .tool-content {{
    margin: 4px 0 0 0;
    padding: 8px 12px;
    background: #111114;
    border-left: 2px solid #2a2a2e;
    border-radius: 0 4px 4px 0;
  }}

  /* ── error block ── */
  .error-block {{
    margin: 8px 0 12px 0;
    padding: 10px 14px;
    background: #1c1014;
    border-left: 3px solid #7a2020;
    border-radius: 0 8px 8px 0;
  }}

  /* ── assistant result ── */
  .assistant-result {{
    line-height: 1.7;
    color: #d0d0d0;
  }}
  .assistant-result strong {{ color: #e8e8e8; }}
  .assistant-result em {{ color: #b0b0b8; font-style: italic; }}
  .assistant-result h1,
  .assistant-result h2,
  .assistant-result h3 {{ color: #e8e8e8; font-weight: 700; }}

  /* ── toggle link (non-tool blocks) ── */
  .toggle-link {{
    color: #3a3a40;
    font-size: 11px;
    text-decoration: none;
    margin-left: 8px;
  }}
  .toggle-link:hover {{ color: #5a5a64; text-decoration: none; }}
</style>
</head>
<body>
"""
    ]

    for event in chat_events:

        # ── Skip events belonging to a collapsed work group ───────────────────
        if event.group_id and event.group_id in collapsed_blocks:
            continue

        # ── Work group header ("Работал на протяжении X ›") ──────────────────
        if event.kind == "group_header":
            collapsed = event.block_id in collapsed_blocks
            arrow = "&rsaquo;" if collapsed else "&#10549;"
            html_parts.append(f"""
<div class="step-divider" style="margin: 18px 0 14px 0;">
  <a href="toggle:{html.escape(event.block_id)}"
     style="color:#4a4a52; text-decoration:none; white-space:nowrap; padding:0 4px; cursor:pointer;">
    {html.escape(event.title)}&nbsp;{arrow}
  </a>
</div>
""")
            continue

        # ── Chat messages ─────────────────────────────────────────────────────
        if event.kind == "message":

            if event.tone == "user":
                # Normalize newlines, strip ends; pre-wrap would also preserve
                # indentation from the HTML template around the injected body.
                user_text = event.body.replace("\r\n", "\n").replace("\r", "\n").strip()
                body_html = html.escape(user_text).replace("\n", "<br>")
                html_parts.append(f"""
<div style="margin: 10px 0 16px 0; display: flex; flex-direction: column; align-items: flex-end;">
  <table cellpadding="0" cellspacing="0"
         style="max-width: 72%; border-collapse: separate; border-spacing: 0;">
    <tr>
      <td style="background-color: #222226; border: 1px solid #2a2a2e;
          border-radius: 14px 14px 4px 14px;
          padding: 10px 16px; color: #e8e8e8; font-size: 13.5px;
          line-height: 1.6; white-space: normal; word-wrap: break-word; overflow-wrap: break-word;">{body_html}</td>
    </tr>
  </table>
</div>
""")

            elif event.tone == "assistant":
                md_html = _md_to_html(event.body, mono=_mono, copy_store=copy_store)
                html_parts.append(f"""
<div class="assistant-result" style="margin: 6px 0 16px 0;">
{md_html}
</div>
""")

            elif event.tone == "error":
                body_html = html.escape(event.body).replace("\n", "<br>")
                html_parts.append(f"""
<div class="error-block">
  <div class="label" style="color: #e05555; margin-bottom: 4px;">{html.escape(event.title)}</div>
  <div class="msg-body" style="color: #d49090;">{body_html}</div>
</div>
""")

            else:  # meta / system
                html_parts.append(f"""
<div class="step-divider">
  <span class="step-divider-text">{html.escape(event.body)}</span>
</div>
""")
            continue

        # ── Step / duration indicator ─────────────────────────────────────────
        if event.kind == "step":
            step_label = html.escape(event.title) if event.title else f"{event.step}\u202f/\u202f{event.total}"
            html_parts.append(f"""
<div class="step-divider" style="margin: 22px 0 14px 0;">
  <span class="step-divider-text">{step_label} &rsaquo;</span>
</div>
""")
            continue

        # ── Tool / code block ─────────────────────────────────────────────────
        if event.kind == "block":
            collapsed  = event.block_id in collapsed_blocks
            title_esc  = html.escape(event.title)
            bid_esc    = html.escape(event.block_id)

            if event.tone == "tool":
                arrow = "&rsaquo;" if collapsed else "&#10549;"
                row = (
                    f'<a class="tool-run-row" href="toggle:{bid_esc}">'
                    f'<span class="tool-run-label">Запущен</span> '
                    f'<span class="tool-run-cmd">{title_esc}</span>'
                    f'<span class="tool-run-arrow">&nbsp;{arrow}</span>'
                    f'</a>'
                )
                if collapsed:
                    html_parts.append(f'<div style="margin: 3px 0 2px 0;">{row}</div>\n')
                else:
                    html_parts.append(f"""
<div style="margin: 4px 0 8px 0;">
  {row}
  <div class="tool-content">
    <pre>{html.escape(event.body)}</pre>
  </div>
</div>
""")

            elif event.tone == "error":
                toggle_icon = "&rsaquo;" if collapsed else "&#10549;"
                content_html = (
                    f'<pre style="color: #d49090; margin: 0;">{html.escape(event.body)}</pre>'
                    if not collapsed
                    else f'<div class="dim" style="font-style:italic;">{html.escape(event.body[:160])}…</div>'
                )
                html_parts.append(f"""
<div class="error-block" style="margin: 6px 0 10px 0;">
  <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:5px;">
    <span class="label" style="color: #e05555;">{title_esc}</span>
    <a class="toggle-link" href="toggle:{bid_esc}">{toggle_icon}</a>
  </div>
  {content_html}
</div>
""")

            else:  # assistant / meta blocks
                toggle_icon = "&rsaquo;" if collapsed else "&#10549;"
                if collapsed:
                    content_html = ""
                else:
                    content_html = f'<pre style="color: #b0b0b8;">{html.escape(event.body)}</pre>'

                label_color = "#4ade80" if event.tone == "assistant" else "#8a8a96"
                usage_html = _usage_caption_html(event, mono_css=_mono)
                html_parts.append(f"""
<div style="margin: 4px 0 10px 0;">
  <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">
    <a class="toggle-link" style="color:{label_color}; font-size:10px; font-weight:700;
       letter-spacing:0.08em; text-transform:uppercase;"
       href="toggle:{bid_esc}">{title_esc}&nbsp;{toggle_icon}</a>
  </div>
  {usage_html}
  {content_html}
</div>
""")

    html_parts.append("</body></html>")

    # Publish the copy store for clipboard access
    _copy_blocks.clear()
    _copy_blocks.update(copy_store)

    return html_parts
