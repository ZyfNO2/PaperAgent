"""Re04/06 SOP §5 acceptance — resource_retrieval_eval tests (offline, Re06).

Re06 changes:
  * Removed ``STRONG_NOISE_TOKENS`` / ``_is_strong_noise`` (Task A).
  * Status is now driven by ``compute_resource_status`` which uses
    ``evidence_consistency.audit_synthesis`` and ``evidence_roles``
    instead of substring matching on a local cross-domain token list.
  * Old ``has_strong_noise_in_core`` field replaced by
    ``critical_consistency_error_n`` / ``metadata_mismatch_n``.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.agents.eval import (
    aggregate_metrics,
    compute_resource_status,
    load_jsonl,
    write_markdown_report,
)


def _pass_result() -> dict:
    return {
        "candidate_pool": [
            *[{"evidence_type": "paper", "title": f"Paper {i}"} for i in range(10)],
            # B1-named topic dataset → topic_dataset under Re06.
            {"evidence_type": "dataset", "title": "B1 dataset",
             "name": "B1 dataset"},
            {"evidence_type": "repo", "title": "owner/R1"},
        ],
        "synthesis": {
            "paper_groups": {
                "baseline": [{
                    "candidate_id": "c-aaaaaa00", "title": "B1",
                    "abstract": "B1 baseline paper on B1 topic with extended "
                                "evaluation across multiple datasets.",
                }],
                "parallel": [
                    {"candidate_id": "c-bbbbbb00", "title": "P1",
                     "abstract": "P1 parallel paper on B1 topic with extensive "
                                 "comparison to B1 baseline."},
                    {"candidate_id": "c-bbbbbb01", "title": "P2",
                     "abstract": "P2 parallel paper on B1 topic providing "
                                 "ablation study of B1 baseline."},
                ],
                "reference": [],
                "long_tail_candidates": [],
            },
            "candidate_pool": {
                "core": [{"candidate_id": "c-core-1", "title": "Core1",
                          "abstract": "Core1 baseline paper on B1 topic"}],
                "dataset": [{
                    "candidate_id": "c-ds-1", "title": "B1 dataset",
                    "name": "B1 dataset",
                    "source_type": "openalex",
                }],
            },
            # Topic atoms must cover B1 + Core1 so axis matching
            # produces aligned core/baseline under Re06.
            "topic_atoms": {
                "task": ["B1 topic"],
                "object": ["B1", "Core1"],
                "method": [],
                "scenario": ["B1 topic"],
            },
        },
        "evidence_review": [],
    }


def _weak_result() -> dict:
    return {
        "candidate_pool": [
            *[{"evidence_type": "paper", "title": f"Paper {i}"} for i in range(5)],
        ],
        "synthesis": {
            "paper_groups": {
                "baseline": [{"candidate_id": "c-aaaaaa00", "title": "B1"}],
                "parallel": [],
                "reference": [],
                "long_tail_candidates": [],
            },
        },
        "evidence_review": [],
    }


def _metadata_mismatch_result() -> dict:
    """Re05 048 root cause: crossref glued AGN title onto ORB-SLAM3 abstract."""
    return {
        "candidate_pool": [{"evidence_type": "paper", "title": f"Paper {i}"}
                            for i in range(10)],
        "synthesis": {
            "paper_groups": {
                "baseline": [{
                    "candidate_id": "c-aaaaaa00",
                    "title": "A rich bounty of AGN in the 9 square degree "
                             "Bootes survey",
                    "abstract": "We propose ORB-LINE-SLAM3, a tightly coupled "
                                "Lidar-Inertial-Visual SLAM system for dynamic "
                                "environments with moving object rejection.",
                }],
                "parallel": [],
                "reference": [],
                "long_tail_candidates": [],
            },
            "candidate_pool": {"core": [], "dataset": []},
        },
        "evidence_review": [],
    }


def _no_baseline_result() -> dict:
    return {
        "candidate_pool": [{"evidence_type": "paper", "title": f"Paper {i}"}
                            for i in range(10)],
        "synthesis": {
            "paper_groups": {"baseline": [], "parallel": [], "reference": [],
                             "long_tail_candidates": []},
        },
        "evidence_review": [],
    }


def _blocked_result() -> dict:
    return {"blocked_reason": "needs_clarification"}


def test_strong_noise_module_removed():
    """Re06 SOP §4 Task A: production code MUST NOT contain
    ``STRONG_NOISE_TOKENS`` or ``_is_strong_noise``.
    """
    import app.services.agents.eval as eval_mod
    assert not hasattr(eval_mod, "STRONG_NOISE_TOKENS")
    assert not hasattr(eval_mod, "_is_strong_noise")


def test_compute_pass_status():
    out = compute_resource_status(_pass_result())
    assert out["status"] == "pass", out
    assert out["paper_n"] == 10
    assert out["baseline_n"] == 1
    assert out["parallel_n"] == 2
    assert out["dataset_n"] == 1
    assert out["repo_n"] == 1


def test_compute_weak_status():
    out = compute_resource_status(_weak_result())
    assert out["status"] == "weak", out


def test_compute_fail_when_metadata_mismatch_in_baseline():
    """Re05 048 root cause regression — metadata_mismatch in baseline
    must yield status='fail' under the new consistency auditor.
    """
    out = compute_resource_status(_metadata_mismatch_result())
    assert out["status"] == "fail", out
    assert out["metadata_mismatch_n"] >= 1
    assert out["critical_consistency_error_n"] >= 1


def test_compute_fail_when_no_baseline():
    out = compute_resource_status(_no_baseline_result())
    assert out["status"] == "fail", out
    assert any("baseline" in r for r in out["evidence_gap_reasons"])


def test_compute_blocked_for_needs_clarification():
    out = compute_resource_status(_blocked_result())
    assert out["status"] == "blocked"
    assert "needs_clarification" in out["reason"]


def test_aggregate_metrics_pass_rate():
    per_case = [
        {"status": "pass"}, {"status": "pass"}, {"status": "weak"},
        {"status": "fail"}, {"status": "blocked"},
    ]
    agg = aggregate_metrics(per_case)
    assert agg["total"] == 5
    assert agg["by_status"]["pass"] == 2
    assert agg["by_status"]["weak"] == 1
    assert agg["by_status"]["fail"] == 1
    assert agg["by_status"]["blocked"] == 1
    assert agg["pass_rate"] == 0.4
    assert agg["weak_or_pass_rate"] == 0.6


def test_write_markdown_report_contains_table(tmp_path: Path):
    out = tmp_path / "re07_report.md"
    per_case = [
        {"case_id": "ENG-THESIS-074", "title": "concrete bridge crack detection",
         "status": "pass", "paper_n": 10, "dataset_n": 1, "repo_n": 1,
         "baseline_n": 2, "parallel_n": 3, "core_direct_n": 1,
         "baseline_direct_n": 1, "baseline_proxy_n": 1,
         "parallel_direct_n": 1, "parallel_proxy_n": 2,
         "effective_baseline_n": 2, "effective_parallel_n": 3,
         "effective_core_n": 1, "core_n": 1,
         "topic_dataset_n": 1, "pretrain_dataset_n": 0,
         "quarantined_baseline_n": 0, "quarantined_parallel_n": 0,
         "quarantined_core_n": 0,
         "axis_status": "evaluable",
         "critical_consistency_error_n": 0,
         "reason": "all_metrics_met"},
        {"case_id": "ENG-THESIS-080", "title": "3D crack detection",
         "status": "weak", "paper_n": 23, "dataset_n": 1, "repo_n": 2,
         "baseline_n": 1, "parallel_n": 2, "core_direct_n": 0,
         "baseline_direct_n": 0, "baseline_proxy_n": 1,
         "parallel_direct_n": 1, "parallel_proxy_n": 1,
         "effective_baseline_n": 1, "effective_parallel_n": 2,
         "effective_core_n": 0, "core_n": 1,
         "topic_dataset_n": 0, "pretrain_dataset_n": 1,
         "quarantined_baseline_n": 1, "quarantined_parallel_n": 0,
         "quarantined_core_n": 0,
         "axis_status": "not_evaluable",
         "critical_consistency_error_n": 1,
         "reason": "metadata_mismatch_quarantined_baseline_n=1"},
    ]
    write_markdown_report(per_case, str(out), source_url="apps/api/tests/fixtures/...jsonl")
    text = out.read_text(encoding="utf-8")
    assert "Re07 Resource Retrieval Eval Report" in text
    assert "ENG-THESIS-074" in text
    assert "ENG-THESIS-080" in text
    assert "pass_rate" in text
    assert "quarantined_total" in text


def test_load_jsonl_roundtrip(tmp_path: Path):
    p = tmp_path / "test.jsonl"
    records = [{"id": "a", "title": "x"}, {"id": "b", "title": "y"}]
    p.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    out = load_jsonl(str(p))
    assert out == records