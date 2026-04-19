"""
Demo window for low-level Win32 chrome.

Win32 implementation lives in src/ui/native_chrome_win32.py (single source of truth).
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from PySide6.QtCore import Qt, QSize  # noqa: E402
from PySide6.QtGui import QMouseEvent, QShowEvent  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QLabel,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QHBoxLayout,
    QWidget,
)

from src.ui.native_chrome_win32 import LowLevelNativeChromeMixin  # noqa: E402


class DemoWindow(QMainWindow, LowLevelNativeChromeMixin):
    def nativeEvent(self, eventType, message):
        if sys.platform == "win32":
            result = self._process_native_event(message)
            if result is not None:
                return result
        return super().nativeEvent(eventType, message)

    def __init__(self):
        super().__init__()
        self._native_chrome_applied = False
        # Build UI first so layout/size hints exist before the native window is
        # realized. On some Windows setups, CreateWindowEx fails for a bare
        # Window|FramelessWindowHint combo; min/max/system-menu hints map to
        # standard WS_* styles and match what _apply_native_styles restores.
        self._build_ui()
        self.setMinimumSize(320, 240)
        self.resize(1100, 760)
        self.setWindowFlags(
            Qt.Window
            | Qt.FramelessWindowHint
            | Qt.WindowMinMaxButtonsHint
            | Qt.WindowSystemMenuHint,
        )

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        # winId() realizes the HWND; do that only after the widget tree exists and
        # the platform window is up, otherwise CreateWindowEx can fail on Windows.
        if not self._native_chrome_applied and sys.platform == "win32":
            self._native_chrome_applied = True
            self._apply_native_styles()

    def _build_ui(self):
        root = QWidget(self)
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.titlebar_widget = QWidget(self)
        self.titlebar_widget.setFixedHeight(40)
        self.titlebar_widget.setObjectName("titlebar")

        tb = QHBoxLayout(self.titlebar_widget)
        tb.setContentsMargins(12, 0, 0, 0)
        tb.setSpacing(0)

        self.title_label = QLabel("Low-level native Win32 chrome")
        self.title_label.setObjectName("titleLabel")

        self.min_button = QPushButton("—")
        self.max_button = QPushButton("□")
        self.close_button = QPushButton("✕")

        for btn in (self.min_button, self.max_button, self.close_button):
            btn.setFixedSize(QSize(46, 40))
            btn.setObjectName("captionButton")

        self.close_button.setObjectName("closeButton")

        self.min_button.clicked.connect(self.showMinimized)
        self.max_button.clicked.connect(self._toggle_max_restore)
        self.close_button.clicked.connect(self.close)

        tb.addWidget(self.title_label, 1)
        tb.addWidget(self.min_button)
        tb.addWidget(self.max_button)
        tb.addWidget(self.close_button)

        self.editor = QTextEdit()
        self.editor.setPlaceholderText(
            "Это обычная клиентская область.\n\n"
            "Окно управляется через WM_NCHITTEST / WM_NCCALCSIZE / WM_GETMINMAXINFO."
        )

        outer.addWidget(self.titlebar_widget)
        outer.addWidget(self.editor, 1)

        # Эти виджеты исключаем из drag-region
        self.no_drag_widgets = [
            self.min_button,
            self.max_button,
            self.close_button,
            self.editor,
        ]

        self.setStyleSheet("""
            QMainWindow {
                background: #1e1e1e;
            }

            QWidget#titlebar {
                background: #181818;
                border-bottom: 1px solid #2b2b2b;
            }

            QLabel#titleLabel {
                color: #d4d4d4;
                font-size: 13px;
                padding-left: 4px;
            }

            QPushButton#captionButton, QPushButton#closeButton {
                border: none;
                background: transparent;
                color: #d4d4d4;
                font-size: 14px;
            }

            QPushButton#captionButton:hover {
                background: #2a2d2e;
            }

            QPushButton#closeButton:hover {
                background: #c42b1c;
                color: white;
            }

            QTextEdit {
                background: #252526;
                color: #d4d4d4;
                border: none;
                padding: 12px;
                font-size: 14px;
            }
        """)

    def _toggle_max_restore(self):
        if self.isMaximized():
            self.showNormal()
            self.max_button.setText("□")
        else:
            self.showMaximized()
            self.max_button.setText("❐")

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            p = event.position().toPoint()
            if self._point_in_titlebar_drag_region(p.x(), p.y()):
                self._toggle_max_restore()
                event.accept()
                return
        super().mouseDoubleClickEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = DemoWindow()
    win.show()
    sys.exit(app.exec())
