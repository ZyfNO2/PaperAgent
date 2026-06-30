"""OneTopic API 端点测试.

不依赖 LLM, 不依赖 arXiv 网络 — 都用 heuristic/heuristic 占位, 跑通验收.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"


def test_analyze_yolo_steel_happy_path() -> None:
    """示例题目 1: YOLO 钢材 (应有真实启发式拆解 + 公开数据集命中).

    Session 65 T7: 未选 baseline 时 work_packages 应为空, 但推荐理由里应说明.
    """

    r = client.post("/api/v1/one-topic/analyze", json={
        "raw_topic": "基于YOLO的钢材表面缺陷检测",
        "goal_level": "保毕业",
        "prefer": "heuristic",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    # 6 段产物齐
    for k in ("topic_understanding", "keyword_breakdown", "search_plan",
              "evidence_summary", "feasibility", "proposal_recommendation",
              "light_review"):
        assert k in body, f"missing {k}"
    # 关键词
    kb = body["keyword_breakdown"]
    assert "YOLO" in kb["method_keywords"] or any("YOLO" in m for m in kb["method_keywords"])
    assert any("钢" in o for o in kb["object_keywords"])
    # 证据
    ev = body["evidence_summary"]
    assert ev["paper_count"] >= 1
    assert ev["dataset_count"] >= 1
    # NEU-DET / GC10-DET 至少一个
    dataset_names = " ".join(d["name"] for d in ev["datasets"])
    assert ("NEU-DET" in dataset_names) or ("GC10-DET" in dataset_names)
    # 可行性
    feas = body["feasibility"]
    assert feas["verdict"] in ("可做", "收缩后可做", "暂缓", "不建议")
    # 推荐
    rec = body["proposal_recommendation"]
    assert "钢材" in rec["recommended_topic"] or "YOLO" in rec["recommended_topic"]
    # Session 65 T7: 没选 baseline → work_packages 应为空, 推荐理由应提示先选 baseline
    assert rec["work_packages"] == [], "未选 baseline 时不应生成工作包"
    assert any("请先从候选论文" in r for r in rec["recommendation_reason"]), (
        "未选 baseline 时推荐理由应提示用户先选 baseline"
    )
    # 审核
    rev = body["light_review"]
    assert rev["verdict"] in ("通过", "有条件通过", "需修改", "不建议")
    assert len(rev["checks"]) == 5


def test_analyze_niche_topic_triggers_shrink_or_pause() -> None:
    """示例题目 2: 极小众对象 — 应进入"暂缓/收缩后可做/不建议"."""

    r = client.post("/api/v1/one-topic/analyze", json={
        "raw_topic": "基于XXX的极小众对象检测",
        "goal_level": "保毕业",
        "prefer": "heuristic",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    feas = body["feasibility"]
    # 小众 + 无公开数据 → 暂缓 / 收缩后可做 / 可转向 / 不建议 (5 档 Session 4)
    assert feas["verdict"] in ("暂缓", "收缩后可做", "可转向", "不建议")
    # 缺证据项里应包含数据集
    assert any("数据集" in m for m in feas["missing_evidence"])


def test_analyze_pcb_bridge_skin_match_known_datasets() -> None:
    """示例题目 3-5: 几个特殊对象的公开数据集命中."""

    for topic, expected in [
        ("基于深度学习的PCB缺陷检测方法研究", "DeepPCB"),
        ("基于YOLO的桥梁裂缝检测", "CODEBRIM"),
        ("基于CNN的皮肤病变分类", "HAM10000"),
    ]:
        r = client.post("/api/v1/one-topic/analyze", json={
            "raw_topic": topic, "goal_level": "保毕业", "prefer": "heuristic",
        })
        assert r.status_code == 200, r.text
        ev = r.json()["evidence_summary"]
        names = " ".join(d["name"] for d in ev["datasets"])
        assert expected in names, f"topic={topic} expected={expected} got datasets={names}"


def test_request_validation() -> None:
    """空 raw_topic 必拒绝."""

    r = client.post("/api/v1/one-topic/analyze", json={
        "raw_topic": "",
        "goal_level": "保毕业",
    })
    assert r.status_code == 422


def test_stream_endpoint_emits_expected_events() -> None:
    """SSE 流式端点: 至少包含 start / step / result / end."""

    with client.stream("POST", "/api/v1/one-topic/analyze/stream", json={
        "raw_topic": "基于YOLO的钢材表面缺陷检测",
        "goal_level": "保毕业",
        "prefer": "heuristic",
    }) as r:
        assert r.status_code == 200
        seen: list[str] = []
        for line in r.iter_lines():
            if not line or not line.startswith("data: "):
                continue
            try:
                import json as _json
                ev = _json.loads(line[6:])
            except Exception:
                continue
            seen.append(ev.get("type", ""))
        # 至少要有 start, step, result, end
        for t in ("start", "step", "result", "end"):
            assert t in seen, f"missing event type {t}, got {seen}"


def test_keyword_breakdown_always_has_query_keywords() -> None:
    """任何题目都必须能生成中英检索词 (heuristic 兜底)."""

    r = client.post("/api/v1/one-topic/analyze", json={
        "raw_topic": "智能交通",
        "goal_level": "稳中求新",
        "prefer": "heuristic",
    })
    assert r.status_code == 200
    kb = r.json()["keyword_breakdown"]
    assert len(kb["query_keywords_zh"]) >= 1
    assert len(kb["query_keywords_en"]) >= 1
