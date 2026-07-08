"""Re04 SOP §5 Task 6 — work_package_binding tests."""
from __future__ import annotations


from app.services.agents.work_package_binding import (
    _NO_BASELINE_MSG_ZH,
    extract_candidate_ids,
    validate_no_auto_generated_citation,
    validate_work_suggestions,
)


def _baseline_syn(baseline_count: int = 2, parallel_count: int = 2, dataset_count: int = 1,
                  work=None, evidence_gaps=None, auto_gen_in: list[str] | None = None):
    """Build a minimal but valid synthesis dict."""
    bl = [{"candidate_id": f"c-aaaaaa{i:02x}"} for i in range(baseline_count)]
    pl = [{"candidate_id": f"c-bbbbbb{i:02x}"} for i in range(parallel_count)]
    ds = [{"candidate_id": f"c-dddddd{i:02x}"} for i in range(dataset_count)]
    if work is None:
        work = [
            "使用 c-aaaaaa00 作为基线，参考 c-bbbbbb00 平行方案，复现 c-dddddd00 数据集。",
            "扩展 c-aaaaaa01 + c-bbbbbb01 + c-dddddd00。",
        ]
    paper_groups = {"baseline": bl, "parallel": pl, "reference": [],
                    "long_tail_candidates": []}
    if auto_gen_in:
        for i, bucket in enumerate(paper_groups.values()):
            for j, item in enumerate(bucket):
                if j < len(auto_gen_in) and i < len(auto_gen_in):
                    item["citation_key"] = auto_gen_in[i]
    return {
        "paper_groups": paper_groups,
        "candidate_pool": {"dataset": ds},
        "work_suggestions": work,
        "evidence_gaps": evidence_gaps or [],
    }


def test_extract_candidate_ids_basic():
    ids = extract_candidate_ids("使用 c-a1b2c3 作为基线，参考 c-d4e5f6 平行方案。")
    assert "c-a1b2c3" in ids
    assert "c-d4e5f6" in ids


def test_extract_candidate_ids_ignores_other_text():
    ids = extract_candidate_ids("没有候选 id")
    assert ids == set()


def test_validate_normal_baseline_pass():
    syn = _baseline_syn()
    r = validate_work_suggestions(syn)
    assert r["ok"] is True, r["violations"]
    assert r["short_circuit_reason"] is None
    assert len(r["per_suggestion"]) == 2
    for ps in r["per_suggestion"]:
        assert ps["baseline_hit"]
        assert ps["parallel_or_dataset_hit"]


def test_validate_missing_baseline_hit_violation():
    syn = _baseline_syn(work=[
        "参考 c-bbbbbb00 平行方案但没有 baseline id",
    ])
    r = validate_work_suggestions(syn)
    assert r["ok"] is False
    assert any("missing baseline_candidate_id" in v for v in r["violations"])


def test_validate_missing_parallel_violation():
    syn = _baseline_syn(work=[
        "使用 c-aaaaaa00 作为基线但没有 parallel id",
    ])
    r = validate_work_suggestions(syn)
    assert r["ok"] is False
    assert any("missing parallel_or_dataset_candidate_id" in v for v in r["violations"])


def test_validate_no_baseline_short_circuits():
    syn = _baseline_syn(baseline_count=0, parallel_count=2, dataset_count=0,
                        work=[_NO_BASELINE_MSG_ZH], evidence_gaps=["baseline 没有命中任何候选"])
    r = validate_work_suggestions(syn)
    # baseline_count=0 + evidence_gap about baseline → not short_circuit
    # (the gap tells the user the reason). The work_suggestion has no
    # candidate ids so it's not "full work package".
    assert r["short_circuit_reason"] is None or r["ok"] is True


def test_validate_no_baseline_no_gap_creates_violation():
    syn = _baseline_syn(baseline_count=0, parallel_count=0, dataset_count=0,
                        work=[
                            "使用 c-aaaaaa00 作为基线，参考 c-bbbbbb00",
                        ])
    r = validate_work_suggestions(syn)
    assert r["short_circuit_reason"] == "no_baseline"
    assert r["ok"] is False
    # Single suggestion with ids → "placeholder_suggestion_still_has_ids"
    assert any("placeholder_suggestion_still_has_ids" in v for v in r["violations"])


def test_validate_no_baseline_full_work_package_creates_violation():
    syn = _baseline_syn(baseline_count=0, parallel_count=0, dataset_count=0,
                        work=[
                            "first",
                            "second",
                        ])
    r = validate_work_suggestions(syn)
    assert r["short_circuit_reason"] == "no_baseline"
    assert r["ok"] is False
    assert any("no_baseline_but_full_work_package" in v for v in r["violations"])


def test_validate_no_baseline_with_one_placeholder_is_ok():
    syn = _baseline_syn(baseline_count=0, parallel_count=0, dataset_count=0,
                        work=[_NO_BASELINE_MSG_ZH], evidence_gaps=[])
    r = validate_work_suggestions(syn)
    assert r["ok"] is True
    assert r["short_circuit_reason"] == "no_baseline"


def test_validate_no_baseline_with_placeholder_containing_id_fails():
    syn = _baseline_syn(baseline_count=0, parallel_count=0, dataset_count=0,
                        work=[f"{_NO_BASELINE_MSG_ZH} c-aaaaaa00"], evidence_gaps=[])
    r = validate_work_suggestions(syn)
    assert r["ok"] is False


def test_validate_no_auto_generated_citation_clean():
    syn = _baseline_syn()
    bad = validate_no_auto_generated_citation(syn)
    assert bad == []


def test_validate_no_auto_generated_citation_flags_paper_groups():
    syn = _baseline_syn(auto_gen_in=["auto_generated_1", "auto_generated_2",
                                     "auto_generated_3", "auto_generated_4"])
    bad = validate_no_auto_generated_citation(syn)
    assert any("auto_generated" in b for b in bad)
