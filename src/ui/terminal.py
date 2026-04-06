"""Terminal widget + backend controller for BabkaCode UI."""

from __future__ import annotations

import os
import re
import threading
from typing import Final

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Qt, Signal
from PySide6.QtGui import QKeyEvent, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit, QWidget

try:
    from winpty import PtyProcess
except Exception:  # pragma: no cover - optional Windows dependency
    PtyProcess = None  # type: ignore[assignment]

_TERMINAL_PROMPT: Final[str] = "pwsh> "
_TERMINAL_START_ARGS: Final[tuple[str, ...]] = ("-NoLogo", "-NoExit")
_TERMINAL_ENV_VARS: Final[dict[str, str]] = {
    "POWERSHELL_DISABLE_TELEMETRY": "1",
    "TERM": "xterm-256color",
    "COLORTERM": "truecolor",
}

_ANSI_CSI_RE: Final[re.Pattern[str]] = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_ANSI_OSC_RE: Final[re.Pattern[str]] = re.compile(r"\x1b\][^\x07]*(?:\x07|\x1b\\)")
_ANSI_SS3_RE: Final[re.Pattern[str]] = re.compile(r"\x1bO.")
_CHA_TO_FIRST_COLUMN_RE: Final[re.Pattern[str]] = re.compile(r"\x1b\[(?:0|1)?G")
_SHELL_PROMPT_LINE_RE: Final[re.Pattern[str]] = re.compile(r"(?m)^(?:pwsh>|PS [^\r\n>]+>)\s*")
_WINPTY_AVAILABLE: Final[bool] = os.name == "nt" and PtyProcess is not None


def strip_ansi(text: str) -> str:
    if not text:
        return text
    text = _ANSI_OSC_RE.sub("", text)
    text = _ANSI_CSI_RE.sub("", text)
    text = _ANSI_SS3_RE.sub("", text)
    return text


def _tty_cursor_home_to_cr(text: str) -> str:
    """Turn CHA-to-column-0/1 into CR so append_output treats output as a line redraw, not more text."""
    if not text:
        return text
    return _CHA_TO_FIRST_COLUMN_RE.sub("\r", text)


def _strip_shell_prompts(text: str) -> str:
    """Remove shell prompt fragments that the UI already renders itself."""
    if not text:
        return text
    return _SHELL_PROMPT_LINE_RE.sub("", text)


def _terminal_environment() -> dict[str, str]:
    env = os.environ.copy()
    env.update(_TERMINAL_ENV_VARS)
    return env


class TerminalTextEdit(QPlainTextEdit):
    """Pseudo terminal surface implemented with Qt text editing primitives."""

    command_submitted = Signal(str)
    interrupt_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._prompt = _TERMINAL_PROMPT
        self._base_text = ""
        self._current_input = ""
        self._input_start = 0
        self._history: list[str] = []
        self._history_index: int | None = None
        self._pending_echo_prefix = ""
        self._pending_echo_buffer = ""
        self.setUndoRedoEnabled(False)
        self.setPlaceholderText("Pseudo PowerShell terminal")
        self._render()

    def reset_terminal(self, banner: str = "") -> None:
        self._base_text = ""
        self._current_input = ""
        self._history_index = None
        self._pending_echo_prefix = ""
        self._pending_echo_buffer = ""
        if banner:
            self._base_text = banner.rstrip("\n") + "\n"
        self._render()

    def set_prompt(self, prompt: str) -> None:
        self._prompt = prompt
        self._render()

    def clear_terminal(self) -> None:
        self.reset_terminal()

    def expect_command_echo(self, command: str) -> None:
        command = command.rstrip("\r\n")
        if not command:
            self._pending_echo_prefix = ""
            self._pending_echo_buffer = ""
            return

        self._pending_echo_prefix = command + "\n"
        self._pending_echo_buffer = ""

    def append_output(self, text: str) -> None:
        text = _tty_cursor_home_to_cr(text)
        text = strip_ansi(text).replace("\r\n", "\n").replace("\r", "\n")
        text = _strip_shell_prompts(text)
        text = self._consume_pending_echo(text)
        if not text:
            return

        self._base_text += text
        self._history_index = None
        self._render()

    def current_input(self) -> str:
        return self._current_input

    def submit_current_input(self) -> str:
        command = self._current_input
        self._base_text += f"{self._prompt}{command}\n"
        if command.strip():
            self._history.append(command)
        self._current_input = ""
        self._history_index = None
        self._render()
        return command

    def _render(self) -> None:
        plain = f"{self._base_text}{self._prompt}{self._current_input}"
        self.setPlainText(plain)
        self._input_start = len(self._base_text) + len(self._prompt)
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def _append_text_to_current_input(self, text: str) -> None:
        if not text:
            return
        self._current_input += text
        self._history_index = None
        self._render()

    def _consume_pending_echo(self, text: str) -> str:
        if not text or not self._pending_echo_prefix:
            return text

        combined = self._pending_echo_buffer + text
        prefix = self._pending_echo_prefix

        if combined.startswith(prefix):
            self._pending_echo_prefix = ""
            self._pending_echo_buffer = ""
            return combined[len(prefix) :]

        if prefix.startswith(combined):
            self._pending_echo_buffer = combined
            return ""

        self._pending_echo_prefix = ""
        self._pending_echo_buffer = ""
        return combined

    def _set_history_item(self, index: int | None) -> None:
        if index is None:
            self._history_index = None
            self._current_input = ""
            self._render()
            return

        if index < 0 or index >= len(self._history):
            return

        self._history_index = index
        self._current_input = self._history[index]
        self._render()

    def _history_previous(self) -> None:
        if not self._history:
            return
        if self._history_index is None:
            self._set_history_item(len(self._history) - 1)
            return
        self._set_history_item(max(0, self._history_index - 1))

    def _history_next(self) -> None:
        if self._history_index is None:
            return
        if self._history_index >= len(self._history) - 1:
            self._set_history_item(None)
            return
        self._set_history_item(self._history_index + 1)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt callback signature
        key = event.key()
        mods = event.modifiers()

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            command = self.submit_current_input()
            self.command_submitted.emit(command)
            event.accept()
            return

        if key == Qt.Key.Key_C and mods & Qt.KeyboardModifier.ControlModifier:
            self.interrupt_requested.emit()
            event.accept()
            return

        if key == Qt.Key.Key_L and mods & Qt.KeyboardModifier.ControlModifier:
            self.clear_terminal()
            event.accept()
            return

        if key == Qt.Key.Key_Backspace:
            if self._current_input:
                self._current_input = self._current_input[:-1]
                self._history_index = None
                self._render()
            event.accept()
            return

        if key == Qt.Key.Key_Up:
            self._history_previous()
            event.accept()
            return

        if key == Qt.Key.Key_Down:
            self._history_next()
            event.accept()
            return

        if key in (Qt.Key.Key_Left, Qt.Key.Key_Home, Qt.Key.Key_PageUp):
            event.accept()
            return

        text = event.text()
        if text:
            self._append_text_to_current_input(text)
            event.accept()
            return

        event.accept()

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt callback signature
        super().mousePressEvent(event)
        cursor = self.textCursor()
        if cursor.position() < self._input_start:
            cursor.setPosition(len(self.toPlainText()))
            self.setTextCursor(cursor)

    def insertFromMimeData(self, source) -> None:  # noqa: N802 - Qt callback signature
        text = source.text()
        if text:
            self._append_text_to_current_input(text)
            return
        super().insertFromMimeData(source)


class TerminalController(QObject):
    """Qt-backed pseudo terminal controller."""

    output_ready = Signal(str)
    error = Signal(str)
    started = Signal(str)
    stopped = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process: QProcess | PtyProcess | None = None
        self._backend: str | None = None
        self._reader_thread: threading.Thread | None = None
        self._reader_stop = threading.Event()
        self._stop_emitted = False

    def backend_name(self) -> str | None:
        return self._backend

    def is_running(self) -> bool:
        if self._process is None:
            return False
        if self._backend == "winpty":
            return bool(self._process.isalive())
        return self._process.state() != QProcess.ProcessState.NotRunning

    def start(
        self,
        *,
        cwd: str,
        program: str = "pwsh",
        backend: str = "auto",
        rows: int = 24,
        columns: int = 80,
    ) -> None:
        if self.is_running():
            return

        self._stop_emitted = False
        backend_name = backend.lower().strip()
        if backend_name == "auto":
            backend_name = "winpty" if _WINPTY_AVAILABLE else "qprocess"
        if backend_name not in {"qprocess", "winpty"}:
            raise ValueError(f"Unsupported terminal backend: {backend}")

        if backend_name == "winpty":
            if not _WINPTY_AVAILABLE:
                self.error.emit("winpty backend is not available on this system.")
                self.stopped.emit()
                return
            self._start_winpty(cwd=cwd, program=program, rows=rows, columns=columns)
            return

        self._start_qprocess(cwd=cwd, program=program)

    def _start_qprocess(self, *, cwd: str, program: str) -> None:
        self._process = QProcess(self)
        process_environment = QProcessEnvironment.systemEnvironment()
        for key, value in _TERMINAL_ENV_VARS.items():
            process_environment.insert(key, value)
        self._process.setProcessEnvironment(process_environment)
        self._process.setWorkingDirectory(cwd)
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self._process.readyReadStandardOutput.connect(self._read_stdout)
        self._process.readyReadStandardError.connect(self._read_stderr)
        self._process.errorOccurred.connect(self._handle_error)
        self._process.finished.connect(self._handle_finished)
        self._process.start(program, [*_TERMINAL_START_ARGS, "-Command", "-"])

        if not self._process.waitForStarted(3000):
            error_text = self._process.errorString()
            self._cleanup_process()
            self.error.emit(f"Failed to start pseudo terminal process: {error_text}")
            self.stopped.emit()
            return

        self._backend = "pyside6"
        self.started.emit(self._backend)

    def _start_winpty(self, *, cwd: str, program: str, rows: int, columns: int) -> None:
        try:
            self._process = PtyProcess.spawn(
                [program, *_TERMINAL_START_ARGS],
                cwd=cwd,
                env=_terminal_environment(),
                dimensions=(rows, columns),
            )
        except Exception as exc:
            self._process = None
            self.error.emit(f"Failed to start pseudo terminal process: {exc}")
            self.stopped.emit()
            return

        self._reader_stop.clear()
        self._reader_thread = threading.Thread(target=self._read_winpty_output, daemon=True)
        self._reader_thread.start()
        self._backend = "winpty"
        self.started.emit(self._backend)

    def submit_command(self, command: str) -> None:
        if self._process is None or not command:
            return
        self.write(command + ("\r" if self._backend == "winpty" else "\n"))
        self._drain_pending_output()

    def write(self, text: str) -> None:
        if self._process is None or not text:
            return
        if self._backend == "winpty":
            self._process.write(text)
            return
        self._process.write(text.encode("utf-8"))

    def send_ctrl_c(self) -> None:
        if self._process is None:
            return
        if self._backend == "winpty":
            try:
                if hasattr(self._process, "sendintr"):
                    self._process.sendintr()
                else:
                    self._process.sendcontrol("c")
            except Exception:
                try:
                    self._process.terminate(force=True)
                except Exception:
                    pass
            return

        self._process.terminate()
        if not self._process.waitForFinished(1000):
            self._process.kill()
            self._process.waitForFinished(1000)

    def close(self) -> None:
        if self._process is None:
            return
        if self._backend == "winpty":
            self._reader_stop.set()
            try:
                self._process.terminate(force=True)
            except Exception:
                try:
                    self._process.close(force=True)
                except Exception:
                    pass
            try:
                self._process.wait()
            except Exception:
                pass
            self._join_reader_thread()
            self._cleanup_process()
            self._backend = None
            self._emit_stopped_once()
            return

        self._process.terminate()
        if not self._process.waitForFinished(1000):
            self._process.kill()
            self._process.waitForFinished(1000)
        self._cleanup_process()
        self._backend = None
        self._emit_stopped_once()

    def resize(self, columns: int, rows: int) -> None:
        if self._process is None or self._backend != "winpty":
            return

        for method_name in ("setwinsize", "set_size", "resize"):
            method = getattr(self._process, method_name, None)
            if method is None:
                continue
            for args in ((rows, columns), (columns, rows)):
                try:
                    method(*args)
                    return
                except TypeError:
                    continue
                except Exception:
                    return

    def _read_stdout(self) -> None:
        if self._process is None:
            return
        data = bytes(self._process.readAllStandardOutput()).decode("utf-8", errors="replace")
        if data:
            self.output_ready.emit(data)

    def _read_stderr(self) -> None:
        if self._process is None:
            return
        data = bytes(self._process.readAllStandardError()).decode("utf-8", errors="replace")
        if data:
            self.output_ready.emit(data)

    def _drain_pending_output(self) -> None:
        if self._process is None:
            return
        if self._backend == "winpty":
            return
        self._read_stdout()
        self._read_stderr()

    def _read_winpty_output(self) -> None:
        process = self._process
        if process is None:
            return

        try:
            while not self._reader_stop.is_set() and process.isalive():
                try:
                    data = process.read(1024)
                except EOFError:
                    break
                if data:
                    self.output_ready.emit(data)
        except Exception as exc:
            self.error.emit(f"Failed to read pseudo terminal output: {exc}")
        finally:
            if self._process is process:
                self._process = None
            self._backend = None
            self._emit_stopped_once()

    def _join_reader_thread(self) -> None:
        thread = self._reader_thread
        if thread is None or thread is threading.current_thread():
            self._reader_thread = None
            return
        thread.join(timeout=1.0)
        self._reader_thread = None

    def _emit_stopped_once(self) -> None:
        if self._stop_emitted:
            return
        self._stop_emitted = True
        self.stopped.emit()

    def _handle_error(self, _error) -> None:
        if self._process is None:
            return
        self.error.emit(self._process.errorString())

    def _handle_finished(self, *_args) -> None:
        self._cleanup_process()
        self._backend = None
        self._emit_stopped_once()

    def _cleanup_process(self) -> None:
        if self._process is None:
            return
        if self._backend == "winpty":
            try:
                if self._process.isalive():
                    self._process.close(force=True)
            except Exception:
                pass
            self._process = None
            return
        try:
            self._process.readyReadStandardOutput.disconnect(self._read_stdout)
        except Exception:
            pass
        try:
            self._process.readyReadStandardError.disconnect(self._read_stderr)
        except Exception:
            pass
        try:
            self._process.errorOccurred.disconnect(self._handle_error)
        except Exception:
            pass
        try:
            self._process.finished.disconnect(self._handle_finished)
        except Exception:
            pass
        self._process.deleteLater()
        self._process = None
