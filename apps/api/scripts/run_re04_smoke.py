"""Re04 SOP §6.2 — Online Smoke driver.

Loads the 5 ENG-THESIS cases from the JSONL, runs each through
run_research_agent_re04 (real LLM-online), and writes per-case raw
dumps + a summary JSON.

Run:
    .venv/Scripts/python.exe apps/api/scripts/run_re04_smoke.py \\
        --jsonl apps/api/tests/fixtures/re04_engineering_resource_cases.jsonl \\
        --ids apps/api/tests/fixtures/re04_smoke_20_ids.txt \\
        --max 5 \\
        --out-dir tmp_re04_eval

The script consumes LLM quota; that's the point. Per CLAUDE.md
"Minimax 配额随便烧" and the Re04 SOP §6.2 acceptance.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path

# Force UTF-8 stdout on Windows
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Ensure project root is on sys.path so `app.*` imports resolve
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps"))
sys.path.insert(0, str(ROOT / "apps" / "api"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("re04_smoke")


def _coerce(o):
    if hasattr(o, "to_dict"):
        return o.to_dict()
    if hasattr(o, "as_list"):
        return o.as_list()
    if isinstance(o, dict):
        return {k: _coerce(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_coerce(x) for x in o]
    return o


async def run_one(case: dict, out_dir: Path) -> dict:
    """Run a single case via Re04 and dump raw JSON."""
    from app.services.agents.re04_entry import run_research_agent_re04
    from app.services.agents.eval import compute_resource_status

    case_id = case["id"]
    raw_topic = case["title"]
    t0 = time.time()
    logger.info("[%s] starting LLM-online Re04 run", case_id)
    try:
        result = await run_research_agent_re04(raw_topic)
    except Exception as exc:  # noqa: BLE001
        logger.error("[%s] Re04 crashed: %s", case_id, exc)
        return {
            "case_id": case_id,
            "title": raw_topic,
            "status": "fail",
            "reason": f"Re04 crashed: {exc}",
            "elapsed_s": round(time.time() - t0, 2),
            "paper_n": 0, "dataset_n": 0, "repo_n": 0,
            "baseline_n": 0, "parallel_n": 0,
            "has_strong_noise_in_core": False,
        }
    elapsed = round(time.time() - t0, 2)
    status = compute_resource_status(result)
    status["case_id"] = case_id
    status["title"] = raw_topic
    status["elapsed_s"] = elapsed
    # Source URL from the case record (SOP §3 — preserved verbatim)
    status["source_url"] = case.get("source_url", "")
    status["domain"] = case.get("domain", "")
    # Dump raw to disk
    out_path = out_dir / f"{case_id}.json"
    out_path.write_text(
        json.dumps(_coerce(result), ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    logger.info(
        "[%s] done in %.1fs — status=%s paper=%d dataset=%d repo=%d baseline=%d parallel=%d",
        case_id, elapsed,
        status.get("status"), status.get("paper_n", 0),
        status.get("dataset_n", 0), status.get("repo_n", 0),
        status.get("baseline_n", 0), status.get("parallel_n", 0),
    )
    return status


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jsonl", required=True)
    ap.add_argument("--ids", help="Optional id list file (one id per line)")
    ap.add_argument("--max", type=int, default=5)
    ap.add_argument("--out-dir", default="tmp_re04_eval")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cases = [json.loads(line) for line in
             Path(args.jsonl).read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.ids:
        ids = {l.strip() for l in Path(args.ids).read_text(encoding="utf-8").splitlines() if l.strip()}
        cases = [c for c in cases if c["id"] in ids]
    cases = cases[: args.max]

    logger.info("Re04 Online Smoke running %d case(s)", len(cases))
    per_case: list[dict] = []
    for c in cases:
        s = await run_one(c, out_dir)
        per_case.append(s)

    # Summary
    summary = {
        "n": len(per_case),
        "per_case": per_case,
    }
    (out_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    # Markdown report
    from app.services.agents.eval import write_markdown_report
    write_markdown_report(per_case, str(out_dir / "report.md"),
                          source_url=str(args.jsonl))
    n_pass = sum(1 for c in per_case if c.get("status") == "pass")
    n_weak = sum(1 for c in per_case if c.get("status") == "weak")
    n_fail = sum(1 for c in per_case if c.get("status") == "fail")
    n_blocked = sum(1 for c in per_case if c.get("status") == "blocked")
    print(f"\n=== Re04 Online Smoke done ===")
    print(f"  pass: {n_pass}/{len(per_case)}  weak: {n_weak}  fail: {n_fail}  blocked: {n_blocked}")
    print(f"  per-case dumps: {out_dir}/<case_id>.json")
    print(f"  summary:        {out_dir}/summary.json")
    print(f"  markdown:       {out_dir}/report.md")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
