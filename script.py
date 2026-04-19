"""Backward-compatible entry point: PNG generation lives in ``src/ui/assets/assets_gen.py``."""

from __future__ import annotations

from src.ui.assets.assets_gen import build_icons, main

__all__ = ["build_icons", "main"]

if __name__ == "__main__":
    raise SystemExit(main())
