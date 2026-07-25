from __future__ import annotations

import sys
from pathlib import Path

PLUGIN_PARENT = Path(__file__).resolve().parents[2]
if str(PLUGIN_PARENT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_PARENT))

from atelier.plugin_api_v2 import router  # noqa: E402

__all__ = ["router"]
