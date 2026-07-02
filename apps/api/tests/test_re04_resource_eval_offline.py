"""Re04 SOP §5 Task 2 acceptance — resource_retrieval_eval tests (offline)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.agents.eval import (
    STRONG_NOISE_TOKENS,
    _is_strong_noise,
    aggregate_metrics,
    compute_resource_status,
    load_jsonl,
    write_markdown_report,
)


def _pass_result() -> dict:
    return {
        "candidate_pool": [
            *[{"evidence_type": "paper", "title": f"Paper {i}"} for i in range(10)],
            {"evidence_type": "dataset", "title": "D1"},
            {"evidence_type": "repo", "title": "owner/R1"},
        ],
        "synthesis": {
            "paper_groups": {
                "baseline": [{"candidate_id": "c-aaaaaa00", "title": "B1"}],
                "parallel": [
                    {"candidate_id": "c-bbbbbb00", "title": "P1"},
                    {"candidate_id": "c-bbbbbb01", "title": "P2"},
                ],
                "reference": [],
                "long_tail_candidates": [],
            },
            "candidate_pool": {"core": [], "dataset": []},
        },
        "evidence_review": [
            {"status": "core", "title": "B1"},
        ],
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


def _noise_result() -> dict:
    return {
        "candidate_pool": [{"evidence_type": "paper", "title": f"Paper {i}"} for i in range(10)],
        "synthesis": {
            "paper_groups": {
                "baseline": [{"candidate_id": "c-aaaaaa00", "title": "Astro paper"}],
                "parallel": [],
                "reference": [],
                "long_tail_candidates": [],
            },
            "candidate_pool": {"core": [{"title": "AGN survey at 9 sq deg"}]},
        },
        "evidence_review": [{"status": "core", "title": "AGN survey at 9 sq deg"}],
    }


def _no_baseline_result() -> dict:
    return {
        "candidate_pool": [{"evidence_type": "paper", "title": f"Paper {i}"} for i in range(10)],
        "synthesis": {
            "paper_groups": {"baseline": [], "parallel": [], "reference": [],
                             "long_tail_candidates": []},
        },
        "evidence_review": [],
    }


def _blocked_result() -> dict:
    return {"blocked_reason": "needs_clarification"}


def test_strong_noise_detects_cross_domain():
    assert _is_strong_noise("AGN survey at 9 sq deg") is True
    assert _is_strong_noise("captcha recognition") is True
    assert _is_strong_noise("cosmic ray at CERN") is True
    assert _is_strong_noise("Brown dwarf physics") is True
    assert _is_strong_noise("3D crack detection") is False
    assert _is_strong_noise("U-Net steel segmentation") is False


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


def test_compute_fail_when_noise_in_core():
    out = compute_resource_status(_noise_result())
    assert out["status"] == "fail", out
    assert out["has_strong_noise_in_core"] is True


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
    out = tmp_path / "re04_report.md"
    per_case = [
        {"case_id": "ENG-THESIS-074", "title": "concrete bridge crack detection",
         "status": "pass", "paper_n": 10, "dataset_n": 1, "repo_n": 1,
         "baseline_n": 2, "parallel_n": 3, "has_strong_noise_in_core": False,
         "reason": "all_metrics_met"},
        {"case_id": "ENG-THESIS-080", "title": "3D crack detection",
         "status": "fail", "paper_n": 23, "dataset_n": 1, "repo_n": 2,
         "baseline_n": 0, "parallel_n": 2, "has_strong_noise_in_core": True,
         "reason": "strong_noise_in_core_or_baseline_or_parallel"},
    ]
    write_markdown_report(per_case, str(out), source_url="apps/api/tests/fixtures/...jsonl")
    text = out.read_text(encoding="utf-8")
    assert "Re04 Resource Retrieval Eval Report" in text
    assert "ENG-THESIS-074" in text
    assert "ENG-THESIS-080" in text
    assert "pass_rate" in text
    assert "strong_noise" in text


def test_load_jsonl_roundtrip(tmp_path: Path):
    p = tmp_path / "test.jsonl"
    records = [{"id": "a", "title": "x"}, {"id": "b", "title": "y"}]
    p.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    out = load_jsonl(str(p))
    assert out == records
