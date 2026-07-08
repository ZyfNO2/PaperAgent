"""Session 65 T6 测试: evidence_refs 必须用 clean_status / literature_role 门控.

跑法:  .venv/Scripts/python.exe -m pytest apps/api/tests/test_session65_t6_evidence_filter.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.schemas import FeasibilitySummary  # noqa: E402
from app.services import evidence_refs as refs_service  # noqa: E402


# ---------- fixtures ---------- #


def _feas() -> FeasibilitySummary:
    return FeasibilitySummary(
        verdict="可做",
        reason="test",
        paper_status="",
        dataset_status="",
        baseline_status="",
        engineering_status="",
        missing_evidence=[],
        recommended_next_action="",
    )


def _paper(paper_id: str, title: str, *,
           clean_status: str = "keep",
           literature_role: str = "parallel_application_paper",
           review_status: str = "accepted",
           relevance_score: float = 0.6,
           topic_atoms: list[str] | None = None) -> dict:
    """构造一个模拟 paper dict (喂给 build_feasibility_refs)."""
    return {
        "paper_id": paper_id,
        "evidence_id": paper_id,
        "title": title,
        "url": f"https://example.com/{paper_id}",
        "year": 2024,
        "review_status": review_status,
        "relevance_score": relevance_score,
        "paper_type": "baseline_method",
        "clean_status": clean_status,
        "literature_role": literature_role,
        "topic_atoms": topic_atoms or [],
    }


# ---------- T6 §1: 拒收 / 隔离 / survey / irrelevant 不得进 supports ---------- #


def test_rejected_clean_status_not_in_supports():
    feas = _feas()
    papers = [
        _paper("p_rej", "REJECTED paper", clean_status="reject"),
        _paper("p_ok", "OK paper", clean_status="keep", literature_role="parallel_application_paper"),
    ]
    out = refs_service.build_feasibility_refs(feas, papers, [], [])
    supporting = [r for r in out.evidence_refs if r.role == "supports"]
    assert all(r.evidence_id != "p_rej" for r in supporting), "clean_status=reject 不应进 supports"
    assert any(r.evidence_id == "p_ok" for r in supporting), "keep 论文应进 supports"


def test_quarantine_clean_status_not_in_supports():
    feas = _feas()
    papers = [
        _paper("p_q", "QUARANTINE paper", clean_status="quarantine"),
        _paper("p_ok2", "OK paper 2", clean_status="keep"),
    ]
    out = refs_service.build_feasibility_refs(feas, papers, [], [])
    supporting = [r for r in out.evidence_refs if r.role == "supports"]
    assert all(r.evidence_id != "p_q" for r in supporting), "clean_status=quarantine 不应进 supports"


def test_survey_role_not_in_supports():
    feas = _feas()
    papers = [
        _paper("p_survey", "A Survey on Crack Detection", clean_status="keep", literature_role="survey"),
        _paper("p_method", "U-Net Crack Method", clean_status="keep", literature_role="baseline_method"),
    ]
    out = refs_service.build_feasibility_refs(feas, papers, [], [])
    supporting = [r for r in out.evidence_refs if r.role == "supports"]
    assert all(r.evidence_id != "p_survey" for r in supporting), "literature_role=survey 不应进 supports"
    assert any(r.evidence_id == "p_method" for r in supporting), "baseline_method 论文应进 supports"


def test_irrelevant_role_not_in_supports():
    feas = _feas()
    papers = [
        _paper("p_irr", "AGN Study in German", clean_status="keep", literature_role="irrelevant"),
        _paper("p_ok3", "Real Method", clean_status="keep", literature_role="baseline_method"),
    ]
    out = refs_service.build_feasibility_refs(feas, papers, [], [])
    supporting = [r for r in out.evidence_refs if r.role == "supports"]
    assert all(r.evidence_id != "p_irr" for r in supporting), "literature_role=irrelevant 不应进 supports"


def test_survey_paper_not_in_background_either():
    """§6.2 硬规则: survey / irrelevant 既不能 supports, 也不能 background (主区)."""
    feas = _feas()
    papers = [
        _paper("p_s", "A Survey on Something", clean_status="keep", literature_role="survey"),
    ]
    out = refs_service.build_feasibility_refs(feas, papers, [], [])
    # 应走"证据不足"fallback, evidence_refs 为空
    assert out.evidence_refs == [], "survey-only 候选被过滤后, evidence_refs 应为空"
    assert any("证据不足" in r or "未找到" in r for r in out.missing_ref_reasons), "应有'证据不足'提示"


# ---------- T6 §2: reason 不再写"相关性 0.XX" ---------- #


def test_reason_uses_keyword_match_not_score():
    feas = _feas()
    papers = [
        _paper("p_kw", "U-Net Steel Crack Detection",
               topic_atoms=["U-Net", "Steel", "Crack"]),
    ]
    out = refs_service.build_feasibility_refs(feas, papers, [], [], topic_keywords=["U-Net", "Steel", "Crack"])
    assert out.evidence_refs, "应有 supports ref"
    reason = out.evidence_refs[0].reason
    assert "相关性" not in reason, f"reason 不应含'相关性': {reason}"
    assert "命中关键词" in reason, f"reason 应含'命中关键词': {reason}"
    assert "U-Net" in reason, f"reason 应列出命中关键词 U-Net: {reason}"


def test_reason_lists_missing_keywords():
    feas = _feas()
    papers = [
        _paper("p_kw2", "U-Net Concrete Crack",
               topic_atoms=["U-Net", "Concrete", "Crack"]),
    ]
    out = refs_service.build_feasibility_refs(
        feas, papers, [], [], topic_keywords=["U-Net", "Steel", "Crack", "Dataset"]
    )
    reason = out.evidence_refs[0].reason
    assert "缺失" in reason, f"reason 应列出缺失关键词: {reason}"
    assert "Steel" in reason, f"reason 应列出缺失 Steel: {reason}"
    assert "Dataset" in reason, f"reason 应列出缺失 Dataset: {reason}"


# ---------- T6 §3: 全部 paper 被过滤 → 走"证据不足" fallback ---------- #


def test_all_papers_filtered_triggers_evidence_gap_fallback():
    feas = _feas()
    papers = [
        _paper("p_r1", "Rejected 1", clean_status="reject"),
        _paper("p_r2", "Rejected 2", clean_status="quarantine"),
        _paper("p_s", "Survey only", clean_status="keep", literature_role="survey"),
        _paper("p_i", "Irrelevant", clean_status="keep", literature_role="irrelevant"),
    ]
    out = refs_service.build_feasibility_refs(feas, papers, [], [])
    assert out.evidence_refs == [], "全部过滤后 evidence_refs 应为空"
    assert out.confidence == 0.0
    assert any("证据不足" in r for r in out.missing_ref_reasons), "应有'证据不足'原因"
    assert any("待人工" in r for r in out.missing_ref_reasons), "应有'待人工选择'或'待人工确认'提示"


def test_extras_paper_can_rescue_from_evidence_gap():
    """即使自动 paper 全被过滤, extras (用户手动入池) 仍能进 supports."""
    feas = _feas()
    papers = [
        _paper("p_r1", "Rejected", clean_status="reject"),
    ]
    extras = [{
        "evidence_id": "p_manual",
        "evidence_type": "paper",
        "title": "Manual paper",
        "url": "https://example.com",
        "year": 2024,
        "review_status": "core",
        "relevance_score": 0.7,
        "paper_type": "baseline_method",
        "dataset_status": "unverified",
        "repo_type": "unknown",
    }]
    out = refs_service.build_feasibility_refs(feas, papers, [], [], extras=extras)
    assert any(r.evidence_id == "p_manual" for r in out.evidence_refs), "extras 论文应能进 supports"


# ---------- 回归: 旧 test_session7 仍能通过 ---------- #


def test_pydantic_object_paper_does_not_crash():
    """paper 传 Pydantic 对象 (有 .title / .paper_id) 时不应崩."""
    from types import SimpleNamespace
    feas = _feas()
    paper_obj = SimpleNamespace(
        paper_id="p_obj", title="Some Method", year=2024,
        url="https://example.com", relevance_score=0.6, paper_type="baseline_method",
    )
    # Pydantic 对象无 clean_status / literature_role, 视为 keep + parallel
    out = refs_service.build_feasibility_refs(feas, [paper_obj], [], [])
    # 不崩 + 不被过滤 (默认 keep)
    assert isinstance(out.evidence_refs, list)
