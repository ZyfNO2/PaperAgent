"""Phase 03 FastAPI + SQLite end-to-end tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


def _complete_intake(case_id: str = "P3_E2E") -> dict:
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
            "school_requirements": ["中文文献"],
            "inherited_resources": [],
            "student_resources": {
                "programming_level": "熟练",
                "dl_or_algorithm_foundation": "中",
                "paper_reading_ability": "中",
                "english_reading_ability": "中",
                "compute_resource": "笔记本 3060",
                "weekly_hours": 25,
                "data_collection_ability": "中",
                "data_annotation_ability": "中",
                "code_reproduction_ability": "中",
                "system_dev_ability": "中",
            },
            "raw_topic": "基于图神经网络的学术论文推荐方法研究",
            "must_keep": ["图神经网络"],
            "can_drop": [],
            "missing_fields": [],
            "intake_rating": "A",
        }
    }


async def _setup_project_with_spec(client: AsyncClient, case_id: str) -> int:
    pid = (await client.post("/api/v1/projects", json=_complete_intake(case_id))).json()["id"]
    await client.post(f"/api/v1/projects/{pid}/topic/decompose", json={"prefer": "heuristic"})
    return pid


@pytest.mark.asyncio
async def test_build_search_plan_endpoint(client: AsyncClient) -> None:
    pid = await _setup_project_with_spec(client, "P3_E2E_OK")
    r = await client.post(f"/api/v1/projects/{pid}/search/plan")
    assert r.status_code == 200, r.text
    j = r.json()
    plan = j["payload"]
    assert j["maturity_rating"] in ("A", "B")
    assert j["allow_proceed_to_phase04"] is True
    assert len(plan["query_layers"]) == 7
    layers = [l["layer"] for l in plan["query_layers"]]
    assert layers == ["L0", "L1", "L2", "L3", "L4", "L5", "L6"]


@pytest.mark.asyncio
async def test_get_search_plan_endpoint(client: AsyncClient) -> None:
    pid = await _setup_project_with_spec(client, "P3_E2E_GET")
    await client.post(f"/api/v1/projects/{pid}/search/plan")
    r = await client.get(f"/api/v1/projects/{pid}/search/plan")
    assert r.status_code == 200
    j = r.json()
    assert j["project_id"] == str(pid)
    assert len(j["payload"]["query_layers"]) == 7


@pytest.mark.asyncio
async def test_search_plan_blocked_without_topicspec(client: AsyncClient) -> None:
    """没有 TopicSpec 就调 search/plan 应 404。"""

    body = _complete_intake("P3_E2E_NO_SPEC")
    pid = (await client.post("/api/v1/projects", json=body)).json()["id"]
    r = await client.post(f"/api/v1/projects/{pid}/search/plan")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_search_plan_blocked_when_decompose_failed(client: AsyncClient) -> None:
    """D 评级项目（Phase 01 阻断）调 decompose → 409；调 search/plan → 404。"""

    body = {
        "intake": {
            "case_id": "P3_E2E_BLOCK",
            "goal_level": "保毕业",
            "raw_topic": "TBD",
            "intake_rating": "A",
        }
    }
    pid = (await client.post("/api/v1/projects", json=body)).json()["id"]
    # 没 TopicSpec 也没有
    r = await client.post(f"/api/v1/projects/{pid}/search/plan")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_search_plan_has_total_query_count(client: AsyncClient) -> None:
    pid = await _setup_project_with_spec(client, "P3_E2E_COUNT")
    r = await client.post(f"/api/v1/projects/{pid}/search/plan")
    plan = r.json()["payload"]
    total = sum(len(l["queries"]) for l in plan["query_layers"])
    assert total >= 10
