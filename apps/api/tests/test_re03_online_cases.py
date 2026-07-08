"""Re03 SOP §6.2: V3/V4 real cases (LLM-online).

These run with the LLM online (MiniMax M3). With `SESSION66_LLM_BUDGET=0`
they short-circuit to heuristic and assert connectivity only.

The 4 cases are the SOP-required domains:
  A. 基于三维成像的智能损伤检测   (vision_3d)
  B. 基于Unet的钢材裂缝分割      (vision_2d)
  C. 基于大语言模型的中文主观题自动评分 (nlp_llm)
  D. 基于多时相遥感数据的作物早期识别  (remote_sensing)
"""

import os
import pytest

from app.services.agents.research_agent import run_research_agent_re02, reset_counter


CASES = [
    ("A_3d_damage", "基于三维成像的智能损伤检测"),
    ("B_unet_steel", "基于Unet的钢材裂缝分割"),
    ("C_llm_chinese_scoring", "基于大语言模型的中文主观题自动评分"),
    ("D_remote_sensing_crop", "基于多时相遥感数据的作物早期识别"),
]


def _run_one(topic: str) -> dict:
    reset_counter()
    import asyncio
    return asyncio.run(run_research_agent_re02(topic, auto_low_bar=True)).to_dict()


def test_case_a_3d_damage_query_atoms_english_not_machine_learning():
    """The Re02 bug: heuristic fallback made query_atoms_en = 'machine
    learning'. With LLM online, query_atoms_en must contain domain terms
    (point cloud / damage / LiDAR / etc.)."""
    if os.environ.get("SESSION66_LLM_BUDGET") == "0":
        pytest.skip("LLM-dead path: skipping English-atom check")
    d = _run_one("基于三维成像的智能损伤检测")
    parsed = d["parsed_topic"]
    atoms = parsed.get("query_atoms_en") or []
    assert atoms, "query_atoms_en must be non-empty"
    # Must contain at least one domain-specific term
    blob = " ".join(atoms).lower()
    assert any(t in blob for t in ("point cloud", "damage", "lidar", "voxel", "mesh", "3d")), \
        f"no domain term in query_atoms_en: {atoms}"


def test_case_b_unet_steel_real_baseline_present():
    """Re02 Case B found a real U-Net steel crack paper. With LLM online
    this should still be there (Case A noise must not leak to Case B)."""
    d = _run_one("基于Unet的钢材裂缝分割")
    cp = d["candidate_pool"]
    titles = " ".join((c.get("title") or "").lower() for c in cp)
    # Look for any U-Net / crack / steel / segment title
    assert any(t in titles for t in ("u-net", "unet", "crack", "steel", "segmentation")), \
        f"no U-Net/crack/steel/segmentation in Case B pool: {titles[:200]}"


def test_case_c_llm_chinese_scoring_real_paper():
    d = _run_one("基于大语言模型的中文主观题自动评分")
    cp = d["candidate_pool"]
    titles = " ".join((c.get("title") or "").lower() for c in cp)
    # LLM dead path returns awesome-machine-learning etc.
    if os.environ.get("SESSION66_LLM_BUDGET") == "0":
        pytest.skip("LLM-dead path: skipping real-paper check")
    assert "awesome-machine-learning" not in titles, "LLM-dead path noise leaked"
    assert "changing data sources" not in titles, "LLM-dead path noise leaked"


def test_case_d_multi_temporal_remote_sensing_real_paper():
    d = _run_one("基于多时相遥感数据的作物早期识别")
    cp = d["candidate_pool"]
    titles = " ".join((c.get("title") or "").lower() for c in cp)
    if os.environ.get("SESSION66_LLM_BUDGET") == "0":
        pytest.skip("LLM-dead path: skipping real-paper check")
    assert "awesome-machine-learning" not in titles, "LLM-dead path noise leaked"
    assert "changing data sources" not in titles, "LLM-dead path noise leaked"


def test_round_delta_field_present_in_result():
    """Re03 SOP §1.6: every 完工报告 must have per-round data delta."""
    d = _run_one("基于Unet的钢材裂缝分割")
    assert "round_delta" in d, "AgentResultRe02 must expose round_delta"
    # round_delta should mention at least one round name
    assert isinstance(d["round_delta"], dict)
