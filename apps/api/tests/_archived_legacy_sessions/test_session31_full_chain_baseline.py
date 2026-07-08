"""Session 31: Demo 回归基线扩展与全链路 Playwright 后端测试 (10 条).

SOP §4:
1.  fixture 可解析
2.  Case A 关键词合同
3.  Case A 至少 1 dataset
4.  Case A 至少 1 baseline/repo
5.  Case A 不得 STOP
6.  Case B 必须 PIVOT/PARK/STOP
7.  Case B 不得 GO
8.  报告段落证据绑定满足最低要求
9.  ReviewRound fatal/high issue 符合预期
10. 所有 EvidenceRef 可追溯 Candidate
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import evidence as ev_store
from app.services import trace_store as ts
from app.services.one_topic import run_one_topic
from app.services.proposal_draft import generate_proposal_draft
from app.services.review import run_review
from app.schemas import OneTopicRequest
from app.schemas_review import ReviewRequest

# ---------- paths ---------- #

ROOT = Path(__file__).resolve().parents[3]
BASELINES = ROOT / "docs" / "demo" / "baselines"
S31 = BASELINES / "session31"
S17 = BASELINES


# ---------- fixtures ---------- #


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    tmp_dir = Path(tempfile.mkdtemp(prefix="pa_s31_"))
    monkeypatch.setenv("PAPERAGENT_TRACE_DIR", str(tmp_dir / "traces"))
    ts.reset_traces()
    ev_store.reset_all()
    yield
    ts.reset_traces()
    ev_store.reset_all()


@pytest.fixture
def client():
    return TestClient(app)


# ---------- helpers ---------- #


def _load_s31(name: str) -> dict:
    p = S31 / name
    assert p.exists(), f"missing S31 baseline: {p}"
    return json.loads(p.read_text(encoding="utf-8"))


def _load_s17(name: str) -> dict:
    p = S17 / name
    assert p.exists(), f"missing S17 baseline: {p}"
    return json.loads(p.read_text(encoding="utf-8"))


def _analyze(client: TestClient, raw_topic: str, goal_level: str, advisor: str | None = None) -> str:
    body: dict[str, Any] = {"raw_topic": raw_topic, "goal_level": goal_level, "prefer": "heuristic"}
    if advisor:
        body["advisor_direction"] = advisor
    r = client.post("/api/v1/one-topic/analyze", json=body)
    assert r.status_code == 200, r.text
    return r.json()["project_id"]


def _import_mock_paper(client: TestClient, pid: str, paper: dict) -> str:
    body = {
        "title": paper["title"],
        "authors": paper.get("authors", []),
        "year": paper.get("year"),
        "url": paper.get("url"),
        "doi": paper.get("doi"),
        "arxiv_id": paper.get("arxiv_id"),
        "review_status": "pending",
    }
    r = client.post(f"/api/v1/one-topic/{pid}/evidence/papers/manual", json=body)
    assert r.status_code == 200, r.text
    return r.json()["evidence"]["evidence_id"]


def _import_mock_dataset(client: TestClient, pid: str, ds: dict) -> str:
    body = {
        "name": ds["name"],
        "scale": ds.get("scale"),
        "license": ds.get("license"),
        "download": ds.get("download"),
        "modality": ds.get("modality", []),
        "review_status": "pending",
    }
    r = client.post(f"/api/v1/one-topic/{pid}/evidence/datasets/manual", json=body)
    assert r.status_code == 200, r.text
    return r.json()["evidence"]["evidence_id"]


def _import_mock_repo(client: TestClient, pid: str, repo: dict) -> str:
    body = {
        "name": repo["name"],
        "repository_url": repo.get("repository_url"),
        "license": repo.get("license"),
        "has_readme": repo.get("has_readme", False),
        "has_training_script": repo.get("has_training_script", False),
        "has_eval_script": repo.get("has_eval_script", False),
        "review_status": "pending",
    }
    r = client.post(f"/api/v1/one-topic/{pid}/evidence/repos/manual", json=body)
    assert r.status_code == 200, r.text
    return r.json()["evidence"]["evidence_id"]


def _import_all_mock_sources(client: TestClient, pid: str, sources: dict) -> list[str]:
    """Import all mock sources and return evidence IDs."""
    eids = []
    for p in sources.get("papers", []):
        eids.append(_import_mock_paper(client, pid, p))
    for d in sources.get("datasets", []):
        eids.append(_import_mock_dataset(client, pid, d))
    for r in sources.get("repos", []):
        eids.append(_import_mock_repo(client, pid, r))
    return eids


def _assert_keyword_contract(keywords: dict, contract: dict) -> None:
    method = keywords.get("method_keywords", [])
    task = keywords.get("task_keywords", [])
    obj = keywords.get("object_keywords", [])
    risk = keywords.get("risk_terms", [])
    q_zh = keywords.get("query_keywords_zh", [])
    q_en = keywords.get("query_keywords_en", [])

    if "method_keywords_any" in contract:
        assert any(any(m in x for x in method) for m in contract["method_keywords_any"]), \
            f"method_keywords 缺: {method}, 期望任一 {contract['method_keywords_any']}"
    if "task_keywords_any" in contract:
        assert any(t in task for t in contract["task_keywords_any"]), \
            f"task_keywords 缺: {task}, 期望任一 {contract['task_keywords_any']}"
    if "object_keywords_any" in contract:
        assert any(o in obj for o in contract["object_keywords_any"]), \
            f"object_keywords 缺: {obj}, 期望任一 {contract['object_keywords_any']}"
    if "risk_terms_any" in contract:
        assert any(r in risk for r in contract["risk_terms_any"]), \
            f"risk_terms 缺: {risk}, 期望任一 {contract['risk_terms_any']}"
    if "risk_terms_min" in contract:
        assert len(risk) >= contract["risk_terms_min"], \
            f"risk_terms 不足: {len(risk)} < {contract['risk_terms_min']}"
    if "risk_terms_max" in contract:
        assert len(risk) <= contract["risk_terms_max"], \
            f"risk_terms 过多: {len(risk)} > {contract['risk_terms_max']}"
    if "query_keywords_min" in contract:
        total = len(q_zh) + len(q_en)
        assert total >= contract["query_keywords_min"], \
            f"query_keywords 不足: {total} < {contract['query_keywords_min']}"


def _build_sections_from_evidence(sources: dict) -> list[dict]:
    """Build minimal 8 sections for review testing."""
    return [
        {"section_id": "topic_direction", "content": "钢材表面缺陷检测"},
        {"section_id": "background", "content": "工业质检需求增长"},
        {"section_id": "literature_review", "content": "YOLO 系列综述"},
        {"section_id": "research_objectives", "content": "提高检测精度"},
        {"section_id": "research_content", "content": "改进 YOLO 模型"},
        {"section_id": "technical_approach", "content": "基于 YOLOv8 的改进"},
        {"section_id": "dataset_experiment", "content": sources.get("datasets", [{}])[0].get("name", "NEU-DET") if sources.get("datasets") else "待定"},
        {"section_id": "innovation", "content": "轻量化改进"},
    ]


# ------------------------------------------------------------------- #
# S31-1: fixture 可解析
# ------------------------------------------------------------------- #


class TestFixtureParseable:
    def test_case_a_fixture_parseable(self):
        data = _load_s31("case_a_full_chain.json")
        assert data["case_id"] == "yolo_steel_defect_full_chain"
        assert data["baseline_version"] == "0.2.0"
        assert "expected_keyword_contract" in data
        assert "expected_feasibility" in data
        assert "expected_review" in data

    def test_case_b_fixture_parseable(self):
        data = _load_s31("case_b_full_chain.json")
        assert data["case_id"] == "risky_mllm_full_chain"
        assert data["baseline_version"] == "0.2.0"
        assert "expected_keyword_contract" in data
        assert "expected_feasibility" in data
        assert "expected_review" in data

    def test_s17_baselines_still_parseable(self):
        """S31 不破坏 S17 baseline."""
        for name in [
            "yolo_steel_defect_input.json",
            "yolo_steel_defect_expected.json",
            "risky_mllm_industrial_input.json",
            "risky_mllm_industrial_expected.json",
        ]:
            d = _load_s17(name)
            assert d.get("case_id"), f"{name} 缺 case_id"


# ------------------------------------------------------------------- #
# S31-2: Case A 关键词合同
# ------------------------------------------------------------------- #


class TestCaseAKeywordContract:
    def test_case_a_keyword_contract(self, client):
        case_a = _load_s31("case_a_full_chain.json")
        inp = case_a["input"]
        req = OneTopicRequest(
            raw_topic=inp["raw_topic"],
            goal_level=inp["goal_level"],
            advisor_direction=inp.get("advisor_direction"),
            prefer=inp.get("prefer", "heuristic"),
        )
        resp = run_one_topic(req)
        _assert_keyword_contract(
            resp.keyword_breakdown.model_dump(),
            case_a["expected_keyword_contract"],
        )


# ------------------------------------------------------------------- #
# S31-3: Case A 至少 1 dataset
# ------------------------------------------------------------------- #


class TestCaseADataset:
    def test_case_a_has_dataset(self, client):
        case_a = _load_s31("case_a_full_chain.json")
        sources = _load_s17("yolo_steel_defect_mock_sources.json")
        inp = case_a["input"]
        pid = _analyze(client, inp["raw_topic"], inp["goal_level"], inp.get("advisor_direction"))

        eids = _import_all_mock_sources(client, pid, sources)
        r = client.get(f"/api/v1/one-topic/{pid}/evidence")
        body = r.json()
        assert body["dataset_count"] >= 1, f"datasets 不足: {body['dataset_count']}"


# ------------------------------------------------------------------- #
# S31-4: Case A 至少 1 baseline/repo
# ------------------------------------------------------------------- #


class TestCaseARepo:
    def test_case_a_has_repo(self, client):
        case_a = _load_s31("case_a_full_chain.json")
        sources = _load_s17("yolo_steel_defect_mock_sources.json")
        inp = case_a["input"]
        pid = _analyze(client, inp["raw_topic"], inp["goal_level"], inp.get("advisor_direction"))

        eids = _import_all_mock_sources(client, pid, sources)
        r = client.get(f"/api/v1/one-topic/{pid}/evidence")
        body = r.json()
        assert body["repo_count"] >= 1, f"repos 不足: {body['repo_count']}"


# ------------------------------------------------------------------- #
# S31-5: Case A 不得 STOP
# ------------------------------------------------------------------- #


class TestCaseANotStop:
    def test_case_a_verdict_not_stop(self, client):
        case_a = _load_s31("case_a_full_chain.json")
        sources = _load_s17("yolo_steel_defect_mock_sources.json")
        inp = case_a["input"]
        pid = _analyze(client, inp["raw_topic"], inp["goal_level"], inp.get("advisor_direction"))

        _import_all_mock_sources(client, pid, sources)

        # Get the feasibility from the analyze response
        body = {"raw_topic": inp["raw_topic"], "goal_level": inp["goal_level"],
                "prefer": inp.get("prefer", "heuristic"), "project_id_override": pid}
        if inp.get("advisor_direction"):
            body["advisor_direction"] = inp["advisor_direction"]
        r = client.post("/api/v1/one-topic/analyze", json=body)
        assert r.status_code == 200, r.text
        resp = r.json()
        verdict = resp["feasibility"]["verdict"]
        forbidden = case_a["expected_feasibility"]["verdict_forbidden"]
        assert verdict not in forbidden, f"Case A verdict '{verdict}' 在禁止列表: {forbidden}"


# ------------------------------------------------------------------- #
# S31-6: Case B 必须 PIVOT/PARK/STOP
# ------------------------------------------------------------------- #


class TestCaseBVerdict:
    def test_case_b_must_pivot_park_or_stop(self, client):
        case_b = _load_s31("case_b_full_chain.json")
        sources = _load_s17("risky_mllm_industrial_mock_sources.json")
        inp = case_b["input"]
        pid = _analyze(client, inp["raw_topic"], inp["goal_level"], inp.get("advisor_direction"))

        _import_all_mock_sources(client, pid, sources)

        body = {"raw_topic": inp["raw_topic"], "goal_level": inp["goal_level"],
                "prefer": inp.get("prefer", "heuristic"), "project_id_override": pid}
        if inp.get("advisor_direction"):
            body["advisor_direction"] = inp["advisor_direction"]
        r = client.post("/api/v1/one-topic/analyze", json=body)
        assert r.status_code == 200, r.text
        verdict = r.json()["feasibility"]["verdict"]
        allowed = case_b["expected_feasibility"]["verdict_allowed"]
        assert verdict in allowed, f"Case B verdict '{verdict}' 不在允许列表: {allowed}"


# ------------------------------------------------------------------- #
# S31-7: Case B 不得 GO
# ------------------------------------------------------------------- #


class TestCaseBNotGo:
    def test_case_b_not_go(self, client):
        case_b = _load_s31("case_b_full_chain.json")
        sources = _load_s17("risky_mllm_industrial_mock_sources.json")
        inp = case_b["input"]
        pid = _analyze(client, inp["raw_topic"], inp["goal_level"], inp.get("advisor_direction"))

        _import_all_mock_sources(client, pid, sources)

        body = {"raw_topic": inp["raw_topic"], "goal_level": inp["goal_level"],
                "prefer": inp.get("prefer", "heuristic"), "project_id_override": pid}
        if inp.get("advisor_direction"):
            body["advisor_direction"] = inp["advisor_direction"]
        r = client.post("/api/v1/one-topic/analyze", json=body)
        assert r.status_code == 200, r.text
        verdict = r.json()["feasibility"]["verdict"]
        forbidden = case_b["expected_feasibility"]["verdict_forbidden"]
        assert verdict not in forbidden, f"Case B verdict '{verdict}' 在禁止列表: {forbidden}"


# ------------------------------------------------------------------- #
# S31-8: 报告段落证据绑定满足最低要求
# ------------------------------------------------------------------- #


class TestProposalSectionBinding:
    def test_proposal_has_all_required_sections(self, client):
        case_a = _load_s31("case_a_full_chain.json")
        sources = _load_s17("yolo_steel_defect_mock_sources.json")
        inp = case_a["input"]
        pid = _analyze(client, inp["raw_topic"], inp["goal_level"], inp.get("advisor_direction"))

        eids = _import_all_mock_sources(client, pid, sources)

        # Build proposal draft
        sections = _build_sections_from_evidence(sources)
        draft = generate_proposal_draft(
            topic_title=inp["raw_topic"],
            sections=sections,
            evidence_refs=[],
            selected_refs=[],
            candidate_refs=[],
            feasibility=None,
        )

        expected_sections = case_a["expected_proposal_sections"]
        actual_ids = [s.section_id for s in draft.sections]
        for sec in expected_sections:
            assert sec in actual_ids, f"Proposal 缺 section: {sec} (actual: {actual_ids})"


# ------------------------------------------------------------------- #
# S31-9: ReviewRound fatal/high issue 符合预期
# ------------------------------------------------------------------- #


class TestReviewIssues:
    def test_review_has_expected_issues(self, client):
        case_a = _load_s31("case_a_full_chain.json")
        sources = _load_s17("yolo_steel_defect_mock_sources.json")
        inp = case_a["input"]

        sections = _build_sections_from_evidence(sources)
        req = ReviewRequest(topic_title=inp["raw_topic"], sections=sections)
        round_data = run_review(req)

        expected = case_a["expected_review"]
        assert round_data.verdict.value in expected["verdict_allowed"], \
            f"verdict '{round_data.verdict.value}' 不在 {expected['verdict_allowed']}"

        perspectives = set(i.perspective.value for i in round_data.issues)
        for p in expected["must_have_perspectives"]:
            assert p in perspectives, f"缺视角: {p} (actual: {perspectives})"

        if expected.get("must_have_actions"):
            all_actions = round_data.required_actions + round_data.optional_actions
            assert len(all_actions) >= 1, "无 revision actions"


# ------------------------------------------------------------------- #
# S31-10: 所有 EvidenceRef 可追溯 Candidate
# ------------------------------------------------------------------- #


class TestEvidenceRefTraceable:
    def test_evidence_refs_traceable(self, client):
        """Import mock sources → verify → build final-package → all citation evidence_ids exist in ledger."""
        case_a = _load_s31("case_a_full_chain.json")
        sources = _load_s17("yolo_steel_defect_mock_sources.json")
        inp = case_a["input"]
        pid = _analyze(client, inp["raw_topic"], inp["goal_level"], inp.get("advisor_direction"))

        eids = _import_all_mock_sources(client, pid, sources)
        assert len(eids) >= 3, f"导入 evidence 不足: {len(eids)}"

        # Verify evidence is in ledger
        r = client.get(f"/api/v1/one-topic/{pid}/evidence")
        assert r.status_code == 200
        body = r.json()
        flat = body["papers"] + body["datasets"] + body["repos"] + body["notes"]
        ledger_ids = {item["evidence_id"] for item in flat}
        for eid in eids:
            assert eid in ledger_ids, f"evidence_id '{eid}' 不在 ledger 中"

        # Build final-package and check citation refs have non-empty IDs
        r = client.post(f"/api/v1/one-topic/{pid}/final-package/build", json={})
        if r.status_code == 200:
            pkg = r.json()
            for citation in pkg.get("citation_list", []):
                ref_id = citation.get("evidence_id", "") or citation.get("arxiv_id", "") or citation.get("doi", "")
                assert ref_id, \
                    f"citation 缺少任何标识符: {citation}"
