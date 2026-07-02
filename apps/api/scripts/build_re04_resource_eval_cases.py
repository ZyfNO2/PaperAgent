"""Re04 SOP §5 Task 1 — build Re04 resource eval JSONL.

Parse `Plan/PaperAgent_工科学位论文爬取测试集_100篇.md` table 5 (the
100-row engineering thesis catalog) into a JSONL fixture that downstream
Re04 Resource Retrieval Eval can consume.

Per SOP §3 + §5 Task 1:
- Output only fields Re04 actively evaluates: id / title / year / domain /
  source_url / paperagent_test + active_eval + excluded_eval.
- MUST NOT include difficulty / cycle / repeatability / experiment_need
  (those are gold labels reserved for Re05 / HumanGate).
- MUST NOT mutate the source Markdown.
- MUST NOT call network or LLM.

Outputs:
- apps/api/tests/fixtures/re04_engineering_resource_cases.jsonl (100 lines)
- apps/api/tests/fixtures/re04_smoke_20_ids.txt
- apps/api/tests/fixtures/re04_balanced_40_ids.txt

Usage:
    .venv/Scripts/python.exe apps/api/scripts/build_re04_resource_eval_cases.py \\
        --src Plan/PaperAgent_工科学位论文爬取测试集_100篇.md \\
        --out-dir apps/api/tests/fixtures
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Force UTF-8 stdout on Windows so box-drawing / check marks render.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Smoke 20 — taken verbatim from source §7 (推荐 smoke 20).
SMOKE_20 = [
    "ENG-THESIS-015", "ENG-THESIS-016", "ENG-THESIS-018", "ENG-THESIS-024",
    "ENG-THESIS-027", "ENG-THESIS-028", "ENG-THESIS-032", "ENG-THESIS-033",
    "ENG-THESIS-043", "ENG-THESIS-046", "ENG-THESIS-050", "ENG-THESIS-063",
    "ENG-THESIS-066", "ENG-THESIS-074", "ENG-THESIS-075", "ENG-THESIS-080",
    "ENG-THESIS-091", "ENG-THESIS-092", "ENG-THESIS-093", "ENG-THESIS-096",
]

# Balanced 40 = Smoke 20 + these 20 extras (per SOP §3.2).
BALANCED_40_EXTRA = [
    "ENG-THESIS-002", "ENG-THESIS-003", "ENG-THESIS-004", "ENG-THESIS-005",
    "ENG-THESIS-010", "ENG-THESIS-014", "ENG-THESIS-022", "ENG-THESIS-035",
    "ENG-THESIS-040", "ENG-THESIS-048", "ENG-THESIS-051", "ENG-THESIS-058",
    "ENG-THESIS-060", "ENG-THESIS-064", "ENG-THESIS-072", "ENG-THESIS-073",
    "ENG-THESIS-079", "ENG-THESIS-083", "ENG-THESIS-089", "ENG-THESIS-100",
]
BALANCED_40 = SMOKE_20 + BALANCED_40_EXTRA

ACTIVE_EVAL = ["query_plan", "resource_retrieval", "role_bucket", "evidence_ledger"]
EXCLUDED_EVAL = ["difficulty", "cycle", "repeatability", "experiment_need"]

ROW_RE = re.compile(
    r"^\|\s*(ENG-THESIS-\d+)\s*\|"           # 1. id
    r"\s*([^|]+?)\s*\|"                        # 2. title
    r"\s*(\d{4})\s*\|"                         # 3. year
    r"\s*([^|]+?)\s*\|"                        # 4. domain
    r"\s*\[(?:原文/题录链接|原文|题录链接)?\]\(([^)]+)\)\s*\|"  # 5. source_url
    r"\s*([^|]+?)\s*\|"                        # 6. experiment_need (DROPPED)
    r"\s*([^|]+?)\s*\|"                        # 7. difficulty (DROPPED)
    r"\s*([^|]+?)\s*\|"                        # 8. cycle (DROPPED)
    r"\s*([^|]+?)\s*\|"                        # 9. repeatability (DROPPED)
    r"\s*([^|]+?)\s*\|",                       # 10. paperagent_test
    re.MULTILINE,
)


def parse_table(md_text: str) -> list[dict]:
    """Extract 100 catalog rows from markdown §5 table.

    Returns only the Re04-active fields. Drops difficulty / cycle /
    repeatability / experiment_need (those are gold labels reserved for
    Re05/HumanGate; Re04 must not use them as inputs).
    """
    rows: list[dict] = []
    seen_ids: set[str] = set()
    for m in ROW_RE.finditer(md_text):
        eid, title, year, domain, source_url, _exp, _diff, _cycle, _rep, test = m.groups()
        eid = eid.strip()
        if eid in seen_ids:
            continue
        seen_ids.add(eid)
        rows.append({
            "id": eid,
            "title": title.strip(),
            "year": int(year),
            "domain": domain.strip(),
            "source_url": source_url.strip(),
            "paperagent_test": test.strip(),
            "active_eval": list(ACTIVE_EVAL),
            "excluded_eval": list(EXCLUDED_EVAL),
        })
    return rows


def write_jsonl(rows: list[dict], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def write_ids(ids: list[str], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(ids) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="Path to 100-case markdown")
    ap.add_argument("--out-dir", required=True, help="Output directory for JSONL + smoke/balanced id files")
    args = ap.parse_args()

    src = Path(args.src)
    out_dir = Path(args.out_dir)

    md = src.read_text(encoding="utf-8")
    rows = parse_table(md)
    if len(rows) < 100:
        print(f"⚠️  expected 100 rows; parsed {len(rows)}", file=sys.stderr)
        if len(rows) < 90:
            print("✗ abort: too few rows; check source markdown", file=sys.stderr)
            return 2

    write_jsonl(rows, out_dir / "re04_engineering_resource_cases.jsonl")
    write_ids(SMOKE_20, out_dir / "re04_smoke_20_ids.txt")
    write_ids(BALANCED_40, out_dir / "re04_balanced_40_ids.txt")

    smoke_present = sum(1 for r in rows if r["id"] in SMOKE_20)
    balanced_present = sum(1 for r in rows if r["id"] in BALANCED_40)
    print(f"✓ wrote {len(rows)} cases -> {out_dir}/re04_engineering_resource_cases.jsonl")
    print(f"✓ smoke 20 present: {smoke_present}/20")
    print(f"✓ balanced 40 present: {balanced_present}/40")
    return 0


if __name__ == "__main__":
    sys.exit(main())
