"""FastAPI + real SQLite end-to-end tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from packages.domain import (
    InheritedResource,
    ProjectIntake,
    StudentResourceProfile,
)


# ----------------------------- helpers ----------------------------- #


def _complete_intake(case_id: str = "20260616_AI_e2e") -> dict:
    """Return a request body dict that will rate A (zero missing fields)."""

    intake = ProjectIntake.model_validate(
        {
            "case_id": case_id,
            "major": "计算机科学与技术",
            "degree_type": "硕士",
            "goal_level": "保毕业",
            "thesis_deadline": "2027-06-01",
            "proposal_deadline": "2026-10-15",
            "first_result_deadline": "2026-12-31",
            "advisor_direction": "图神经网络",
            "school_requirements": ["必须中文文献"],
            "inherited_resources": [
                InheritedResource(
                    kind="同门毕业论文",
                    description="师兄 2024 届硕士论文",
                    available=True,
                )
            ],
            "student_resources": StudentResourceProfile(
                programming_level="熟练",
                compute_resource="笔记本 3060",
                weekly_hours=25,
            ),
            "raw_topic": "基于图神经网络的学术论文推荐",
            "must_keep": ["图神经网络"],
            "can_drop": [],
            "missing_fields": [],
            "intake_rating": "A",  # 服务端会覆盖
        }
    )
    return {"intake": intake.model_dump(mode="json")}


def _placeholder_intake(case_id: str = "TBD_AI_e2e") -> dict:
    """Body that should rate D and BLOCK."""

    intake = ProjectIntake.model_validate(
        {
            "case_id": case_id,
            "goal_level": "保毕业",
            "raw_topic": "TBD",
            "intake_rating": "A",
        }
    )
    return {"intake": intake.model_dump(mode="json")}


# ----------------------------- /health ----------------------------- #


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient) -> None:
    r = await client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body == {"status": "ok", "phase": "01"}


# ----------------------------- create ----------------------------- #


@pytest.mark.asyncio
async def test_create_project_returns_201_and_rating(client: AsyncClient) -> None:
    body = _complete_intake()
    r = await client.post("/api/v1/projects", json=body)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["case_id"] == body["intake"]["case_id"]
    assert isinstance(data["id"], int) and data["id"] > 0
    assert data["payload"]["intake_rating"] == "A"
    assert data["payload"]["missing_fields"] == []


@pytest.mark.asyncio
async def test_create_placeholder_project_rates_D(client: AsyncClient) -> None:
    body = _placeholder_intake(case_id="TBD_e2e_D")
    r = await client.post("/api/v1/projects", json=body)
    assert r.status_code == 201
    payload = r.json()["payload"]
    assert payload["intake_rating"] == "D"
    assert len(payload["missing_fields"]) >= 6
    # 至少出现一个 P0
    assert any(m["priority"] == "P0" for m in payload["missing_fields"])


@pytest.mark.asyncio
async def test_create_duplicate_case_id_returns_409(client: AsyncClient) -> None:
    body = _complete_intake(case_id="DUP_e2e")
    r1 = await client.post("/api/v1/projects", json=body)
    assert r1.status_code == 201

    r2 = await client.post("/api/v1/projects", json=body)
    assert r2.status_code == 409
    assert "已存在" in r2.json()["detail"]


@pytest.mark.asyncio
async def test_create_invalid_payload_returns_422(client: AsyncClient) -> None:
    bad = _complete_intake()
    bad["intake"]["raw_topic"] = ""  # violates min_length=1
    r = await client.post("/api/v1/projects", json=bad)
    assert r.status_code == 422


# ----------------------------- get by id ----------------------------- #


@pytest.mark.asyncio
async def test_get_project_by_id(client: AsyncClient) -> None:
    body = _complete_intake(case_id="GET_e2e")
    created = (await client.post("/api/v1/projects", json=body)).json()
    pid = created["id"]

    r = await client.get(f"/api/v1/projects/{pid}")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == pid
    assert data["case_id"] == "GET_e2e"
    assert data["payload"]["raw_topic"] == "基于图神经网络的学术论文推荐"


@pytest.mark.asyncio
async def test_get_missing_project_returns_404(client: AsyncClient) -> None:
    r = await client.get("/api/v1/projects/99999")
    assert r.status_code == 404


# ----------------------------- validate endpoint ----------------------------- #


@pytest.mark.asyncio
async def test_validate_placeholder_returns_BLOCKED(client: AsyncClient) -> None:
    body = _placeholder_intake(case_id="VAL_BLOCK_e2e")
    pid = (await client.post("/api/v1/projects", json=body)).json()["id"]

    r = await client.post(f"/api/v1/projects/{pid}/intake/validate")
    assert r.status_code == 200
    out = r.json()
    assert out["outcome"] == "BLOCKED"
    assert out["intake_rating"] == "D"
    assert out["allow_proceed_to_phase02"] is False


@pytest.mark.asyncio
async def test_validate_complete_returns_OK(client: AsyncClient) -> None:
    body = _complete_intake(case_id="VAL_OK_e2e")
    pid = (await client.post("/api/v1/projects", json=body)).json()["id"]

    r = await client.post(f"/api/v1/projects/{pid}/intake/validate")
    assert r.status_code == 200
    out = r.json()
    assert out["outcome"] == "OK"
    assert out["intake_rating"] == "A"
    assert out["allow_proceed_to_phase02"] is True


@pytest.mark.asyncio
async def test_clarification_loop_promotes_D_to_A(client: AsyncClient) -> None:
    """端到端补问流程：占位建档 D → 完整补问 → 再 validate 拿 A。"""

    body = _placeholder_intake(case_id="LOOP_e2e")
    pid = (await client.post("/api/v1/projects", json=body)).json()["id"]

    # 初次 validate 必为 BLOCKED
    first = (await client.post(f"/api/v1/projects/{pid}/intake/validate")).json()
    assert first["intake_rating"] == "D"

    # 模拟 HumanClarificationNode 补问：调用方更新数据库中的 payload。
    # Phase 01 暂不提供 PATCH 端点，这里直接通过仓储层覆盖 payload。
    from packages.domain import validate_intake
    from app.db.database import SessionLocal, Project
    from sqlalchemy import select

    async with SessionLocal() as session:
        proj = (await session.execute(select(Project).where(Project.id == pid))).scalar_one()
        new_intake = ProjectIntake.model_validate(_complete_intake(case_id="LOOP_e2e")["intake"])
        proj.payload = new_intake.model_dump(mode="json")
        await session.commit()

    # 再 validate 应升级为 OK
    second = (await client.post(f"/api/v1/projects/{pid}/intake/validate")).json()
    assert second["outcome"] == "OK"
    assert second["intake_rating"] == "A"
    assert second["allow_proceed_to_phase02"] is True


@pytest.mark.asyncio
async def test_validate_missing_project_returns_404(client: AsyncClient) -> None:
    r = await client.post("/api/v1/projects/99999/intake/validate")
    assert r.status_code == 404
