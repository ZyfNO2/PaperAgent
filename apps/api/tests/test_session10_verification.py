"""Session 10: 多源轻验证 + URL Verified 后端测试 (SOP §10.1).

覆盖 12 项 SOP 要求:
 1. arXiv URL 能提取 arxiv_id 并 verified/partial
 2. GitHub URL 能提取 owner/repo
 3. HuggingFace dataset URL 能识别 dataset
 4. Kaggle dataset URL 能识别 dataset
 5. 普通文本 note verification_status=skipped
 6. 批量 verify 返回 summary
 7. failed verification 不进入 supports
 8. assistant_intake + unverified 不进入 supports
 9. manual verification 能写入 Trace
10. verification_confidence 影响 EvidenceRef priority
11. Markdown citation list 显示验证状态
12. verification 不改变 review_status
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import evidence as ev_store
from app.services import evidence_refs as refs_service
from app.services import verification as ver_service
from app.schemas_evidence import (
    EvidenceItem,
    PaperManualCreate,
    VerificationResult,
    VerificationStatus,
)


@pytest.fixture(autouse=True)
def _reset_store():
    """每个测试前清空 evidence store, 避免跨测试污染."""

    ev_store.reset_all()
    ev_store.clear_trace("dummy")
    yield
    ev_store.reset_all()


@pytest.fixture
def client():
    return TestClient(app)


def _analyze(client, topic: str = "YOLO 钢材表面缺陷检测") -> str:
    r = client.post("/api/v1/one-topic/analyze", json={"raw_topic": topic, "prefer": "heuristic"})
    assert r.status_code == 200
    return r.json()["project_id"]


# ---------- 1: arXiv URL 识别 ---------- #


def test_01_arxiv_url_extraction_and_verification(client):
    """§10.1.1: arXiv URL 能提取 arxiv_id 并产生 verified/partial/failed."""

    parsed = ver_service.parse_url("https://arxiv.org/abs/2106.09685")
    assert parsed["platform"] == "arxiv"
    assert parsed["arxiv_id"] == "2106.09685"

    item = EvidenceItem(
        evidence_id="test_arxiv_1",
        project_id="ot_test",
        evidence_type="paper",
        source_mode="manual",
        title="YOLOv4 Paper",
        url="https://arxiv.org/abs/2106.09685",
        arxiv_id="2106.09685",
        review_status="accepted",
    )
    result = ver_service.verify_evidence_item(item, refresh=True)
    assert result.evidence_id == "test_arxiv_1"
    assert result.verification_source == "arxiv"
    assert result.verification_status in ("verified", "partial")
    assert 0 <= result.verification_confidence <= 1
    # failed 分支: 完全无效的 arxiv_id
    item_bad = EvidenceItem(
        evidence_id="test_arxiv_bad",
        project_id="ot_test",
        evidence_type="paper",
        source_mode="manual",
        title="bad",
        url="not_a_url",
        review_status="accepted",
    )
    bad = ver_service.verify_evidence_item(item_bad, refresh=True)
    # 无 url 的 paper 走 metadata 分支, 不应 failed
    assert bad.verification_status != "failed" or "arxiv_id" in (bad.warnings[0] if bad.warnings else "")


# ---------- 2: GitHub URL 识别 ---------- #


def test_02_github_url_owner_repo(client):
    """§10.1.2: GitHub URL 能提取 owner/repo."""

    parsed = ver_service.parse_url("https://github.com/ultralytics/ultralytics")
    assert parsed["platform"] == "github"
    assert parsed["owner"] == "ultralytics"
    assert parsed["repo"] == "ultralytics"

    # 解析失败的情况
    parsed_bad = ver_service.parse_url("https://github.com/ultralytics")
    assert parsed_bad["platform"] == "generic" or parsed_bad["repo"] is None


# ---------- 3: HuggingFace dataset URL 识别 ---------- #


def test_03_huggingface_dataset_url(client):
    """§10.1.3: HF dataset URL 能识别."""

    parsed = ver_service.parse_url("https://huggingface.co/datasets/imagenet-1k")
    assert parsed["platform"] == "huggingface_dataset"
    assert parsed["dataset_slug"] == "imagenet-1k"


# ---------- 4: Kaggle dataset URL 识别 ---------- #


def test_04_kaggle_dataset_url(client):
    """§10.1.4: Kaggle dataset URL 能识别."""

    parsed = ver_service.parse_url("https://www.kaggle.com/datasets/uciml/iris")
    assert parsed["platform"] == "kaggle_dataset"
    assert "iris" in (parsed["dataset_slug"] or "")

    parsed_comp = ver_service.parse_url("https://www.kaggle.com/competitions/titanic")
    assert parsed_comp["platform"] == "kaggle_dataset"
    assert "titanic" in (parsed_comp["dataset_slug"] or "")


# ---------- 5: 纯文本 note → skipped ---------- #


def test_05_text_note_skipped(client):
    """§10.1.5: 普通文本 note verification_status=skipped."""

    note = EvidenceItem(
        evidence_id="test_note_1",
        project_id="ot_test",
        evidence_type="note",
        source_mode="manual",
        title="导师说了一句话",
        review_status="pending",
    )
    result = ver_service.verify_evidence_item(note, refresh=True)
    assert result.verification_status == "skipped"
    assert result.verification_source == "none"


# ---------- 6: 批量 verify 返回 summary ---------- #


def test_06_batch_verify_returns_summary(client):
    """§10.1.6: 批量 verify 返回 summary."""

    pid = _analyze(client)

    # 手动加一个 GitHub repo evidence
    repo_body = {
        "name": "ultralytics/ultralytics",
        "repository_url": "https://github.com/ultralytics/ultralytics",
        "has_readme": True,
        "has_env_file": True,
        "has_training_script": True,
        "has_eval_script": True,
    }
    r = client.post(f"/api/v1/one-topic/{pid}/evidence/repos/manual", json=repo_body)
    assert r.status_code == 200, r.text

    # 加一个 arxiv paper
    paper_body = {
        "title": "YOLOv4 Paper",
        "url": "https://arxiv.org/abs/2106.09685",
        "arxiv_id": "2106.09685",
        "year": 2021,
    }
    r = client.post(f"/api/v1/one-topic/{pid}/evidence/papers/manual", json=paper_body)
    assert r.status_code == 200, r.text

    # 批量 verify
    r = client.post(f"/api/v1/one-topic/{pid}/evidence/verify", json={"scope": "all"})
    assert r.status_code == 200, r.text
    summary = r.json()
    assert summary["project_id"] == pid
    assert summary["total"] >= 1
    assert "verified" in summary and "partial" in summary
    assert "failed" in summary and "skipped" in summary


# ---------- 7: failed verification 不进入 supports ---------- #


def test_07_failed_not_in_supports(client):
    """§10.1.7: verification_status=failed 不进入 supports (SOP §7.1 硬规则)."""

    item = EvidenceItem(
        evidence_id="test_failed_1",
        project_id="ot_test",
        evidence_type="paper",
        source_mode="manual",
        title="Fake",
        url="https://arxiv.org/abs/INVALID",
        arxiv_id="INVALID_ID_FORMAT",
        review_status="accepted",
    )
    role = refs_service._select_role(
        item.review_status, 0.7, "paper", "system_found",
        item.source_mode, "failed",
    )
    assert role in ("warns", "alternative"), f"failed 不应 supports, got {role}"


# ---------- 8: assistant_intake + unverified 不进入 supports ---------- #


def test_08_assistant_intake_unverified_not_in_supports(client):
    """§10.1.8: assistant_intake + unverified 不进入 supports (SOP §7.1 硬规则)."""

    role_unverified = refs_service._select_role(
        "accepted", 0.7, "repo", "system_found", "assistant_intake", "unverified",
    )
    assert role_unverified in ("warns", "background"), f"got {role_unverified}"

    role_partial = refs_service._select_role(
        "accepted", 0.7, "repo", "system_found", "assistant_intake", "partial",
    )
    # partial 可以 supports (但会带 warning)
    assert role_partial == "supports"


# ---------- 9: manual verification 写入 Trace ---------- #


def test_09_manual_verification_writes_trace(client):
    """§10.1.9: manual verification 能写入 Trace."""

    pid = _analyze(client)
    repo_body = {
        "name": "owner/repo",
        "repository_url": "https://github.com/owner/repo",
        "has_readme": True,
    }
    r = client.post(f"/api/v1/one-topic/{pid}/evidence/repos/manual", json=repo_body)
    assert r.status_code == 200
    eid = r.json()["evidence_id"]

    # 手动确认
    r = client.patch(
        f"/api/v1/one-topic/{pid}/evidence/{eid}/verification",
        json={
            "verification_status": "verified",
            "verification_source": "manual",
            "verification_confidence": 0.90,
            "reason": "用户已打开网页确认可访问",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["verification_status"] == "verified"
    assert body["verification_source"] == "manual"
    assert body["verification_confidence"] == 0.90

    # 检查 Trace
    trace = ev_store.get_trace(pid)
    actions = [t["action"] for t in trace]
    assert "manual_verification" in actions


# ---------- 10: verification_confidence 影响 EvidenceRef priority ---------- #


def test_10_verification_confidence_affects_priority(client):
    """§10.1.10: verification_confidence 影响 EvidenceRef priority."""

    base_item = {
        "review_status": "accepted",
        "relevance_score": 0.7,
        "paper_type": "baseline_method",
        "workspace_lane": "system_found",
        "evidence_type": "paper",
    }
    p_unverified = refs_service._ref_priority({**base_item, "verification_status": "unverified"})
    p_verified = refs_service._ref_priority({**base_item, "verification_status": "verified", "verification_confidence": 0.9})
    p_partial = refs_service._ref_priority({**base_item, "verification_status": "partial", "verification_confidence": 0.6})
    assert p_verified > p_unverified, f"verified ({p_verified}) 应高于 unverified ({p_unverified})"
    assert p_partial > p_unverified, f"partial ({p_partial}) 应高于 unverified ({p_unverified})"


# ---------- 11: Markdown citation list 显示验证状态 ---------- #


def test_11_markdown_citation_shows_verification(client):
    """§10.1.11: Markdown 证据引用清单显示验证状态."""

    pid = _analyze(client)

    # 加 paper + 验证
    r = client.post(f"/api/v1/one-topic/{pid}/evidence/papers/manual", json={
        "title": "arxiv paper",
        "url": "https://arxiv.org/abs/2106.09685",
        "arxiv_id": "2106.09685",
    })
    assert r.status_code == 200
    eid = r.json()["evidence_id"]

    # 手动标 verified
    r = client.patch(
        f"/api/v1/one-topic/{pid}/evidence/{eid}/verification",
        json={"verification_status": "verified", "verification_source": "manual",
              "verification_confidence": 0.85, "reason": "ok"},
    )
    assert r.status_code == 200

    # rebuild refs + build final package
    r = client.post(f"/api/v1/one-topic/{pid}/evidence/refs/rebuild")
    assert r.status_code == 200

    r = client.post(f"/api/v1/one-topic/{pid}/final-package/build", json={})
    assert r.status_code == 200, r.text
    pkg = r.json()
    md = pkg["proposal_markdown"]
    # 应包含验证率行
    assert "证据验证率" in md
    # citation 列表应包含 验证 列
    assert "| 验证 |" in md
    assert "verified" in md.lower()


# ---------- 12: verification 不改变 review_status ---------- #


def test_12_verification_does_not_change_review_status(client):
    """§10.1.12: verification 不改变 review_status."""

    pid = _analyze(client)
    r = client.post(f"/api/v1/one-topic/{pid}/evidence/papers/manual", json={
        "title": "paper",
        "url": "https://arxiv.org/abs/2106.09685",
        "arxiv_id": "2106.09685",
        "review_status": "core",
    })
    assert r.status_code == 200
    eid = r.json()["evidence_id"]

    # 验证
    r = client.post(f"/api/v1/one-topic/{pid}/evidence/{eid}/verify")
    assert r.status_code == 200
    new_ev = r.json()

    # review_status 应保持 core
    assert new_ev["verification_status"] in ("verified", "partial", "failed")
    assert new_ev.get("url_verified") is not None

    # 查 ledger
    item = ev_store.get_item(eid)
    assert item.review_status == "core", f"verification 不应改 review_status, got {item.review_status}"


# ---------- 额外: 验证摘要端点 ---------- #


def test_13_verification_summary_endpoint(client):
    """Session 10 §6.3: GET /verification-summary 返回 summary."""

    pid = _analyze(client)
    # 空 evidence 也应能调 (但是 409)
    r = client.get(f"/api/v1/one-topic/{pid}/evidence/verification-summary")
    assert r.status_code == 200 or r.status_code == 409

    # 加一个 evidence
    r = client.post(f"/api/v1/one-topic/{pid}/evidence/papers/manual", json={
        "title": "p1", "url": "https://arxiv.org/abs/2106.09685",
    })
    assert r.status_code == 200

    r = client.get(f"/api/v1/one-topic/{pid}/evidence/verification-summary")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["project_id"] == pid
    assert body["total"] >= 1


# ---------- 额外: 验证结果写回 evidence ledger ---------- #


def test_14_verify_updates_ledger(client):
    """单条 verify 写回 evidence ledger, verification_status 持久化."""

    pid = _analyze(client)
    r = client.post(f"/api/v1/one-topic/{pid}/evidence/repos/manual", json={
        "name": "owner/repo",
        "repository_url": "https://github.com/owner/repo",
    })
    eid = r.json()["evidence_id"]

    r = client.post(f"/api/v1/one-topic/{pid}/evidence/{eid}/verify")
    assert r.status_code == 200

    # 从 ledger 重新拉
    item = ev_store.get_item(eid)
    assert item.verification_status in ("verified", "partial", "failed")
    assert item.verification_checked_at is not None
    # github 验证应给 owner/repo metadata
    if item.verification_source == "github":
        meta = item.verification_metadata
        assert meta.get("owner") == "owner"
        assert meta.get("repo") == "repo"


# ---------- 额外: filter by scope ---------- #


def test_15_batch_scope_filter(client):
    """批量 verify 可按 scope 过滤.

    auto_* evidence (paper/dataset/repo) 在 _filter_by_scope 中按 evidence_type 过滤.
    paper scope 应该只返回 paper 类型证据数.
    """

    pid = _analyze(client)

    # 在 analyze 之后, paper scope 应过滤 auto_paper_*
    r = client.post(f"/api/v1/one-topic/{pid}/evidence/verify", json={"scope": "paper"})
    assert r.status_code == 200
    body = r.json()
    pool = ev_store.get_pool_items(pid)
    expected_papers = sum(1 for it in pool if it.evidence_type == "paper")
    assert body["total"] == expected_papers, (
        f"scope=paper 应只验证 paper, got total={body['total']}, expected={expected_papers}"
    )

    # repo scope
    r = client.post(f"/api/v1/one-topic/{pid}/evidence/verify", json={"scope": "repo"})
    assert r.status_code == 200
    body_repo = r.json()
    expected_repos = sum(1 for it in pool if it.evidence_type == "repo")
    assert body_repo["total"] == expected_repos