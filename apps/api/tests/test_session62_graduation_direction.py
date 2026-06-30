"""Session 62: GraduationDirection tests.

覆盖 (SOP §8.1):
1. 输入题目能生成 2-3 个方向
2. 每个方向都有 score / risk_level / evidence_bundle
3. 推荐方向必须有 baseline
4. baseline 至少包含名称、理由、复现难度
5. extension_modules 数量在 2-4
6. 数据集缺失时必须生成降级方向
7. 无证据时不得给高分
8. 响应必须包含 stop_reason, 且说明不生成开题报告
9. schema 拒绝多余字段
10. 不调用外部 LLM 时 heuristic fallback 可跑通
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.graduation import build_decision_report


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch, tmp_path):
    """每个测试独立目录."""
    monkeypatch.setenv("PAPERAGENT_PAPER_LIBRARY_DIR", str(tmp_path / "paper_library"))
    from app.services import evidence as ev_store
    from app.services.paper_library import embedding
    ev_store.reset_all()
    embedding.reset_vocab()
    yield
    ev_store.reset_all()
    embedding.reset_vocab()


@pytest.fixture()
def client():
    return TestClient(app)


PROJECT = "s62-test"
TOPIC = "基于三维成像的损伤智能检测"


# ---------------------------------------------------------------------------
# 1) 输入题目能生成 2-3 个方向
# ---------------------------------------------------------------------------


def test_plan_returns_2_to_3_directions(client):
    resp = client.post(
        f"/api/v1/projects/{PROJECT}/graduation-direction/plan",
        json={"topic": TOPIC, "use_last_retrieval": False, "use_local_rag": False},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert 2 <= len(body["directions"]) <= 3, body["directions"]
    assert body["recommended_direction_id"], "recommended_direction_id 必填"
    assert body["project_id"] == PROJECT
    assert body["topic"] == TOPIC


# ---------------------------------------------------------------------------
# 2) 每个方向都有 score / risk_level / evidence_bundle
# ---------------------------------------------------------------------------


def test_each_direction_has_score_risk_bundle(client):
    resp = client.post(
        f"/api/v1/projects/{PROJECT}/graduation-direction/plan",
        json={"topic": TOPIC, "use_last_retrieval": False, "use_local_rag": False},
    )
    body = resp.json()
    for d in body["directions"]:
        assert "score" in d and 0 <= d["score"] <= 100, d
        assert d["risk_level"] in ("low", "medium", "high"), d
        assert "evidence_bundle" in d, d
        eb = d["evidence_bundle"]
        for k in ("papers", "datasets", "repos", "rag_refs", "gaps"):
            assert k in eb, eb


# ---------------------------------------------------------------------------
# 3) 推荐方向必须有 baseline; baseline 至少包含 name/rationale/reproducibility
# ---------------------------------------------------------------------------


def test_recommended_direction_has_baselines(client):
    resp = client.post(
        f"/api/v1/projects/{PROJECT}/graduation-direction/plan",
        json={"topic": TOPIC, "use_last_retrieval": False, "use_local_rag": False},
    )
    body = resp.json()
    rec = next(d for d in body["directions"] if d["direction_id"] == body["recommended_direction_id"])
    assert rec["recommended_baselines"], "推荐方向必须有 baseline"
    for b in rec["recommended_baselines"]:
        assert b["name"], b
        assert b["rationale"], b
        assert b["reproducibility"] in ("low", "medium", "high"), b


# ---------------------------------------------------------------------------
# 4) extension_modules 数量在 2-4
# ---------------------------------------------------------------------------


def test_extension_modules_count_in_range(client):
    resp = client.post(
        f"/api/v1/projects/{PROJECT}/graduation-direction/plan",
        json={"topic": TOPIC, "use_last_retrieval": False, "use_local_rag": False},
    )
    body = resp.json()
    for d in body["directions"]:
        assert 2 <= len(d["extension_modules"]) <= 4, d
        for m in d["extension_modules"]:
            assert m["name"] and m["attach_to"] and m["ablation_plan"], m


# ---------------------------------------------------------------------------
# 5) 数据集缺失时, 降级方向必须存在
# ---------------------------------------------------------------------------


def test_fallback_direction_present_when_no_dataset(client):
    resp = client.post(
        f"/api/v1/projects/{PROJECT}/graduation-direction/plan",
        json={"topic": TOPIC, "use_last_retrieval": False, "use_local_rag": False},
    )
    body = resp.json()
    has_fallback = any(d["fallback_route"] for d in body["directions"])
    assert has_fallback, "无证据时必须给出降级方向"


# ---------------------------------------------------------------------------
# 6) 无证据时不得给高分 (risk_scorer 应扣分)
# ---------------------------------------------------------------------------


def test_no_evidence_lowers_score(monkeypatch):
    """直接调用 service 层, 对比有/无证据下推荐方向分数."""

    # 无证据
    rpt_no = build_decision_report(
        "ot_test", TOPIC,
        use_last_retrieval=False, use_local_rag=False, max_directions=3,
    )
    score_no = max(d.score for d in rpt_no.directions)

    # mock local_rag.ask_local_rag → 模拟有命中
    from app.services.graduation import evidence_bundle
    from app.services.paper_library import local_rag as lr_mod
    from app.schemas_graduation_direction import EvidenceBundleRef

    class _StubOutcome:
        no_hit = False
        evidence_refs = [
            type("R", (), {"paper_id": "p1", "chunk_id": "c1", "section_title": "Method",
                           "chunk_type": "body", "page_start": 1, "page_end": 2,
                           "quote": "crack detection dataset", "score": 0.8})()
        ]

    def _stub(*args, **kwargs):
        return _StubOutcome()

    monkeypatch.setattr(evidence_bundle.local_rag, "ask_local_rag", _stub)
    rpt_yes = build_decision_report(
        "ot_test", TOPIC,
        use_last_retrieval=False, use_local_rag=True,
        local_rag_query="裂缝检测", max_directions=3,
    )
    score_yes = max(d.score for d in rpt_yes.directions)

    assert score_no < 70, f"无证据时 score 应偏低, got {score_no}"
    assert score_yes > score_no, (score_no, score_yes)


# ---------------------------------------------------------------------------
# 7) 响应必须包含 stop_reason, 且明确不生成开题报告
# ---------------------------------------------------------------------------


def test_stop_reason_present(client):
    resp = client.post(
        f"/api/v1/projects/{PROJECT}/graduation-direction/plan",
        json={"topic": TOPIC},
    )
    body = resp.json()
    assert "stop_reason" in body, body
    assert "不生成开题报告" in body["stop_reason"], body["stop_reason"]


# ---------------------------------------------------------------------------
# 8) schema 拒绝多余字段
# ---------------------------------------------------------------------------


def test_schema_rejects_extra_fields(client):
    resp = client.post(
        f"/api/v1/projects/{PROJECT}/graduation-direction/plan",
        json={"topic": TOPIC, "extra_field": "should_be_rejected"},
    )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# 9) heuristic fallback: 不调用 LLM 也能跑通
# ---------------------------------------------------------------------------


def test_no_llm_needed():
    """不调外部 LLM, 纯 heuristic 跑通."""
    rpt = build_decision_report(
        "ot_no_llm", TOPIC,
        use_last_retrieval=False, use_local_rag=False, max_directions=3,
    )
    assert rpt.directions, rpt
    for d in rpt.directions:
        # scoring_breakdown 必填 (开发者窗口)
        assert d.scoring_breakdown and len(d.scoring_breakdown) == 7, d


# ---------------------------------------------------------------------------
# 10) 空题目 422
# ---------------------------------------------------------------------------


def test_empty_topic_422(client):
    resp = client.post(
        f"/api/v1/projects/{PROJECT}/graduation-direction/plan",
        json={"topic": ""},
    )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# 11) 普通 2-3 方向题 (无三维) 仍能跑
# ---------------------------------------------------------------------------


def test_generic_topic_returns_directions(client):
    resp = client.post(
        f"/api/v1/projects/{PROJECT}/graduation-direction/plan",
        json={"topic": "钢材表面缺陷识别"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert 2 <= len(body["directions"]) <= 3, body["directions"]


# ---------------------------------------------------------------------------
# 12) 服务层 direct 调用: 必须有 stop_reason + warnings 可选
# ---------------------------------------------------------------------------


def test_service_layer_direct():
    rpt = build_decision_report("ot_x", TOPIC, max_directions=3)
    assert rpt.stop_reason
    assert rpt.generated_at
    # 无证据时, warnings 应非空
    assert isinstance(rpt.warnings, list)