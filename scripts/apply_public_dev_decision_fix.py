from __future__ import annotations

import runpy
from pathlib import Path

root = Path(__file__).resolve().parent
patches = (
    root / "apply_public_dev_decision_fix_v4.py",
    root / "apply_public_dev_decision_fix_v5.py",
    root / "apply_public_dev_decision_fix_v6.py",
)
for patch in patches:
    runpy.run_path(str(patch), run_name="__main__")
for stale in (
    root / "apply_public_dev_decision_fix_v2.py",
    root / "apply_public_dev_decision_fix_v3.py",
    *patches,
):
    stale.unlink(missing_ok=True)
