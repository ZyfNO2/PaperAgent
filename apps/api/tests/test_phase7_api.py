"""Phase 07 FastAPI end-to-end tests."""

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
    await client.post(f"/api/v1/projects/{pid}/work_package/plan")
    return pid


@pytest.mark.asyncio
async def test_build_proposal_draft(client: AsyncClient) -> None:
    pid = await _setup_full(client, "P7_E2E_DRAFT")
    r = await client.post(f"/api/v1/projects/{pid}/proposal/draft")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["section_count"] == 10
    assert j["innovation_count"] == 2
    # payload 必含 10 节
    sections = j["payload"]["proposal_sections"]
    assert len(sections) == 10


@pytest.mark.asyncio
async def test_get_proposal_draft(client: AsyncClient) -> None:
    pid = await _setup_full(client, "P7_E2E_GET")
    await client.post(f"/api/v1/projects/{pid}/proposal/draft")
    r = await client.get(f"/api/v1/projects/{pid}/proposal/draft")
    assert r.status_code == 200
    assert r.json()["section_count"] == 10


@pytest.mark.asyncio
async def test_committee_review_seven_dimensions(client: AsyncClient) -> None:
    pid = await _setup_full(client, "P7_E2E_COM")
    r = await client.post(f"/api/v1/projects/{pid}/committee/review")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["review_count"] == 7
    assert j["question_count"] == 6
    assert j["allow_proceed_to_phase08"] is True
    payload = j["payload"]
    dims = {rv["dimension"] for rv in payload["reviews"]}
    assert dims == {
        "题目边界", "研究现状", "创新点", "数据与 baseline",
        "实验方案", "工作量", "风险预案",
    }


@pytest.mark.asyncio
async def test_get_committee_review(client: AsyncClient) -> None:
    pid = await _setup_full(client, "P7_E2E_GET_COM")
    await client.post(f"/api/v1/projects/{pid}/committee/review")
    r = await client.get(f"/api/v1/projects/{pid}/committee/review")
    assert r.status_code == 200
    j = r.json()
    assert j["review_count"] == 7


@pytest.mark.asyncio
async def test_proposal_blocked_without_work_package(client: AsyncClient) -> None:
    body = _complete_intake("P7_E2E_NO_WP")
    pid = (await client.post("/api/v1/projects", json=body)).json()["id"]
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
    # 跳过 work_package/plan
    r = await client.post(f"/api/v1/projects/{pid}/proposal/draft")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_proposal_invalid_project_404(client: AsyncClient) -> None:
    r = await client.post("/api/v1/projects/99999/proposal/draft")
    assert r.status_code == 404
    r2 = await client.post("/api/v1/projects/99999/committee/review")
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_proposal_404_when_not_built(client: AsyncClient) -> None:
    pid = await _setup_full(client, "P7_E2E_NO_BUILD")
    r = await client.get(f"/api/v1/projects/{pid}/proposal/draft")
    assert r.status_code == 404
    r2 = await client.get(f"/api/v1/projects/{pid}/committee/review")
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_committee_upsert_idempotent(client: AsyncClient) -> None:
    pid = await _setup_full(client, "P7_E2E_IDEMPOTENT")
    r1 = await client.post(f"/api/v1/projects/{pid}/committee/review")
    r2 = await client.post(f"/api/v1/projects/{pid}/committee/review")
    assert r1.status_code == r2.status_code == 200
    assert r1.json()["overall_verdict"] == r2.json()["overall_verdict"]
