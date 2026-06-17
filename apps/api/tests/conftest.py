"""Pytest config: 默认 asyncio_mode=auto."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
