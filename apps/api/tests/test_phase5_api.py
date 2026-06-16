"""Phase 05 FastAPI + SQLite end-to-end tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


def _complete_intake(case_id: str) -> dict:
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


async def _setup_full(client: AsyncClient, case_id: str) -> int:
    pid = (await client.post("/api/v1/projects", json=_complete_intake(case_id))).json()["id"]
    await client.post(
        f"/api/v1/projects/{pid}/topic/decompose", json={"prefer": "heuristic"}
    )
    await client.post(f"/api/v1/projects/{pid}/search/plan")
    await client.post(
        f"/api/v1/projects/{pid}/evidence/build", json={"prefer": "heuristic"}
    )
    return pid


@pytest.mark.asyncio
async def test_evaluate_risk_heuristic(client: AsyncClient) -> None:
    pid = await _setup_full(client, "P5_E2E_A")
    r = await client.post(
        f"/api/v1/projects/{pid}/risk/evaluate", json={"prefer": "heuristic"}
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["overall_rating"] in ("A", "B")
    assert 0.0 <= j["overall_score"] <= 100.0
    assert j["decision"] in ("继续", "收缩", "转向")
    assert j["pivot_count"] >= 1
    assert j["allow_proceed_to_phase06"] is True
    # payload 必含 6 维
    dims = j["payload"]["risk_score"]["dimensions"]
    assert len(dims) == 6


@pytest.mark.asyncio
async def test_get_risk_evaluation(client: AsyncClient) -> None:
    pid = await _setup_full(client, "P5_E2E_GET")
    await client.post(
        f"/api/v1/projects/{pid}/risk/evaluate", json={"prefer": "heuristic"}
    )
    r = await client.get(f"/api/v1/projects/{pid}/risk/evaluation")
    assert r.status_code == 200
    j = r.json()
    assert j["project_id"] == str(pid)
    assert j["payload"]["decision"] in ("继续", "收缩", "转向")


@pytest.mark.asyncio
async def test_risk_blocked_without_evidence(client: AsyncClient) -> None:
    """无 EvidenceLedger → 409。"""

    body = _complete_intake("P5_E2E_NO_EV")
    pid = (await client.post("/api/v1/projects", json=body)).json()["id"]
    await client.post(
        f"/api/v1/projects/{pid}/topic/decompose", json={"prefer": "heuristic"}
    )
    await client.post(f"/api/v1/projects/{pid}/search/plan")
    # 跳过 evidence/build
    r = await client.post(
        f"/api/v1/projects/{pid}/risk/evaluate", json={"prefer": "heuristic"}
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_risk_blocked_without_search_plan(client: AsyncClient) -> None:
    body = _complete_intake("P5_E2E_NO_PLAN")
    pid = (await client.post("/api/v1/projects", json=body)).json()["id"]
    await client.post(
        f"/api/v1/projects/{pid}/topic/decompose", json={"prefer": "heuristic"}
    )
    # 跳过 plan
    r = await client.post(
        f"/api/v1/projects/{pid}/risk/evaluate", json={"prefer": "heuristic"}
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_risk_blocked_without_topicspec(client: AsyncClient) -> None:
    body = _complete_intake("P5_E2E_NO_SPEC")
    pid = (await client.post("/api/v1/projects", json=body)).json()["id"]
    r = await client.post(
        f"/api/v1/projects/{pid}/risk/evaluate", json={"prefer": "heuristic"}
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_risk_invalid_project_404(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/projects/99999/risk/evaluate", json={"prefer": "heuristic"}
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_risk_404_when_not_evaluated(client: AsyncClient) -> None:
    pid = await _setup_full(client, "P5_E2E_NO_EVAL")
    r = await client.get(f"/api/v1/projects/{pid}/risk/evaluation")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_risk_upsert_idempotent(client: AsyncClient) -> None:
    pid = await _setup_full(client, "P5_E2E_IDEMPOTENT")
    r1 = await client.post(
        f"/api/v1/projects/{pid}/risk/evaluate", json={"prefer": "heuristic"}
    )
    r2 = await client.post(
        f"/api/v1/projects/{pid}/risk/evaluate", json={"prefer": "heuristic"}
    )
    assert r1.status_code == r2.status_code == 200
    assert r1.json()["overall_rating"] == r2.json()["overall_rating"]
