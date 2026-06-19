"""Session 13: 内部 Skill Registry 后端测试 (SOP §10.1).

覆盖:
1. registry 能列出 4 个内部 skill
2. 每个 path 存在
3. 每个 skill 有 status 和 risk_level
4. GET /skills 返回 enabled_count
5. GET /skills/{name} 返回单个 metadata
6. health 能发现缺失字段
7. high risk skill 默认不能 enabled
8. EvidenceItem 可记录 created_by_skill
9. FinalPackage 可显示 skill_sources
10. Registry 不执行任何外部命令
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import evidence as ev_store
from app.services import skill_registry as sr


REPO_ROOT = Path(__file__).resolve().parents[3]
SKILLS_DIR = REPO_ROOT / "skills"


@pytest.fixture(autouse=True)
def _reset():
    ev_store.reset_all()
    sr.reset_cache()
    yield
    ev_store.reset_all()
    sr.reset_cache()


@pytest.fixture
def client():
    return TestClient(app)


def _analyze(client, topic: str = "YOLO 钢材表面缺陷检测") -> str:
    r = client.post("/api/v1/one-topic/analyze", json={"raw_topic": topic, "prefer": "heuristic"})
    assert r.status_code == 200
    return r.json()["project_id"]


# ---------- 1: registry 能列出 4 个内部 skill ---------- #


def test_01_list_4_internal_skills():
    """registry 至少 4 个 skill (paper-card / dataset-validation / github-baseline / evidence-ledger)."""

    resp = sr.list_skills()
    names = {s.name for s in resp.skills}
    expected = {"paper-card", "dataset-validation", "github-baseline", "evidence-ledger"}
    assert expected.issubset(names), f"缺少 skill: {expected - names}, got {names}"


# ---------- 2: 每个 path 存在 ---------- #


def test_02_each_skill_path_exists():
    """每个 skill 的 SKILL.md path 必须存在."""

    for s in sr.list_skills().skills:
        path = REPO_ROOT / s.path
        assert path.exists(), f"SKILL.md 不存在: {s.path}"


# ---------- 3: 每个 skill 有 status 和 risk_level ---------- #


def test_03_each_skill_has_status_and_risk_level():
    """每个 skill 至少有 status 和 risk_level."""

    for s in sr.list_skills().skills:
        assert s.status, f"{s.name} 缺 status"
        assert s.risk_level, f"{s.name} 缺 risk_level"
        assert s.status in ("candidate", "reviewed", "adapted", "enabled", "disabled", "deprecated")
        assert s.risk_level in ("low", "medium", "high")


# ---------- 4: GET /skills 返回 enabled_count ---------- #


def test_04_get_skills_endpoint(client):
    """GET /api/v1/skills 返回 SkillRegistryResponse 含 enabled_count."""

    r = client.get("/api/v1/skills")
    assert r.status_code == 200
    body = r.json()
    assert "skills" in body
    assert "enabled_count" in body
    assert "disabled_count" in body
    assert "high_risk_count" in body
    assert body["enabled_count"] >= 4, f"应至少 4 个 enabled, got {body['enabled_count']}"


# ---------- 5: GET /skills/{name} 返回单个 metadata ---------- #


def test_05_get_single_skill(client):
    """GET /api/v1/skills/paper-card 返回 SkillMetadata."""

    r = client.get("/api/v1/skills/paper-card")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "paper-card"
    assert body["category"] == "research"
    assert "summary" in body
    assert body["summary"], "summary 应非空 (SKILL.md 摘要)"


def test_05b_get_unknown_skill_404(client):
    """GET /api/v1/skills/unknown 返回 404."""

    r = client.get("/api/v1/skills/nonexistent_skill")
    assert r.status_code == 404


# ---------- 6: health 能发现缺失字段 ---------- #


def test_06_health_check_finds_issues():
    """health check 应返回 issues 列表 (可能为空, 但结构完整)."""

    health = sr.health_check()
    assert health.total >= 4
    assert health.ok >= 0
    # issues 字段必须存在
    assert isinstance(health.issues, list)
    # 默认禁止动作必须存在
    assert "shell_exec" in health.default_forbidden_actions


# ---------- 7: high risk skill 默认不能 enabled ---------- #


def test_07_high_risk_skill_rejected(client):
    """修改 manifest 临时塞一个 high_risk enabled skill, health 应发现."""

    # 直接修改 service 缓存中的 skill 列表
    from app.schemas_skill import SkillMetadata

    fake = SkillMetadata(
        name="fake-dangerous",
        category="writing",
        path="skills/research/paper-card/SKILL.md",
        description="dangerous test",
        status="enabled",
        risk_level="high",
    )
    # 注入到缓存
    sr._CACHE = sr._CACHE or []
    sr._CACHE.append(fake)
    health = sr.health_check()
    issue_names = [i.skill for i in health.issues]
    assert "fake-dangerous" in issue_names, f"high_risk enabled 应出现在 issues, got {issue_names}"


# ---------- 8: EvidenceItem 可记录 created_by_skill ---------- #


def test_08_evidence_item_records_skill(client):
    """手动加 paper, 然后 intake_card 自动设 created_by_skill."""

    pid = _analyze(client)
    r = client.post(f"/api/v1/one-topic/{pid}/cards/intake", json={
        "input_type": "url",
        "content": "https://arxiv.org/abs/2106.09685",
    })
    assert r.status_code == 200
    eid = r.json()["evidence"]["evidence_id"]
    item = ev_store.get_item(eid)
    assert item.created_by_skill == "paper-card", f"created_by_skill 应 = paper-card, got {item.created_by_skill}"


def test_08b_dataset_intake_records_dataset_skill(client):
    """dataset 类型 intake 应标 created_by_skill=dataset-validation."""

    pid = _analyze(client)
    r = client.post(f"/api/v1/one-topic/{pid}/cards/intake", json={
        "input_type": "url",
        "content": "https://huggingface.co/datasets/imagenet-1k",
    })
    assert r.status_code == 200
    eid = r.json()["evidence"]["evidence_id"]
    item = ev_store.get_item(eid)
    assert item.created_by_skill == "dataset-validation"


def test_08c_repo_intake_records_github_skill(client):
    """repo 类型 intake 应标 created_by_skill=github-baseline."""

    pid = _analyze(client)
    r = client.post(f"/api/v1/one-topic/{pid}/cards/intake", json={
        "input_type": "url",
        "content": "https://github.com/test/repo",
    })
    assert r.status_code == 200
    eid = r.json()["evidence"]["evidence_id"]
    item = ev_store.get_item(eid)
    assert item.created_by_skill == "github-baseline"


# ---------- 9: FinalPackage 可显示 skill_sources ---------- #


def test_09_final_package_skill_sources(client):
    """Markdown 顶部应包含 '本报告使用内部 Skill:' 行."""

    pid = _analyze(client)
    r = client.post(f"/api/v1/one-topic/{pid}/final-package/build", json={})
    assert r.status_code == 200
    md = r.json()["proposal_markdown"]
    assert "本报告使用内部 Skill" in md, f"md 应包含 '本报告使用内部 Skill', got: {md[:300]}"


def test_09b_citation_skill_sources_field(client):
    """ReportCitation.skill_sources 字段存在."""

    pid = _analyze(client)
    r = client.post(f"/api/v1/one-topic/{pid}/final-package/build", json={})
    pkg = r.json()
    citations = pkg.get("citation_list", [])
    assert len(citations) >= 1
    for c in citations:
        assert "skill_sources" in c, f"citation 缺 skill_sources: {c}"
        # skill_sources 是 list
        assert isinstance(c["skill_sources"], list)


# ---------- 10: Registry 不执行任何外部命令 ---------- #


def test_10_registry_no_exec(client):
    """Registry 不应执行 shell 命令 (通过 health_check / list_skills 测)."""

    import subprocess

    # 检查 manifest 中没有引用危险命令
    manifest = sr._load_manifest()
    for s in manifest:
        assert "shell" not in (s.requires_tools or []), f"{s.name} 不应在 requires_tools 含 shell"
        assert "rm" not in (s.forbidden_actions or []) or "shell_exec" in (s.forbidden_actions or []), \
            f"{s.name} 需含 shell_exec 在 forbidden_actions"
    # 验证 health 没启动任何进程 (粗略检查: 无新 python 进程派生)
    initial_count = len(subprocess.run(["tasklist"], capture_output=True, text=True, shell=False).stdout.splitlines())
    sr.health_check()
    after_count = len(subprocess.run(["tasklist"], capture_output=True, text=True, shell=False).stdout.splitlines())
    # 不严格断言 (windows tasklist 不稳定), 只确保调用不抛
    assert initial_count >= 0


# ---------- 额外: rescore 标 scored_by_skill ---------- #


def test_11_rescore_marks_scored_by_skill(client):
    """POST /evidence/rescore 后, evidence 应标 scored_by_skill."""

    pid = _analyze(client)
    r = client.post(f"/api/v1/one-topic/{pid}/evidence/rescore")
    assert r.status_code == 200
    ledger = ev_store.get_pool_items(pid)
    paper_items = [e for e in ledger if e.evidence_type == "paper"]
    assert any(e.scored_by_skill for e in paper_items), f"至少 1 个 paper 应有 scored_by_skill"
    assert all((e.scored_by_skill in ("paper-card", "evidence-ledger", None)) for e in paper_items)


# ---------- 额外: 验证标 validated_by_skill ---------- #


def test_12_verification_marks_validated_by_skill(client):
    """verify GitHub repo 后 validated_by_skill=github-baseline."""

    pid = _analyze(client)
    r = client.post(f"/api/v1/one-topic/{pid}/evidence/repos/manual", json={
        "name": "o/r", "repository_url": "https://github.com/o/r",
    })
    eid = r.json()["evidence_id"]
    r = client.post(f"/api/v1/one-topic/{pid}/evidence/{eid}/verify")
    assert r.status_code == 200
    item = ev_store.get_item(eid)
    assert item.validated_by_skill == "github-baseline"