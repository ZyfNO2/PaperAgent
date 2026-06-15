"""Phase 04 FastAPI + SQLite end-to-end tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


def _complete_intake(case_id: str = "P4_E2E") -> dict:
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


async def _setup_full(client: AsyncClient, case_id: str) -> int:
    pid = (await client.post("/api/v1/projects", json=_complete_intake(case_id))).json()["id"]
    await client.post(f"/api/v1/projects/{pid}/topic/decompose", json={"prefer": "heuristic"})
    await client.post(f"/api/v1/projects/{pid}/search/plan")
    return pid


@pytest.mark.asyncio
async def test_build_evidence_heuristic_endpoint(client: AsyncClient) -> None:
    pid = await _setup_full(client, "P4_E2E_OK")
    r = await client.post(
        f"/api/v1/projects/{pid}/evidence/build",
        json={"prefer": "heuristic"},
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["evidence_rating"] in ("A", "B")
    assert j["paper_count"] >= 5
    assert j["dataset_count"] >= 2
    assert j["baseline_count"] >= 2
    assert j["metric_count"] >= 1


@pytest.mark.asyncio
async def test_get_evidence_ledger(client: AsyncClient) -> None:
    pid = await _setup_full(client, "P4_E2E_GET")
    await client.post(f"/api/v1/projects/{pid}/evidence/build", json={"prefer": "heuristic"})
    r = await client.get(f"/api/v1/projects/{pid}/evidence/ledger")
    assert r.status_code == 200
    j = r.json()
    assert j["project_id"] == str(pid)
    payload = j["payload"]
    assert len(payload["papers"]) >= 5
    assert len(payload["datasets"]) >= 2
    assert len(payload["baselines"]) >= 2
    assert len(payload["thesis_templates"]) >= 1


@pytest.mark.asyncio
async def test_evidence_blocked_without_search_plan(client: AsyncClient) -> None:
    """没有 SearchQueryPlan 就调 evidence/build 应 409。"""

    body = _complete_intake("P4_E2E_NO_PLAN")
    pid = (await client.post("/api/v1/projects", json=body)).json()["id"]
    await client.post(f"/api/v1/projects/{pid}/topic/decompose", json={"prefer": "heuristic"})
    # 跳过 search/plan
    r = await client.post(
        f"/api/v1/projects/{pid}/evidence/build", json={"prefer": "heuristic"}
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_evidence_blocked_without_topicspec(client: AsyncClient) -> None:
    """没有 TopicSpec 就调 evidence/build 应 404。"""

    body = _complete_intake("P4_E2E_NO_SPEC")
    pid = (await client.post("/api/v1/projects", json=body)).json()["id"]
    r = await client.post(
        f"/api/v1/projects/{pid}/evidence/build", json={"prefer": "heuristic"}
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_evidence_invalid_project_returns_404(client: AsyncClient) -> None:
    r = await client.post(
        "/api/v1/projects/99999/evidence/build", json={"prefer": "heuristic"}
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_evidence_404_when_not_built(client: AsyncClient) -> None:
    pid = await _setup_full(client, "P4_E2E_NO_BUILD")
    r = await client.get(f"/api/v1/projects/{pid}/evidence/ledger")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_evidence_idempotent(client: AsyncClient) -> None:
    """调两次 build 不应出错（upsert）。"""

    pid = await _setup_full(client, "P4_E2E_IDEMPOTENT")
    r1 = await client.post(
        f"/api/v1/projects/{pid}/evidence/build", json={"prefer": "heuristic"}
    )
    r2 = await client.post(
        f"/api/v1/projects/{pid}/evidence/build", json={"prefer": "heuristic"}
    )
    assert r1.status_code == r2.status_code == 200
    assert r1.json()["paper_count"] == r2.json()["paper_count"]
