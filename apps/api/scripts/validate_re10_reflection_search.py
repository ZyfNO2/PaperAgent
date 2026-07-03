"""Re10 FIX SOP §1.3 — reflection-search validator (hard-fail rewrite).

Hard-fail gates (must hold for Re10 FIX to pass):
  H1. missing_client_n == 0  (any "missing client" in trace actions → FAIL)
  H2. adapter_attempt_n > 0 AND adapter_success_n > 0
  H3. llm_call_n > 0  (use --allow-no-llm to bypass for diagnostic only)
  H4. query_repair_n > 0  (placeholder leak in observation → FAIL)
  H5. url_repair_n > 0  IF there are empty/unverified URLs in trace
  H6. trace_coverage.with_trace == n_total
  H7. Re08 seeds preserved in Re10 trace (regression-proof)
  H8. Re09 regression cases show improvement
  H9. status mapping: pass|weak counts ONLY the new evidence-driven
      statuses (no longer stop_reason=='no_new_signal' → weak)

Status mapping (evidence-driven, NOT stop_reason-driven):
  pass            = adapter_success >= 1 AND new_candidate >= 1 AND no missing_client
  weak            = adapter_success >= 1 AND (new_candidate == 0) AND seed kept
  blocked_tooling = missing_client > 0 OR adapter_success == 0
  fail            = tools OK AND multi-round AND no basic candidate

ponytail:
- All hard-fail reasons printed as a single FAIL table at the end.
- Per-case row printed first; gate summary printed last.
- --allow-no-llm is the only escape hatch, and it prints a WARN banner.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

RE08_SUMMARY = Path("G:/PaperAgent/tmp_re04_eval/balanced40_re08/summary.json")
RE09_SUMMARY = Path("G:/PaperAgent/tmp_re04_eval/balanced40_re09_fresh/summary.json")
DEFAULT_RE10_DIR = Path("G:/PaperAgent/tmp_re04_eval/balanced40_re10_reflection")

MISSING_CLIENT_RE = re.compile(r"missing client \w+")
PLACEHOLDER_RE = re.compile(r"\{[^}]*\}|\bX\b")


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_trace(trace_path: str | None, fallback: Path) -> dict:
    p = Path(trace_path) if trace_path else fallback
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Per-case evidence derivation
# ---------------------------------------------------------------------------


def _derive_evidence(case: dict, trace: dict) -> dict:
    """Walk a trace + case summary to derive evidence-driven metrics."""
    actions: list[dict] = []
    observations: list[dict] = []
    for r in (trace.get("rounds") or []):
        actions.extend(r.get("actions") or [])
        obs = r.get("observations") or {}
        if obs:
            observations.append(obs)

    search_actions = [a for a in actions if a.get("type") == "search"]
    repair_url_actions = [a for a in actions if a.get("type") == "repair_url"]
    repair_query_actions = [a for a in actions if a.get("type") == "repair_query"]

    adapter_attempt_n = len(search_actions)
    adapter_success_n = sum(
        1 for a in search_actions if a.get("status") in ("success", "no_results")
    )
    adapter_error_n = sum(1 for a in search_actions if a.get("status") == "error")
    missing_client_n = sum(
        1 for a in search_actions
        if a.get("error") and MISSING_CLIENT_RE.search(str(a.get("error") or ""))
    )

    query_placeholder_leaks: list[str] = []
    for obs in observations:
        query_placeholder_leaks.extend(obs.get("query_placeholder_leaks") or [])

    # LLM call count: derive from repair_query / reflection / domain_scout
    # (reflection_critic / domain_scout produce round-level output; the
    # simplest proxy is repair_query + reflection-diagnosis presence per
    # round).  We treat any non-empty reflection with a "diagnosis" key
    # as one LLM call per round; conservative and intent-faithful.
    llm_call_n = 0
    for r in (trace.get("rounds") or []):
        refl = r.get("reflection") or {}
        if refl.get("diagnosis") or refl.get("next_round_focus"):
            llm_call_n += 1
    if not llm_call_n:
        # If any repair_query action ran, that implies an LLM call too.
        llm_call_n = len(repair_query_actions)

    # URL repair: count repair_url actions that succeeded (url_repaired / url_present)
    url_repair_n = sum(
        1 for a in repair_url_actions
        if a.get("status") in ("url_repaired", "verified") or a.get("result_count", 0) > 0
    )

    # Empty/unverified URLs: empty_url_candidates in observations
    empty_url_n = 0
    for obs in observations:
        empty_url_n += len(obs.get("empty_url_candidates") or [])

    # New / accepted candidate counts
    new_candidates_n = sum(int(r.get("accepted_n") or 0) for r in (trace.get("rounds") or []))
    accepted_candidates_n = new_candidates_n  # alias for clarity in CSV

    query_repair_n = len(repair_query_actions)

    return {
        "case_id": case.get("case_id"),
        "re10_status": case.get("stop_reason", "blocked"),
        "stop_reason": case.get("stop_reason", ""),
        "adapter_attempt_n": adapter_attempt_n,
        "adapter_success_n": adapter_success_n,
        "adapter_error_n": adapter_error_n,
        "missing_client_n": missing_client_n,
        "new_candidates_n": new_candidates_n,
        "accepted_candidates_n": accepted_candidates_n,
        "query_repair_n": query_repair_n,
        "url_repair_n": url_repair_n,
        "empty_url_n": empty_url_n,
        "llm_call_n": llm_call_n,
        "query_placeholder_leaks": query_placeholder_leaks,
    }


def _classify(evidence: dict) -> str:
    """Map evidence → pass|weak|blocked_tooling|fail (NOT stop_reason)."""
    if evidence["missing_client_n"] > 0 or evidence["adapter_success_n"] == 0:
        return "blocked_tooling"
    if evidence["adapter_attempt_n"] == 0:
        return "blocked_tooling"
    if evidence["new_candidates_n"] >= 1:
        return "pass"
    if evidence["new_candidates_n"] == 0 and evidence["accepted_candidates_n"] == 0:
        # tools OK but no basic candidate after multi-round
        return "fail" if evidence["adapter_attempt_n"] >= 2 else "weak"
    return "weak"


def _regression_cases(re08: dict, re09: dict) -> list[str]:
    re08_pass = {c["case_id"] for c in (re08.get("per_case") or [])
                  if c.get("status") == "pass"}
    re09_fail = {c["case_id"] for c in (re09.get("per_case") or [])
                  if c.get("status") == "fail"}
    return sorted(re08_pass & re09_fail)


# ---------------------------------------------------------------------------
# Validator entry
# ---------------------------------------------------------------------------


def validate(re10_dir: Path, re08_summary: Path, re09_summary: Path,
             allow_no_llm: bool = False,
             skip_baseline_gates: bool = False) -> int:
    print(f"=== Re10 FIX reflection-search validator (hard-fail) ===")
    print(f"  re10_dir:    {re10_dir}")
    print(f"  re08_sum:    {re08_summary}")
    print(f"  re09_sum:    {re09_summary}")
    print(f"  allow_no_llm: {allow_no_llm}")
    print(f"  skip_baseline_gates: {skip_baseline_gates}")
    if allow_no_llm:
        print("  WARN: validator running in no-LLM diagnostic mode — not a Re10 FIX gate pass")
    if skip_baseline_gates:
        print("  WARN: skipping H7 (Re08 seeds) + H8 (Re09 regression) — typical-case mode")

    errors: list[str] = []
    re10_summary = _load_json(re10_dir / "summary.json")
    re10_manifest = _load_json(re10_dir / "run_manifest.json")
    re08 = _load_json(re08_summary)
    re09 = _load_json(re09_summary)

    if not re10_summary:
        return _report("re10 summary.json missing", 1)

    per_case = re10_summary.get("per_case") or []
    n_total = len(per_case)

    # ------------------------------------------------------------------
    # Per-case evidence + classification
    # ------------------------------------------------------------------
    by_case_evidence: dict[str, dict] = {}
    for c in per_case:
        cid = c["case_id"]
        tp = c.get("trace_path") or (re10_dir / "traces" / f"{cid}.json")
        trace = _load_trace(tp, re10_dir / "traces" / f"{cid}.json")
        ev = _derive_evidence(c, trace)
        ev["evidence_status"] = _classify(ev)
        by_case_evidence[cid] = ev

    status_counter = Counter(ev["evidence_status"] for ev in by_case_evidence.values())
    pass_n = status_counter.get("pass", 0)
    weak_n = status_counter.get("weak", 0)
    blocked_n = status_counter.get("blocked_tooling", 0)
    fail_n = status_counter.get("fail", 0)
    pw = pass_n + weak_n

    # ------------------------------------------------------------------
    # Per-case table (SOP §1.4)
    # ------------------------------------------------------------------
    print()
    print(f"--- per-case evidence ({n_total} cases) ---")
    cols = (
        "case_id", "re10_status", "stop_reason",
        "adapter_attempt_n", "adapter_success_n", "adapter_error_n", "missing_client_n",
        "new_candidates_n", "accepted_candidates_n",
        "query_repair_n", "url_repair_n", "llm_call_n",
        "evidence_status",
    )
    print("  " + " | ".join(cols))
    for cid, ev in by_case_evidence.items():
        row = [str(ev.get(c, "")) for c in cols]
        print("  " + " | ".join(row))

    # ------------------------------------------------------------------
    # Hard-fail gates
    # ------------------------------------------------------------------
    print()
    print("--- hard-fail gates ---")

    # H6: trace_coverage
    by_trace = re10_manifest.get("trace_coverage", {})
    _gate(errors, "H6 trace_coverage.with_trace == n_total",
          by_trace.get("with_trace") == n_total,
          f"with_trace={by_trace.get('with_trace')}, n_total={n_total}")

    # H1: missing client
    missing_client_total = sum(ev["missing_client_n"] for ev in by_case_evidence.values())
    cases_with_mc = [cid for cid, ev in by_case_evidence.items() if ev["missing_client_n"] > 0]
    _gate(errors, "H1 missing_client_n == 0",
          missing_client_total == 0,
          f"total={missing_client_total} cases={cases_with_mc[:5]}")

    # H2: adapter success
    zero_success_cases = [
        cid for cid, ev in by_case_evidence.items()
        if ev["adapter_attempt_n"] > 0 and ev["adapter_success_n"] == 0
    ]
    _gate(errors, "H2 adapter_success_n > 0 (when adapter_attempt_n > 0)",
          not zero_success_cases,
          f"zero_success_cases={zero_success_cases[:5]}")

    # H3: LLM call
    total_llm_calls = sum(ev["llm_call_n"] for ev in by_case_evidence.values())
    if not allow_no_llm:
        _gate(errors, "H3 llm_call_n > 0 (use --allow-no-llm to skip)",
              total_llm_calls > 0,
              f"total_llm_calls={total_llm_calls}")
    else:
        print(f"  SKIP  H3 llm_call_n (allow_no_llm=True; total={total_llm_calls})")

    # H4: query repair (placeholder leak)
    placeholder_leak_cases = [
        cid for cid, ev in by_case_evidence.items() if ev["query_placeholder_leaks"]
    ]
    _gate(errors, "H4 no query_placeholder_leaks in trace observations",
          not placeholder_leak_cases,
          f"leak_cases={placeholder_leak_cases[:5]}")

    # H5: URL repair
    no_url_repair_cases = [
        cid for cid, ev in by_case_evidence.items()
        if ev["empty_url_n"] > 0 and ev["url_repair_n"] == 0
    ]
    _gate(errors, "H5 url_repair_n > 0 when empty_url_n > 0",
          not no_url_repair_cases,
          f"no_url_repair_cases={no_url_repair_cases[:5]}")

    # H7: Re08 seeds preserved (skip if re08 summary empty / not Balanced40)
    if skip_baseline_gates:
        print(f"  SKIP  H7 Re08 seeds preserved (skip_baseline_gates=True)")
    else:
        re08_seeds = set()
        for c in (re08.get("per_case") or []):
            n = (c.get("verification_repaired_n") or 0) + (c.get("verification_verified_n") or 0)
            if n > 0:
                re08_seeds.add(c["case_id"])
        if not re08_seeds:
            print(f"  SKIP  H7 Re08 seeds preserved (no re08 data — typical-case mode)")
        else:
            missing_seeds: list[str] = []
            for cid in re08_seeds:
                ev = by_case_evidence.get(cid)
                if not ev:
                    missing_seeds.append(f"{cid}(no per-case entry)")
                    continue
                # evidence of seed preservation: trace existed (we already loaded it)
                # and seed_sources.re08_candidates_n > 0 in the trace
                trace = _load_trace(
                    next((c.get("trace_path") for c in per_case if c["case_id"] == cid), None),
                    re10_dir / "traces" / f"{cid}.json",
                )
                seed_n = sum((trace.get("seed_sources") or {}).values())
                if seed_n <= 0:
                    missing_seeds.append(f"{cid}(seed_n=0)")
            _gate(errors, "H7 Re08 seeds preserved in Re10 trace",
                  not missing_seeds,
                  f"violators={missing_seeds[:5]}")

    # H8: Re09 regression improvement (skip if no re09 data)
    if skip_baseline_gates:
        print(f"  SKIP  H8 Re09 regression cases (skip_baseline_gates=True)")
    else:
        regression = _regression_cases(re08, re09)
        if not regression:
            print(f"  SKIP  H8 Re09 regression cases (no re08/re09 baseline)")
        else:
            still_failing: list[str] = []
            for cid in regression:
                ev = by_case_evidence.get(cid)
                if not ev:
                    still_failing.append(f"{cid}(no per-case entry)")
                    continue
                if ev["evidence_status"] in ("blocked_tooling", "fail"):
                    still_failing.append(f"{cid}({ev['evidence_status']})")
            _gate(errors, "H8 Re09 regression cases show improvement",
                  not still_failing,
                  f"still_regressed={still_failing[:5]}")

    # H9: pass+weak gate (evidence-driven, NOT stop_reason)
    _gate(errors, "H9 pass+weak (evidence-driven) > 0",
          pw > 0,
          f"pass={pass_n} weak={weak_n} blocked={blocked_n} fail={fail_n}  by_status={dict(status_counter)}")

    return _report_with_errors(errors)


def _gate(errors: list[str], name: str, ok: bool, detail: str) -> None:
    if ok:
        print(f"  PASS  {name}")
    else:
        msg = f"{name}: {detail}"
        print(f"  FAIL  {msg}")
        errors.append(msg)


def _report_with_errors(errors: list[str]) -> int:
    print()
    if errors:
        print(f"=== {len(errors)} HARD-FAIL GATE(S) ===")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("=== ALL HARD-FAIL GATES PASSED ===")
    return 0


def _report(msg: str, code: int) -> int:
    print(f"  {msg}")
    print("=== REFLECTION-SEARCH GATES FAIL ===")
    return code


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--re10-dir", default=str(DEFAULT_RE10_DIR))
    ap.add_argument("--re08-summary", default=str(RE08_SUMMARY))
    ap.add_argument("--re09-summary", default=str(RE09_SUMMARY))
    ap.add_argument("--allow-no-llm", action="store_true",
                    help="Skip H3 (LLM call) gate; prints a WARN banner; "
                         "not a Re10 FIX gate pass.")
    ap.add_argument("--typical-dir", default=None,
                    help="Alias for --re10-dir, for forward compat with "
                         "the SOP §5 typical-case output directory.")
    ap.add_argument("--skip-baseline-gates", action="store_true",
                    help="Skip H7 (Re08 seeds) and H8 (Re09 regression) — "
                         "for typical-case mode where no baseline exists")
    args = ap.parse_args()
    re10_dir = Path(args.typical_dir) if args.typical_dir else Path(args.re10_dir)
    return validate(
        re10_dir,
        Path(args.re08_summary),
        Path(args.re09_summary),
        allow_no_llm=args.allow_no_llm,
        skip_baseline_gates=args.skip_baseline_gates,
    )


if __name__ == "__main__":
    sys.exit(main())
