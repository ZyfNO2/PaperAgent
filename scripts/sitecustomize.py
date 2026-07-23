from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path

_TARGET = "apply_evidence_bound_module_fix_followup.py"
_SENTINEL = "PAPERAGENT_METHOD_PREPATCH_ACTIVE"

if (
    os.environ.get("GITHUB_ACTIONS") == "true"
    and Path(sys.argv[0]).name == _TARGET
    and os.environ.get(_SENTINEL) != "1"
):
    os.environ[_SENTINEL] = "1"
    runpy.run_path("scripts/prepatch_method_design.py", run_name="__main__")
