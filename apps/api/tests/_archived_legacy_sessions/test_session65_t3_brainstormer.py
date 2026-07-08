"""Tests for Session 65 T3 work_package_brainstormer.

Run: .venv/Scripts/python.exe -m pytest apps/api/tests/test_session65_t3_brainstormer.py -v
"""

from __future__ import annotations

from app.services.proposal.work_package_brainstormer import (
    BrainstormResult,
    WorkPackageOption,
    _check_evidence_sufficiency,
    _select_modules_from_papers,
    brainstorm_work_packages,
)


# ---------- needs_baseline_selection ----------


def test_no_baseline_returns_needs_baseline_selection():
    r = brainstorm_work_packages([], [], [], [])
    assert r.status == "needs_baseline_selection"
    assert r.options == []
    assert "baseline" in r.missing[0].lower()
    assert "open_baseline_selection_panel" in r.recommended_tool_calls


def test_none_baseline_returns_needs_baseline_selection():
    """selected_baselines 为空 (parallel + dataset 都有) → 仍 needs_baseline_selection."""
    r = brainstorm_work_packages(
        # selected_baselines: 空
        [],
        # parallel_papers: 有
        [{"candidate_id": "p1", "title": "Y paper", "datasets": ["COCO"]}],
        # module_papers: 空
        [],
        # datasets: 有
        [{"name": "COCO"}],
    )
    assert r.status == "needs_baseline_selection"


# ---------- need_more_search ----------


def test_baseline_without_parallel_returns_need_more_search():
    r = brainstorm_work_packages(
        [{"candidate_id": "c1", "name": "YOLOv8n"}],
        [],  # no parallel
        [],
        [{"name": "COCO"}],  # dataset present in list
    )
    assert r.status == "need_more_search"
    assert any("parallel" in m.lower() for m in r.missing)


def test_baseline_parallel_without_dataset_returns_need_more_search():
    r = brainstorm_work_packages(
        [{"candidate_id": "c1", "name": "YOLOv8n"}],
        [{"candidate_id": "p1", "title": "Y paper", "datasets": []}],
        [],
        [],
    )
    assert r.status == "need_more_search"
    assert any("dataset" in m.lower() for m in r.missing)


def test_baseline_with_full_evidence_returns_ok():
    r = brainstorm_work_packages(
        [{"candidate_id": "c1", "name": "YOLOv8n"}],
        [{"candidate_id": "p1", "title": "Y paper", "datasets": ["COCO"]}],
        [],
        [],
    )
    assert r.status == "ok"
    assert len(r.options) == 1


# ---------- default attention forbidden ----------


def test_default_attention_not_in_options():
    """当 module_papers 只有 'attention' 时, 选项里不应出现 attention (无兜底)."""
    r = brainstorm_work_packages(
        [{"candidate_id": "c1", "name": "YOLOv8n"}],
        [{"candidate_id": "p1", "title": "Y paper", "datasets": ["COCO"]}],
        [{"candidate_id": "m1", "title": "Y paper", "modules_added": ["Attention"]}],
        [],
    )
    assert r.status == "ok"
    mods = [m.lower() for m in r.options[0].module_candidates]
    assert "attention" not in mods
    assert "attention mechanism" not in mods


def test_attention_mechanism_string_filtered():
    r = brainstorm_work_packages(
        [{"candidate_id": "c1", "name": "YOLOv8n"}],
        [{"candidate_id": "p1", "title": "Y paper", "datasets": ["COCO"]}],
        [{"candidate_id": "m1", "title": "Y paper", "modules_added": ["Attention Mechanism", "CIoU Loss"]}],
        [],
    )
    mods = [m.lower() for m in r.options[0].module_candidates]
    assert "attention mechanism" not in mods
    assert "ciou loss" in mods


def test_no_module_papers_yields_empty_modules_not_attention():
    """没有 module_papers 时 modules 为空, 不补 'attention'."""
    r = brainstorm_work_packages(
        [{"candidate_id": "c1", "name": "YOLOv8n"}],
        [{"candidate_id": "p1", "title": "Y paper", "datasets": ["COCO"]}],
        [],
        [],
    )
    assert r.status == "ok"
    assert r.options[0].module_candidates == []
    assert "attention" not in [m.lower() for m in r.options[0].module_candidates]


# ---------- modules come from real paper candidates ----------


def test_modules_extracted_from_paper_modules_added():
    r = brainstorm_work_packages(
        [{"candidate_id": "c1", "name": "YOLOv8n"}],
        [{"candidate_id": "p1", "title": "X paper", "datasets": ["COCO"]}],
        [{"candidate_id": "m1", "title": "Y paper", "modules_added": ["DropBlock", "Mosaic Aug"]}],
        [],
    )
    mods = r.options[0].module_candidates
    assert "DropBlock" in mods
    assert "Mosaic Aug" in mods


def test_modules_deduped_across_papers():
    r = brainstorm_work_packages(
        [{"candidate_id": "c1", "name": "YOLOv8n"}],
        [{"candidate_id": "p1", "title": "X paper", "datasets": ["COCO"]}],
        [
            {"candidate_id": "m1", "title": "Y1", "modules_added": ["DropBlock"]},
            {"candidate_id": "m2", "title": "Y2", "modules_added": ["DropBlock", "CIoU"]},
        ],
        [],
    )
    mods = r.options[0].module_candidates
    assert mods.count("DropBlock") == 1


def test_borrowed_from_papers_capped_at_three():
    papers = [{"candidate_id": f"m{i}", "title": f"Y{i}", "modules_added": [f"Mod{i}"]} for i in range(5)]
    r = brainstorm_work_packages(
        [{"candidate_id": "c1", "name": "YOLOv8n"}],
        [{"candidate_id": "p1", "title": "X paper", "datasets": ["COCO"]}],
        papers,
        [],
    )
    borrowed = r.options[0].borrowed_from_papers
    assert len(borrowed) == 3
    assert borrowed == ["m0", "m1", "m2"]


# ---------- _select_modules_from_papers ----------


def test_select_modules_from_papers_empty():
    assert _select_modules_from_papers([]) == []


def test_select_modules_filters_all_attention_variants():
    papers = [
        {"modules_added": ["Attention", "Self-Attention", "Multi-Head Attention"]},
        {"modules_added": ["Transformer Encoder"]},
    ]
    assert _select_modules_from_papers(papers) == []


def test_select_modules_falls_back_to_borrowable_ideas():
    """当 modules_added 缺, 但 borrowable_ideas 有短名时, 取第一条."""
    papers = [{"borrowable_ideas": ["DropBlock augmentation"]}]
    out = _select_modules_from_papers(papers)
    assert out == ["DropBlock augmentation"]


def test_select_modules_skips_long_borrowable_ideas():
    """borrowable_ideas 的长句 (>40 字符) 跳过, 避免把整句当模块名."""
    long_idea = "a" * 50
    papers = [{"borrowable_ideas": [long_idea]}]
    assert _select_modules_from_papers(papers) == []


# ---------- _check_evidence_sufficiency ----------


def test_evidence_check_returns_baseline_missing_first():
    ok, missing = _check_evidence_sufficiency([], [], [])
    assert ok is False
    assert any("baseline" in m.lower() for m in missing)


def test_evidence_check_dataset_from_datasets_list():
    ok, missing = _check_evidence_sufficiency(
        [{"name": "YOLOv8n"}],
        [],
        [{"name": "COCO"}],
    )
    assert ok is False  # parallel 仍缺
    assert any("parallel" in m.lower() for m in missing)


def test_evidence_check_all_present():
    ok, missing = _check_evidence_sufficiency(
        [{"name": "YOLOv8n"}],
        [{"datasets": ["COCO"]}],
        [],
    )
    assert ok is True
    assert missing == []


# ---------- options shape ----------


def test_options_count_matches_baseline_count_capped_at_max():
    r = brainstorm_work_packages(
        [{"candidate_id": f"c{i}", "name": f"B{i}"} for i in range(7)],
        [{"candidate_id": "p1", "title": "X paper", "datasets": ["COCO"]}],
        [],
        [],
        max_options=5,
    )
    assert r.status == "ok"
    assert len(r.options) == 5


def test_options_have_required_fields():
    r = brainstorm_work_packages(
        [{"candidate_id": "c1", "name": "YOLOv8n", "reproducibility": "high"}],
        [{"candidate_id": "p1", "title": "X paper", "datasets": ["COCO"]}],
        [{"candidate_id": "m1", "title": "Y paper", "modules_added": ["DropBlock"]}],
        [],
    )
    opt = r.options[0]
    assert isinstance(opt, WorkPackageOption)
    assert opt.proposal_id.startswith("wp_")
    assert opt.baseline_candidate_id == "c1"
    assert opt.baseline_name == "YOLOv8n"
    assert opt.dataset == "COCO"
    assert opt.confidence > 0
    assert len(opt.experiment_plan) >= 3
    assert len(opt.why_graduation_friendly) >= 1
    assert len(opt.risk) >= 1
    assert len(opt.must_verify_next) >= 1


def test_brainstorm_result_type():
    r = brainstorm_work_packages(
        [{"candidate_id": "c1", "name": "YOLOv8n"}],
        [{"candidate_id": "p1", "title": "X paper", "datasets": ["COCO"]}],
        [],
        [],
    )
    assert isinstance(r, BrainstormResult)
    assert r.status in {"ok", "need_more_search", "needs_baseline_selection"}


def test_no_fabricated_papers_in_borrowed_list():
    """borrowed_from_papers 必须只来自真实 module_papers 的 candidate_id."""
    r = brainstorm_work_packages(
        [{"candidate_id": "c1", "name": "YOLOv8n"}],
        [{"candidate_id": "p1", "title": "X paper", "datasets": ["COCO"]}],
        [{"candidate_id": "m_real", "title": "Real Y", "modules_added": ["DropBlock"]}],
        [],
    )
    borrowed = r.options[0].borrowed_from_papers
    assert "m_real" in borrowed
    assert "fabricated_paper_xyz" not in borrowed


if __name__ == "__main__":
    import sys

    test_funcs = [v for k, v in globals().items() if k.startswith("test_")]
    failed = 0
    for fn in test_funcs:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(test_funcs) - failed}/{len(test_funcs)} passed")
    sys.exit(0 if failed == 0 else 1)