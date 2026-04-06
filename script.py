"""Generate PNG title bar buttons for the app."""

from __future__ import annotations

import argparse
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPolygonF


BUTTON_SIZE = 48
OUTPUT_DIR = Path(__file__).resolve().parent / "generated_titlebar_icons"


def _draw_minimize(painter: QPainter, size: int, color: QColor) -> None:
    pen = QPen(color, 3.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    y = size * 0.62
    painter.drawLine(QPointF(size * 0.28, y), QPointF(size * 0.72, y))


def _draw_maximize(painter: QPainter, size: int, color: QColor) -> None:
    pen = QPen(color, 3.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    inset = size * 0.28
    painter.drawRect(QRectF(inset, inset, size - inset * 2, size - inset * 2))


def _draw_close(painter: QPainter, size: int, color: QColor) -> None:
    pen = QPen(color, 3.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    a = size * 0.30
    b = size * 0.70
    painter.drawLine(QPointF(a, a), QPointF(b, b))
    painter.drawLine(QPointF(b, a), QPointF(a, b))


def _draw_diamond_symbol(painter: QPainter, size: int, color: QColor) -> None:
    """Draw ◈ (U+25C8): outer diamond stroke, inner filled diamond."""
    cx = size * 0.5
    cy = size * 0.5
    r = size * 0.30
    outer = QPolygonF(
        [
            QPointF(cx, cy - r),
            QPointF(cx + r, cy),
            QPointF(cx, cy + r),
            QPointF(cx - r, cy),
        ]
    )
    pen = QPen(color, 2.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPolygon(outer)

    ir = r * 0.42
    inner = QPolygonF(
        [
            QPointF(cx, cy - ir),
            QPointF(cx + ir, cy),
            QPointF(cx, cy + ir),
            QPointF(cx - ir, cy),
        ]
    )
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    painter.drawPolygon(inner)


def _make_button(name: str, draw_icon, output_dir: Path, size: int = BUTTON_SIZE) -> Path:
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        draw_icon(painter, size, QColor("#d7d7d7"))
    finally:
        painter.end()

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{name}.png"
    image.save(str(path))
    return path


def build_icons(output_dir: Path = OUTPUT_DIR, size: int = BUTTON_SIZE) -> list[Path]:
    return [
        _make_button("minimize", _draw_minimize, output_dir, size=size),
        _make_button("maximize", _draw_maximize, output_dir, size=size),
        _make_button("close", _draw_close, output_dir, size=size),
        _make_button("diamond", _draw_diamond_symbol, output_dir, size=size),
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate PNG title bar buttons.")
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_DIR,
        help="Output directory for PNG files.",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=BUTTON_SIZE,
        help="Button image size in pixels.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    output_dir = args.output.resolve()
    paths = build_icons(output_dir=output_dir, size=max(16, args.size))
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
