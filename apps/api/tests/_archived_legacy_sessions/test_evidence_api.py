"""Evidence API 测试 (Session 1).

覆盖:
- 跑一次 analyze, 看 response.project_id 非空, evidence 池有自动入池
- 手动添加论文 / 数据集 / repo
- dedup: 同 DOI 第二次返回 ok=False + 指向已存在
- PATCH review: 接受 / 拒绝 / 核心
- DELETE: 删除一条
- 多次手动添加后 summary 计数对
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services import evidence as ev_store

client = TestClient(app)


def _setup() -> str:
    """跑一次 analyze 拿 project_id (会触发 auto-ingest)."""

    ev_store.reset_all()
    r = client.post("/api/v1/one-topic/analyze", json={
        "raw_topic": "基于YOLO的钢材表面缺陷检测",
        "goal_level": "保毕业",
        "prefer": "heuristic",
    })
    assert r.status_code == 200, r.text
    pid = r.json().get("project_id", "")
    assert pid, f"project_id missing: {r.json().keys()}"
    return pid


def test_analyze_returns_project_id() -> None:
    pid = _setup()
    assert pid.startswith("ot_")
    assert len(pid) > 10


def test_auto_ingest_after_analyze() -> None:
    pid = _setup()
    r = client.get(f"/api/v1/one-topic/{pid}/evidence")
    assert r.status_code == 200
    body = r.json()
    assert body["project_id"] == pid
    # 自动检索的 papers + datasets + repos 都进池
    assert body["paper_count"] >= 1, f"no auto papers: {body}"
    assert body["dataset_count"] >= 1, f"no auto datasets: {body}"
    # 自动入池默认 review_status=pending
    for p in body["papers"]:
        assert p["source_mode"] == "auto_search"
        assert p["review_status"] in ("pending", "accepted")


def test_manual_add_paper() -> None:
    pid = _setup()
    r = client.post(
        f"/api/v1/one-topic/{pid}/evidence/papers/manual",
        json={
            "title": "Lightweight YOLOv8 for Steel Defect Detection",
            "authors": ["He, X.", "Wang, Y."],
            "year": 2024,
            "url": "https://example.com/paper.pdf",
            "doi": "10.1234/lightweight-yolov8-steel",
            "abstract": "We propose a lightweight YOLOv8 variant.",
            "user_note": "导师给的",
            "tags": ["advisor-given", "core"],
            "review_status": "core",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["evidence"]["source_mode"] == "manual"
    assert body["evidence"]["review_status"] == "core"
    assert body["evidence"]["doi"] == "10.1234/lightweight-yolov8-steel"
    assert body["ledger_summary"]["paper_count"] >= 2
    assert body["ledger_summary"]["core_count"] >= 1


def test_dedup_by_doi() -> None:
    """同 DOI 第二次添加应返回 ok=False + 指向已存在的 evidence_id."""

    pid = _setup()
    body = {
        "title": "Some Paper With DOI",
        "doi": "10.5555/unique-doi-1",
        "review_status": "pending",
    }
    r1 = client.post(f"/api/v1/one-topic/{pid}/evidence/papers/manual", json=body)
    assert r1.json()["ok"] is True
    eid1 = r1.json()["evidence_id"]

    r2 = client.post(f"/api/v1/one-topic/{pid}/evidence/papers/manual", json=body)
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["ok"] is False
    assert body2["evidence_id"] == eid1
    assert "重复" in body2["message"]


def test_dedup_by_title() -> None:
    """同标题 (大小写/标点差异) 应被 dedup."""

    pid = _setup()
    base = {
        "title": "YOLOv8 Steel Defect Survey",
        "review_status": "pending",
    }
    r1 = client.post(f"/api/v1/one-topic/{pid}/evidence/papers/manual", json=base)
    assert r1.json()["ok"] is True

    variant = {"title": "yolov8-steel-defect-survey", "review_status": "pending"}  # jaccard > 0.92
    r2 = client.post(f"/api/v1/one-topic/{pid}/evidence/papers/manual", json=variant)
    assert r2.json()["ok"] is False


def test_manual_add_dataset_and_repo() -> None:
    pid = _setup()
    # 数据集
    r1 = client.post(
        f"/api/v1/one-topic/{pid}/evidence/datasets/manual",
        json={
            "name": "Severstal Steel Defect",
            "scale": "12000 张",
            "license": "CC BY-NC-SA",
            "download": "https://www.kaggle.com/c/severstal-steel-defect-detection",
            "modality": ["image"],
            "annotation": "pixel-level mask",
            "user_note": "Kaggle 公开",
        },
    )
    assert r1.json()["ok"] is True
    assert r1.json()["evidence"]["source_mode"] == "manual"
    assert r1.json()["evidence"]["evidence_type"] == "dataset"
    # Repo
    r2 = client.post(
        f"/api/v1/one-topic/{pid}/evidence/repos/manual",
        json={
            "name": "YOLOv8 Fork (Steel)",
            "repository_url": "https://github.com/example/yolov8-steel",
            "paper_title": "Lightweight YOLOv8 for Steel Defect Detection",
            "license": "MIT",
            "has_readme": True,
            "has_env_file": True,
            "has_training_script": True,
            "has_eval_script": True,
        },
    )
    assert r2.json()["ok"] is True
    # 池里既有自动又有手动
    ledger = client.get(f"/api/v1/one-topic/{pid}/evidence").json()
    assert ledger["dataset_count"] >= 2  # 自动 + 手动
    assert ledger["repo_count"] >= 2


def test_patch_review() -> None:
    pid = _setup()
    # 拿一条自动入池的 paper
    ledger = client.get(f"/api/v1/one-topic/{pid}/evidence").json()
    assert ledger["papers"], "no papers to patch"
    eid = ledger["papers"][0]["evidence_id"]
    # 接受
    r = client.patch(
        f"/api/v1/one-topic/evidence/{eid}/review",
        json={"review_status": "accepted", "user_note": "approved by user"},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["evidence"]["review_status"] == "accepted"
    assert r.json()["evidence"]["user_note"] == "approved by user"
    # summary 计数更新
    assert r.json()["ledger_summary"]["accepted_count"] >= 1


def test_patch_review_reject() -> None:
    pid = _setup()
    ledger = client.get(f"/api/v1/one-topic/{pid}/evidence").json()
    eid = ledger["papers"][0]["evidence_id"]
    r = client.patch(
        f"/api/v1/one-topic/evidence/{eid}/review",
        json={"review_status": "rejected"},
    )
    assert r.json()["ok"] is True
    assert r.json()["ledger_summary"]["rejected_count"] >= 1


def test_delete_evidence() -> None:
    pid = _setup()
    ledger_before = client.get(f"/api/v1/one-topic/{pid}/evidence").json()
    n_before = ledger_before["paper_count"]
    eid = ledger_before["papers"][0]["evidence_id"]
    r = client.delete(f"/api/v1/one-topic/evidence/{eid}")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    ledger_after = client.get(f"/api/v1/one-topic/{pid}/evidence").json()
    assert ledger_after["paper_count"] == n_before - 1


def test_patch_nonexistent_evidence() -> None:
    r = client.patch(
        "/api/v1/one-topic/evidence/nonexistent_xxx/review",
        json={"review_status": "accepted"},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is False
    assert "不存在" in r.json()["message"]


def test_existing_one_topic_tests_still_pass() -> None:
    """回归: 老的 OneTopic 端点不变 (response 加了 project_id 字段不应破坏)."""

    r = client.post("/api/v1/one-topic/analyze", json={
        "raw_topic": "基于Transformer的皮肤病变分类",
        "goal_level": "保毕业",
        "prefer": "heuristic",
    })
    assert r.status_code == 200
    body = r.json()
    for k in ("topic_understanding", "keyword_breakdown", "search_plan",
              "evidence_summary", "feasibility", "proposal_recommendation", "light_review"):
        assert k in body
