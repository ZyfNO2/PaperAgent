from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from typing import Any, TypedDict

from paperagent.claw_academic_benchmark import GoldCase, load_gold_dataset
from paperagent.literature.factory import LiteratureProviderSettings, build_literature_runtime
from paperagent.literature.query_concepts import matches_required_candidate_terms
from paperagent.schemas import SearchQuery

_QUERY_OVERRIDES = {
    "at-001-uav-small-object-lightweight": (
        "lightweight UAV aerial small object detection VisDrone AP_small latency TensorRT"
    ),
}

_TOPIC_GROUPS = {
    "scene": ("uav", "aerial", "drone", "visdrone", "remote sensing"),
    "scale": (
        "small object",
        "tiny object",
        "small target",
        "tiny target",
        "tiny pixel-area",
    ),
    "visual_object_detection": (
        "object detection",
        "object detector",
        "detect objects",
        "detecting objects",
        "target detection",
        "oriented object detection",
        "computer vision",
    ),
    "efficiency": (
        "lightweight",
        "efficient",
        "real-time",
        "realtime",
        "latency",
        "tensorrt",
        "edge",
        "computational demands",
    ),
}


class ProbeResult(TypedDict):
    title: str
    locator: str
    providers: str
    verification_status: str
    relevance_score: float
    rank_score: float
    required_concepts_match: bool
    topic_matches: list[str]
    snippet: str


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run one real, rate-limited literature retrieval probe for a CLAW case."
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=Path("evals/claw_academic_tailoring_v1"),
    )
    parser.add_argument(
        "--case-id",
        default="at-001-uav-small-object-lightweight",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provider-call-budget", type=int, default=3)
    parser.add_argument("--verification-call-budget", type=int, default=8)
    return parser


def _select_case(root: Path, case_id: str) -> GoldCase:
    dataset = load_gold_dataset(root)
    for case in dataset.cases:
        if case.case_id == case_id:
            return case
    raise ValueError(f"unknown case ID: {case_id}")


def _query_for(case: GoldCase) -> str:
    try:
        return _QUERY_OVERRIDES[case.case_id]
    except KeyError as exc:
        raise ValueError(
            f"no reviewed retrieval query is registered for {case.case_id}; "
            "do not issue an unreviewed live search"
        ) from exc


def _topic_matches(title: str, snippet: str) -> list[str]:
    text = f"{title} {snippet}".casefold()
    return [group for group, terms in _TOPIC_GROUPS.items() if any(term in text for term in terms)]


def _verification_budget(service: object) -> dict[str, int | None] | None:
    verifier = getattr(service, "_verifier", None)
    reader = getattr(verifier, "verification_budget", None)
    if not callable(reader):
        return None
    value: Any = reader()
    if not isinstance(value, dict):
        return None
    return value


async def _run(args: argparse.Namespace) -> int:
    if not 1 <= args.provider_call_budget <= 3:
        raise ValueError("--provider-call-budget must be between 1 and 3 for a single-case probe")
    if not 1 <= args.verification_call_budget <= 12:
        raise ValueError(
            "--verification-call-budget must be between 1 and 12 for a single-case probe"
        )

    case = _select_case(args.dataset_root, args.case_id)
    reviewed_query = _query_for(case)
    query_id = f"probe-{case.case_id}"
    runtime = build_literature_runtime(
        LiteratureProviderSettings(
            contact_email=os.getenv("PAPERAGENT_CONTACT_EMAIL"),
            semantic_scholar_api_key=os.getenv("SEMANTIC_SCHOLAR_API_KEY"),
            enable_web_search=False,
            results_per_provider_request=3,
            max_provider_calls_total=args.provider_call_budget,
            max_verification_calls_total=args.verification_call_budget,
        )
    )
    try:
        candidates = await runtime.adapter.search(
            query=SearchQuery(
                query_id=query_id,
                gap_id=f"{case.case_id}-baseline-and-gap",
                query=reviewed_query,
                source_types=["paper"],
            ),
            scenario="live-probe",
            call_index=0,
            fixture_version="live-v1",
            limit=5,
        )
        diagnostics = runtime.adapter.last_query_diagnostics(query_id)
        provider_results = [
            {
                "provider": result.provider,
                "status": result.status,
                "raw_paper_count": len(result.papers),
                "error_code": result.error_code,
                "cache_status": result.cache_status,
            }
            for result in runtime.adapter.last_provider_results(query_id)
        ]
        results: list[ProbeResult] = []
        for candidate in candidates:
            text = f"{candidate.title} {candidate.snippet}"
            matches = _topic_matches(candidate.title, candidate.snippet)
            results.append(
                {
                    "title": candidate.title,
                    "locator": candidate.locator,
                    "providers": candidate.metadata.get("providers", ""),
                    "verification_status": candidate.metadata.get("verification_status", ""),
                    "relevance_score": float(candidate.metadata.get("relevance_score", "0")),
                    "rank_score": float(candidate.metadata.get("rank_score", "0")),
                    "required_concepts_match": matches_required_candidate_terms(
                        reviewed_query, text
                    ),
                    "topic_matches": matches,
                    "snippet": candidate.snippet,
                }
            )
        provider_budget = runtime.service.provider_call_budget()
        verification_budget = _verification_budget(runtime.service)
        verified = [item for item in results if item["verification_status"] == "verified"]
        checks = {
            "query_approved": diagnostics.get("query_approved") is True,
            "precision_risk_low": diagnostics.get("precision_risk") == "low",
            "provider_budget_respected": (
                isinstance(provider_budget.get("used"), int)
                and provider_budget["used"] <= args.provider_call_budget
            ),
            "verification_budget_respected": (
                verification_budget is not None
                and isinstance(verification_budget.get("used"), int)
                and verification_budget["used"] <= args.verification_call_budget
            ),
            "found_results": bool(results),
            "found_verified_result": bool(verified),
            "all_results_pass_adapter_thresholds": all(
                item["relevance_score"] >= float(diagnostics["minimum_relevance"])
                and item["rank_score"] >= float(diagnostics["minimum_rank_score"]) * 0.85
                for item in results
            ),
            "zero_semantic_false_positives": bool(results)
            and all(item["required_concepts_match"] for item in results),
            "web_not_used": diagnostics.get("fallback_used") is False,
        }
        payload = {
            "case_id": case.case_id,
            "original_question": case.user_input,
            "reviewed_query": reviewed_query,
            "diagnostics": diagnostics,
            "provider_results": provider_results,
            "provider_call_budget": provider_budget,
            "verification_call_budget": verification_budget,
            "checks": checks,
            "passed": all(checks.values()),
            "results": results,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if payload["passed"] else 1
    finally:
        await runtime.aclose()


def main() -> int:
    return asyncio.run(_run(_parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
