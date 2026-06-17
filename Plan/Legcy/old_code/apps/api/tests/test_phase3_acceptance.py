"""Phase 03 §3.2 后续测试：补 TopicSpec 不允许 409 + 6 类覆盖 + Pivot + upsert。

test_phase3_api.py 已覆盖：无 TopicSpec 404、L0-L6 顺序、总词数等。
这里补 [Phase_02-04_后续测试与验收需求.md] §3.2 列出的剩余验收点。
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


# ----------------------------- helpers ----------------------------- #


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


async def _setup_with_spec(
    client: AsyncClient, case_id: str
) -> int:
    """建档 + 跑 Phase 02 heuristic。返回 project_id。"""

    pid = (await client.post("/api/v1/projects", json=_ab_intake(case_id))).json()["id"]
    r = await client.post(
        f"/api/v1/projects/{pid}/topic/decompose", json={"prefer": "heuristic"}
    )
    assert r.status_code == 200, r.text
    return pid


# ----------------------------- 1) TopicSpec 不允许 409 ----------------------------- #


@pytest.mark.asyncio
async def test_search_plan_409_when_topicspec_not_allowed(client: AsyncClient) -> None:
    """§3.2: TopicSpec 不允许进入 Phase 03 时调 /search/plan 返 409。

    通过直接改 DB 中的 TopicSpec 为 allow_proceed=False 触发（heuristic
    通常产出 A，难以在合法路径下造不允许 TopicSpec）。
    """

    pid = await _setup_with_spec(client, "P3_NOTALLOWED")

    # 注入一个 decomposition_rating=C 的 TopicSpec
    from sqlalchemy import select
    from app.db.database import SessionLocal, TopicSpec
    from packages.domain import TopicSpec as TopicSpecDomain
    from packages.domain.phase2_models import (
        ThesisMapping, WorkPackageDraft, TopicSpec as TopicSpecM,
    )

    bad = TopicSpecM(
        project_id=str(pid),
        source_intake_case_id="P3_NOTALLOWED",
        goal_level="保毕业",
        raw_topic="x",
        normalized_topic="x",
        decomposition_rating="C",
        thesis_mapping=ThesisMapping(
            chapter_1_intro="a", chapter_2_basics="b",
            chapter_3_wp1="c", chapter_4_wp2="d", chapter_5_summary="e",
        ),
        work_package_drafts=[
            WorkPackageDraft(
                wp_id="WP1", title="t", research_question="q",
                method_approach="m", data_source="d",
                experiment_plan="e", chapter="第三章",
            ),
            WorkPackageDraft(
                wp_id="WP2", title="t", research_question="q",
                method_approach="m", data_source="d",
                experiment_plan="e", chapter="第四章",
            ),
        ],
        evaluation_metrics=[],  # 关键：让 allow_proceed=False
    )
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(TopicSpec).where(TopicSpec.project_id == str(pid))
            )
        ).scalar_one()
        row.payload = bad.model_dump(mode="json")
        row.decomposition_rating = "C"
        await session.commit()

    r = await client.post(f"/api/v1/projects/{pid}/search/plan")
    assert r.status_code == 409
    assert "不允许" in r.json()["detail"]


# ----------------------------- 2) 6 类覆盖 ----------------------------- #


@pytest.mark.asyncio
async def test_plan_covers_six_evidence_types(client: AsyncClient) -> None:
    """§3.2: 检索计划覆盖 论文 / 综述 / 数据集 / baseline / benchmark / 学位论文模板。"""

    pid = await _setup_with_spec(client, "P3_COVERAGE")
    r = await client.post(f"/api/v1/projects/{pid}/search/plan")
    plan = r.json()["payload"]
    all_queries = " ".join(q for l in plan["query_layers"] for q in l["queries"]).lower()

    # 6 类至少 4 个关键词命中（论文/综述/数据集/baseline/benchmark/学位论文模板）
    indicators = {
        "论文": ["paper", "arxiv", "openalex"],
        "综述": ["survey", "review"],
        "数据集": ["dataset"],
        "baseline/code": ["github", "code", "baseline", "papers with code"],
        "benchmark/指标": ["benchmark", "metric"],
        "学位论文模板": ["学位论文", "开题"],
    }
    missing = []
    for cat, kws in indicators.items():
        if not any(kw in all_queries for kw in kws):
            missing.append(cat)
    assert not missing, f"覆盖缺失类别: {missing}"


# ----------------------------- 3) Pivot 备选 ----------------------------- #


@pytest.mark.asyncio
async def test_plan_contains_pivot_candidates(client: AsyncClient) -> None:
    """§3.2: 至少 1 个 Pivot 备选方向。"""

    pid = await _setup_with_spec(client, "P3_PIVOT")
    r = await client.post(f"/api/v1/projects/{pid}/search/plan")
    plan = r.json()["payload"]
    l6 = next((l for l in plan["query_layers"] if l["layer"] == "L6"), None)
    assert l6 is not None
    assert len(l6["queries"]) >= 1


# ----------------------------- 4) 重复 upsert ----------------------------- #


@pytest.mark.asyncio
async def test_plan_upsert_idempotent(client: AsyncClient) -> None:
    """§3.2: 重复 /search/plan 不出错。"""

    pid = await _setup_with_spec(client, "P3_UPSERT")
    r1 = await client.post(f"/api/v1/projects/{pid}/search/plan")
    r2 = await client.post(f"/api/v1/projects/{pid}/search/plan")
    r3 = await client.post(f"/api/v1/projects/{pid}/search/plan")
    assert r1.status_code == r2.status_code == r3.status_code == 200
    assert r1.json()["maturity_rating"] == r2.json()["maturity_rating"] == r3.json()["maturity_rating"]


# ----------------------------- 5) GET 恢复 ----------------------------- #


@pytest.mark.asyncio
async def test_plan_get_persistence(client: AsyncClient) -> None:
    """§3.2: GET /search/plan 在生成后可恢复。"""

    pid = await _setup_with_spec(client, "P3_GET")
    await client.post(f"/api/v1/projects/{pid}/search/plan")
    r = await client.get(f"/api/v1/projects/{pid}/search/plan")
    assert r.status_code == 200
    assert len(r.json()["payload"]["query_layers"]) == 7
