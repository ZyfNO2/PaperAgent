"""Phase 04 §3.3 后续测试：补来源/无法追溯标记 + wp_binding 跨类别断言。

test_phase4_api.py 已覆盖：无 spec 404、无 plan 409、6 类齐全、
baseline 复现难度、upsert、GET 404。这里补 [Phase_02-04_后续测试与验收需求.md] §3.3 剩余验收点。
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


async def _setup_full(client: AsyncClient, case_id: str) -> int:
    pid = (await client.post("/api/v1/projects", json=_ab_intake(case_id))).json()["id"]
    await client.post(
        f"/api/v1/projects/{pid}/topic/decompose", json={"prefer": "heuristic"}
    )
    await client.post(f"/api/v1/projects/{pid}/search/plan")
    return pid


# ----------------------------- 1) 来源/无法追溯标记 ----------------------------- #


@pytest.mark.asyncio
async def test_all_evidence_have_source_field(client: AsyncClient) -> None:
    """§3.3: 每类关键证据必须有 source 或明确标记'无法追溯'。"""

    pid = await _setup_full(client, "P4_SRC")
    r = await client.post(
        f"/api/v1/projects/{pid}/evidence/build", json={"prefer": "heuristic"}
    )
    assert r.status_code == 200
    payload = r.json()["payload"]

    # 论文 evidence 必含 source
    for p in payload["papers"]:
        assert p.get("source"), f"论文 {p.get('paper_id')} 缺 source"

    # 综述
    for s in payload["surveys"]:
        assert s.get("source"), f"综述 {s.get('paper_id')} 缺 source"

    # dataset 不强制 source 但需有可追溯字段（name + scale/license/download 任一）
    for d in payload["datasets"]:
        ok = d.get("name") and (d.get("scale") or d.get("license") or d.get("download") or d.get("modality"))
        assert ok, f"dataset {d.get('dataset_id')} 缺可追溯字段"

    # baseline 必含 repository_url 或 paper_title
    for b in payload["baselines"]:
        assert b.get("repository_url") or b.get("paper_title"), (
            f"baseline {b.get('baseline_id')} 缺 repository_url 与 paper_title"
        )


# ----------------------------- 2) wp_binding 跨类别 ----------------------------- #


@pytest.mark.asyncio
async def test_wp_binding_consistent_across_evidence_types(client: AsyncClient) -> None:
    """§3.3: 证据账本应能绑定到工作包。

    heuristic 模式下，每个 WP 至少应在以下任一类别（papers/datasets/baselines）
    出现 wp_binding 标记。
    """

    pid = await _setup_full(client, "P4_BIND")
    r = await client.post(
        f"/api/v1/projects/{pid}/evidence/build", json={"prefer": "heuristic"}
    )
    payload = r.json()["payload"]
    wp_seen: set[str] = set()
    for p in payload["papers"]:
        wp_seen.update(p.get("wp_binding") or [])
    for d in payload["datasets"]:
        wp_seen.update(d.get("wp_binding") or [])
    for b in payload["baselines"]:
        wp_seen.update(b.get("wp_binding") or [])
    # 至少 WP1 / WP2 都被绑到
    assert "WP1" in wp_seen, f"WP1 未被任何 evidence 绑定 (seen={wp_seen})"
    assert "WP2" in wp_seen, f"WP2 未被任何 evidence 绑定 (seen={wp_seen})"


# ----------------------------- 3) 风险 flags 必含来源信息 ----------------------------- #


@pytest.mark.asyncio
async def test_risk_flags_have_meaningful_messages(client: AsyncClient) -> None:
    """§3.3: 风险 flags 是字符串列表，不能为空字符串。"""

    pid = await _setup_full(client, "P4_FLAGS")
    r = await client.post(
        f"/api/v1/projects/{pid}/evidence/build", json={"prefer": "heuristic"}
    )
    risk_flags = r.json()["risk_flags"]
    # heuristic 模式默认 A 评级 → 应当是空列表
    assert isinstance(risk_flags, list)
    # 若有 flag，必是非空字符串
    for f in risk_flags:
        assert isinstance(f, str) and f.strip() != ""


# ----------------------------- 4) GET 恢复 + 内容一致 ----------------------------- #


@pytest.mark.asyncio
async def test_evidence_get_persistence(client: AsyncClient) -> None:
    """§3.3: /evidence/ledger 未生成时返 404，生成后可恢复。"""

    pid = await _setup_full(client, "P4_PERSIST")
    # 第一次 GET
    r = await client.get(f"/api/v1/projects/{pid}/evidence/ledger")
    assert r.status_code == 404

    # 生成
    await client.post(
        f"/api/v1/projects/{pid}/evidence/build", json={"prefer": "heuristic"}
    )

    # 第二次 GET 拿到
    r = await client.get(f"/api/v1/projects/{pid}/evidence/ledger")
    assert r.status_code == 200
    j = r.json()
    assert j["project_id"] == str(pid)
    assert j["paper_count"] >= 5


# ----------------------------- 5) 评级与 outcome 一致 ----------------------------- #


@pytest.mark.asyncio
async def test_evidence_rating_equals_risk_flags_state(client: AsyncClient) -> None:
    """heuristic 模式下默认 A 评级 → risk_flags 为空。"""

    pid = await _setup_full(client, "P4_RATE")
    r = await client.post(
        f"/api/v1/projects/{pid}/evidence/build", json={"prefer": "heuristic"}
    )
    j = r.json()
    assert j["evidence_rating"] == "A"
    assert j["risk_flags"] == []
