"""Pytest loads this module before test packages; env must precede UI imports (WebView2 / pythonnet)."""

import os
from pathlib import Path
import sys

os.environ["BABKACLI_DISABLE_WEBVIEW2"] = "1"


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
