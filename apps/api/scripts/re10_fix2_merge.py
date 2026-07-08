"""Re10 FIX-2 merge_dir helper.

Use case: keep ``iter1_full/`` (39 already-passed cases) verbatim and
only swap in fresh traces for cases where a P0 fix was applied
(e.g. ENG-THESIS-066 after Iter 2).  This avoids re-running the 80-min
Balanced40 batch just to repair one case.

Usage::

    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe \
        apps/api/scripts/re10_fix2_merge.py \
        --base tmp_re04_eval/re10_fix2_iter1_full \
        --overrides tmp_re04_eval/re10_fix2_iter2_retest \
        --out tmp_re04_eval/re10_fix2_iter3_combined
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="dir to copy from (e.g. full Balanced40 run)")
    ap.add_argument("--overrides", required=True, action="append", default=[],
                    help="dir(s) whose case_id-named JSONs overwrite base")
    ap.add_argument("--out", required=True, help="destination dir")
    args = ap.parse_args()

    base = Path(args.base)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "traces").mkdir(exist_ok=True)
    for bd in (base).iterdir():
        if bd.is_dir() and bd.name.startswith("batch"):
            (out / bd.name).mkdir(exist_ok=True)
            for f in bd.iterdir():
                shutil.copy(f, out / bd.name / f.name)
        elif bd.is_file() and bd.suffix == ".json":
            shutil.copy(bd, out / bd.name)

    for f in (base / "traces").iterdir():
        if f.is_file():
            shutil.copy(f, out / "traces" / f.name)

    overrides_cases: dict[str, Path] = {}
    for ov_src in args.overrides:
        ov = Path(ov_src)
        for f in (ov / "traces").iterdir():
            if not f.is_file() or not f.name.startswith("TYPICAL-"):
                continue
            cid = json.loads(f.read_text(encoding="utf-8")).get("case_id") or f.stem
            overrides_cases[cid] = ov
            shutil.copy(f, out / "traces" / f"{cid}.json")

        for bd in ov.iterdir():
            if not bd.is_dir() or not bd.name.startswith("batch"):
                continue
            (out / bd.name).mkdir(exist_ok=True)
            for f in bd.iterdir():
                if not f.is_file() or not f.name.startswith("TYPICAL-"):
                    continue
                cid = json.loads(f.read_text(encoding="utf-8")).get("case_id") or f.stem
                overrides_cases[cid] = ov
                shutil.copy(f, out / bd.name / f"{cid}.json")

    summary_path = out / "summary.json"
    if summary_path.exists():
        s = json.loads(summary_path.read_text(encoding="utf-8"))
        for c in s.get("per_case", []):
            cid = c.get("case_id")
            if cid in overrides_cases:
                new_path = (out / "traces" / f"{cid}.json").resolve()
                c["trace_path"] = str(new_path).replace(chr(92), "/")
        summary_path.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"merged {len(overrides_cases)} override(s) into {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
