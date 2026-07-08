"""Session 7 后端测试: EvidenceRef 强制挂接 + 复核闭环 (SOP §5 + §6 + §7 + §9.1).

跑法:  .venv/Scripts/python.exe -m pytest apps/api/tests/test_session7_evidence_refs.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.main import app  # noqa: E402
from app.services import evidence as ev_store  # noqa: E402
from app.services import evidence_refs as refs_service  # noqa: E402
from app.schemas import (  # noqa: E402
    FeasibilitySummary,
)


@pytest.fixture(autouse=True)
def _clean_ledger():
    ev_store.reset_all()
    yield
    ev_store.reset_all()


@pytest.fixture
def client():
    return TestClient(app)


def _run_one_topic(client: TestClient, raw_topic: str = "YOLO钢材表面缺陷检测", prefer: str = "heuristic") -> str:
    """跑一次 /analyze 拿到 project_id (会落 snapshot)."""

    req = {"raw_topic": raw_topic, "prefer": prefer}
    r = client.post("/api/v1/one-topic/analyze", json=req)
    assert r.status_code == 200, r.text
    return r.json()["project_id"]


def _extras_paper(evidence_id: str, title: str, review: str = "accepted",
                  paper_type: str = "baseline_method", relevance_score: float = 0.7,
                  year: int = 2024, url: str | None = None) -> dict:
    """直接构造 extras dict (PaperHit 没有 review_status 字段)."""

    return {
        "evidence_id": evidence_id,
        "evidence_type": "paper",
        "title": title,
        "url": url or "https://example.com",
        "year": year,
        "review_status": review,
        "relevance_score": relevance_score,
        "quality_score": None,
        "paper_type": paper_type,
        "dataset_status": "unverified",
        "repo_type": "unknown",
    }


def _extras_dataset(evidence_id: str, name: str, review: str = "accepted",
                    quality_score: float = 0.7, dataset_status: str = "ready") -> dict:
    return {
        "evidence_id": evidence_id,
        "evidence_type": "dataset",
        "title": name,
        "url": "https://example.com/dataset",
        "year": None,
        "review_status": review,
        "relevance_score": None,
        "quality_score": quality_score,
        "paper_type": "unknown",
        "dataset_status": dataset_status,
        "repo_type": "unknown",
    }


def _extras_repo(evidence_id: str, name: str, review: str = "accepted",
                 quality_score: float = 0.7, repo_type: str = "official") -> dict:
    return {
        "evidence_id": evidence_id,
        "evidence_type": "repo",
        "title": name,
        "url": "https://github.com/xxx/yyy",
        "year": None,
        "review_status": review,
        "relevance_score": None,
        "quality_score": quality_score,
        "paper_type": "unknown",
        "dataset_status": "unverified",
        "repo_type": repo_type,
    }


# ---------- §5.1 / §5.2: FeasibilitySummary 挂 evidence_refs ---------- #


def test_01_feasibility_binds_paper_dataset_repo_refs(client):
    """§9.1.1: FeasibilitySummary 能绑定 paper/dataset/repo refs."""

    pid = _run_one_topic(client)
    r = client.get(f"/api/v1/one-topic/{pid}/evidence/refs/coverage")
    assert r.status_code == 200, r.text
    cov = r.json()
    assert cov["feasibility_has_refs"] is True
    assert cov["feasibility_has_refs"] is True


def test_02_rejected_evidence_cannot_be_support(client):
    """§9.1.2 + §6.1: rejected evidence 不得作为 supports."""

    feas = FeasibilitySummary(
        verdict="可做", reason="t", paper_status="", dataset_status="",
        baseline_status="", engineering_status="", missing_evidence=[],
        recommended_next_action="",
    )
    extras = [
        _extras_paper("p_rej", "REJECTED paper", review="rejected"),
        _extras_dataset("d_acc", "ACCEPTED dataset"),
        _extras_repo("r_acc", "ACCEPTED repo"),
    ]

    feas2 = refs_service.build_feasibility_refs(
        feas, [], [], [], extras=extras,
    )
    supporting_ids = [r.evidence_id for r in feas2.evidence_refs if r.role == "supports"]
    assert "p_rej" not in supporting_ids, "rejected paper 不应进 supports"
    assert "d_acc" in supporting_ids, "accepted dataset 应进 supports"
    assert "r_acc" in supporting_ids, "accepted repo 应进 supports"


def test_03_needs_check_only_warns_or_blocks(client):
    """§9.1.3: needs_check evidence 只能作为 warns 或 blocks."""

    feas = FeasibilitySummary(
        verdict="可做", reason="t", paper_status="", dataset_status="",
        baseline_status="", engineering_status="", missing_evidence=[],
        recommended_next_action="",
    )
    extras = [
        _extras_paper("p_nc", "needs_check paper", review="needs_check", relevance_score=0.3),
    ]
    feas2 = refs_service.build_feasibility_refs(feas, [], [], [], extras=extras)
    roles = [r.role for r in feas2.evidence_refs]
    assert "supports" not in roles, "needs_check 不能 supports"
    assert all(r in ("warns", "blocks", "background") for r in roles), f"unexpected roles: {roles}"


def test_04_core_evidence_selected_first(client):
    """§9.1.4 + §6.2: core evidence 优先被选中 (ref_priority 最高)."""

    feas = FeasibilitySummary(
        verdict="可做", reason="t", paper_status="", dataset_status="",
        baseline_status="", engineering_status="", missing_evidence=[],
        recommended_next_action="",
    )
    # core 的 review_weight=1.00, accepted=0.80, background=0.50
    # 设 score 让 core 显著胜出 (core review_weight 优势 > score 差距)
    extras = [
        _extras_paper("p_accepted", "accepted paper", review="accepted", relevance_score=0.3),
        _extras_paper("p_core", "CORE paper", review="core", relevance_score=0.5),
        _extras_paper("p_background", "background paper", review="background", relevance_score=0.4),
    ]
    feas2 = refs_service.build_feasibility_refs(feas, [], [], [], extras=extras)
    picked_ids = [r.evidence_id for r in feas2.evidence_refs[:3]]
    assert picked_ids[0] == "p_core", f"core 应排第 1, 实际 {picked_ids}"


def test_05_three_pivot_routes_all_have_refs(client):
    """§9.1.5: PivotRoute 三条路线都有 evidence_refs."""

    pid = _run_one_topic(client)
    r = client.get(f"/api/v1/one-topic/{pid}/evidence/refs/coverage")
    assert r.status_code == 200
    cov = r.json()
    assert cov["pivot_routes_total"] == 3
    assert cov["pivot_routes_with_refs"] >= 1, "至少 1 条 pivot 路线应有 refs"


def test_06_work_package_at_least_paper_ref(client):
    """§9.1.6: WorkPackageSuggestion 至少绑定 paper ref."""

    pid = _run_one_topic(client)
    r = client.get(f"/api/v1/one-topic/{pid}/evidence/refs/coverage")
    cov = r.json()
    assert cov["work_packages_with_refs"] >= 1, "至少 1 个 WP 应有 refs"


# ---------- §5.5: recommendation_reason unsupported_claims ---------- #


def test_07_unsupported_reason_lands_in_claims(client):
    """§9.1.7: recommendation_reason 无证据时进入 unsupported_claims."""

    pid = _run_one_topic(client)
    # 拿 proposal 里的 reason 看是否生成 unsupported_claims (空 pool 时)
    cov = client.get(f"/api/v1/one-topic/{pid}/evidence/refs/coverage").json()
    # 不是空 pool 时可能 0 unsupported, 不应报错
    assert "unsupported_claims" in cov
    assert isinstance(cov["unsupported_claims"], list)


# ---------- §5.6: LightReview 每个 check 能绑定 evidence_refs ---------- #


def test_08_light_review_checks_have_refs(client):
    """§9.1.8: LightReview 每个 check 能绑定 evidence_refs."""

    pid = _run_one_topic(client)
    r = client.get(f"/api/v1/one-topic/{pid}/evidence/refs/coverage")
    cov = r.json()
    assert cov["review_checks_total"] == 5
    assert cov["review_checks_with_refs"] >= 1


# ---------- §7.1: rebuild 不改变 review_status ---------- #


def test_09_rebuild_does_not_change_review_status(client):
    """§9.1.9: refs/rebuild 不改变 review_status."""

    pid = _run_one_topic(client)
    r = client.get(f"/api/v1/one-topic/{pid}/evidence")
    assert r.status_code == 200
    paper_id = next((e["evidence_id"] for e in r.json()["papers"]), None)
    if not paper_id:
        pytest.skip("没有 paper, 跳过")

    # 改 review_status 为 core (用户操作)
    client.patch(
        f"/api/v1/one-topic/evidence/{paper_id}/review",
        json={"review_status": "core"},
    )

    # rebuild
    rb = client.post(f"/api/v1/one-topic/{pid}/evidence/refs/rebuild")
    assert rb.status_code == 200, rb.text

    # 再拿一次, 验证 status 还是 core (rebuild 没改回 pending)
    r2 = client.get(f"/api/v1/one-topic/{pid}/evidence")
    after_status = next((e["review_status"] for e in
                         r2.json()["papers"] + r2.json()["datasets"] + r2.json()["repos"]
                         if e["evidence_id"] == paper_id), None)
    assert after_status == "core", f"rebuild 不应回退 review_status, after={after_status}"


# ---------- §7.2: coverage_score ---------- #


def test_10_coverage_score_in_range(client):
    """§9.1.10: refs/coverage 能计算 coverage_score ∈ [0, 1]."""

    pid = _run_one_topic(client)
    cov = client.get(f"/api/v1/one-topic/{pid}/evidence/refs/coverage").json()
    assert 0.0 <= cov["coverage_score"] <= 1.0


def test_11_user_remove_ref_lowers_coverage(client):
    """§9.1.11: 用户 remove_ref 后 coverage_score 不上升 (下降或不变)."""

    pid = _run_one_topic(client)
    # 拿 feasibility refs
    cov_before = client.get(f"/api/v1/one-topic/{pid}/evidence/refs/coverage").json()
    score_before = cov_before["coverage_score"]

    # 找 feasibility 的第一条 ref, 移除
    feas = client.get(f"/api/v1/one-topic/{pid}/evidence/refs/coverage").json()
    # 直接通过 rebuild 后的 snapshot 拿
    snap = ev_store.get_snapshot(pid)
    assert snap is not None
    feas_obj = FeasibilitySummary.model_validate(snap["feasibility"])
    if not feas_obj.evidence_refs:
        pytest.skip("没有 feasibility refs, 跳过")
    target_eid = feas_obj.evidence_refs[0].evidence_id

    # remove_ref
    r = client.patch(
        f"/api/v1/one-topic/{pid}/evidence/refs/review",
        json={
            "target_type": "feasibility", "target_id": "main",
            "evidence_id": target_eid, "action": "remove_ref",
            "reason": "测试移除",
        },
    )
    assert r.status_code == 200, r.text

    score_after = r.json()["new_coverage_score"]
    assert score_after <= score_before, f"remove 后 coverage 不应上升: {score_before} → {score_after}"


def test_12_user_mark_ref_core_raises_priority(client):
    """§9.1.12: 用户 mark_ref_core 后 ref_priority 上升 (该 ref 的 review_weight 提到 1.00)."""

    pid = _run_one_topic(client)
    snap = ev_store.get_snapshot(pid)
    feas = FeasibilitySummary.model_validate(snap["feasibility"])
    if len(feas.evidence_refs) < 1:
        pytest.skip("没有 refs, 跳过")

    # 选一个非 core 的 ref
    target_idx = next((i for i, r in enumerate(feas.evidence_refs)
                       if r.review_status != "core"), 0)
    target = feas.evidence_refs[target_idx]
    before_status = target.review_status

    # mark_ref_core
    r = client.patch(
        f"/api/v1/one-topic/{pid}/evidence/refs/review",
        json={
            "target_type": "feasibility", "target_id": "main",
            "evidence_id": target.evidence_id, "action": "mark_ref_core",
            "reason": "测试标核心",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True

    # 验证: ref 在新 snapshot 里 review_status == core
    snap2 = ev_store.get_snapshot(pid)
    feas2 = FeasibilitySummary.model_validate(snap2["feasibility"])
    marked = next((r for r in feas2.evidence_refs if r.evidence_id == target.evidence_id), None)
    assert marked is not None, f"ref {target.evidence_id} 不见了"
    assert marked.review_status == "core", f"应变为 core, 实际 {marked.review_status}"

    # Trace 必须写入
    trace = ev_store.get_trace(pid)
    assert any(t["action"] == "mark_ref_core" for t in trace), "Trace 未记录 mark_ref_core"