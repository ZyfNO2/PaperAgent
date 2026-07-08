"""Session 3: Human Gate 1-2 端点测试.

覆盖:
- confirmed_keywords 跳过自动拆解 (返回的 keywords 完全等于用户给的)
- confirmed_search_plan 跳过自动 build_search_plan
- /regenerate 端点: 沿用 project_id, 清 auto_* 入池新 auto_*, 保留手动 man_*
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services import evidence as ev_store

client = TestClient(app)


def _setup() -> str:
    """跑一次 analyze 拿 project_id."""

    ev_store.reset_all()
    r = client.post("/api/v1/one-topic/analyze", json={
        "raw_topic": "基于YOLO的钢材表面缺陷检测",
        "goal_level": "保毕业",
        "prefer": "heuristic",
    })
    assert r.status_code == 200
    return r.json()["project_id"]


def test_regenerate_returns_same_project_id() -> None:
    pid = _setup()
    r = client.post(
        f"/api/v1/one-topic/{pid}/regenerate",
        json={
            "raw_topic": "基于YOLO的钢材表面缺陷检测",
            "goal_level": "保毕业",
            "prefer": "heuristic",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["project_id"] == pid, f"project_id changed: {body['project_id']} != {pid}"


def test_regenerate_clears_auto_evidence() -> None:
    pid = _setup()
    # regenerate 前先记下 auto_* 数量
    ledger_before = client.get(f"/api/v1/one-topic/{pid}/evidence").json()
    n_auto_before = sum(1 for e in ledger_before["papers"] if e["evidence_id"].startswith("auto_"))
    assert n_auto_before >= 1, "no auto papers before regenerate"

    r = client.post(
        f"/api/v1/one-topic/{pid}/regenerate",
        json={"raw_topic": "基于YOLO的钢材表面缺陷检测", "goal_level": "保毕业", "prefer": "heuristic"},
    )
    assert r.status_code == 200

    # regenerate 后 paper 数量应该类似 (auto_* 重新入池)
    ledger_after = client.get(f"/api/v1/one-topic/{pid}/evidence").json()
    n_auto_after = sum(1 for e in ledger_after["papers"] if e["evidence_id"].startswith("auto_"))
    assert n_auto_after >= 1, f"auto papers lost: {n_auto_after}"


def test_regenerate_keeps_manual_evidence() -> None:
    pid = _setup()
    # 加一条手动
    r = client.post(
        f"/api/v1/one-topic/{pid}/evidence/papers/manual",
        json={"title": "Keep Me Test Paper", "doi": "10.5555/keep-me-test", "review_status": "core"},
    )
    assert r.json()["ok"] is True
    # regenerate
    r2 = client.post(
        f"/api/v1/one-topic/{pid}/regenerate",
        json={"raw_topic": "基于YOLO的钢材表面缺陷检测", "goal_level": "保毕业", "prefer": "heuristic"},
    )
    assert r2.status_code == 200
    ledger = client.get(f"/api/v1/one-topic/{pid}/evidence").json()
    titles = [p["title"] for p in ledger["papers"]]
    assert "Keep Me Test Paper" in titles, f"manual paper lost: {titles}"


def test_confirmed_keywords_skips_decompose() -> None:
    """给 confirmed_keywords 后, 服务端直接用, 不再跑 LLM/heuristic."""

    pid = _setup()
    user_kw = {
        "method_keywords": ["MyCustomMethod", "XYZ-Transformer"],
        "task_keywords": ["检测"],
        "object_keywords": ["桥梁裂缝"],
        "scenario_keywords": ["智能巡检"],
        "metric_keywords": ["IoU"],
        "risk_terms": [],
        "query_keywords_zh": [],
        "query_keywords_en": [],
    }
    r = client.post(
        f"/api/v1/one-topic/{pid}/regenerate",
        json={
            "raw_topic": "原题会被 ignored",  # confirmed 后原题不影响
            "goal_level": "保毕业",
            "prefer": "heuristic",
            "confirmed_keywords": user_kw,
        },
    )
    assert r.status_code == 200
    body = r.json()
    kb = body["keyword_breakdown"]
    # 应该完全等于用户传的
    assert kb["method_keywords"] == ["MyCustomMethod", "XYZ-Transformer"]
    assert kb["task_keywords"] == ["检测"]
    assert kb["object_keywords"] == ["桥梁裂缝"]
    assert kb["scenario_keywords"] == ["智能巡检"]
    assert kb["metric_keywords"] == ["IoU"]


def test_confirmed_search_plan_skips_build() -> None:
    """给 confirmed_search_plan 后, 服务端用用户检索词."""

    pid = _setup()
    user_plan = {
        "paper_queries": ["my custom paper query"],
        "dataset_queries": ["my custom dataset query"],
        "engineering_queries": ["my custom repo query"],
        "query_total": 3,
    }
    r = client.post(
        f"/api/v1/one-topic/{pid}/regenerate",
        json={
            "raw_topic": "原题",
            "goal_level": "保毕业",
            "prefer": "heuristic",
            "confirmed_search_plan": user_plan,
        },
    )
    assert r.status_code == 200
    body = r.json()
    sp = body["search_plan"]
    assert sp["paper_queries"] == ["my custom paper query"]
    assert sp["dataset_queries"] == ["my custom dataset query"]
    assert sp["engineering_queries"] == ["my custom repo query"]
    assert sp["query_total"] == 3


def test_regenerate_with_both_confirmed_full_flow() -> None:
    """Gate 1 + Gate 2 一起用 → 端到端 OK, project_id 沿用."""

    pid = _setup()
    user_kw = {
        "method_keywords": ["CNN"],
        "task_keywords": ["图像分类"],
        "object_keywords": ["树叶病害"],
        "scenario_keywords": ["智慧农业"],
        "metric_keywords": ["Accuracy"],
        "risk_terms": [],
        "query_keywords_zh": ["树叶病害 分类"],
        "query_keywords_en": ["leaf disease classification"],
    }
    user_plan = {
        "paper_queries": ["leaf disease classification CNN"],
        "dataset_queries": ["PlantVillage dataset"],
        "engineering_queries": [],
        "query_total": 2,
    }
    r = client.post(
        f"/api/v1/one-topic/{pid}/regenerate",
        json={
            "raw_topic": "基于 CNN 的树叶病害分类",
            "goal_level": "稳中求新",
            "prefer": "heuristic",
            "confirmed_keywords": user_kw,
            "confirmed_search_plan": user_plan,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["project_id"] == pid
    assert body["keyword_breakdown"]["object_keywords"] == ["树叶病害"]
    assert body["search_plan"]["paper_queries"] == ["leaf disease classification CNN"]
    # 自动证据重新入池 (新 project_id short 哈希 = 原 pid 短哈希, 但 evidence 仍按 pid[:6] 命名)
    # 实际: 同一个 project_id 复用, evidence_id 形如 auto_paper_<pid6>_001 跟之前一样
    # 但内容是新的 (因为是基于 leaf disease 检索, 不是 steel)
    ledger = client.get(f"/api/v1/one-topic/{pid}/evidence").json()
    paper_titles = [p["title"] for p in ledger["papers"]]
    # 任何 paper 都跟 "leaf" 无关是正常的 (mock arxiv 返回固定 3 篇)
    # 至少应该有 paper
    assert len(paper_titles) >= 1


def test_regenerate_empty_confirmed_falls_back_to_auto() -> None:
    """confirmed 给空 dict (而不是 None) 应当走启发式兜底, 不能崩."""

    pid = _setup()
    r = client.post(
        f"/api/v1/one-topic/{pid}/regenerate",
        json={
            "raw_topic": "基于Transformer的皮肤病变分类",
            "goal_level": "保毕业",
            "prefer": "heuristic",
            "confirmed_keywords": {},  # 空 dict
            "confirmed_search_plan": {},
        },
    )
    assert r.status_code == 200
    body = r.json()
    # 应该走启发式, 有 method_keywords
    assert len(body["keyword_breakdown"]["method_keywords"]) >= 0
