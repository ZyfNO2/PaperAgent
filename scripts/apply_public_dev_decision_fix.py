from __future__ import annotations

import runpy
from pathlib import Path

path = Path(__file__).with_name("apply_public_dev_decision_fix_v2.py")
runpy.run_path(str(path), run_name="__main__")
