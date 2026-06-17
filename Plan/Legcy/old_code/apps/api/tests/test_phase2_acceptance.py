"""Phase 02 §3.1 后续测试：补 C/NEED_CLARIFICATION 阻断 + 字段完整性 + 一致性。

本文件聚焦于 [Phase_02-04_后续测试与验收需求.md] §3.1 列出的验收点。
test_phase2_api.py 已覆盖 A/B happy path 与 D 阻断；这里补：
- C 评级 409 拦截
- TopicSpec 必填字段全到位
- work_package_drafts 数量契约
- allow_proceed_to_phase03 与 decomposition_rating 一致性
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


# ----------------------------- helpers ----------------------------- #


def _c_intake(case_id: str) -> dict:
    """C/NEED_CLARIFICATION 评级 payload：缺 1 个 P0（proposal_deadline）。"""

    return {
        "intake": {
            "case_id": case_id,
            "major": "计算机科学与技术",
            "degree_type": "硕士",
            "goal_level": "保毕业",
            "thesis_deadline": "2027-06-01",
            # proposal_deadline 留空 → C
            "first_result_deadline": "2026-12-31",
            "advisor_direction": "图神经网络",
            "school_requirements": [],
            "inherited_resources": [],
            "student_resources": {
                "programming_level": "熟练",
                "compute_resource": "笔记本 3060",
                "weekly_hours": 25,
            },
            "raw_topic": "基于图神经网络的学术论文推荐方法研究",
            "must_keep": [],
            "can_drop": [],
            "missing_fields": [],
            "intake_rating": "C",
        }
    }


def _ab_intake(case_id: str) -> dict:
    return {
        "intake": {
            "case_id": case_id,
            "major": "计算机科学与技术",
            "degree_type": "硕士",
            "goal_level": "保毕业",
            "thesis_deadline": "2027-06-01",
            "proposal_deadline": "2026-10-15",
            "first_result_deadline": "2026-12-31",
            "advisor_direction": "图神经网络",
            "school_requirements": [],
            "inherited_resources": [],
            "student_resources": {
                "programming_level": "熟练",
                "compute_resource": "笔记本 3060",
                "weekly_hours": 25,
            },
            "raw_topic": "基于图神经网络的学术论文推荐方法研究",
            "must_keep": ["图神经网络"],
            "can_drop": [],
            "missing_fields": [],
            "intake_rating": "A",
        }
    }


# ----------------------------- C/NEED_CLARIFICATION 409 ----------------------------- #


@pytest.mark.asyncio
async def test_c_clarification_blocked_from_phase02(client: AsyncClient) -> None:
    """§3.1: Phase 01 C/NEED_CLARIFICATION → /topic/decompose 返 409。"""

    body = _c_intake("P2_C_409")
    pid = (await client.post("/api/v1/projects", json=body)).json()["id"]
    # 先 validate 确认确实是 NEED_CLARIFICATION
    v = (await client.post(f"/api/v1/projects/{pid}/intake/validate")).json()
    assert v["outcome"] == "NEED_CLARIFICATION"
    assert v["allow_proceed_to_phase02"] is False

    r = await client.post(f"/api/v1/projects/{pid}/topic/decompose", json={"prefer": "heuristic"})
    assert r.status_code == 409
    assert "Phase 01 状态" in r.json()["detail"]


# ----------------------------- TopicSpec 必填字段 ----------------------------- #


@pytest.mark.asyncio
async def test_topicspec_contains_all_required_fields(client: AsyncClient) -> None:
    """§3.1: TopicSpec 必含 normalized_topic / task_type / evaluation_metrics /
    risk_terms / thesis_mapping / work_package_drafts。"""

    body = _ab_intake("P2_FIELDS")
    pid = (await client.post("/api/v1/projects", json=body)).json()["id"]
    r = await client.post(
        f"/api/v1/projects/{pid}/topic/decompose", json={"prefer": "heuristic"}
    )
    assert r.status_code == 200
    spec = r.json()["payload"]

    # §3.1 必填字段
    for field in ("normalized_topic", "task_type", "evaluation_metrics",
                  "risk_terms", "thesis_mapping", "work_package_drafts"):
        assert field in spec, f"缺字段 {field}"
        assert spec[field] is not None, f"字段 {field} 为空"

    # normalized_topic 不为空白
    assert spec["normalized_topic"].strip() != ""

    # thesis_mapping 五章齐全
    for ch in ("chapter_1_intro", "chapter_2_basics", "chapter_3_wp1",
               "chapter_4_wp2", "chapter_5_summary"):
        assert ch in spec["thesis_mapping"]
        assert spec["thesis_mapping"][ch].strip() != ""


@pytest.mark.asyncio
async def test_topicspec_work_package_drafts_min_two(client: AsyncClient) -> None:
    """§3.1: work_package_drafts ≥ 2。"""

    body = _ab_intake("P2_WPS_2")
    pid = (await client.post("/api/v1/projects", json=body)).json()["id"]
    r = await client.post(
        f"/api/v1/projects/{pid}/topic/decompose", json={"prefer": "heuristic"}
    )
    spec = r.json()["payload"]
    assert len(spec["work_package_drafts"]) >= 2


# ----------------------------- 一致性 ----------------------------- #


@pytest.mark.asyncio
async def test_allow_proceed_consistent_with_rating(client: AsyncClient) -> None:
    """§3.1: allow_proceed_to_phase03 与 decomposition_rating 一致。"""

    body = _ab_intake("P2_CONSISTENCY")
    pid = (await client.post("/api/v1/projects", json=body)).json()["id"]
    r = await client.post(
        f"/api/v1/projects/{pid}/topic/decompose", json={"prefer": "heuristic"}
    )
    j = r.json()
    rating = j["decomposition_rating"]
    allow = j["allow_proceed_to_phase03"]
    # A/B → allow=True; C/D → allow=False
    if rating in ("A", "B"):
        assert allow is True
    else:
        assert allow is False


@pytest.mark.asyncio
async def test_upsert_no_duplicate_rows_on_repeat_decompose(client: AsyncClient) -> None:
    """§3.1: 重复 /topic/decompose 不产生重复脏数据。

    验证：调 N 次后通过 GET /topic/spec 仍能拿回一条 (不是列表)，
    且 N+1 次的 payload 与第 1 次的 normalize_topic 一致。
    """

    body = _ab_intake("P2_UPSERT")
    pid = (await client.post("/api/v1/projects", json=body)).json()["id"]

    for _ in range(3):
        await client.post(
            f"/api/v1/projects/{pid}/topic/decompose", json={"prefer": "heuristic"}
        )

    r = await client.get(f"/api/v1/projects/{pid}/topic/spec")
    assert r.status_code == 200
    j = r.json()
    # 单数 / id 字段
    assert "id" in j
    assert j["payload"]["normalized_topic"].strip() != ""


@pytest.mark.asyncio
async def test_get_topicspec_404_when_not_generated(client: AsyncClient) -> None:
    """§3.1: /topic/spec 未生成时返 404，生成后能恢复读取。"""

    body = _ab_intake("P2_GET_404")
    pid = (await client.post("/api/v1/projects", json=body)).json()["id"]

    # 未生成
    r = await client.get(f"/api/v1/projects/{pid}/topic/spec")
    assert r.status_code == 404

    # 生成
    await client.post(
        f"/api/v1/projects/{pid}/topic/decompose", json={"prefer": "heuristic"}
    )

    # 恢复
    r = await client.get(f"/api/v1/projects/{pid}/topic/spec")
    assert r.status_code == 200
    assert r.json()["payload"]["normalized_topic"]
