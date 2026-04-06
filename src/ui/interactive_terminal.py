"""Interactive ANSI/VT100 terminal widget for BabkaCode UI."""

from __future__ import annotations

import html
from dataclasses import dataclass, replace
from typing import Final

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QKeyEvent, QResizeEvent, QShowEvent
from PySide6.QtWidgets import QApplication, QTextEdit, QWidget

if __package__ in {None, ""}:
    from src.ui.ui_utils import monospace_font_stack_css
else:
    from .ui_utils import monospace_font_stack_css

DEFAULT_FOREGROUND: Final[tuple[int, int, int]] = (212, 212, 212)
DEFAULT_BACKGROUND: Final[tuple[int, int, int]] = (17, 17, 17)
CURSOR_FOREGROUND: Final[tuple[int, int, int]] = (17, 17, 17)
CURSOR_BACKGROUND: Final[tuple[int, int, int]] = (212, 212, 212)
SCROLLBACK_LIMIT: Final[int] = 5000

ANSI_16_COLORS: Final[tuple[tuple[int, int, int], ...]] = (
    (0, 0, 0),
    (205, 49, 49),
    (13, 188, 121),
    (229, 229, 16),
    (36, 114, 200),
    (188, 63, 188),
    (17, 168, 205),
    (229, 229, 229),
    (102, 102, 102),
    (241, 76, 76),
    (35, 209, 139),
    (245, 245, 67),
    (59, 142, 234),
    (214, 112, 214),
    (41, 184, 219),
    (255, 255, 255),
)

DEC_SPECIAL_GRAPHICS: Final[dict[str, str]] = {
    "_": " ",
    "`": "◆",
    "a": "▒",
    "b": "␉",
    "c": "␌",
    "d": "␍",
    "e": "␊",
    "f": "°",
    "g": "±",
    "h": "␤",
    "i": "␋",
    "j": "┘",
    "k": "┐",
    "l": "┌",
    "m": "└",
    "n": "┼",
    "o": "⎺",
    "p": "⎻",
    "q": "─",
    "r": "⎼",
    "s": "⎽",
    "t": "├",
    "u": "┤",
    "v": "┴",
    "w": "┬",
    "x": "│",
    "y": "≤",
    "z": "≥",
    "{": "π",
    "|": "≠",
    "}": "£",
    "~": "·",
}


def _clamp(value: int, lower: int, upper: int) -> int:
    return max(lower, min(upper, value))


def _rgb_to_css(color: tuple[int, int, int]) -> str:
    return f"rgb({color[0]}, {color[1]}, {color[2]})"


def _blend(
    foreground: tuple[int, int, int],
    background: tuple[int, int, int],
    amount: float,
) -> tuple[int, int, int]:
    return tuple(
        round((foreground[channel] * amount) + (background[channel] * (1.0 - amount)))
        for channel in range(3)
    )


def _xterm_256_color(index: int) -> tuple[int, int, int]:
    if 0 <= index < 16:
        return ANSI_16_COLORS[index]
    if 16 <= index <= 231:
        level = (0, 95, 135, 175, 215, 255)
        value = index - 16
        return (
            level[value // 36],
            level[(value // 6) % 6],
            level[value % 6],
        )
    if 232 <= index <= 255:
        shade = 8 + (index - 232) * 10
        return (shade, shade, shade)
    return DEFAULT_FOREGROUND


@dataclass(frozen=True)
class TerminalStyle:
    fg: tuple[int, int, int] | None = None
    bg: tuple[int, int, int] | None = None
    bold: bool = False
    dim: bool = False
    italic: bool = False
    underline: bool = False
    blink: bool = False
    inverse: bool = False
    hidden: bool = False
    strike: bool = False


DEFAULT_STYLE: Final[TerminalStyle] = TerminalStyle()


@dataclass(frozen=True)
class TerminalCell:
    char: str = " "
    style: TerminalStyle = DEFAULT_STYLE


@dataclass
class SavedCursor:
    row: int = 0
    column: int = 0
    style: TerminalStyle = DEFAULT_STYLE
    origin_mode: bool = False
    active_charset: int = 0
    charsets: tuple[str, str] = ("B", "B")


class TerminalEmulator:
    """A compact VT100/xterm-style screen emulator with scrollback."""

    def __init__(self, rows: int = 24, columns: int = 80, *, scrollback_limit: int = SCROLLBACK_LIMIT) -> None:
        self.rows = max(2, rows)
        self.columns = max(8, columns)
        self.scrollback_limit = max(0, scrollback_limit)
        self.reset()

    def reset(self) -> None:
        self.scrollback: list[list[TerminalCell]] = []
        self.screen: list[list[TerminalCell]] = [self._blank_line() for _ in range(self.rows)]
        self.cursor_row = 0
        self.cursor_column = 0
        self.saved_cursor = SavedCursor()
        self.current_style = DEFAULT_STYLE
        self.top_margin = 0
        self.bottom_margin = self.rows - 1
        self.origin_mode = False
        self.auto_wrap = True
        self.insert_mode = False
        self.cursor_visible = True
        self.app_cursor_keys = False
        self.app_keypad = False
        self.bracketed_paste = False
        self._wrap_pending = False
        self._last_printed: TerminalCell | None = None
        self._charsets = ["B", "B"]
        self._active_charset = 0
        self._tab_stops = {column for column in range(8, self.columns, 8)}
        self._alternate_active = False
        self._main_state: dict[str, object] | None = None
        self._parser_state = "normal"
        self._csi_buffer = ""
        self._osc_buffer = ""
        self._string_escape = False
        self._charset_target = 0
        self._responses: list[str] = []

    def resize(self, rows: int, columns: int) -> None:
        rows = max(2, rows)
        columns = max(8, columns)
        if rows == self.rows and columns == self.columns:
            return

        old_rows = self.rows
        self.rows = rows
        self.columns = columns
        self.screen = [self._resize_line(line, columns) for line in self.screen]

        if rows > old_rows:
            self.screen.extend(self._blank_line() for _ in range(rows - old_rows))
        elif rows < old_rows:
            trimmed = self.screen[: old_rows - rows]
            self.screen = self.screen[old_rows - rows :]
            if not self._alternate_active:
                self._append_scrollback(trimmed)

        self.saved_cursor.row = _clamp(self.saved_cursor.row, 0, rows - 1)
        self.saved_cursor.column = _clamp(self.saved_cursor.column, 0, columns - 1)
        self.cursor_row = _clamp(self.cursor_row, 0, rows - 1)
        self.cursor_column = _clamp(self.cursor_column, 0, columns - 1)
        self.top_margin = 0
        self.bottom_margin = rows - 1
        self._tab_stops = {column for column in self._tab_stops if column < columns}
        self._tab_stops.update(column for column in range(8, columns, 8) if column not in self._tab_stops)
        self._wrap_pending = False

    def feed(self, data: str) -> list[str]:
        if not data:
            return []

        self._responses = []
        for char in data:
            self._feed_char(char)
        responses = list(self._responses)
        self._responses.clear()
        return responses

    def plain_text(self, *, include_scrollback: bool = True) -> str:
        return "\n".join(self.display_lines(include_scrollback=include_scrollback))

    def display_lines(self, *, include_scrollback: bool = True) -> list[str]:
        rendered: list[str] = []
        source: list[list[TerminalCell]] = []
        if include_scrollback and not self._alternate_active:
            source.extend(self.scrollback)
        source.extend(self.screen)
        for line in source:
            rendered.append("".join(cell.char for cell in line).rstrip())
        return rendered

    def render_html(self) -> str:
        lines: list[list[TerminalCell]] = []
        if not self._alternate_active:
            lines.extend(self.scrollback)
        lines.extend(self.screen)

        cursor_screen_index = len(lines) - self.rows + self.cursor_row
        html_lines: list[str] = []
        for line_index, line in enumerate(lines):
            html_lines.append(self._render_html_line(line, line_index == cursor_screen_index))

        body = "\n".join(html_lines) if html_lines else " "
        _mono = monospace_font_stack_css()
        return (
            "<html><head><meta charset='utf-8'></head>"
            "<body style='margin:0; background: rgb(17, 17, 17);'>"
            f'<pre style="margin:0; font-family: {_mono}; white-space:pre;">'
            f"{body}"
            "</pre></body></html>"
        )

    def _render_html_line(self, line: list[TerminalCell], has_cursor: bool) -> str:
        parts: list[str] = []
        current_css: str | None = None
        current_run: list[str] = []

        def flush() -> None:
            nonlocal current_css, current_run
            if current_css is None:
                return
            parts.append(f"<span style=\"{current_css}\">{''.join(current_run) or ' '}</span>")
            current_css = None
            current_run = []

        for column, cell in enumerate(line):
            css, rendered_char = self._cell_to_html(
                cell,
                is_cursor=has_cursor and self.cursor_visible and column == self.cursor_column,
            )
            if css != current_css:
                flush()
                current_css = css
            current_run.append(rendered_char)

        flush()
        return "".join(parts) or " "

    def _cell_to_html(self, cell: TerminalCell, *, is_cursor: bool) -> tuple[str, str]:
        style = cell.style
        foreground = style.fg or DEFAULT_FOREGROUND
        background = style.bg or DEFAULT_BACKGROUND
        if style.inverse:
            foreground, background = background, foreground
        if style.dim:
            foreground = _blend(foreground, background, 0.55)
        if style.hidden:
            foreground = background
        if is_cursor:
            foreground, background = CURSOR_FOREGROUND, CURSOR_BACKGROUND

        css = [
            f"color: {_rgb_to_css(foreground)}",
            f"background-color: {_rgb_to_css(background)}",
            f"font-weight: {'700' if style.bold else '400'}",
            f"font-style: {'italic' if style.italic else 'normal'}",
        ]
        decorations: list[str] = []
        if style.underline:
            decorations.append("underline")
        if style.strike:
            decorations.append("line-through")
        css.append(f"text-decoration: {' '.join(decorations) if decorations else 'none'}")
        return "; ".join(css), html.escape(cell.char)

    def _feed_char(self, char: str) -> None:
        if self._parser_state == "normal":
            self._handle_normal_char(char)
            return
        if self._parser_state == "esc":
            self._handle_escape(char)
            return
        if self._parser_state == "csi":
            self._handle_csi(char)
            return
        if self._parser_state == "osc":
            self._handle_osc(char)
            return
        if self._parser_state == "ignore_string":
            self._handle_ignored_string(char)
            return
        if self._parser_state == "charset":
            self._charsets[self._charset_target] = char
            self._parser_state = "normal"
            return
        if self._parser_state == "hash":
            if char == "8":
                self._screen_alignment_test()
            self._parser_state = "normal"

    def _handle_normal_char(self, char: str) -> None:
        codepoint = ord(char)
        if char == "\x1b":
            self._parser_state = "esc"
            return
        if char == "\x07":
            return
        if char == "\b":
            self._wrap_pending = False
            self.cursor_column = max(0, self.cursor_column - 1)
            return
        if char == "\t":
            self._wrap_pending = False
            next_stop = next((column for column in sorted(self._tab_stops) if column > self.cursor_column), self.columns - 1)
            self.cursor_column = _clamp(next_stop, 0, self.columns - 1)
            return
        if char == "\r":
            self._wrap_pending = False
            self.cursor_column = 0
            return
        if char in {"\n", "\v", "\f"}:
            self._linefeed()
            return
        if char == "\x0e":
            self._active_charset = 1
            return
        if char == "\x0f":
            self._active_charset = 0
            return
        if codepoint < 0x20 or codepoint == 0x7F:
            return
        self._write_printable(char)

    def _handle_escape(self, char: str) -> None:
        self._parser_state = "normal"
        if char == "[":
            self._parser_state = "csi"
            self._csi_buffer = ""
            return
        if char == "]":
            self._parser_state = "osc"
            self._osc_buffer = ""
            self._string_escape = False
            return
        if char in {"P", "^", "_", "X"}:
            self._parser_state = "ignore_string"
            self._string_escape = False
            return
        if char == "(":
            self._parser_state = "charset"
            self._charset_target = 0
            return
        if char == ")":
            self._parser_state = "charset"
            self._charset_target = 1
            return
        if char == "#":
            self._parser_state = "hash"
            return
        if char == "7":
            self._save_cursor()
            return
        if char == "8":
            self._restore_cursor()
            return
        if char == "D":
            self._index()
            return
        if char == "E":
            self.cursor_column = 0
            self._linefeed()
            return
        if char == "M":
            self._reverse_index()
            return
        if char == "H":
            self._tab_stops.add(self.cursor_column)
            return
        if char == "c":
            self.reset()
            return
        if char == "=":
            self.app_keypad = True
            return
        if char == ">":
            self.app_keypad = False

    def _handle_csi(self, char: str) -> None:
        if 0x40 <= ord(char) <= 0x7E:
            self._dispatch_csi(self._csi_buffer, char)
            self._parser_state = "normal"
            self._csi_buffer = ""
            return
        self._csi_buffer += char

    def _handle_osc(self, char: str) -> None:
        if char == "\x07":
            self._parser_state = "normal"
            self._osc_buffer = ""
            self._string_escape = False
            return
        if self._string_escape:
            self._string_escape = False
            if char == "\\":
                self._parser_state = "normal"
                self._osc_buffer = ""
                return
            self._osc_buffer += "\x1b"
        if char == "\x1b":
            self._string_escape = True
            return
        self._osc_buffer += char

    def _handle_ignored_string(self, char: str) -> None:
        if self._string_escape:
            self._string_escape = False
            if char == "\\":
                self._parser_state = "normal"
                return
        if char == "\x1b":
            self._string_escape = True

    def _dispatch_csi(self, payload: str, final: str) -> None:
        private = ""
        params_payload = payload
        if params_payload and params_payload[0] in {"?", ">", "!", "="}:
            private = params_payload[0]
            params_payload = params_payload[1:]
        params_payload = params_payload.replace(":", ";")
        params = [part for part in params_payload.split(";")] if params_payload else []
        integers = [int(part) if part.isdigit() else 0 for part in params if part != ""]

        if private == "!" and final == "p":
            self._soft_reset()
            return
        if private == "?" and final in {"h", "l"}:
            self._set_private_modes(integers or [0], enable=final == "h")
            return
        if final in {"h", "l"}:
            self._set_modes(integers or [0], enable=final == "h")
            return
        if final == "m":
            self._set_graphics_rendition(params)
            return
        if final == "A":
            self.cursor_row = max(self._region_top(), self.cursor_row - max(1, integers[0] if integers else 1))
            self._wrap_pending = False
            return
        if final == "B":
            self.cursor_row = min(self._region_bottom(), self.cursor_row + max(1, integers[0] if integers else 1))
            self._wrap_pending = False
            return
        if final == "C":
            self.cursor_column = min(self.columns - 1, self.cursor_column + max(1, integers[0] if integers else 1))
            self._wrap_pending = False
            return
        if final == "D":
            self.cursor_column = max(0, self.cursor_column - max(1, integers[0] if integers else 1))
            self._wrap_pending = False
            return
        if final == "E":
            self.cursor_row = min(self._region_bottom(), self.cursor_row + max(1, integers[0] if integers else 1))
            self.cursor_column = 0
            self._wrap_pending = False
            return
        if final == "F":
            self.cursor_row = max(self._region_top(), self.cursor_row - max(1, integers[0] if integers else 1))
            self.cursor_column = 0
            self._wrap_pending = False
            return
        if final in {"G", "`"}:
            self.cursor_column = _clamp((integers[0] if integers else 1) - 1, 0, self.columns - 1)
            self._wrap_pending = False
            return
        if final in {"H", "f"}:
            row = (integers[0] if len(integers) >= 1 else 1) - 1
            column = (integers[1] if len(integers) >= 2 else 1) - 1
            self._move_cursor(row, column)
            return
        if final == "d":
            self._move_cursor((integers[0] if integers else 1) - 1, self.cursor_column)
            return
        if final == "e":
            self._move_cursor(self.cursor_row + max(1, integers[0] if integers else 1), self.cursor_column)
            return
        if final == "J":
            self._erase_in_display(integers[0] if integers else 0)
            return
        if final == "K":
            self._erase_in_line(integers[0] if integers else 0)
            return
        if final == "L":
            self._insert_lines(max(1, integers[0] if integers else 1))
            return
        if final == "M":
            self._delete_lines(max(1, integers[0] if integers else 1))
            return
        if final == "@":
            self._insert_characters(max(1, integers[0] if integers else 1))
            return
        if final == "P":
            self._delete_characters(max(1, integers[0] if integers else 1))
            return
        if final == "X":
            self._erase_characters(max(1, integers[0] if integers else 1))
            return
        if final == "S":
            self._scroll_up(max(1, integers[0] if integers else 1))
            return
        if final == "T":
            self._scroll_down(max(1, integers[0] if integers else 1))
            return
        if final == "r":
            top = (integers[0] if len(integers) >= 1 else 1) - 1
            bottom = (integers[1] if len(integers) >= 2 else self.rows) - 1
            self._set_scroll_region(top, bottom)
            return
        if final == "s":
            self._save_cursor()
            return
        if final == "u":
            self._restore_cursor()
            return
        if final == "g":
            mode = integers[0] if integers else 0
            if mode == 0:
                self._tab_stops.discard(self.cursor_column)
            elif mode == 3:
                self._tab_stops.clear()
            return
        if final == "I":
            count = max(1, integers[0] if integers else 1)
            next_stops = sorted(column for column in self._tab_stops if column > self.cursor_column)
            self.cursor_column = next_stops[min(count - 1, len(next_stops) - 1)] if next_stops else self.columns - 1
            self._wrap_pending = False
            return
        if final == "Z":
            count = max(1, integers[0] if integers else 1)
            previous = sorted((column for column in self._tab_stops if column < self.cursor_column), reverse=True)
            self.cursor_column = previous[min(count - 1, len(previous) - 1)] if previous else 0
            self._wrap_pending = False
            return
        if final == "b":
            repeat = max(1, integers[0] if integers else 1)
            if self._last_printed is not None:
                for _ in range(repeat):
                    self._put_cell(self._last_printed)
            return
        if final == "c":
            self._responses.append("\x1b[>0;10;0c" if private == ">" else "\x1b[?1;2c")
            return
        if final == "n":
            self._report_device_status(private, integers[0] if integers else 0)

    def _report_device_status(self, private: str, code: int) -> None:
        if private == "?" and code == 6:
            self._responses.append(f"\x1b[?{self.cursor_row + 1};{self.cursor_column + 1}R")
            return
        if code == 5:
            self._responses.append("\x1b[0n")
            return
        if code == 6:
            self._responses.append(f"\x1b[{self.cursor_row + 1};{self.cursor_column + 1}R")

    def _soft_reset(self) -> None:
        self.current_style = DEFAULT_STYLE
        self.top_margin = 0
        self.bottom_margin = self.rows - 1
        self.origin_mode = False
        self.auto_wrap = True
        self.insert_mode = False
        self.cursor_visible = True
        self.app_cursor_keys = False
        self.app_keypad = False
        self.bracketed_paste = False
        self._charsets = ["B", "B"]
        self._active_charset = 0
        self._wrap_pending = False

    def _set_modes(self, modes: list[int], *, enable: bool) -> None:
        for mode in modes:
            if mode == 4:
                self.insert_mode = enable

    def _set_private_modes(self, modes: list[int], *, enable: bool) -> None:
        for mode in modes:
            if mode == 1:
                self.app_cursor_keys = enable
            elif mode == 6:
                self.origin_mode = enable
                self._move_cursor(0, 0)
            elif mode == 7:
                self.auto_wrap = enable
            elif mode == 25:
                self.cursor_visible = enable
            elif mode in {47, 1047}:
                self._use_alternate_screen(enable, clear=True, save_cursor=False)
            elif mode == 1048:
                if enable:
                    self._save_cursor()
                else:
                    self._restore_cursor()
            elif mode == 1049:
                self._use_alternate_screen(enable, clear=True, save_cursor=True)
            elif mode == 2004:
                self.bracketed_paste = enable

    def _use_alternate_screen(self, enable: bool, *, clear: bool, save_cursor: bool) -> None:
        if enable == self._alternate_active:
            if enable and clear:
                self.screen = [self._blank_line() for _ in range(self.rows)]
                self.cursor_row = 0
                self.cursor_column = 0
            return

        if enable:
            if save_cursor:
                self._save_cursor()
            self._main_state = {
                "screen": [list(line) for line in self.screen],
                "cursor_row": self.cursor_row,
                "cursor_column": self.cursor_column,
                "saved_cursor": replace(self.saved_cursor),
                "wrap_pending": self._wrap_pending,
            }
            self._alternate_active = True
            self.screen = [self._blank_line() for _ in range(self.rows)] if clear else [list(line) for line in self.screen]
            self.cursor_row = 0
            self.cursor_column = 0
            self.top_margin = 0
            self.bottom_margin = self.rows - 1
            self._wrap_pending = False
            return

        main_state = self._main_state
        self._alternate_active = False
        if main_state is None:
            self.screen = [self._blank_line() for _ in range(self.rows)]
            self.cursor_row = 0
            self.cursor_column = 0
            return
        self.screen = [self._resize_line(list(line), self.columns) for line in main_state["screen"]]  # type: ignore[index]
        self.screen = (self.screen + [self._blank_line() for _ in range(self.rows - len(self.screen))])[: self.rows]
        self.cursor_row = _clamp(int(main_state["cursor_row"]), 0, self.rows - 1)
        self.cursor_column = _clamp(int(main_state["cursor_column"]), 0, self.columns - 1)
        self.saved_cursor = replace(main_state["saved_cursor"])  # type: ignore[arg-type]
        self.top_margin = 0
        self.bottom_margin = self.rows - 1
        self._wrap_pending = bool(main_state["wrap_pending"])
        self._main_state = None
        if save_cursor:
            self._restore_cursor()

    def _set_graphics_rendition(self, params: list[str]) -> None:
        if not params:
            params = ["0"]

        values: list[int] = []
        for part in params:
            values.append(int(part) if part.isdigit() else 0)

        index = 0
        while index < len(values):
            value = values[index]
            if value == 0:
                self.current_style = DEFAULT_STYLE
            elif value == 1:
                self.current_style = replace(self.current_style, bold=True)
            elif value == 2:
                self.current_style = replace(self.current_style, dim=True)
            elif value == 3:
                self.current_style = replace(self.current_style, italic=True)
            elif value == 4:
                self.current_style = replace(self.current_style, underline=True)
            elif value == 5:
                self.current_style = replace(self.current_style, blink=True)
            elif value == 7:
                self.current_style = replace(self.current_style, inverse=True)
            elif value == 8:
                self.current_style = replace(self.current_style, hidden=True)
            elif value == 9:
                self.current_style = replace(self.current_style, strike=True)
            elif value == 21:
                self.current_style = replace(self.current_style, bold=False)
            elif value == 22:
                self.current_style = replace(self.current_style, bold=False, dim=False)
            elif value == 23:
                self.current_style = replace(self.current_style, italic=False)
            elif value == 24:
                self.current_style = replace(self.current_style, underline=False)
            elif value == 25:
                self.current_style = replace(self.current_style, blink=False)
            elif value == 27:
                self.current_style = replace(self.current_style, inverse=False)
            elif value == 28:
                self.current_style = replace(self.current_style, hidden=False)
            elif value == 29:
                self.current_style = replace(self.current_style, strike=False)
            elif 30 <= value <= 37:
                self.current_style = replace(self.current_style, fg=ANSI_16_COLORS[value - 30])
            elif value == 39:
                self.current_style = replace(self.current_style, fg=None)
            elif 40 <= value <= 47:
                self.current_style = replace(self.current_style, bg=ANSI_16_COLORS[value - 40])
            elif value == 49:
                self.current_style = replace(self.current_style, bg=None)
            elif 90 <= value <= 97:
                self.current_style = replace(self.current_style, fg=ANSI_16_COLORS[8 + (value - 90)])
            elif 100 <= value <= 107:
                self.current_style = replace(self.current_style, bg=ANSI_16_COLORS[8 + (value - 100)])
            elif value in {38, 48} and index + 1 < len(values):
                is_foreground = value == 38
                mode = values[index + 1]
                if mode == 5 and index + 2 < len(values):
                    color = _xterm_256_color(values[index + 2])
                    self.current_style = replace(self.current_style, fg=color) if is_foreground else replace(self.current_style, bg=color)
                    index += 2
                elif mode == 2 and index + 4 < len(values):
                    color = (
                        _clamp(values[index + 2], 0, 255),
                        _clamp(values[index + 3], 0, 255),
                        _clamp(values[index + 4], 0, 255),
                    )
                    self.current_style = replace(self.current_style, fg=color) if is_foreground else replace(self.current_style, bg=color)
                    index += 4
            index += 1

    def _move_cursor(self, row: int, column: int) -> None:
        if self.origin_mode:
            row += self.top_margin
            lower = self.top_margin
            upper = self.bottom_margin
        else:
            lower = 0
            upper = self.rows - 1
        self.cursor_row = _clamp(row, lower, upper)
        self.cursor_column = _clamp(column, 0, self.columns - 1)
        self._wrap_pending = False

    def _save_cursor(self) -> None:
        self.saved_cursor = SavedCursor(
            row=self.cursor_row,
            column=self.cursor_column,
            style=self.current_style,
            origin_mode=self.origin_mode,
            active_charset=self._active_charset,
            charsets=(self._charsets[0], self._charsets[1]),
        )

    def _restore_cursor(self) -> None:
        self.cursor_row = _clamp(self.saved_cursor.row, 0, self.rows - 1)
        self.cursor_column = _clamp(self.saved_cursor.column, 0, self.columns - 1)
        self.current_style = self.saved_cursor.style
        self.origin_mode = self.saved_cursor.origin_mode
        self._active_charset = self.saved_cursor.active_charset
        self._charsets = [self.saved_cursor.charsets[0], self.saved_cursor.charsets[1]]
        self._wrap_pending = False

    def _region_top(self) -> int:
        return self.top_margin if self.origin_mode else 0

    def _region_bottom(self) -> int:
        return self.bottom_margin if self.origin_mode else self.rows - 1

    def _index(self) -> None:
        if self.cursor_row == self.bottom_margin:
            self._scroll_up(1)
        else:
            self.cursor_row = min(self.rows - 1, self.cursor_row + 1)
        self._wrap_pending = False

    def _reverse_index(self) -> None:
        if self.cursor_row == self.top_margin:
            self._scroll_down(1)
        else:
            self.cursor_row = max(0, self.cursor_row - 1)
        self._wrap_pending = False

    def _linefeed(self) -> None:
        if self.cursor_row == self.bottom_margin:
            self._scroll_up(1)
        else:
            self.cursor_row = min(self.rows - 1, self.cursor_row + 1)
        self._wrap_pending = False

    def _write_printable(self, char: str) -> None:
        if self._wrap_pending:
            self.cursor_column = 0
            self._linefeed()
        self._put_cell(TerminalCell(self._translate_character(char), self.current_style))

    def _put_cell(self, cell: TerminalCell) -> None:
        row = self.screen[self.cursor_row]
        if self.insert_mode:
            row[self.cursor_column + 1 :] = row[self.cursor_column : -1]
        row[self.cursor_column] = cell
        self._last_printed = cell
        if self.cursor_column == self.columns - 1:
            self._wrap_pending = self.auto_wrap
        else:
            self.cursor_column += 1
            self._wrap_pending = False

    def _translate_character(self, char: str) -> str:
        return DEC_SPECIAL_GRAPHICS.get(char, char) if self._charsets[self._active_charset] == "0" else char

    def _erase_in_display(self, mode: int) -> None:
        if mode == 0:
            self._erase_in_line(0)
            for row in range(self.cursor_row + 1, self.rows):
                self.screen[row] = self._blank_line()
            return
        if mode == 1:
            self._erase_in_line(1)
            for row in range(0, self.cursor_row):
                self.screen[row] = self._blank_line()
            return
        if mode in {2, 3}:
            self.screen = [self._blank_line() for _ in range(self.rows)]
            if mode == 3:
                self.scrollback.clear()

    def _erase_in_line(self, mode: int) -> None:
        row = self.screen[self.cursor_row]
        if mode == 0:
            start, end = self.cursor_column, self.columns
        elif mode == 1:
            start, end = 0, self.cursor_column + 1
        else:
            start, end = 0, self.columns
        blank = TerminalCell()
        for column in range(start, end):
            row[column] = blank

    def _erase_characters(self, count: int) -> None:
        row = self.screen[self.cursor_row]
        for column in range(self.cursor_column, min(self.columns, self.cursor_column + count)):
            row[column] = TerminalCell()

    def _insert_characters(self, count: int) -> None:
        row = self.screen[self.cursor_row]
        count = min(count, self.columns - self.cursor_column)
        row[self.cursor_column :] = [TerminalCell() for _ in range(count)] + row[self.cursor_column : self.columns - count]

    def _delete_characters(self, count: int) -> None:
        row = self.screen[self.cursor_row]
        count = min(count, self.columns - self.cursor_column)
        row[self.cursor_column :] = row[self.cursor_column + count :] + [TerminalCell() for _ in range(count)]

    def _insert_lines(self, count: int) -> None:
        if not (self.top_margin <= self.cursor_row <= self.bottom_margin):
            return
        count = min(count, self.bottom_margin - self.cursor_row + 1)
        top = self.screen[: self.cursor_row]
        middle = [self._blank_line() for _ in range(count)] + self.screen[self.cursor_row : self.bottom_margin - count + 1]
        self.screen = top + middle + self.screen[self.bottom_margin + 1 :]

    def _delete_lines(self, count: int) -> None:
        if not (self.top_margin <= self.cursor_row <= self.bottom_margin):
            return
        count = min(count, self.bottom_margin - self.cursor_row + 1)
        top = self.screen[: self.cursor_row]
        middle = self.screen[self.cursor_row + count : self.bottom_margin + 1] + [self._blank_line() for _ in range(count)]
        self.screen = top + middle + self.screen[self.bottom_margin + 1 :]

    def _set_scroll_region(self, top: int, bottom: int) -> None:
        self.top_margin = _clamp(top, 0, self.rows - 1)
        self.bottom_margin = _clamp(bottom, self.top_margin, self.rows - 1)
        self._move_cursor(0, 0)

    def _scroll_up(self, count: int) -> None:
        for _ in range(count):
            removed = self.screen.pop(self.top_margin)
            self.screen.insert(self.bottom_margin, self._blank_line())
            if self.top_margin == 0 and self.bottom_margin == self.rows - 1 and not self._alternate_active:
                self._append_scrollback([removed])

    def _scroll_down(self, count: int) -> None:
        for _ in range(count):
            self.screen.pop(self.bottom_margin)
            self.screen.insert(self.top_margin, self._blank_line())

    def _append_scrollback(self, lines: list[list[TerminalCell]]) -> None:
        if self.scrollback_limit <= 0:
            return
        self.scrollback.extend(list(line) for line in lines)
        overflow = len(self.scrollback) - self.scrollback_limit
        if overflow > 0:
            del self.scrollback[:overflow]

    def _screen_alignment_test(self) -> None:
        fill = TerminalCell("E", DEFAULT_STYLE)
        self.screen = [[fill for _ in range(self.columns)] for _ in range(self.rows)]
        self.cursor_row = 0
        self.cursor_column = 0
        self._wrap_pending = False

    def _blank_line(self) -> list[TerminalCell]:
        return [TerminalCell() for _ in range(self.columns)]

    def _resize_line(self, line: list[TerminalCell], width: int) -> list[TerminalCell]:
        if len(line) > width:
            return list(line[:width])
        if len(line) < width:
            return list(line) + [TerminalCell() for _ in range(width - len(line))]
        return list(line)


class InteractiveTerminal(QTextEdit):
    """Rich terminal surface with ANSI/VT100 emulation and raw keyboard input."""

    data_ready = Signal(str)
    interrupt_requested = Signal()
    resize_requested = Signal(int, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._emulator = TerminalEmulator()
        self._last_rows = self._emulator.rows
        self._last_columns = self._emulator.columns
        self.setAcceptRichText(True)
        self.setReadOnly(True)
        self.setUndoRedoEnabled(False)
        self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByKeyboard | Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.setPlaceholderText("Interactive ANSI/VT100 terminal")
        self._refresh_document(autoscroll=True)

    def setFont(self, font: QFont) -> None:
        super().setFont(font)
        self.document().setDefaultFont(font)

    def reset_terminal(self, banner: str = "") -> None:
        self._emulator.reset()
        self._refresh_document(autoscroll=True)
        if banner:
            self.append_output(banner.rstrip("\n"))
            self.append_output("\n")

    def clear_terminal(self) -> None:
        self.reset_terminal()

    def append_output(self, text: str) -> None:
        if not text:
            return
        should_autoscroll = self._is_scrolled_to_bottom()
        responses = self._emulator.feed(text)
        self._refresh_document(autoscroll=should_autoscroll)
        for response in responses:
            self.data_ready.emit(response)

    def expect_command_echo(self, _command: str) -> None:
        return

    def terminal_size(self) -> tuple[int, int]:
        metrics = self.fontMetrics()
        cell_width = max(1, metrics.horizontalAdvance("M"))
        cell_height = max(1, metrics.lineSpacing())
        viewport = self.viewport().size()
        columns = max(8, viewport.width() // cell_width)
        rows = max(2, viewport.height() // cell_height)
        return columns, rows

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 - Qt callback signature
        super().resizeEvent(event)
        self._sync_geometry()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 - Qt callback signature
        super().showEvent(event)
        self._sync_geometry()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt callback signature
        key = event.key()
        modifiers = event.modifiers()

        if modifiers == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
            if key == Qt.Key.Key_C:
                self.copy()
                event.accept()
                return
            if key == Qt.Key.Key_V:
                self._paste_clipboard()
                event.accept()
                return

        if modifiers == Qt.KeyboardModifier.ShiftModifier and key == Qt.Key.Key_Insert:
            self._paste_clipboard()
            event.accept()
            return

        if modifiers == Qt.KeyboardModifier.ControlModifier and key == Qt.Key.Key_C:
            self.interrupt_requested.emit()
            event.accept()
            return

        sequence = self._key_to_sequence(event)
        if sequence is not None:
            self.data_ready.emit(sequence)
            event.accept()
            return

        super().keyPressEvent(event)

    def _paste_clipboard(self) -> None:
        text = QApplication.clipboard().text()
        if not text:
            return
        if self._emulator.bracketed_paste:
            self.data_ready.emit(f"\x1b[200~{text}\x1b[201~")
            return
        self.data_ready.emit(text)

    def _key_to_sequence(self, event: QKeyEvent) -> str | None:
        key = event.key()
        modifiers = event.modifiers()
        text = event.text()

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            return "\r"
        if key == Qt.Key.Key_Backspace:
            return "\x7f"
        if key == Qt.Key.Key_Tab:
            return "\t"
        if key == Qt.Key.Key_Backtab:
            return "\x1b[Z"
        if key == Qt.Key.Key_Escape:
            return "\x1b"
        if key == Qt.Key.Key_Up:
            return "\x1bOA" if self._emulator.app_cursor_keys else "\x1b[A"
        if key == Qt.Key.Key_Down:
            return "\x1bOB" if self._emulator.app_cursor_keys else "\x1b[B"
        if key == Qt.Key.Key_Right:
            return "\x1bOC" if self._emulator.app_cursor_keys else "\x1b[C"
        if key == Qt.Key.Key_Left:
            return "\x1bOD" if self._emulator.app_cursor_keys else "\x1b[D"
        if key == Qt.Key.Key_Home:
            return "\x1bOH" if self._emulator.app_cursor_keys else "\x1b[H"
        if key == Qt.Key.Key_End:
            return "\x1bOF" if self._emulator.app_cursor_keys else "\x1b[F"
        if key == Qt.Key.Key_Insert:
            return "\x1b[2~"
        if key == Qt.Key.Key_Delete:
            return "\x1b[3~"
        if key == Qt.Key.Key_PageUp:
            return "\x1b[5~"
        if key == Qt.Key.Key_PageDown:
            return "\x1b[6~"

        function_keys = {
            Qt.Key.Key_F1: "\x1bOP",
            Qt.Key.Key_F2: "\x1bOQ",
            Qt.Key.Key_F3: "\x1bOR",
            Qt.Key.Key_F4: "\x1bOS",
            Qt.Key.Key_F5: "\x1b[15~",
            Qt.Key.Key_F6: "\x1b[17~",
            Qt.Key.Key_F7: "\x1b[18~",
            Qt.Key.Key_F8: "\x1b[19~",
            Qt.Key.Key_F9: "\x1b[20~",
            Qt.Key.Key_F10: "\x1b[21~",
            Qt.Key.Key_F11: "\x1b[23~",
            Qt.Key.Key_F12: "\x1b[24~",
        }
        if key in function_keys:
            return function_keys[key]

        if modifiers == Qt.KeyboardModifier.ControlModifier and text:
            letter = text.upper()
            if "@" <= letter <= "_":
                return chr(ord(letter) & 0x1F)

        if modifiers == Qt.KeyboardModifier.AltModifier and text:
            return "\x1b" + text

        if modifiers in {Qt.KeyboardModifier.NoModifier, Qt.KeyboardModifier.ShiftModifier} and text:
            return text

        return None

    def _sync_geometry(self) -> None:
        columns, rows = self.terminal_size()
        if columns == self._last_columns and rows == self._last_rows:
            return
        self._last_columns = columns
        self._last_rows = rows
        should_autoscroll = self._is_scrolled_to_bottom()
        self._emulator.resize(rows, columns)
        self._refresh_document(autoscroll=should_autoscroll)
        self.resize_requested.emit(columns, rows)

    def _refresh_document(self, *, autoscroll: bool) -> None:
        scrollbar = self.verticalScrollBar()
        previous_value = scrollbar.value()
        self.setHtml(self._emulator.render_html())
        if autoscroll:
            scrollbar.setValue(scrollbar.maximum())
        else:
            scrollbar.setValue(min(previous_value, scrollbar.maximum()))

    def _is_scrolled_to_bottom(self) -> bool:
        scrollbar = self.verticalScrollBar()
        return scrollbar.value() >= max(0, scrollbar.maximum() - 4)
