from types import SimpleNamespace

from azure.ai.inference.models import SystemMessage
import pytest

from src.ui import _allowed_commands_for_mode, _build_messages
from src.ui import agent_studio_window as agent_studio_window_module
from src.ui.agent_studio_window import AgentStudioWindow
from src.ui import interactive_terminal as interactive_terminal_module
from src.ui import terminal as terminal_module
from src.ui import windows_frame as windows_frame_module
from PySide6.QtCore import QPoint, QSize
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtWidgets import QToolButton


class _FakeSignal:
    def __init__(self) -> None:
        self.connected = []
        self.disconnected = []

    def connect(self, slot) -> None:
        self.connected.append(slot)

    def disconnect(self, slot) -> None:
        self.disconnected.append(slot)

    def emit(self, *args) -> None:
        for slot in self.connected:
            try:
                slot(*args)
            except TypeError:
                slot()


class _FakeChatWebViewHost(QWidget):
    instances: list["_FakeChatWebViewHost"] = []

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.anchor_activated = _FakeSignal()
        self.loadFinished = _FakeSignal()
        self.html_calls: list[str] = []
        self.scroll_calls = 0
        self.__class__.instances.append(self)

    def set_chat_html(self, html: str) -> None:
        self.html_calls.append(html)

    def scroll_to_bottom(self) -> None:
        self.scroll_calls += 1


class _FakeQProcess:
    class ProcessState:
        NotRunning = 0
        Running = 1

    class ProcessChannelMode:
        SeparateChannels = 0

    def __init__(self, parent=None) -> None:
        self.parent = parent
        self.cwd = None
        self.channel_mode = None
        self.program = None
        self.args = None
        self.state_value = self.ProcessState.NotRunning
        self.written = []
        self.stdout_data = b""
        self.stderr_data = b""
        self.process_environment = None
        self.terminated = False
        self.killed = False
        self.waited_for_started = None
        self.waited_for_finished = []
        self.deleted = False
        self.readyReadStandardOutput = _FakeSignal()
        self.readyReadStandardError = _FakeSignal()
        self.errorOccurred = _FakeSignal()
        self.finished = _FakeSignal()

    def setWorkingDirectory(self, cwd: str) -> None:
        self.cwd = cwd

    def setProcessChannelMode(self, mode) -> None:
        self.channel_mode = mode

    def setProcessEnvironment(self, env) -> None:
        self.process_environment = env

    def errorString(self) -> str:
        return "fake qprocess error"

    def start(self, program: str, args: list[str]) -> None:
        self.program = program
        self.args = args

    def waitForStarted(self, timeout: int) -> bool:
        self.waited_for_started = timeout
        self.state_value = self.ProcessState.Running
        return True

    def state(self):
        return self.state_value

    def readAllStandardOutput(self):
        data = self.stdout_data
        self.stdout_data = b""
        return data

    def readAllStandardError(self):
        data = self.stderr_data
        self.stderr_data = b""
        return data

    def write(self, data: bytes) -> None:
        self.written.append(data)

    def terminate(self) -> None:
        self.terminated = True

    def waitForFinished(self, timeout: int) -> bool:
        self.waited_for_finished.append(timeout)
        return True

    def kill(self) -> None:
        self.killed = True

    def deleteLater(self) -> None:
        self.deleted = True


class _FakePtyProcess:
    spawned: list[tuple[list[str], str | None]] = []
    instances: list["_FakePtyProcess"] = []

    def __init__(self) -> None:
        self.argv = None
        self.cwd = None
        self.env = None
        self.written: list[str] = []
        self.closed = False
        self.terminated = False
        self.alive = True
        self._chunks = ["result from pty\n"]

    @classmethod
    def spawn(cls, argv, cwd=None, env=None, dimensions=(24, 80), backend=None):
        proc = cls()
        proc.argv = list(argv)
        proc.cwd = cwd
        proc.env = env
        cls.spawned.append((proc.argv, cwd))
        cls.instances.append(proc)
        return proc

    def isalive(self) -> bool:
        return self.alive

    def read(self, size: int = 1024) -> str:
        if not self._chunks:
            self.alive = False
            raise EOFError("Pty is closed")
        return self._chunks.pop(0)

    def write(self, text: str) -> None:
        self.written.append(text)

    def sendintr(self) -> None:
        self.terminated = True
        self.alive = False

    def sendcontrol(self, key: str) -> None:
        self.terminated = True
        self.alive = False

    def terminate(self, force: bool = False) -> None:
        self.terminated = True
        self.alive = False

    def close(self, force: bool = False) -> None:
        self.closed = True
        self.alive = False

    def wait(self) -> int:
        return 0


def test_allowed_commands_for_ask_mode_are_read_only():
    assert _allowed_commands_for_mode("ask") == {"done", "ls", "readfiles"}


def test_allowed_commands_for_agent_mode_include_write_actions():
    assert _allowed_commands_for_mode("agent") == {
        "createFiles",
        "createFolders",
        "done",
        "ls",
        "readfiles",
        "runpy",
        "writefile",
    }


def test_build_messages_uses_selected_mode_prompt():
    messages = _build_messages("ask")

    assert len(messages) == 1
    assert isinstance(messages[0], SystemMessage)
    assert "режиме ask" in messages[0].content
    assert "writefile:" not in messages[0].content


def test_allowed_commands_for_mode_rejects_invalid_value():
    with pytest.raises(ValueError, match="Unsupported mode"):
        _allowed_commands_for_mode("invalid")


def test_terminal_starts_pyside6_pseudo_backend(monkeypatch):
    monkeypatch.setattr(terminal_module, "QProcess", _FakeQProcess)

    controller = terminal_module.TerminalController()
    controller.start(cwd="C:/workspace", backend="qprocess")

    assert controller.backend_name() == "pyside6"
    assert controller._process is not None
    assert controller._process.program == "pwsh"
    assert controller._process.args == ["-NoLogo", "-NoExit", "-Command", "-"]
    assert controller._process.process_environment is not None
    assert controller._process.process_environment.value("POWERSHELL_DISABLE_TELEMETRY") == "1"
    assert controller._process.process_environment.value("TERM") == "xterm-256color"
    assert controller._process.process_environment.value("COLORTERM") == "truecolor"


def test_terminal_submit_command_writes_newline(monkeypatch):
    monkeypatch.setattr(terminal_module, "QProcess", _FakeQProcess)

    controller = terminal_module.TerminalController()
    controller.start(cwd="C:/workspace", backend="qprocess")
    controller.submit_command("Get-ChildItem")

    assert controller._process is not None
    assert controller._process.written == [b"Get-ChildItem\n"]


def test_terminal_submit_command_reads_pending_output(monkeypatch):
    monkeypatch.setattr(terminal_module, "QProcess", _FakeQProcess)

    controller = terminal_module.TerminalController()
    controller.start(cwd="C:/workspace", backend="qprocess")
    assert controller._process is not None

    received: list[str] = []
    controller.output_ready.connect(received.append)

    controller._process.stdout_data = b"result from pwsh\n"
    controller.submit_command("Get-ChildItem")

    assert controller._process.written == [b"Get-ChildItem\n"]
    assert received == ["result from pwsh\n"]


def test_terminal_textedit_strips_shell_prompt_and_command_echo():
    app = QApplication.instance() or QApplication([])
    assert app is not None

    terminal = terminal_module.TerminalTextEdit()
    terminal.expect_command_echo("py -m main")
    terminal.append_output("pwsh> py -m main\nВремя работы quicksort: 0.007226 секунд\n")

    assert terminal.toPlainText() == "Время работы quicksort: 0.007226 секунд\npwsh> "


def test_terminal_winpty_backend_streams_output(monkeypatch):
    monkeypatch.setattr(terminal_module, "PtyProcess", _FakePtyProcess)
    controller = terminal_module.TerminalController()
    controller._process = _FakePtyProcess.spawn(["pwsh", "-NoLogo", "-NoProfile", "-NoExit"], cwd="C:/workspace")
    controller._backend = "winpty"

    received: list[str] = []
    controller.output_ready.connect(received.append)

    controller._read_winpty_output()

    assert received == ["result from pty\n"]


def test_terminal_winpty_spawn_receives_terminal_environment(monkeypatch):
    monkeypatch.setattr(terminal_module, "PtyProcess", _FakePtyProcess)
    monkeypatch.setattr(terminal_module, "_WINPTY_AVAILABLE", True)
    _FakePtyProcess.spawned = []
    _FakePtyProcess.instances = []

    controller = terminal_module.TerminalController()
    controller.start(cwd="C:/workspace", backend="winpty")

    assert _FakePtyProcess.spawned
    assert _FakePtyProcess.instances
    proc = _FakePtyProcess.instances[-1]
    _, cwd = _FakePtyProcess.spawned[-1]
    assert cwd == "C:/workspace"
    assert proc.argv == ["pwsh", "-NoLogo", "-NoExit"]
    assert proc.env["POWERSHELL_DISABLE_TELEMETRY"] == "1"
    assert proc.env["TERM"] == "xterm-256color"
    assert proc.env["COLORTERM"] == "truecolor"


def test_title_bar_hit_test_treats_caption_area_as_caption():
    button = QToolButton()
    fake_title_bar = SimpleNamespace(
        isVisible=lambda: True,
        mapToGlobal=lambda point: QPoint(100, 50),
        size=lambda: QSize(800, 38),
        childAt=lambda point: button if point == QPoint(770, 10) else None,
    )

    assert windows_frame_module.hit_test_title_bar(fake_title_bar, QPoint(150, 60)) is True
    assert windows_frame_module.hit_test_title_bar(fake_title_bar, QPoint(870, 60)) is False


def test_resize_border_hit_test_includes_top_edge():
    frame_geometry = windows_frame_module.QRect(100, 50, 800, 600)

    assert windows_frame_module.hit_test_resize_border(frame_geometry, QPoint(500, 52)) == windows_frame_module.HTTOP


def test_resolve_hit_test_returns_client_when_maximized_outside_title_bar():
    fake_title_bar = SimpleNamespace(
        isVisible=lambda: True,
        mapToGlobal=lambda point: QPoint(100, 50),
        size=lambda: QSize(800, 38),
        childAt=lambda point: None,
    )
    frame_geometry = windows_frame_module.QRect(100, 50, 800, 600)

    assert windows_frame_module.resolve_hit_test(
        title_bar=fake_title_bar,
        frame_geometry=frame_geometry,
        cursor_pos=QPoint(102, 120),
        is_maximized=True,
    ) == windows_frame_module.HTCLIENT


def test_apply_extended_client_area_noops_without_native_handle(monkeypatch):
    calls: list[object] = []

    monkeypatch.setattr(windows_frame_module, "_dwm_extend_frame_into_client_area", lambda *args: calls.append("dwm"), raising=False)
    monkeypatch.setattr(windows_frame_module, "_set_window_pos", lambda *args: calls.append("swp"), raising=False)

    class _FakeWindow:
        def winId(self) -> int:
            return 0

    windows_frame_module.apply_extended_client_area(_FakeWindow(), top_margin=38)

    assert calls == []


def test_apply_nccalcsize_insets_uses_dpi_aware_top_border(monkeypatch):
    monkeypatch.setattr(windows_frame_module, "top_client_inset_for_window", lambda window: 11)
    rect = windows_frame_module.RECT(0, 100, 500, 400)

    windows_frame_module.apply_nccalcsize_insets(object(), rect)

    assert rect.top == 111


def test_top_client_inset_is_zero_for_maximized_window(monkeypatch):
    monkeypatch.setattr(windows_frame_module, "frame_border_thickness_for_window", lambda window: 12)

    class _FakeWindow:
        def isMaximized(self) -> bool:
            return True

    assert windows_frame_module.top_client_inset_for_window(_FakeWindow()) == 0


def test_terminal_winpty_submit_command_writes_carriage_return(monkeypatch):
    monkeypatch.setattr(terminal_module, "PtyProcess", _FakePtyProcess)

    controller = terminal_module.TerminalController()
    controller._process = _FakePtyProcess.spawn(["pwsh", "-NoLogo", "-NoProfile", "-NoExit"], cwd="C:/workspace")
    controller._backend = "winpty"

    controller.submit_command("Get-ChildItem")
    assert controller._process.written == ["Get-ChildItem\r"]


def test_agent_window_uses_frameless_custom_title_bar(tmp_path):
    app = QApplication.instance() or QApplication([])
    assert app is not None

    window = AgentStudioWindow(workspace=tmp_path, model="gpt-4.1-mini", max_steps=10)
    try:
        flags = window.windowFlags()
        assert bool(flags & agent_studio_window_module.Qt.WindowType.FramelessWindowHint)
        expanded_client_area_hint = getattr(agent_studio_window_module.Qt.WindowType, "ExpandedClientAreaHint", None)
        if expanded_client_area_hint is not None:
            assert not bool(flags & expanded_client_area_hint)
        no_title_bar_background_hint = getattr(agent_studio_window_module.Qt.WindowType, "NoTitleBarBackgroundHint", None)
        if no_title_bar_background_hint is not None:
            assert not bool(flags & no_title_bar_background_hint)
        assert window._title_bar.parentWidget() is window.centralWidget()
        layout = window.centralWidget().layout()
        assert layout.itemAt(0).widget() is window._title_bar
        assert layout.itemAt(1).widget() is window._title_content_gap
        assert layout.itemAt(2).widget() is window._splitter
        assert layout.count() == 3
        margins = layout.contentsMargins()
        assert margins.top() == 0
        assert window._title_bar.geometry().top() == 0
        assert window._title_bar.geometry().height() == window._title_bar.height()
        assert not window._title_bar._app_icon.isHidden()
        assert not window._title_bar._controls.isHidden()
        assert not hasattr(window, "_title_bar_secondary")
    finally:
        window.close()


def test_agent_window_renders_chat_history_through_chat_webview_host(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    assert app is not None

    _FakeChatWebViewHost.instances = []
    monkeypatch.setattr(agent_studio_window_module, "ChatWebViewHost", _FakeChatWebViewHost)
    monkeypatch.setattr(agent_studio_window_module, "render_chat_history", lambda events, collapsed: ["<html>chat</html>"])

    window = AgentStudioWindow(workspace=tmp_path, model="gpt-4.1-mini", max_steps=10)
    try:
        host = _FakeChatWebViewHost.instances[-1]

        window._append_chat_message("Assistant", "Rendered", tone="assistant")

        assert host.html_calls[-1] == "<html>chat</html>"
        assert host.scroll_calls == 0

        host.loadFinished.emit(True)

        assert host.scroll_calls == 1
    finally:
        window.close()


def test_agent_window_copy_anchor_uses_clipboard(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    assert app is not None

    _FakeChatWebViewHost.instances = []
    monkeypatch.setattr(agent_studio_window_module, "ChatWebViewHost", _FakeChatWebViewHost)
    monkeypatch.setattr(agent_studio_window_module, "get_copy_block", lambda block_id: "copied text" if block_id == "cb_1" else None)

    window = AgentStudioWindow(workspace=tmp_path, model="gpt-4.1-mini", max_steps=10)
    try:
        QApplication.clipboard().clear()

        window._handle_chat_anchor_clicked("copy%3Acb_1")

        assert QApplication.clipboard().text() == "copied text"
    finally:
        window.close()


def test_agent_window_toggle_anchor_re_renders_history(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    assert app is not None

    _FakeChatWebViewHost.instances = []
    monkeypatch.setattr(agent_studio_window_module, "ChatWebViewHost", _FakeChatWebViewHost)

    window = AgentStudioWindow(workspace=tmp_path, model="gpt-4.1-mini", max_steps=10)
    try:
        renders: list[set[str]] = []
        monkeypatch.setattr(window, "_render_chat_history", lambda: renders.append(set(window._collapsed_blocks)))

        window._collapsed_blocks = {"block-7"}
        window._handle_chat_anchor_clicked("toggle%3Ablock-7")
        assert "block-7" not in window._collapsed_blocks

        window._handle_chat_anchor_clicked("toggle%3Ablock-7")
        assert "block-7" in window._collapsed_blocks
        assert len(renders) == 2
    finally:
        window.close()


def test_interactive_terminal_emulator_handles_cursor_rewrites():
    emulator = interactive_terminal_module.TerminalEmulator(rows=3, columns=8)

    emulator.feed("hello\rHEL")

    assert emulator.display_lines(include_scrollback=False)[0] == "HELlo"


def test_interactive_terminal_emulator_supports_scrollback_and_alt_screen():
    emulator = interactive_terminal_module.TerminalEmulator(rows=2, columns=10)

    emulator.feed("one\r\ntwo\r\n")
    emulator.feed("main")
    emulator.feed("\x1b[?1049hALT")
    emulator.feed("\x1b[?1049l")

    lines = emulator.display_lines()
    assert lines[0] == "one"
    assert lines[-2] == "two"
    assert lines[-1] == "main"


def test_interactive_terminal_emulator_supports_sgr_and_dec_graphics():
    emulator = interactive_terminal_module.TerminalEmulator(rows=2, columns=8)

    emulator.feed("\x1b[31mR\x1b[0m\x1b(0lqk")

    assert emulator.screen[0][0].style.fg == interactive_terminal_module.ANSI_16_COLORS[1]
    assert emulator.display_lines(include_scrollback=False)[0].startswith("R┌─┐")


def test_interactive_terminal_emulator_reports_cursor_position():
    emulator = interactive_terminal_module.TerminalEmulator(rows=4, columns=8)

    responses = emulator.feed("abc\x1b[6n")

    assert responses == ["\x1b[1;4R"]
