"""Environment settings shared by the terminal and desktop clients."""

import os

from dotenv import load_dotenv

load_dotenv()


def debug_colors_enabled() -> bool:
    return os.getenv("DEBUG_COLORS", "false").strip().lower() in {"1", "true", "yes"}
