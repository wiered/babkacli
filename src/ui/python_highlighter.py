"""Python syntax highlighting for the editor."""

from __future__ import annotations

from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QSyntaxHighlighter


class PythonHighlighter(QSyntaxHighlighter):
    """Lightweight Python syntax highlighter for QPlainTextEdit."""

    _TRIPLE_SINGLE = 1
    _TRIPLE_DOUBLE = 2

    def __init__(self, document) -> None:
        super().__init__(document)
        self._enabled = True

        self._keyword_format = self._make_format("#c586c0", bold=True)
        self._builtin_format = self._make_format("#4ec9b0")
        self._class_format = self._make_format("#4fc1ff", bold=True)
        self._function_format = self._make_format("#dcdcaa")
        self._decorator_format = self._make_format("#c586c0")
        self._number_format = self._make_format("#b5cea8")
        self._comment_format = self._make_format("#6a9955", italic=True)
        self._string_format = self._make_format("#ce9178")

        keywords = [
            "and",
            "as",
            "assert",
            "async",
            "await",
            "break",
            "case",
            "class",
            "continue",
            "def",
            "del",
            "elif",
            "else",
            "except",
            "False",
            "finally",
            "for",
            "from",
            "global",
            "if",
            "import",
            "in",
            "is",
            "lambda",
            "match",
            "None",
            "nonlocal",
            "not",
            "or",
            "pass",
            "raise",
            "return",
            "True",
            "try",
            "while",
            "with",
            "yield",
        ]
        builtins = [
            "abs",
            "all",
            "any",
            "bool",
            "bytes",
            "dict",
            "enumerate",
            "float",
            "int",
            "len",
            "list",
            "max",
            "min",
            "print",
            "range",
            "set",
            "str",
            "sum",
            "tuple",
            "zip",
        ]

        self._keyword_patterns = [QRegularExpression(rf"\b{word}\b") for word in keywords]
        self._builtin_patterns = [QRegularExpression(rf"\b{word}\b") for word in builtins]
        self._function_pattern = QRegularExpression(r"\bdef\s+([A-Za-z_][A-Za-z0-9_]*)")
        self._class_pattern = QRegularExpression(r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)")
        self._number_pattern = QRegularExpression(
            r"\b(?:0[xX][0-9A-Fa-f_]+|0[bB][01_]+|0[oO][0-7_]+|\d[\d_]*(?:\.\d[\d_]*)?(?:[eE][+-]?\d[\d_]*)?|"
            r"\.\d[\d_]*(?:[eE][+-]?\d[\d_]*)?)(?:[jJ])?\b"
        )
        self._decorator_pattern = QRegularExpression(r"^\s*@([A-Za-z_][A-Za-z0-9_\.]*)")
        self._single_string_pattern = QRegularExpression(
            r"""(?:[rRuUbBfF]{0,2})?(?:'[^'\\\n]*(?:\\.[^'\\\n]*)*'|\"[^\"\\\n]*(?:\\.[^\"\\\n]*)*\")"""
        )
        self._comment_pattern = QRegularExpression(r"#.*$")
        self._triple_start_pattern = QRegularExpression(r"(?<!\\)(?:[rRuUbBfF]{0,2})?('''|\"\"\")")

    def set_enabled(self, enabled: bool) -> None:
        if self._enabled == enabled:
            return
        self._enabled = enabled
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:  # noqa: N802 - Qt callback signature
        if not self._enabled:
            self.setCurrentBlockState(0)
            return

        self.setCurrentBlockState(0)

        protected_ranges = self._highlight_strings(text)
        self._highlight_comments(text, protected_ranges)
        self._highlight_regex(text, self._keyword_patterns, self._keyword_format, protected_ranges)
        self._highlight_regex(text, self._builtin_patterns, self._builtin_format, protected_ranges)
        self._highlight_regex(text, [self._function_pattern], self._function_format, protected_ranges, capture=1)
        self._highlight_regex(text, [self._class_pattern], self._class_format, protected_ranges, capture=1)
        self._highlight_regex(text, [self._number_pattern], self._number_format, protected_ranges)
        self._highlight_regex(text, [self._decorator_pattern], self._decorator_format, protected_ranges, capture=1)

    def _highlight_strings(self, text: str) -> list[tuple[int, int]]:
        ranges: list[tuple[int, int]] = []
        start = 0
        state = self.previousBlockState()

        if state in {self._TRIPLE_SINGLE, self._TRIPLE_DOUBLE}:
            delimiter = "'''" if state == self._TRIPLE_SINGLE else '"""'
            end = text.find(delimiter)
            if end == -1:
                self.setFormat(0, len(text), self._string_format)
                self.setCurrentBlockState(state)
                return [(0, len(text))]
            self.setFormat(0, end + 3, self._string_format)
            ranges.append((0, end + 3))
            start = end + 3

        while start < len(text):
            match = self._triple_start_pattern.match(text, start)
            if match.hasMatch():
                delimiter = match.captured(1)
                end = text.find(delimiter, match.capturedStart(1) + 3)
                if end == -1:
                    self.setFormat(match.capturedStart(0), len(text) - match.capturedStart(0), self._string_format)
                    self.setCurrentBlockState(self._TRIPLE_SINGLE if delimiter == "'''" else self._TRIPLE_DOUBLE)
                    ranges.append((match.capturedStart(0), len(text) - match.capturedStart(0)))
                    return ranges
                self.setFormat(match.capturedStart(0), end + 3 - match.capturedStart(0), self._string_format)
                ranges.append((match.capturedStart(0), end + 3 - match.capturedStart(0)))
                start = end + 3
                continue

            single = self._single_string_pattern.match(text, start)
            if single.hasMatch():
                length = single.capturedLength(0)
                self.setFormat(single.capturedStart(0), length, self._string_format)
                ranges.append((single.capturedStart(0), length))
                start = single.capturedStart(0) + length
                continue

            start += 1

        return ranges

    def _highlight_comments(self, text: str, protected_ranges: list[tuple[int, int]]) -> None:
        self._highlight_regex(text, [self._comment_pattern], self._comment_format, protected_ranges)

    def _highlight_regex(
        self,
        text: str,
        patterns: list[QRegularExpression],
        format_: QTextCharFormat,
        protected_ranges: list[tuple[int, int]],
        *,
        capture: int = 0,
    ) -> None:
        for pattern in patterns:
            iterator = pattern.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                start = match.capturedStart(capture)
                length = match.capturedLength(capture)
                if length <= 0 or self._overlaps_protected(start, length, protected_ranges):
                    continue
                self.setFormat(start, length, format_)

    def _overlaps_protected(self, start: int, length: int, protected_ranges: list[tuple[int, int]]) -> bool:
        end = start + length
        for protected_start, protected_length in protected_ranges:
            protected_end = protected_start + protected_length
            if start < protected_end and end > protected_start:
                return True
        return False

    def _make_format(self, color: str, *, bold: bool = False, italic: bool = False) -> QTextCharFormat:
        format_ = QTextCharFormat()
        format_.setForeground(QColor(color))
        if bold:
            format_.setFontWeight(QFont.Weight.Bold)
        if italic:
            format_.setFontItalic(True)
        return format_
