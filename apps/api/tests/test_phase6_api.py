"""Phase 06 FastAPI end-to-end tests."""

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
    await client.post(
        f"/api/v1/projects/{pid}/risk/evaluate", json={"prefer": "heuristic"}
    )
    return pid


@pytest.mark.asyncio
async def test_build_work_package_plan(client: AsyncClient) -> None:
    pid = await _setup_full(client, "P6_E2E_OK")
    r = await client.post(f"/api/v1/projects/{pid}/work_package/plan")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["work_package_count"] == 2
    assert j["allow_proceed_to_phase07"] is True
    # payload 必含 5 章 + 2 WP
    p = j["payload"]
    assert len(p["thesis_outline"]) == 5
    assert len(p["work_packages"]) == 2
    assert len(p["experiment_matrices"]) == 2


@pytest.mark.asyncio
async def test_get_work_package_plan(client: AsyncClient) -> None:
    pid = await _setup_full(client, "P6_E2E_GET")
    await client.post(f"/api/v1/projects/{pid}/work_package/plan")
    r = await client.get(f"/api/v1/projects/{pid}/work_package/plan")
    assert r.status_code == 200
    j = r.json()
    assert j["project_id"] == str(pid)


@pytest.mark.asyncio
async def test_work_package_blocked_without_risk(client: AsyncClient) -> None:
    body = _complete_intake("P6_E2E_NO_RISK")
    pid = (await client.post("/api/v1/projects", json=body)).json()["id"]
    await client.post(
        f"/api/v1/projects/{pid}/topic/decompose", json={"prefer": "heuristic"}
    )
    await client.post(f"/api/v1/projects/{pid}/search/plan")
    await client.post(
        f"/api/v1/projects/{pid}/evidence/build", json={"prefer": "heuristic"}
    )
    # 跳过 risk/evaluate
    r = await client.post(f"/api/v1/projects/{pid}/work_package/plan")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_work_package_blocked_without_evidence(client: AsyncClient) -> None:
    """无 EvidenceLedger → risk/evaluate 已先 404 阻断；work_package 端点也 404。

    这是 Phase 06 router 的"上游强依赖"设计：work_package 依赖 risk，
    risk 依赖 evidence；缺 evidence → 必然缺 risk → 端点返 404。
    """

    body = _complete_intake("P6_E2E_NO_EV")
    pid = (await client.post("/api/v1/projects", json=body)).json()["id"]
    await client.post(
        f"/api/v1/projects/{pid}/topic/decompose", json={"prefer": "heuristic"}
    )
    await client.post(f"/api/v1/projects/{pid}/search/plan")
    # 跳过 evidence/build → risk/evaluate 会 404
    r = await client.post(f"/api/v1/projects/{pid}/work_package/plan")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_work_package_invalid_project_404(client: AsyncClient) -> None:
    r = await client.post("/api/v1/projects/99999/work_package/plan")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_work_package_404_when_not_built(client: AsyncClient) -> None:
    pid = await _setup_full(client, "P6_E2E_NO_BUILD")
    r = await client.get(f"/api/v1/projects/{pid}/work_package/plan")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_work_package_upsert_idempotent(client: AsyncClient) -> None:
    pid = await _setup_full(client, "P6_E2E_IDEMPOTENT")
    r1 = await client.post(f"/api/v1/projects/{pid}/work_package/plan")
    r2 = await client.post(f"/api/v1/projects/{pid}/work_package/plan")
    assert r1.status_code == r2.status_code == 200
    assert r1.json()["work_package_count"] == r2.json()["work_package_count"]


@pytest.mark.asyncio
async def test_experiment_count_includes_supporting(client: AsyncClient) -> None:
    """experiment_count = sum(1 + len(supporting) for each WP)."""

    pid = await _setup_full(client, "P6_E2E_EXP")
    r = await client.post(f"/api/v1/projects/{pid}/work_package/plan")
    j = r.json()
    p = j["payload"]
    expected = sum(1 + len(wp["supporting_experiments"]) for wp in p["work_packages"])
    assert j["experiment_count"] == expected
