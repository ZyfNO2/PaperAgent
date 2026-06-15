"""Phase 02 FastAPI + SQLite end-to-end tests."""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient


def _complete_intake(case_id: str = "P2_API_A") -> dict:
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


def _placeholder_intake(case_id: str = "P2_API_D") -> dict:
    return {
        "intake": {
            "case_id": case_id,
            "goal_level": "保毕业",
            "raw_topic": "TBD",
            "intake_rating": "A",
        }
    }


@pytest.mark.asyncio
async def test_decompose_heuristic_returns_complete_spec(client: AsyncClient) -> None:
    body = _complete_intake("P2_E2E_A")
    r = (await client.post("/api/v1/projects", json=body)).json()
    pid = r["id"]

    r = await client.post(f"/api/v1/projects/{pid}/topic/decompose", json={"prefer": "heuristic"})
    assert r.status_code == 200, r.text
    j = r.json()
    spec = j["payload"]
    assert j["decomposition_rating"] in ("A", "B")
    assert j["allow_proceed_to_phase03"] is True
    assert spec["normalized_topic"]
    assert len(spec["work_package_drafts"]) >= 2
    assert spec["thesis_mapping"]["chapter_3_wp1"]
    assert spec["thesis_mapping"]["chapter_4_wp2"]


@pytest.mark.asyncio
async def test_decompose_blocked_when_phase01_failed(client: AsyncClient) -> None:
    """Phase 02 必须 Phase 01 通过才能进；D 评级应被 409 拦截。"""

    body = _placeholder_intake("P2_E2E_BLOCKED")
    r = (await client.post("/api/v1/projects", json=body)).json()
    pid = r["id"]
    # Phase 01 默认 D 阻断
    r = await client.post(f"/api/v1/projects/{pid}/topic/decompose", json={"prefer": "heuristic"})
    assert r.status_code == 409
    assert "Phase 01 状态" in r.json()["detail"]


@pytest.mark.asyncio
async def test_decompose_then_get_spec(client: AsyncClient) -> None:
    body = _complete_intake("P2_E2E_GET")
    pid = (await client.post("/api/v1/projects", json=body)).json()["id"]
    await client.post(f"/api/v1/projects/{pid}/topic/decompose", json={"prefer": "heuristic"})

    r = await client.get(f"/api/v1/projects/{pid}/topic/spec")
    assert r.status_code == 200
    j = r.json()
    assert j["project_id"] == str(pid)
    spec = j["payload"]
    assert spec["raw_topic"] == "基于图神经网络的学术论文推荐方法研究"


@pytest.mark.asyncio
async def test_get_spec_404_when_not_decomposed(client: AsyncClient) -> None:
    body = _complete_intake("P2_E2E_404")
    pid = (await client.post("/api/v1/projects", json=body)).json()["id"]
    r = await client.get(f"/api/v1/projects/{pid}/topic/spec")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_decompose_idempotent(client: AsyncClient) -> None:
    """调两次 decompose 不应出错（upsert）。"""

    body = _complete_intake("P2_E2E_IDEMPOTENT")
    pid = (await client.post("/api/v1/projects", json=body)).json()["id"]

    r1 = await client.post(f"/api/v1/projects/{pid}/topic/decompose", json={"prefer": "heuristic"})
    r2 = await client.post(f"/api/v1/projects/{pid}/topic/decompose", json={"prefer": "heuristic"})
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["payload"]["normalized_topic"] == r2.json()["payload"]["normalized_topic"]


@pytest.mark.asyncio
async def test_decompose_invalid_project_returns_404(client: AsyncClient) -> None:
    r = await client.post("/api/v1/projects/99999/topic/decompose", json={"prefer": "heuristic"})
    assert r.status_code == 404
