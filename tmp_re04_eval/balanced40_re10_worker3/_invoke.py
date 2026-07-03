"""Wrapper to invoke the runner with Path objects (avoids the string-vs-Path bug
in _load_balanced40_cases without editing the script).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path("apps/api/scripts").resolve()))
import run_balanced40_reflection_re10 as M
import argparse

ns = argparse.Namespace(
    out_dir="tmp_re04_eval/balanced40_re10_worker3",
    ids_file="tmp_re04_eval/balanced40_re10_worker3/ids.txt",
)
# Convert string paths to Path so the function can call .read_text()
class _A: pass
a = _A()
a.out_dir = Path(ns.out_dir)
a.ids_file = Path(ns.ids_file)

sys.exit(M.asyncio.run(M.main_async(a)))
