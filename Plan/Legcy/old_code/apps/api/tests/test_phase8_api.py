"""Phase 08 FastAPI end-to-end tests."""

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
    await client.post(f"/api/v1/projects/{pid}/proposal/draft")
    await client.post(f"/api/v1/projects/{pid}/committee/review")
    return pid


@pytest.mark.asyncio
async def test_build_final_package(client: AsyncClient) -> None:
    pid = await _setup_full(client, "P8_E2E_OK")
    r = await client.post(f"/api/v1/projects/{pid}/final_package/build")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["backend_verification"] == "PASS"
    assert j["ui_verification"] == "BLOCKED"  # apps/web 还没建
    assert j["playwright_verification"] == "BLOCKED"
    assert j["ready_for_thesis"] is True
    assert j["block_reasons"] == []
    assert j["proposal_markdown_chars"] > 500
    assert j["final_topic_zh"]


@pytest.mark.asyncio
async def test_get_final_package(client: AsyncClient) -> None:
    pid = await _setup_full(client, "P8_E2E_GET")
    await client.post(f"/api/v1/projects/{pid}/final_package/build")
    r = await client.get(f"/api/v1/projects/{pid}/final_package")
    assert r.status_code == 200
    j = r.json()
    assert j["ready_for_thesis"] is True


@pytest.mark.asyncio
async def test_export_proposal_markdown(client: AsyncClient) -> None:
    pid = await _setup_full(client, "P8_E2E_MD")
    await client.post(f"/api/v1/projects/{pid}/final_package/build")
    r = await client.get(f"/api/v1/projects/{pid}/final_package/markdown")
    assert r.status_code == 200
    assert "text/markdown" in r.headers.get("content-type", "")
    body = r.text
    # 必含 markdown 标题与 10 节
    assert body.startswith("#")
    assert "研究背景" in body
    assert "风险预案" in body
    # 必含 7 答辩问答
    assert "为什么选择" in body or "为什么" in body
    # 答辩问答
    assert "工作量" in body or "答辯" in body or "创新点" in body
    # 来源可追溯
    assert "Phase 04" in body
    assert "Phase 06" in body


@pytest.mark.asyncio
async def test_final_package_blocked_without_proposal(client: AsyncClient) -> None:
    body = _complete_intake("P8_E2E_NO_PROP")
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
    await client.post(f"/api/v1/projects/{pid}/work_package/plan")
    # 跳过 proposal/draft
    r = await client.post(f"/api/v1/projects/{pid}/final_package/build")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_final_package_invalid_project_404(client: AsyncClient) -> None:
    r = await client.post("/api/v1/projects/99999/final_package/build")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_final_package_404_when_not_built(client: AsyncClient) -> None:
    pid = await _setup_full(client, "P8_E2E_NO_BUILD")
    r = await client.get(f"/api/v1/projects/{pid}/final_package")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_final_package_upsert_idempotent(client: AsyncClient) -> None:
    pid = await _setup_full(client, "P8_E2E_IDEMPOTENT")
    r1 = await client.post(f"/api/v1/projects/{pid}/final_package/build")
    r2 = await client.post(f"/api/v1/projects/{pid}/final_package/build")
    assert r1.status_code == r2.status_code == 200
    assert r1.json()["ready_for_thesis"] == r2.json()["ready_for_thesis"]


@pytest.mark.asyncio
async def test_markdown_export_404_when_no_package(client: AsyncClient) -> None:
    pid = await _setup_full(client, "P8_E2E_NO_PKG")
    r = await client.get(f"/api/v1/projects/{pid}/final_package/markdown")
    assert r.status_code == 404
