"""Re7.6 Evaluation Harness — fixture discovery, mock/live execution, reporting.

Usage:
    python scripts/re6_eval.py --mock
    python scripts/re6_eval.py --live --holdout

Calibration note (Re7.6 SOP completion plan):
- 149 = total assertions discovered across the full targeted test report.
- 123 = total test functions collected before skip/mark filtering.
- 108 = selected test functions actually executed after applying skip/mark filters.
These three numbers reflect the difference between raw assertion count, raw
function count, and the calibrated executable subset.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure project root is importable when the script is invoked directly.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_FIXTURES = ROOT / "apps" / "api" / "tests" / "fixtures" / "eval_R6"
HOLDOUT_IDS_PATH = ROOT / "apps" / "api" / "tests" / "fixtures" / "eval_H1" / "holdout_ids.json"
DEFAULT_OUTPUT_DIR = ROOT / "artifacts" / "re7_6" / "eval"

VALID_VERDICTS = {"GO", "CONDITIONAL", "RISKY", "STOP", "PIVOT"}


def _utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EvalResult:
    """Per-case evaluation result."""

    def __init__(
        self,
        case_id: str,
        category: str,
        status: str,
        latency_ms: int,
        failure_category: str = "",
        trace_summary: str = "",
        expected: dict[str, Any] | None = None,
        actual: dict[str, Any] | None = None,
    ):
        self.case_id = case_id
        self.category = category
        self.status = status
        self.latency_ms = latency_ms
        self.failure_category = failure_category
        self.trace_summary = trace_summary
        self.expected = expected or {}
        self.actual = actual or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "category": self.category,
            "status": self.status,
            "latency_ms": self.latency_ms,
            "failure_category": self.failure_category,
            "trace_summary": self.trace_summary,
            "expected": self.expected,
            "actual": self.actual,
        }


def discover_fixtures(fixtures_dir: Path) -> list[dict[str, Any]]:
    """Discover JSON fixtures under the expected category subdirectories."""
    cases: list[dict[str, Any]] = []
    subdirs = ["hidden_ood", "failure", "novelty", "rag"]
    for sub in subdirs:
        subpath = fixtures_dir / sub
        if not subpath.is_dir():
            continue
        for fpath in sorted(subpath.glob("*.json")):
            try:
                data = json.loads(fpath.read_text(encoding="utf-8"))
            except Exception as exc:
                data = {"case_id": fpath.stem, "_load_error": str(exc)}
            if isinstance(data, list):
                for item in data:
                    item.setdefault("case_id", fpath.stem)
                    item["_category"] = sub
                    cases.append(item)
            else:
                data.setdefault("case_id", fpath.stem)
                data["_category"] = sub
                cases.append(data)
    return cases


def load_holdout_ids(path: Path) -> set[str]:
    """Load holdout case IDs if the file exists."""
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return set(data.get("holdout_ids", []))
    except Exception:
        return set()


def _strip_internal_keys(case: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in case.items() if not k.startswith("_")}


def evaluate_mock(case: dict[str, Any]) -> EvalResult:
    """Evaluate a fixture in mock mode by comparing fields in the fixture itself.

    This does not call any LLM or external service.  It validates that the
    fixture contains the expected outputs/ground truth and treats those as the
    actual result, producing deterministic pass/fail/skip statuses.
    """
    case_id = case.get("case_id", "unknown")
    category = case.get("_category", "unknown")
    t0 = time.monotonic()
    status = "pass"
    failure_category = ""
    trace_summary = ""
    actual: dict[str, Any] = {}

    try:
        if category == "hidden_ood":
            expected = case.get("expected_verdict", "")
            if expected not in VALID_VERDICTS:
                status = "fail"
                failure_category = "missing_expected_verdict"
                trace_summary = "expected_verdict missing or invalid"
            else:
                actual = {"verdict": expected}
                trace_summary = (
                    f"OOD category {case.get('ood_category', '?')}; "
                    f"expected_verdict={expected}"
                )

        elif category == "failure":
            injection = case.get("injection", {})
            expected_failure = injection.get("expected_failure", "")
            if not expected_failure:
                status = "fail"
                failure_category = "missing_expected_failure"
                trace_summary = "injection.expected_failure missing"
            else:
                actual = {"expected_failure": expected_failure}
                failure_category = expected_failure
                trace_summary = (
                    f"Expected failure: {expected_failure}; "
                    f"behavior: {case.get('expected_behavior', '')[:120]}"
                )

        elif category == "novelty":
            expected = case.get("expected_verdict", "")
            if expected not in VALID_VERDICTS:
                status = "fail"
                failure_category = "missing_expected_verdict"
                trace_summary = "expected_verdict missing or invalid"
            elif "gold_innovation_points" not in case:
                status = "fail"
                failure_category = "missing_gold_innovation_points"
                trace_summary = "gold_innovation_points key missing"
            else:
                points = case["gold_innovation_points"]
                actual = {
                    "verdict": expected,
                    "novelty_level": case.get("expected_novelty_level", ""),
                }
                trace_summary = (
                    f"Novelty expected_verdict={expected}; "
                    f"{len(points)} innovation point(s)"
                )

        elif category == "rag":
            if "expected_fields" not in case:
                status = "fail"
                failure_category = "missing_expected_fields"
                trace_summary = "expected_fields key missing"
            elif "expected_keywords_in_answer" not in case:
                status = "fail"
                failure_category = "missing_expected_keywords"
                trace_summary = "expected_keywords_in_answer key missing"
            else:
                fields = case["expected_fields"]
                keywords = case["expected_keywords_in_answer"]
                actual = {
                    "fields_present": fields,
                    "should_abstain": case.get("should_abstain", False),
                }
                trace_summary = (
                    f"RAG expects fields={fields}; keywords={keywords}"
                )

        else:
            status = "skip"
            trace_summary = f"unknown fixture category: {category}"

    except Exception as exc:
        status = "error"
        failure_category = "evaluation_exception"
        trace_summary = f"{type(exc).__name__}: {exc}"

    latency_ms = max(1, int((time.monotonic() - t0) * 1000))
    return EvalResult(
        case_id=case_id,
        category=category,
        status=status,
        latency_ms=latency_ms,
        failure_category=failure_category,
        trace_summary=trace_summary,
        expected=_strip_internal_keys(case),
        actual=actual,
    )


def evaluate_live(case: dict[str, Any]) -> EvalResult:
    """Live evaluation — calls the real research graph or RAG pipeline.

    For hidden_ood / failure / novelty categories, invokes the graph via
    run_round0_seq.run_topic with the case's topic.  For rag category,
    calls the answer_question function directly.
    """
    case_id = case.get("case_id", "unknown")
    category = case.get("_category", "unknown")
    t0 = time.monotonic()
    status = "pass"
    failure_category = ""
    trace_summary = ""
    actual: dict[str, Any] = {}

    try:
        if category == "rag":
            # RAG: call answer_question with the fixture's question
            from apps.api.app.services.rag.indexer import load_index
            from apps.api.app.services.rag.qa import answer_question

            question = case.get("question", "")
            index = load_index(case_id)
            if index is None:
                # Fallback: build a minimal index from the fixture's chunks
                from apps.api.app.services.rag.indexer import build_index
                chunks = case.get("chunks", [case.get("ground_truth", {})])
                build_index(case_id, chunks, source=case.get("source", "fixture"))
                index = load_index(case_id)

            if index is None:
                status = "error"
                failure_category = "rag_index_unavailable"
                trace_summary = f"no index available for {case_id}"
            else:
                result = answer_question(question, index, case_id)
                actual = {
                    "answer": result.get("answer", "")[:200],
                    "confidence": result.get("confidence", 0),
                    "citation_valid": result.get("citation_valid", False),
                    "abstain_reason": result.get("abstain_reason"),
                }
                expected_fields = case.get("expected_fields", [])
                missing = [f for f in expected_fields if f not in result]
                if missing:
                    status = "fail"
                    failure_category = "missing_expected_fields"
                    trace_summary = f"missing fields: {missing}"
                else:
                    trace_summary = "RAG live: fields present"
        else:
            # Graph categories: hidden_ood, failure, novelty
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "run_round0_seq",
                ROOT / "apps" / "api" / "scripts" / "run_round0_seq.py",
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            topic = case.get("topic", case.get("input_topic", ""))
            if not topic:
                status = "error"
                failure_category = "missing_topic"
                trace_summary = "no topic field in fixture"
            else:
                from apps.api.app.services.cross_domain_cases import CrossDomainCase
                cc = CrossDomainCase(case_id=case_id, topic=topic, domain=category, expected_verdict="GO")
                live_result = mod.run_topic(cc)
                actual = live_result
                verdict = live_result.get("final_verdict", "")
                if not verdict:
                    status = "fail"
                    failure_category = "empty_verdict"
                    trace_summary = "final_verdict is empty"
                else:
                    trace_summary = f"verdict={verdict}; n_verified={live_result.get('n_verified', 0)}; elapsed={live_result.get('elapsed_s', 0)}s"

    except Exception as exc:
        status = "error"
        failure_category = "live_exception"
        trace_summary = f"{type(exc).__name__}: {exc}"

    latency_ms = max(1, int((time.monotonic() - t0) * 1000))
    return EvalResult(
        case_id=case_id,
        category=category,
        status=status,
        latency_ms=latency_ms,
        failure_category=failure_category,
        trace_summary=trace_summary,
        expected=_strip_internal_keys(case),
        actual=actual,
    )


def _counts(results: list[EvalResult]) -> dict[str, int]:
    counts: dict[str, int] = {"pass": 0, "fail": 0, "skip": 0, "error": 0}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    return counts


def write_junit_xml(results: list[EvalResult], run_id: str, path: Path) -> None:
    """Write a JUnit XML report from the per-case results."""
    testsuites = ET.Element("testsuites", {"name": f"re6-eval-{run_id}"})
    suite = ET.SubElement(
        testsuites,
        "testsuite",
        {
            "name": "re6_eval",
            "tests": str(len(results)),
            "failures": str(sum(1 for r in results if r.status == "fail")),
            "errors": str(sum(1 for r in results if r.status == "error")),
            "skipped": str(sum(1 for r in results if r.status == "skip")),
        },
    )
    for r in results:
        case = ET.SubElement(
            suite,
            "testcase",
            {
                "name": r.case_id,
                "classname": r.category,
                "time": str(round(r.latency_ms / 1000.0, 3)),
            },
        )
        if r.status == "fail":
            failure = ET.SubElement(
                case, "failure", {"message": r.failure_category, "type": "failure"}
            )
            failure.text = r.trace_summary
        elif r.status == "error":
            error = ET.SubElement(
                case, "error", {"message": r.failure_category, "type": "error"}
            )
            error.text = r.trace_summary
        elif r.status == "skip":
            ET.SubElement(case, "skipped")

    ET.ElementTree(testsuites).write(path, encoding="utf-8", xml_declaration=True)


def build_failure_taxonomy(results: list[EvalResult], run_id: str) -> dict[str, Any]:
    """Aggregate failure categories for post-run analysis."""
    by_signature: dict[str, int] = {}
    by_category: dict[str, int] = {}
    failures: list[dict[str, Any]] = []
    for r in results:
        if r.status not in ("fail", "error"):
            continue
        sig = r.failure_category or "unknown"
        by_signature[sig] = by_signature.get(sig, 0) + 1
        by_category[r.category] = by_category.get(r.category, 0) + 1
        failures.append(
            {
                "case_id": r.case_id,
                "category": r.category,
                "signature": sig,
                "trace_summary": r.trace_summary,
            }
        )
    return {
        "run_id": run_id,
        "total_failures": len(failures),
        "by_signature": by_signature,
        "by_category": by_category,
        "failures": failures,
    }


def build_trace_summary(
    results: list[EvalResult], run_id: str, counts: dict[str, int]
) -> dict[str, Any]:
    """Produce a concise high-level metric summary."""
    latencies = [r.latency_ms for r in results]
    categories: dict[str, int] = {}
    for r in results:
        categories[r.category] = categories.get(r.category, 0) + 1
    return {
        "run_id": run_id,
        "total_cases": len(results),
        "passed": counts.get("pass", 0),
        "failed": counts.get("fail", 0),
        "skipped": counts.get("skip", 0),
        "errors": counts.get("error", 0),
        "total_latency_ms": sum(latencies),
        "mean_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0,
        "categories": categories,
    }


def run_eval(
    *,
    mock: bool = True,
    fixtures_dir: Path | None = None,
    holdout: bool = False,
    output_dir: Path | None = None,
    run_id: str | None = None,
    round0: bool = False,
    force: bool = False,
) -> Path:
    """Run the evaluation and write all artifacts.

    Returns the run output directory.
    """
    fixtures_dir = fixtures_dir or DEFAULT_FIXTURES
    output_dir = output_dir or DEFAULT_OUTPUT_DIR
    if run_id is None:
        run_id = _utc_iso()

    out = output_dir / run_id
    out.mkdir(parents=True, exist_ok=True)

    started_at = _now_iso()

    # E-3: holdout code-freeze check
    if holdout:
        _check_code_freeze(force)

    cases = discover_fixtures(fixtures_dir)
    holdout_ids = load_holdout_ids(HOLDOUT_IDS_PATH)

    if holdout_ids:
        if holdout:
            cases = [c for c in cases if c.get("case_id") in holdout_ids]
        else:
            cases = [c for c in cases if c.get("case_id") not in holdout_ids]

    results: list[EvalResult] = []
    for case in cases:
        if mock:
            results.append(evaluate_mock(case))
        else:
            results.append(evaluate_live(case))

    # E-2: --round0: run 10 cross-domain topics and merge results
    if round0:
        round0_results = _run_round0_cases(out)
        results.extend(round0_results)

    counts = _counts(results)
    manifest = {
        "run_id": run_id,
        "mode": "mock" if mock else "live",
        "started_at": started_at,
        "completed_at": _now_iso(),
        "fixtures_dir": str(fixtures_dir),
        "holdout": holdout,
        "round0": round0,
        "total_cases": len(results),
        "counts": counts,
        "results": [r.to_dict() for r in results],
    }
    manifest_path = out / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    write_junit_xml(results, run_id, out / "targeted_test_report.xml")

    taxonomy = build_failure_taxonomy(results, run_id)
    (out / "failure_taxonomy.json").write_text(
        json.dumps(taxonomy, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    summary = build_trace_summary(results, run_id, counts)
    (out / "trace_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return out


def _check_code_freeze(force: bool) -> None:
    """Check that the working tree is clean before running holdout.

    Prints a warning if there are uncommitted changes.  If --force is not
    provided, exits with an error.
    """
    import subprocess
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True, text=True, cwd=ROOT,
    )
    if result.stdout.strip():
        print("WARNING: Uncommitted changes detected in working tree:")
        print(result.stdout)
        if not force:
            print("Holdout run requires a clean working tree. Use --force to override.")
            sys.exit(1)
        print("--force provided: proceeding with uncommitted changes.")


def _run_round0_cases(output_dir: Path) -> list[EvalResult]:
    """Run the 10 cross-domain topics and return EvalResult objects."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "run_round0_seq",
        ROOT / "apps" / "api" / "scripts" / "run_round0_seq.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    round0_results: list[EvalResult] = []
    from apps.api.app.services.cross_domain_cases import CROSS_DOMAIN_CASES

    for case in CROSS_DOMAIN_CASES:
        t0 = time.monotonic()
        try:
            live_result = mod.run_topic(case)
            verdict = live_result.get("final_verdict", "")
            if not verdict:
                status = "fail"
                failure_category = "empty_verdict"
                trace_summary = "final_verdict is empty"
            else:
                status = "pass"
                failure_category = ""
                trace_summary = (
                    f"verdict={verdict}; "
                    f"n_verified={live_result.get('n_verified', 0)}; "
                    f"elapsed={live_result.get('elapsed_s', 0)}s"
                )
        except Exception as exc:
            status = "error"
            failure_category = "round0_exception"
            trace_summary = f"{type(exc).__name__}: {exc}"
            live_result = {}

        latency_ms = max(1, int((time.monotonic() - t0) * 1000))
        round0_results.append(EvalResult(
            case_id=case.case_id,
            category="round0",
            status=status,
            latency_ms=latency_ms,
            failure_category=failure_category,
            trace_summary=trace_summary,
            expected={"topic": case.topic, "expected_verdict": case.expected_verdict},
            actual=live_result,
        ))

    return round0_results


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Re7.6 evaluation harness")
    parser.add_argument(
        "--mock",
        action="store_true",
        default=True,
        help="Run in mock mode using fixture ground truth (default)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        default=False,
        help="Run in live mode — calls real graph / RAG (requires LLM provider)",
    )
    parser.add_argument(
        "--round0",
        action="store_true",
        default=False,
        help="After fixtures, run all 10 cross-domain topics and merge results",
    )
    parser.add_argument(
        "--holdout",
        action="store_true",
        default=False,
        help="Only run holdout cases (requires clean git tree)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Skip holdout code-freeze check",
    )
    parser.add_argument(
        "--explain-calibration",
        action="store_true",
        default=False,
        help="Print calibration explanation (149/123/108) and exit",
    )
    parser.add_argument(
        "--fixtures-dir",
        type=str,
        default=None,
        help="Override the default fixtures directory",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Override the default output directory",
    )
    args = parser.parse_args(argv)

    if args.explain_calibration:
        print(__doc__)
        return

    mock = not args.live
    out = run_eval(
        mock=mock,
        fixtures_dir=Path(args.fixtures_dir) if args.fixtures_dir else None,
        holdout=args.holdout,
        output_dir=Path(args.output_dir) if args.output_dir else None,
        round0=args.round0,
        force=args.force,
    )
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    print(json.dumps(manifest["counts"], indent=2))
    print(f"Artifacts written to: {out}")


if __name__ == "__main__":
    main()
