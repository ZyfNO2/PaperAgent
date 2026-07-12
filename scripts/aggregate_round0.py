"""Aggregate Round 0 batch JSON files into a single summary table.

Reads all ``artifacts/re7_6/round0/batch_*.json`` files, merges every case
result into one combined view, prints a formatted table to stdout, and writes
a combined ``artifacts/re7_6/round0/aggregate.json``.

Usage:
    python scripts/aggregate_round0.py
"""
import glob
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ROUND0_DIR = os.path.join(ROOT, "artifacts", "re7_6", "round0")
OUT_PATH = os.path.join(ROUND0_DIR, "aggregate.json")


def load_all_cases() -> list[dict]:
    """Load every case dict from all batch_*.json files.

    Re7.7: deduplicate by case_id — keep only the latest result per case
    (highest timestamp in filename). This prevents historical runs from
    polluting the aggregate.
    """
    pattern = os.path.join(ROUND0_DIR, "batch_*.json")
    files = sorted(glob.glob(pattern))
    if not files:
        print(f"WARNING: no batch files found matching {pattern}")
        return []

    # Parse timestamp from filename for deduplication.
    # Filename format: batch_<case_ids>_<timestamp>.json
    import re
    latest_by_case: dict[str, dict] = {}
    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"WARNING: failed to load {fp}: {exc}")
            continue
        cases_in_file: list[dict] = []
        if isinstance(data, list):
            cases_in_file = [item for item in data if isinstance(item, dict)]
        elif isinstance(data, dict):
            cases_in_file = [data]
        # Extract timestamp from filename
        m = re.search(r"_(\d+)\.json$", os.path.basename(fp))
        file_ts = int(m.group(1)) if m else 0
        for item in cases_in_file:
            cid = item.get("case_id", "")
            if not cid:
                continue
            item.setdefault("_source_file", os.path.basename(fp))
            item["_file_timestamp"] = file_ts
            # Keep latest by timestamp
            existing = latest_by_case.get(cid)
            if existing is None or file_ts >= existing.get("_file_timestamp", 0):
                latest_by_case[cid] = item
    return list(latest_by_case.values())


def verdict_match(actual: str, expected: str) -> str:
    """Compare verdicts case-insensitively. Returns YES/NO/PARTIAL/—."""
    a = (actual or "").strip().upper()
    e = (expected or "").strip().upper()
    if not a and not e:
        return "—"
    if a == e:
        return "YES"
    # CONDITIONAL vs GO is partial; STOP vs anything negative is partial
    if a and e and (a in e or e in a):
        return "PARTIAL"
    return "NO"


def fmt_stop_reason(reason) -> str:
    """Render stop_reason (list or str) as a compact single-line string."""
    if isinstance(reason, list):
        parts = [str(r) for r in reason if r]
        return "; ".join(parts) if parts else ""
    if reason is None:
        return ""
    return str(reason)


def print_table(cases: list[dict]) -> None:
    """Print a formatted summary table."""
    headers = ["case_id", "verdict", "expected", "match", "total_s",
               "claim_judge", "low_bar", "stop_reason"]
    widths = [8, 12, 14, 7, 8, 14, 12, 40]

    print(f"\n{'=' * 120}")
    print(f"=== Round 0 Aggregate: {len(cases)} cases ===")
    print(f"{'=' * 120}")
    print("  ".join(h.upper().ljust(w) for h, w in zip(headers, widths)))
    print("  ".join("-" * w for w in widths))

    for c in cases:
        verdict = c.get("actual_verdict") or c.get("verdict") or ""
        expected = c.get("expected_verdict", "")
        match = verdict_match(verdict, expected)
        total_s = c.get("total_s", "")
        total_s_str = f"{total_s:.1f}" if isinstance(total_s, (int, float)) else str(total_s)
        claim_judge = c.get("claim_judge_verdict", "")
        low_bar = c.get("low_bar_status", "")
        stop_reason = fmt_stop_reason(c.get("stop_reason", []))

        row = [
            str(c.get("case_id", ""))[:widths[0]],
            str(verdict)[:widths[1]],
            str(expected)[:widths[2]],
            match[:widths[3]],
            total_s_str[:widths[4]],
            str(claim_judge)[:widths[5]],
            str(low_bar)[:widths[6]],
            stop_reason[:widths[7]],
        ]
        print("  ".join(c.ljust(w) for c, w in zip(row, widths)))

    print(f"{'=' * 120}\n")

    # Quick stats
    n = len(cases)
    if n:
        n_yes = sum(1 for c in cases if verdict_match(
            c.get("actual_verdict") or c.get("verdict") or "",
            c.get("expected_verdict", "")) == "YES")
        n_no = sum(1 for c in cases if verdict_match(
            c.get("actual_verdict") or c.get("verdict") or "",
            c.get("expected_verdict", "")) == "NO")
        print(f"Match stats: {n_yes}/{n} exact YES, {n_no}/{n} NO, {n - n_yes - n_no}/{n} PARTIAL/other")

    # Re7.7 Step 7: verify 耗时 + repair loop 统计
    print(f"\n--- Verify / Repair Loop Analysis ---")
    for c in cases:
        cid = c.get("case_id", "")
        node_timings = c.get("node_timings") or []
        verify_time = next((nt.get("elapsed_s", 0) for nt in node_timings
                           if nt.get("node") == "verify"), 0)
        repair = c.get("repair_loop") or {}
        vbt = c.get("verify_batch_timeline") or []
        vbt_str = ", ".join(f"b{b.get('batch')}:{b.get('elapsed_s')}s({b.get('n_papers')}p)" for b in vbt) if vbt else "n/a"
        print(f"  {cid}: verify={verify_time:.1f}s, batches=[{vbt_str}], "
              f"narrative_revs={repair.get('narrative_revisions', '?')}, "
              f"low_bar_runs={repair.get('low_bar_executions', '?')}")


def main() -> None:
    cases = load_all_cases()
    if not cases:
        print("No cases to aggregate. Exiting.")
        return

    print_table(cases)

    # Write combined aggregate.json (BOM-free UTF-8)
    os.makedirs(ROUND0_DIR, exist_ok=True)
    summary = {
        "n_cases": len(cases),
        "cases": cases,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"Aggregate written to {OUT_PATH}")


if __name__ == "__main__":
    main()
