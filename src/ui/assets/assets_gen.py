"""Generate raster UI assets (PNG with transparency).

Includes title bar icons (minimize, maximize, close, cross, diamond), arrow_up,
и два GIF морфа: ``cross_to_arrow.gif`` (крест → стрелка) и ``arrow_to_cross.gif`` (стрелка → крест).
Крест плавно поворачивается на **45°** CCW по ``smoothstep(t)`` без обратного доворота; диагональ
NW–SE сгибается из центра в наконечник; вторая диагональ — древко. Каждый GIF — **20** кадров
(0…1 или 1…0).

Run from repo root:

  .venv\\Scripts\\python.exe src/ui/assets/assets_gen.py
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPolygonF, QTransform


DEFAULT_SIZE = 48
DEFAULT_COLOR = "#d7d7d7"
_DEFAULT_OUTPUT = Path(__file__).resolve().parent

# GIF: half-cycle steps; ``half_steps + 1`` frames per direction (e.g. 19 → 20 frames for 0…1).
_GIF_HALF_STEPS = 19
_GIF_FRAME_MS = 22
# Max tilt of the whole figure vs canvas; Qt negative angle = CCW.
_GIF_ROT_MAX_DEG = 45.0


def _smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _map_rotated(x: float, y: float, cx: float, cy: float, angle_deg: float) -> QPointF:
    """Rotate (x, y) around (cx, cy); Qt: positive angle = CW, negative = CCW."""
    tr = QTransform()
    tr.translate(cx, cy)
    tr.rotate(angle_deg)
    tr.translate(-cx, -cy)
    return tr.map(QPointF(x, y))


def _pen(color: QColor, width_px: float, size: int) -> QPen:
    w = float(size)
    return QPen(
        color,
        max(1.0, w * (width_px / 48.0)),
        Qt.PenStyle.SolidLine,
        Qt.PenCapStyle.RoundCap,
        Qt.PenJoinStyle.RoundJoin,
    )


def _draw_minimize(painter: QPainter, size: int, color: QColor) -> None:
    painter.setPen(_pen(color, 3.2, size))
    y = size * 0.62
    painter.drawLine(QPointF(size * 0.28, y), QPointF(size * 0.72, y))


def _draw_maximize(painter: QPainter, size: int, color: QColor) -> None:
    painter.setPen(_pen(color, 3.0, size))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    inset = size * 0.28
    painter.drawRect(QRectF(inset, inset, size - inset * 2, size - inset * 2))


def _draw_close(painter: QPainter, size: int, color: QColor) -> None:
    painter.setPen(_pen(color, 3.2, size))
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
    painter.setPen(_pen(color, 2.6, size))
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


def _draw_arrow_up(painter: QPainter, size: int, color: QColor) -> None:
    """Stroke-only arrow: slanted head edges + shaft from tip to bottom."""
    w = float(size)
    cx = w * 0.5
    tip_y = w * 0.07
    base_y = w * 0.31
    half_w = w * 0.27
    shaft_bottom = w * 0.93

    pen = QPen(
        color,
        max(1.0, w * 0.048),
        Qt.PenStyle.SolidLine,
        Qt.PenCapStyle.RoundCap,
        Qt.PenJoinStyle.RoundJoin,
    )
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    tip = QPointF(cx, tip_y)
    left = QPointF(cx - half_w, base_y)
    right = QPointF(cx + half_w, base_y)
    shaft_end = QPointF(cx, shaft_bottom)

    painter.drawLine(tip, left)
    painter.drawLine(tip, right)
    painter.drawLine(tip, shaft_end)


def _draw_cross_to_arrow_morph(
    painter: QPainter, size: int, color: QColor, t: float
) -> None:
    """Cross → arrow: NW–SE diagonal splits at center into head; NE–SW → shaft.

    ``t`` ∈ [0, 1]: 0 = cross, 1 = arrow. The whole figure eases from ``0`` to
    :data:`-_GIF_ROT_MAX_DEG` (CCW) once; arrow targets are pre-rotated back by
    :data:`_GIF_ROT_MAX_DEG` so the final displayed arrow stays upright.
    """
    w = float(size)
    u = _smoothstep(t)
    cx = w * 0.5
    cy = w * 0.5
    a = w * 0.30
    b = w * 0.70

    tip_y = w * 0.07
    base_y = w * 0.31
    half_w = w * 0.27
    shaft_bottom = w * 0.93

    # Keep the final arrow visually upright while the whole figure rotates CCW.
    tip_target = _map_rotated(cx, tip_y, cx, cy, _GIF_ROT_MAX_DEG)
    left_target = _map_rotated(cx - half_w, base_y, cx, cy, _GIF_ROT_MAX_DEG)
    right_target = _map_rotated(cx + half_w, base_y, cx, cy, _GIF_ROT_MAX_DEG)
    shaft_top_target = _map_rotated(cx, tip_y, cx, cy, _GIF_ROT_MAX_DEG)
    shaft_bottom_target = _map_rotated(cx, shaft_bottom, cx, cy, _GIF_ROT_MAX_DEG)

    # Former NW–SE diagonal: center (cx,cy) lifts to tip, ends go to head shoulders.
    tip_x = _lerp(cx, tip_target.x(), u)
    tip_y_m = _lerp(cy, tip_target.y(), u)
    lx = _lerp(a, left_target.x(), u)
    ly = _lerp(a, left_target.y(), u)
    rx = _lerp(b, right_target.x(), u)
    ry = _lerp(b, right_target.y(), u)

    # Former NE–SW diagonal → shaft.
    sx0 = _lerp(b, shaft_top_target.x(), u)
    sy0 = _lerp(a, shaft_top_target.y(), u)
    sx1 = _lerp(a, shaft_bottom_target.x(), u)
    sy1 = _lerp(b, shaft_bottom_target.y(), u)

    rot_deg = -_GIF_ROT_MAX_DEG * u

    p_tip = _map_rotated(tip_x, tip_y_m, cx, cy, rot_deg)
    p_l = _map_rotated(lx, ly, cx, cy, rot_deg)
    p_r = _map_rotated(rx, ry, cx, cy, rot_deg)
    p_s0 = _map_rotated(sx0, sy0, cx, cy, rot_deg)
    p_s1 = _map_rotated(sx1, sy1, cx, cy, rot_deg)

    w_close = max(1.0, w * (3.2 / 48.0))
    w_arrow = max(1.0, w * 0.048)
    pen_w = _lerp(w_close, w_arrow, u)
    pen = QPen(
        color,
        pen_w,
        Qt.PenStyle.SolidLine,
        Qt.PenCapStyle.RoundCap,
        Qt.PenJoinStyle.RoundJoin,
    )
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    painter.drawLine(p_s0, p_s1)
    painter.drawLine(p_tip, p_l)
    painter.drawLine(p_tip, p_r)


def _qimage_from_draw(
    draw_fn: Callable[[QPainter, int, QColor], None],
    size: int,
    color: QColor,
) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        draw_fn(painter, size, color)
    finally:
        painter.end()
    return image


def _render_png(
    draw_fn: Callable[[QPainter, int, QColor], None],
    *,
    size: int,
    color: QColor,
    path: Path,
) -> Path:
    image = _qimage_from_draw(draw_fn, size, color)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(path))
    return path


def _make_morph_draw(
    t: float,
) -> Callable[[QPainter, int, QColor], None]:
    def draw(painter: QPainter, size: int, color: QColor) -> None:
        _draw_cross_to_arrow_morph(painter, size, color, t)

    return draw


def _pil_gif_frames(
    size: int,
    color: QColor,
    *,
    half_steps: int,
) -> tuple[list, list]:
    """Return ``(forward_frames, backward_frames)``; needs Pillow."""
    from PIL import Image, ImageQt  # type: ignore[import-untyped]

    n = max(2, half_steps)

    def frame_at_t(tt: float) -> Image.Image:
        qimg = _qimage_from_draw(_make_morph_draw(tt), size, color)
        return ImageQt.fromqimage(qimg).convert("RGBA")

    forward = [frame_at_t(i / n) for i in range(n + 1)]
    backward = [frame_at_t(i / n) for i in range(n, -1, -1)]
    return forward, backward


def _save_gif_sequence(
    frames: list,
    out_path: Path,
    *,
    frame_ms: int,
) -> Path:
    duration = max(20, frame_ms)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        out_path,
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0,
        disposal=2,
        optimize=True,
    )
    return out_path


def _build_cross_arrow_morph_gifs(
    output_dir: Path,
    *,
    size: int,
    color: QColor,
    half_steps: int = _GIF_HALF_STEPS,
    frame_ms: int = _GIF_FRAME_MS,
) -> tuple[Path, Path]:
    try:
        forward, backward = _pil_gif_frames(size, color, half_steps=half_steps)
    except ImportError as e:
        raise ImportError(
            'GIF generation needs Pillow. Install dev extras: pip install -e ".[dev]"'
        ) from e

    p1 = _save_gif_sequence(
        forward, output_dir / "cross_to_arrow.gif", frame_ms=frame_ms
    )
    p2 = _save_gif_sequence(
        backward, output_dir / "arrow_to_cross.gif", frame_ms=frame_ms
    )
    return p1, p2


def build_assets(
    output_dir: Path,
    *,
    size: int = DEFAULT_SIZE,
    color: str = DEFAULT_COLOR,
) -> list[Path]:
    """Generate bundled PNG assets and morph GIFs into ``output_dir``."""
    c = QColor(color)
    specs: list[tuple[str, Callable[[QPainter, int, QColor], None]]] = [
        ("minimize", _draw_minimize),
        ("maximize", _draw_maximize),
        ("close", _draw_close),
        ("cross", _draw_close),
        ("diamond", _draw_diamond_symbol),
        ("arrow_up", _draw_arrow_up),
    ]
    paths: list[Path] = [
        _render_png(fn, size=size, color=c, path=output_dir / f"{name}.png")
        for name, fn in specs
    ]
    paths.extend(_build_cross_arrow_morph_gifs(output_dir, size=size, color=c))
    return paths


def build_icons(
    output_dir: Path | None = None,
    *,
    size: int = DEFAULT_SIZE,
    color: str = DEFAULT_COLOR,
) -> list[Path]:
    """Alias for :func:`build_assets` (same name as the old ``script.py`` API)."""
    out = output_dir if output_dir is not None else _DEFAULT_OUTPUT
    return build_assets(out, size=size, color=color)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate UI PNG assets (transparent background).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=_DEFAULT_OUTPUT,
        help="Directory for generated PNG files (default: this assets folder).",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=DEFAULT_SIZE,
        help="Image size in pixels (square).",
    )
    parser.add_argument(
        "--color",
        default=DEFAULT_COLOR,
        help="Icon color (CSS-style hex or name).",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    output_dir = args.output.resolve()
    size = max(16, args.size)
    for path in build_assets(output_dir, size=size, color=args.color):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
