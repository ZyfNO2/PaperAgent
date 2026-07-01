"""Re02 end-to-end science-skill cases (run_research_agent_re02).

Covers 4 cases via run_research_agent_re02 with SESSION66_LLM_BUDGET=0:
A. 3D-vision damage detection
B. U-Net steel crack segmentation
C. LLM Chinese subjective scoring
D. Multi-temporal remote-sensing crop
"""

from __future__ import annotations

import os

import pytest

from app.services.agents.research_agent import (
    reset_counter,
    run_research_agent_re02,
)


pytestmark = [pytest.mark.re02, pytest.mark.asyncio]


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("SESSION66_LLM_BUDGET", "0")
    reset_counter()
    yield
    reset_counter()
    monkeypatch.delenv("SESSION66_LLM_BUDGET", raising=False)


async def test_case_a_3d_damage_detection_has_pool_rows():
    result = await run_research_agent_re02("基于三维成像的智能损伤检测")
    d = result.to_dict()
    assert d["candidate_pool"]
    pool_types = {c["evidence_type"] for c in d["candidate_pool"]}
    syn = d["synthesis"]
    assert (len(syn.get("manual_questions") or []) >= 1) or bool(syn.get("baseline_options"))
    assert "paper" in pool_types or "repo" in pool_types


async def test_case_b_unet_steel_crack_has_paper():
    result = await run_research_agent_re02("基于Unet的钢材裂缝分割")
    d = result.to_dict()
    pool_types = {c["evidence_type"] for c in d["candidate_pool"]}
    assert "paper" in pool_types
    statuses = {r["status"] for r in d["evidence_review"]}
    assert {"core", "candidate", "needs_manual", "rejected"} & statuses


async def test_case_c_llm_chinese_scoring_has_direction_and_pool():
    result = await run_research_agent_re02("基于大语言模型的中文主观题自动评分")
    d = result.to_dict()
    assert d["synthesis"]["direction_recommendation"] != ""
    assert len(d["candidate_pool"]) >= 1


async def test_case_d_multi_temporal_remote_sensing_has_paper_groups():
    result = await run_research_agent_re02("基于多时相遥感数据的作物早期识别")
    d = result.to_dict()
    syn = d["synthesis"]
    assert isinstance(syn["risk_reminders"], list)
    pg = syn["paper_groups"]
    assert isinstance(pg, dict)
    for k in ("baseline", "parallel", "reference", "long_tail_candidates"):
        assert k in pg
