from __future__ import annotations

import runpy
from pathlib import Path

root = Path(__file__).resolve().parent
current = root / "apply_public_dev_decision_fix_v3.py"
runpy.run_path(str(current), run_name="__main__")
for stale in (
    root / "apply_public_dev_decision_fix_v2.py",
    current,
):
    stale.unlink(missing_ok=True)
