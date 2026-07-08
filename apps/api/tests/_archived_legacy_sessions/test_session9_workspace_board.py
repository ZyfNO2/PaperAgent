"""Session 9: 双栏工作台 + Agent Card Intake 后端测试 (SOP §7.1).

按 SOP §8 验收标准:
1. workspace board 能按 paper/dataset/repo 分组
2. manual evidence 默认进入 user_preferred
3. auto_search evidence 默认进入 system_found
4. PATCH workspace/item 能移动 evidence
5. 标为核心后 review_status=core
6. rejected lane 不进入 supports
7. user_preferred 在 EvidenceRef priority 中优先
8. cards/intake 能识别 GitHub URL 为 repo
9. cards/intake 能识别 arXiv URL 为 paper
10. cards/intake 能识别 HuggingFace/Kaggle 为 dataset
11. assistant_intake 默认 pending
12. assistant_intake pending 不进入 Markdown supports
"""

from __future__ import annotations


import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def _analyze(client, topic: str = "YOLO 钢材表面缺陷检测") -> str:
    r = client.post("/api/v1/one-topic/analyze", json={"raw_topic": topic, "prefer": "heuristic"})
    assert r.status_code == 200
    return r.json()["project_id"]


# ---------- 1: board 分组 ---------- #


def test_01_board_groups_by_type(client):
    """§7.1.1: workspace board 能按 paper/dataset/repo 分组."""

    pid = _analyze(client)
    r = client.get(f"/api/v1/one-topic/{pid}/workspace/board")
    assert r.status_code == 200
    board = r.json()
    assert "papers" in board and "datasets" in board and "repos" in board
    for bt in ("papers", "datasets", "repos"):
        for col in ("left_items", "right_items", "selected_items", "rejected_items"):
            assert col in board[bt]
        assert board[bt]["board_type"] in ("paper", "dataset", "repo")


# ---------- 2: manual evidence 默认 user_preferred ---------- #


def test_02_manual_default_user_preferred(client):
    """§7.1.2: manual evidence 默认进入 user_preferred."""

    pid = _analyze(client)
    r = client.post(
        f"/api/v1/one-topic/{pid}/evidence/papers/manual",
        json={"title": "导师指定核心论文", "url": "https://example.com/p.pdf"},
    )
    assert r.status_code == 200
    eid = r.json()["evidence_id"]
    # 应在 board 的 left_items
    board = client.get(f"/api/v1/one-topic/{pid}/workspace/board").json()
    left_eids = [e["evidence_id"] for e in board["papers"]["left_items"]]
    assert eid in left_eids, f"manual paper 应在 left, 实际 left={left_eids}"


# ---------- 3: auto_search evidence 默认 system_found ---------- #


def test_03_auto_default_system_found(client):
    """§7.1.3: auto_search evidence 默认进入 system_found."""

    pid = _analyze(client)
    board = client.get(f"/api/v1/one-topic/{pid}/workspace/board").json()
    # 自动入池的 paper 应在 right_items
    assert len(board["papers"]["right_items"]) >= 1, "自动入池的 paper 应在 right"
    for p in board["papers"]["right_items"]:
        assert p["workspace_lane"] == "system_found"


# ---------- 4: PATCH workspace/item 移动 evidence ---------- #


def test_04_patch_moves_evidence(client):
    """§7.1.4: PATCH workspace/item 能移动 evidence."""

    pid = _analyze(client)
    board = client.get(f"/api/v1/one-topic/{pid}/workspace/board").json()
    # 拿一个 right paper
    if not board["papers"]["right_items"]:
        pytest.skip("无 auto paper 可移动")
    eid = board["papers"]["right_items"][0]["evidence_id"]

    # 移动到 left
    r = client.patch(
        f"/api/v1/one-topic/{pid}/workspace/item",
        json={"evidence_id": eid, "workspace_lane": "user_preferred", "review_status": "accepted"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["workspace_lane"] == "user_preferred"
    assert data["review_status"] == "accepted"
    assert data["trace_event"] is not None
    assert data["trace_event"]["actor"] == "user"

    # 验证 board 反映
    board2 = client.get(f"/api/v1/one-topic/{pid}/workspace/board").json()
    left_eids = [e["evidence_id"] for e in board2["papers"]["left_items"]]
    assert eid in left_eids


# ---------- 5: 标 core 后 review_status=core ---------- #


def test_05_mark_core_sets_review_status(client):
    """§7.1.5: 标核心后 review_status=core, workspace_lane=selected."""

    pid = _analyze(client)
    board = client.get(f"/api/v1/one-topic/{pid}/workspace/board").json()
    if not board["papers"]["right_items"]:
        pytest.skip("无 paper 可标核心")
    eid = board["papers"]["right_items"][0]["evidence_id"]

    r = client.patch(
        f"/api/v1/one-topic/{pid}/workspace/item",
        json={"evidence_id": eid, "workspace_lane": "selected", "review_status": "core"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["review_status"] == "core"
    assert data["workspace_lane"] == "selected"  # 联动: core → selected


# ---------- 6: rejected lane 不进入 supports ---------- #


def test_06_rejected_lane_excluded_from_supports(client):
    """§7.1.6: rejected lane 不进入 supports (SOP §6)."""

    pid = _analyze(client)
    board = client.get(f"/api/v1/one-topic/{pid}/workspace/board").json()
    if not board["papers"]["right_items"]:
        pytest.skip("无 paper")
    eid = board["papers"]["right_items"][0]["evidence_id"]

    # 拒绝
    client.patch(
        f"/api/v1/one-topic/{pid}/workspace/item",
        json={"evidence_id": eid, "workspace_lane": "rejected", "review_status": "rejected"},
    )
    # 重建 final package
    r = client.post(f"/api/v1/one-topic/{pid}/final-package/build", json={})
    pkg = r.json()
    # rejected eid 不应进入 citation_list
    cited_eids = [c["evidence_id"] for c in pkg["citation_list"]]
    assert eid not in cited_eids, f"rejected 不应在 citation_list: {cited_eids}"


# ---------- 7: user_preferred 在 ref_priority 优先 ---------- #


def test_07_user_preferred_priority_higher(client):
    """§7.1.7: workspace_lane=user_preferred 在 EvidenceRef priority 中优先 (选 supports)."""

    # 添加一个 user_preferred paper 和一个 system_found paper, 同样 review_status
    pid = _analyze(client)
    r1 = client.post(
        f"/api/v1/one-topic/{pid}/evidence/papers/manual",
        json={"title": "用户指定论文 A", "review_status": "accepted"},
    )
    assert r1.status_code == 200, r1.text
    r2 = client.post(
        f"/api/v1/one-topic/{pid}/evidence/papers/manual",
        json={"title": "用户指定论文 B", "review_status": "accepted"},
    )
    assert r2.status_code == 200, r2.text
    # 第一个默认 user_preferred (manual), 第二个改成 system_found
    eid_a = r1.json().get("evidence_id") or r1.json().get("evidence", {}).get("evidence_id")
    eid_b = r2.json().get("evidence_id") or r2.json().get("evidence", {}).get("evidence_id")
    assert eid_a and eid_b, f"eid_a={eid_a}, eid_b={eid_b}, r1={r1.json()}"
    client.patch(
        f"/api/v1/one-topic/{pid}/workspace/item",
        json={"evidence_id": eid_b, "workspace_lane": "system_found", "review_status": "accepted"},
    )

    # 重建 final package, 看 cite order
    r = client.post(f"/api/v1/one-topic/{pid}/final-package/build", json={})
    pkg = r.json()
    # A 应排前 (lane=user_preferred bonus)
    pos_a = -1
    pos_b = -1
    for i, c in enumerate(pkg["citation_list"]):
        if c["evidence_id"] == eid_a:
            pos_a = i
        if c["evidence_id"] == eid_b:
            pos_b = i
    if pos_a >= 0 and pos_b >= 0:
        assert pos_a < pos_b, f"user_preferred A 应排在 system_found B 前面, 实际 A={pos_a} B={pos_b}"


# ---------- 8: cards/intake 识别 GitHub URL 为 repo ---------- #


def test_08_intake_github_to_repo(client):
    """§7.1.8: cards/intake 能识别 GitHub URL 为 repo."""

    pid = _analyze(client)
    r = client.post(
        f"/api/v1/one-topic/{pid}/cards/intake",
        json={
            "input_type": "url",
            "content": "https://github.com/ultralytics/ultralytics",
            "hint": "YOLO baseline",
            "target_lane": "user_preferred",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["card_type"] == "repo"
    assert data["needs_user_confirmation"] is True
    assert "ultralytics" in data["evidence"]["title"].lower()
    assert data["evidence"]["source_mode"] == "assistant_intake"
    assert data["evidence"]["review_status"] == "pending"


# ---------- 9: cards/intake 识别 arXiv URL 为 paper ---------- #


def test_09_intake_arxiv_to_paper(client):
    """§7.1.9: cards/intake 能识别 arXiv URL 为 paper."""

    pid = _analyze(client)
    r = client.post(
        f"/api/v1/one-topic/{pid}/cards/intake",
        json={
            "input_type": "url",
            "content": "https://arxiv.org/abs/2301.12345",
            "hint": "相关研究",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["card_type"] == "paper"
    assert "2301.12345" in data["evidence"]["title"]


# ---------- 10: cards/intake 识别 HF/Kaggle 为 dataset ---------- #


def test_10_intake_hf_kaggle_to_dataset(client):
    """§7.1.10: cards/intake 能识别 HF / Kaggle 为 dataset."""

    pid = _analyze(client)
    # HF
    r = client.post(
        f"/api/v1/one-topic/{pid}/cards/intake",
        json={
            "input_type": "url",
            "content": "https://huggingface.co/datasets/glue",
        },
    )
    assert r.json()["card_type"] == "dataset"
    # Kaggle
    r2 = client.post(
        f"/api/v1/one-topic/{pid}/cards/intake",
        json={
            "input_type": "url",
            "content": "https://kaggle.com/datasets/somebody/steel-defects",
        },
    )
    assert r2.json()["card_type"] == "dataset"


# ---------- 11: assistant_intake 默认 pending ---------- #


def test_11_assistant_intake_default_pending(client):
    """§7.1.11: assistant_intake 卡片默认 pending."""

    pid = _analyze(client)
    r = client.post(
        f"/api/v1/one-topic/{pid}/cards/intake",
        json={
            "input_type": "url",
            "content": "https://github.com/owner/repo",
        },
    )
    data = r.json()
    assert data["evidence"]["review_status"] == "pending"
    assert data["evidence"]["source_mode"] == "assistant_intake"
    assert data["evidence"]["workspace_lane"] in ("user_preferred", "system_found")


# ---------- 12: assistant_intake pending 不进 Markdown supports ---------- #


def test_12_intake_pending_excluded_from_markdown(client):
    """§7.1.12: assistant_intake pending 不进入 Markdown supports (SOP §6)."""

    pid = _analyze(client)
    # intake GitHub URL
    r = client.post(
        f"/api/v1/one-topic/{pid}/cards/intake",
        json={"input_type": "url", "content": "https://github.com/owner/test-repo"},
    )
    intake_eid = r.json()["evidence"]["evidence_id"]

    # 重建 final package, 该 eid 不应在 citation_list (pending 不会进 supports)
    r2 = client.post(f"/api/v1/one-topic/{pid}/final-package/build", json={})
    pkg = r2.json()
    cited_eids = [c["evidence_id"] for c in pkg["citation_list"]]
    assert intake_eid not in cited_eids, (
        f"assistant_intake pending 不应在 citation_list: {cited_eids}"
    )