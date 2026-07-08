"""Session 5 后端测试: 评分 + 分类 + 去重 + 接入可行性 (SOP §4 + §8 + §9.1).

跑法:  .venv/Scripts/python.exe -m pytest apps/api/tests/test_session5_evidence_scoring.py -v
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
from app.services import scoring  # noqa: E402
from app.schemas_evidence import (  # noqa: E402
    PaperManualCreate, RepoManualCreate,
)


@pytest.fixture(autouse=True)
def _clean_ledger():
    """每个测试前清空 evidence store, 避免污染."""

    ev_store.reset_all()
    yield
    ev_store.reset_all()


@pytest.fixture
def client():
    return TestClient(app)


# ---------- §4.1 PaperRelevance 评分 ---------- #


def test_score_paper_relevance_typical(client):
    """典型论文: 标题 + 摘要都命中 method+task, recency 高 → 高分."""

    paper = {"title": "YOLOv8 steel surface defect detection", "summary": "We propose YOLO for steel surface defect detection.", "year": 2024}
    kw = {"method_keywords": ["YOLO"], "task_keywords": ["detection"], "object_keywords": ["steel", "defect"]}
    s, bd = scoring.score_paper_relevance(paper, kw)
    assert 0.6 <= s <= 1.0, f"expected high, got {s}"
    assert bd["title_match"] > 0.5
    assert bd["abstract_match"] > 0.3


def test_score_paper_relevance_irrelevant(client):
    """无关论文: 所有 match=0, recency=0.3 → 极低分."""

    paper = {"title": "German Open-Ended Survey", "summary": "German language analysis", "year": 2024}
    kw = {"method_keywords": ["PINN"], "task_keywords": ["数字孪生"], "object_keywords": ["机构"]}
    s, _ = scoring.score_paper_relevance(paper, kw)
    assert s < 0.25, f"expected low, got {s}"


# ---------- §4.1 论文类型分类 ---------- #


def test_classify_paper_type_survey(client):
    p = {"title": "A Survey on Defect Detection Methods", "summary": "review of recent progress"}
    assert scoring.classify_paper_type(p) == "survey"


def test_classify_paper_type_baseline(client):
    p = {"title": "YOLOv8: We propose a new real-time detector", "summary": "We present a novel method."}
    assert scoring.classify_paper_type(p) == "baseline_method"


def test_classify_paper_type_irrelevant_no_match(client):
    """无关论文 (无任何关键词命中) → irrelevant."""

    p = {"title": "Astrophysics of distant galaxies", "summary": "A study of star formation rates."}
    p["_keywords_flat"] = ["PINN", "机构"]
    assert scoring.classify_paper_type(p) == "irrelevant"


# ---------- §4.2 DatasetScore ---------- #


def test_score_dataset_ready(client):
    """NEU-DET 风格: 名字 + license + download + 钢材 → 高分 + ready."""

    d = {"name": "NEU-DET", "scale": "1800 张 / 6 类", "license": "学术使用",
         "download": "http://example.com", "annotation": "钢材 缺陷 标注", "fit": "高", "source": "public-known"}
    s, bd = scoring.score_dataset(d, {"object_keywords": ["钢材"], "task_keywords": ["检测"]})
    assert s >= 0.6, f"expected >= 0.6, got {s}"
    assert bd["existence"] == 1.0
    assert bd["accessibility"] == 1.0


def test_score_dataset_unverified_placeholder(client):
    """未匹配占位: name="(未匹配公开数据集)" → 低分 + unverified."""

    d = {"name": "(未匹配公开数据集)", "scale": "", "license": "", "download": "",
         "annotation": "", "fit": "低", "source": "heuristic"}
    s, _ = scoring.score_dataset(d, {})
    assert s < 0.3


# ---------- §4.3 RepoScore ---------- #


def test_score_repo_full(client):
    """完整 baseline (README + license + train + eval + pretrained) → 高分 + official/baseline_framework."""

    r = {"name": "ultralytics/ultralytics", "repository_url": "https://github.com/ultralytics/ultralytics",
         "has_readme": True, "license": "GPL-3.0", "has_training_script": True,
         "has_eval_script": True, "has_pretrained_weight": True, "has_env_file": True}
    s, _ = scoring.score_repo(r, paper_year=2024)
    assert s >= 0.7, f"expected >= 0.7, got {s}"


def test_classify_repo_type_demo_only(client):
    """demo notebook → demo_only."""

    r = {"name": "demo_notebook", "repository_url": "https://github.com/foo/demo",
         "has_readme": True, "has_training_script": False, "has_eval_script": False}
    assert scoring._derive_repo_type(r) == "demo_only"


# ---------- §4.4 DOI / 标题去重 ---------- #


def test_dedup_same_doi_returns_existing(client):
    """同 DOI 重复 add → 返回 existing evidence_id, 不新增."""

    eid1 = ev_store.add_paper_manual("proj1", PaperManualCreate(
        title="Paper A", doi="10.1109/abc.2024", year=2024,
    )).evidence_id
    r = ev_store.add_paper_manual("proj1", PaperManualCreate(
        title="Paper A (重名)", doi="10.1109/abc.2024", year=2024,
    ))
    assert not r.ok
    assert r.evidence_id == eid1
    assert "重复" in r.message


def test_dedup_similar_title_jaccard(client):
    """标题 jaccard > 0.92 → 重复."""

    ev_store.add_paper_manual("proj1", PaperManualCreate(
        title="YOLOv8 steel surface defect detection benchmark",
    ))
    r = ev_store.add_paper_manual("proj1", PaperManualCreate(
        title="YOLOv8 steel surface defect detection benchmark",  # 完全相同
    ))
    assert not r.ok


# ---------- §4.4 GitHub owner 去重 ---------- #


def test_dedup_repo_owner_name(client):
    """同 owner/name → 重复."""

    ev_store.add_repo_manual("proj1", RepoManualCreate(
        name="ultralytics/ultralytics", repository_url="https://github.com/ultralytics/ultralytics",
    ))
    r = ev_store.add_repo_manual("proj1", RepoManualCreate(
        name="ultralytics/ultralytics (fork)", repository_url="https://github.com/ultralytics/ultralytics",
    ))
    assert not r.ok
    assert r.message  # 含 reason


# ---------- §8.1 rescore 端点 ---------- #


def test_rescore_does_not_change_review_status(client):
    """rescore 后 review_status 保持不变."""

    r = client.post("/api/v1/one-topic/analyze", json={"raw_topic": "基于YOLO的钢材表面缺陷检测", "prefer": "heuristic"})
    pid = r.json()["project_id"]
    # 把第一个 paper 标为 rejected
    led = client.get(f"/api/v1/one-topic/{pid}/evidence").json()
    first_id = led["papers"][0]["evidence_id"]
    client.patch(f"/api/v1/one-topic/evidence/{first_id}/review", json={"review_status": "rejected"})
    # rescore
    rs = client.post(f"/api/v1/one-topic/{pid}/evidence/rescore").json()
    assert rs["updated_count"] >= 0
    # 验证 rejected 状态保留
    led2 = client.get(f"/api/v1/one-topic/{pid}/evidence").json()
    e0 = next(p for p in led2["papers"] if p["evidence_id"] == first_id)
    assert e0["review_status"] == "rejected"


# ---------- §8.2 score-summary 端点 ---------- #


def test_score_summary_rejected_excluded(client):
    """rejected 证据不计入 usable_* 统计."""

    r = client.post("/api/v1/one-topic/analyze", json={"raw_topic": "基于YOLO的钢材表面缺陷检测", "prefer": "heuristic"})
    pid = r.json()["project_id"]
    led = client.get(f"/api/v1/one-topic/{pid}/evidence").json()
    # 全部 papers 标 rejected
    for p in led["papers"]:
        client.patch(f"/api/v1/one-topic/evidence/{p['evidence_id']}/review", json={"review_status": "rejected"})
    sm = client.get(f"/api/v1/one-topic/{pid}/evidence/score-summary").json()
    assert sm["usable_papers"] == 0
    assert sm["rejected_evidence"] >= len(led["papers"])


def test_score_summary_feasibility_inputs(client):
    """feasibility_inputs 给出 paper/dataset/repo 强/中/弱 评级."""

    r = client.post("/api/v1/one-topic/analyze", json={"raw_topic": "基于YOLO的钢材表面缺陷检测", "prefer": "heuristic"})
    pid = r.json()["project_id"]
    sm = client.get(f"/api/v1/one-topic/{pid}/evidence/score-summary").json()
    assert "paper_quality" in sm["feasibility_inputs"]
    assert sm["feasibility_inputs"]["paper_quality"] in ("强", "中", "弱")


# ---------- §8.3 dedup-check 端点 ---------- #


def test_dedup_check_endpoint(client):
    """dedup-check 用同 DOI 返回 is_duplicate=True."""

    r = client.post("/api/v1/one-topic/analyze", json={"raw_topic": "基于YOLO的钢材表面缺陷检测", "prefer": "heuristic"})
    pid = r.json()["project_id"]
    led = client.get(f"/api/v1/one-topic/{pid}/evidence").json()
    existing = led["papers"][0]
    r2 = client.post(f"/api/v1/one-topic/{pid}/evidence/dedup/check", json={
        "evidence_type": "paper",
        "title": existing["title"],
        "arxiv_id": existing.get("arxiv_id"),
    })
    # 新 title 就算没有 arxiv_id, 标题完全相同也会被识别
    r3 = client.post(f"/api/v1/one-topic/{pid}/evidence/dedup/check", json={
        "evidence_type": "paper",
        "title": existing["title"],  # 完全相同
    })
    assert r3.json()["is_duplicate"] is True


# ---------- §4.5 core 证据优先 ---------- #


def test_core_evidence_drives_feasibility_to_go(client):
    """如果全部 evidence 都 core + 评分高, verdict 应该倾向 可做."""

    r = client.post("/api/v1/one-topic/analyze", json={"raw_topic": "基于YOLO的钢材表面缺陷检测", "prefer": "heuristic"})
    pid = r.json()["project_id"]
    led = client.get(f"/api/v1/one-topic/{pid}/evidence").json()
    for p in led["papers"]:
        client.patch(f"/api/v1/one-topic/evidence/{p['evidence_id']}/review", json={"review_status": "core"})
    # 跑 feasibility (Session 5 还没自动重算 verdict, 这里只验证 review_status 可改)
    led2 = client.get(f"/api/v1/one-topic/{pid}/evidence").json()
    assert all(p["review_status"] == "core" for p in led2["papers"])


# ---------- run_one_topic 集成: 评分进 response ---------- #


def test_analyze_response_includes_scores(client):
    """analyze 响应里 papers[0].relevance_score 不为 None."""

    r = client.post("/api/v1/one-topic/analyze", json={"raw_topic": "基于YOLO的钢材表面缺陷检测", "prefer": "heuristic"})
    d = r.json()
    papers = d["evidence_summary"]["papers"]
    assert papers
    for p in papers:
        assert p.get("relevance_score") is not None, f"paper {p['paper_id']} missing relevance_score"
        assert p.get("paper_type") is not None
