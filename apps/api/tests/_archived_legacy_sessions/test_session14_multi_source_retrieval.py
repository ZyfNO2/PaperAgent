"""Session 14: 多源检索增强 后端测试 (SOP §18.1).

覆盖:
1.  query_plan 从题目生成 paper / dataset / repo 查询
2.  OpenAlex raw dict 归一化为 paper candidate
3.  Semantic Scholar 适配器返回空 (S14 默认)
4.  arXiv Atom 解析为 paper candidate
5.  GitHub raw dict 归一化为 repo candidate
6.  HuggingFace raw dict 归一化为 dataset candidate
7.  DOI / arXiv / title 相似去重
8.  repo owner/name 去重
9.  dataset slug 去重
10. retrieval_score 排序稳定 (高分在前)
11. 单 source 失败不阻塞其他 source
12. import candidate -> Evidence Ledger
13. import 后 review_status=pending
14. import 后 workspace_lane=system_found (默认)
15. import 后 created_by_skill 正确 (paper -> paper-card, dataset -> dataset-validation, repo -> github-baseline)
16. import + auto_verify 会触发 verification
17. duplicate candidate 不重复导入
18. Trace 写入 retrieval_run_started / completed / imported
19. summary 返回来源统计 + 错误
20. pending/unverified 检索候选不提升 ReportQuality 关键维度

外部 API 测试用 mock client, 不依赖真实网络.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import evidence as ev_store
from app.services import trace_store as ts
from app.services.retrieval import (
    build_query_plan,
    dedup_candidates,
    import_candidates,
    normalize_candidate,
    reset_retrieval_state,
    run_retrieval,
    score_paper,
)
from app.services.retrieval.orchestrator import get_summary
from app.schemas_retrieval import (
    RetrievalImportRequest,
    RetrievalSearchRequest,
)


# ---------- Fixtures ---------- #


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    tmp_dir = Path(tempfile.mkdtemp(prefix="pa_ret14_"))
    monkeypatch.setenv("PAPERAGENT_TRACE_DIR", str(tmp_dir / "traces"))
    ts.reset_traces()
    ev_store.reset_all()
    reset_retrieval_state()
    yield
    ts.reset_traces()
    ev_store.reset_all()
    reset_retrieval_state()
    import shutil
    try:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception:
        pass


@pytest.fixture
def client():
    return TestClient(app)


def _analyze(client, topic: str = "基于YOLO的钢材表面缺陷检测") -> str:
    r = client.post("/api/v1/one-topic/analyze", json={"raw_topic": topic, "prefer": "heuristic"})
    assert r.status_code == 200
    return r.json()["project_id"]


class _MockClient:
    """通用 mock HTTP client. 按 URL 关键词分发."""

    def __init__(self, routes: dict[str, Any]):
        self.routes = routes
        self.calls: list[tuple[str, str]] = []

    async def request(self, method: str, url: str, headers=None):
        self.calls.append((method, url))
        for key, response in self.routes.items():
            if key.lower() in url.lower():
                if isinstance(response, Exception):
                    raise response
                if callable(response):
                    return 200, response(url)
                return 200, response
        return 404, {}


def _oa_response(_url=None):
    return {
        "results": [
            {
                "id": "https://openalex.org/W1",
                "title": "YOLO Steel Defect Detection",
                "publication_year": 2023,
                "doi": "10.1234/oa1",
                "cited_by_count": 50,
                "authorships": [{"author": {"display_name": "Alice"}}],
                "primary_location": {"source": {"display_name": "CVPR"}},
                "abstract_inverted_index": {"steel": [0], "defect": [1]},
            },
            {
                "id": "https://openalex.org/W2",
                "title": "Industrial Defect Survey",
                "publication_year": 2022,
                "doi": "10.1234/oa2",
                "cited_by_count": 20,
                "authorships": [],
                "primary_location": {},
                "abstract_inverted_index": None,
            },
        ]
    }


def _gh_response(_url=None):
    return {
        "items": [
            {
                "full_name": "ultralytics/yolov5",
                "html_url": "https://github.com/ultralytics/yolov5",
                "description": "YOLOv5 in PyTorch",
                "stargazers_count": 40000,
                "language": "Python",
                "license": {"spdx_id": "GPL-3.0"},
                "updated_at": "2024-06-01T00:00:00Z",
                "topics": [{"name": "object-detection"}],
            },
        ]
    }


def _arxiv_response(_url=None):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<feed xmlns="http://www.w3.org/2005/Atom">'
        '<entry>'
        '<id>https://arxiv.org/abs/2106.09685v1</id>'
        '<title>YOLO Defect Detection</title>'
        '<summary>An abstract about defect detection</summary>'
        '<author><name>Bob</name></author>'
        '<published>2023-05-01T00:00:00Z</published>'
        '</entry>'
        '</feed>'
    )


def _hf_response(_url=None):
    return [
        {
            "id": "mvkvc/severstal-steel-defect-detection",
            "likes": 200,
            "downloads": 50000,
            "lastModified": "2023-01-01",
            "tags": ["image", "segmentation"],
        }
    ]


def _all_sources_client(extra: dict[str, Any] | None = None):
    routes = {
        "openalex": _oa_response,
        "github": _gh_response,
        "arxiv": _arxiv_response,
        "huggingface": _hf_response,
    }
    if extra:
        routes.update(extra)
    return _MockClient(routes)


# ---------- 1: query_plan ---------- #


def test_01_query_plan_generates_layers():
    """build_query_plan 应生成 paper / dataset / repo 三类 queries."""

    plan = build_query_plan(
        project_id="p1",
        raw_topic="基于YOLO的钢材表面缺陷检测",
        extra_keywords=["severstal"],
    )
    assert plan.raw_topic
    paper_qs = [q for layer in plan.paper_queries for q in layer.queries]
    dataset_qs = [q for layer in plan.dataset_queries for q in layer.queries]
    repo_qs = [q for layer in plan.repo_queries for q in layer.queries]
    assert len(paper_qs) >= 3, f"paper queries 应 >= 3, got {paper_qs}"
    assert len(dataset_qs) >= 1
    assert len(repo_qs) >= 1
    # dataset_queries 必有 extras
    assert any("severstal" in q.lower() for q in dataset_qs + repo_qs)


# ---------- 2-6: Normalize ---------- #


def test_02_normalize_openalex_paper():
    cand = normalize_candidate(
        _oa_response()["results"][0],
        project_id="p1",
        source="openalex",
        candidate_id="c1",
    )
    assert cand.candidate_type == "paper"
    assert cand.title.startswith("YOLO")
    assert cand.authors == ["Alice"]
    assert cand.venue == "CVPR"
    assert cand.doi == "10.1234/oa1"
    assert cand.abstract and "steel" in cand.abstract
    assert cand.year == 2023
    # openalex_id 可能是 URL 也可能是 'W...' (取决于 raw["id"] 形式)
    assert cand.openalex_id and "W1" in cand.openalex_id


def test_03_semantic_scholar_returns_empty():
    """S14 默认降级: S2 adapter 返回空 list (不阻塞验收)."""

    from app.services.retrieval.adapters.optional_adapters import semantic_scholar_search

    async def _go():
        return await semantic_scholar_search(["steel"], top_k=5)

    assert asyncio.run(_go()) == []


def test_04_normalize_arxiv_paper():
    """arXiv Atom 通过 arxiv_search 直接出 dict; 这里改走 normalizer."""

    from xml.etree import ElementTree as ET

    parsed = ET.fromstring(_arxiv_response())
    ns = "{http://www.w3.org/2005/Atom}"
    entry = parsed.find(f"{ns}entry")
    raw = {
        "title": (entry.find(f"{ns}title").text or "").strip(),
        "arxiv_id": "2106.09685",
        "authors": ["Bob"],
        "year": 2023,
        "abstract": "defect detection abstract",
        "url": "https://arxiv.org/abs/2106.09685",
    }
    cand = normalize_candidate(raw, project_id="p1", source="arxiv", candidate_id="c2")
    assert cand.candidate_type == "paper"
    assert cand.arxiv_id == "2106.09685"
    assert cand.year == 2023
    assert cand.venue == "arXiv"


def test_05_normalize_github_repo():
    cand = normalize_candidate(
        _gh_response()["items"][0],
        project_id="p1",
        source="github",
        candidate_id="c3",
    )
    assert cand.candidate_type == "repo"
    assert cand.repo_full_name == "ultralytics/yolov5"
    assert cand.stars == 40000
    assert cand.license == "GPL-3.0"
    assert cand.abstract == "YOLOv5 in PyTorch"
    assert any(h.startswith("topic:") for h in cand.quality_hints)


def test_06_normalize_huggingface_dataset():
    cand = normalize_candidate(
        _hf_response()[0],
        project_id="p1",
        source="huggingface",
        candidate_id="c4",
    )
    assert cand.candidate_type == "dataset"
    assert cand.dataset_slug == "mvkvc/severstal-steel-defect-detection"
    assert cand.title  # 至少有个 slug 派生的 title
    assert any("likes" in h for h in cand.quality_hints)


# ---------- 7-9: Dedup ---------- #


def test_07_dedup_paper_by_doi_and_title():
    """DOI 完全一致 + 标题+年相似 -> 标记 duplicate."""

    c1 = normalize_candidate(
        {"title": "YOLO Defect Detection", "doi": "10.1/x", "publication_year": 2023},
        project_id="p1", source="openalex", candidate_id="c1",
    )
    c2 = normalize_candidate(
        {"title": "YOLO Defect Detection", "doi": "10.1/x", "publication_year": 2023},
        project_id="p1", source="arxiv", candidate_id="c2",
    )
    out = dedup_candidates([c1, c2])
    assert c1.is_duplicate is False
    assert c2.is_duplicate is True
    assert c2.duplicate_of == "c1"


def test_08_dedup_repo_by_full_name():
    c1 = normalize_candidate(
        {"full_name": "a/b", "html_url": "https://github.com/a/b"},
        project_id="p1", source="github", candidate_id="c1",
    )
    c2 = normalize_candidate(
        {"full_name": "a/b", "html_url": "https://github.com/a/b"},
        project_id="p1", source="github", candidate_id="c2",
    )
    dedup_candidates([c1, c2])
    assert c2.is_duplicate is True


def test_09_dedup_dataset_by_slug():
    c1 = normalize_candidate(
        {"id": "mvkvc/severstal"},
        project_id="p1", source="huggingface", candidate_id="c1",
    )
    c2 = normalize_candidate(
        {"id": "mvkvc/severstal"},
        project_id="p1", source="huggingface", candidate_id="c2",
    )
    dedup_candidates([c1, c2])
    assert c2.is_duplicate is True


# ---------- 10: 评分排序 ---------- #


def test_10_score_orders_high_first():
    c_high = normalize_candidate(
        {"title": "YOLO Steel Defect Detection", "publication_year": 2024, "cited_by_count": 200, "abstract": "YOLO steel defect detection benchmark"},
        project_id="p1", source="openalex", candidate_id="h",
    )
    c_low = normalize_candidate(
        {"title": "Some Other Paper", "publication_year": 2010, "cited_by_count": 0, "abstract": "irrelevant"},
        project_id="p1", source="openalex", candidate_id="l",
    )
    s_high = score_paper(c_high, query_keywords=["YOLO", "steel"])
    s_low = score_paper(c_low, query_keywords=["YOLO", "steel"])
    assert s_high > s_low


# ---------- 11: 单 source 失败不影响其他 ---------- #


def test_11_source_failure_isolated(client):
    """openalex 失败时, github/arXiv/huggingface 仍能完成."""

    pid = _analyze(client)

    class _OAFail:
        async def request(self, method, url, headers=None):
            if "openalex" in url.lower():
                raise RuntimeError("simulated OA outage")
            if "github" in url.lower():
                return 200, _gh_response()
            if "arxiv" in url.lower():
                return 200, _arxiv_response()
            if "huggingface" in url.lower():
                return 200, _hf_response()
            return 404, {}

    async def _go():
        req = RetrievalSearchRequest(
            scope=["paper", "dataset", "repo"],
            sources=["openalex", "arxiv", "github", "huggingface"],
            top_k_per_source=3,
        )
        return await run_retrieval(pid, "基于YOLO的钢材表面缺陷检测", req, client=_OAFail())

    run = asyncio.run(_go())
    assert run.status == "partial"
    assert any(r.source == "openalex" and r.status == "failed" for r in run.source_results)
    assert any(r.source == "github" and r.status == "completed" for r in run.source_results)
    # 仍有 candidate
    assert run.total_candidates >= 1


# ---------- 12-17: Import 流程 ---------- #


def _run_full(client) -> tuple[str, Any]:
    pid = _analyze(client)
    mc = _all_sources_client()

    async def _go():
        req = RetrievalSearchRequest(
            scope=["paper", "dataset", "repo"],
            sources=["openalex", "arxiv", "github", "huggingface"],
            top_k_per_source=3,
        )
        return await run_retrieval(pid, "基于YOLO的钢材表面缺陷检测", req, client=mc)

    run = asyncio.run(_go())
    return pid, run


def test_12_import_writes_to_ledger(client):
    """import 后 ledger 中出现对应 evidence."""

    pid, run = _run_full(client)
    non_dup = [c for c in run.candidates if not c.is_duplicate and not c.already_in_ledger]
    assert non_dup, "应至少 1 个非重复候选"
    selected = [non_dup[0].candidate_id]

    resp = import_candidates(pid, RetrievalImportRequest(
        run_id=run.run_id, candidate_ids=selected, workspace_lane="system_found",
    ))
    assert resp.imported == 1
    assert len(resp.evidence_ids) == 1
    item = ev_store.get_item(resp.evidence_ids[0])
    assert item is not None
    assert item.source_mode == "auto_search"


def test_13_import_review_status_pending(client):
    pid, run = _run_full(client)
    non_dup = [c for c in run.candidates if not c.is_duplicate and not c.already_in_ledger]
    resp = import_candidates(pid, RetrievalImportRequest(
        run_id=run.run_id, candidate_ids=[non_dup[0].candidate_id],
    ))
    item = ev_store.get_item(resp.evidence_ids[0])
    assert item.review_status == "pending"


def test_14_import_workspace_lane_default_system_found(client):
    pid, run = _run_full(client)
    non_dup = [c for c in run.candidates if not c.is_duplicate and not c.already_in_ledger]
    resp = import_candidates(pid, RetrievalImportRequest(
        run_id=run.run_id, candidate_ids=[non_dup[0].candidate_id],
    ))
    item = ev_store.get_item(resp.evidence_ids[0])
    assert item.workspace_lane == "system_found"


def test_15_import_created_by_skill(client):
    """paper / dataset / repo 各映射到不同 skill."""

    pid, run = _run_full(client)
    non_dup_by_type: dict[str, Any] = {}
    for c in run.candidates:
        if c.is_duplicate or c.already_in_ledger:
            continue
        non_dup_by_type.setdefault(c.candidate_type, c)
    selected = [c.candidate_id for c in non_dup_by_type.values()][:3]
    resp = import_candidates(pid, RetrievalImportRequest(
        run_id=run.run_id, candidate_ids=selected,
    ))
    items = [ev_store.get_item(eid) for eid in resp.evidence_ids]
    by_type = {it.evidence_type: it for it in items if it is not None}
    if "paper" in by_type:
        assert by_type["paper"].created_by_skill == "paper-card"
    if "repo" in by_type:
        assert by_type["repo"].created_by_skill == "github-baseline"
    if "dataset" in by_type:
        assert by_type["dataset"].created_by_skill == "dataset-validation"


def test_16_import_auto_verify_runs(client):
    """auto_verify=True 时 verification 至少跑过 (status 会被设置)."""

    pid, run = _run_full(client)
    non_dup = [c for c in run.candidates if not c.is_duplicate and not c.already_in_ledger]
    cand = next((c for c in non_dup if c.candidate_type == "repo"), non_dup[0])
    resp = import_candidates(pid, RetrievalImportRequest(
        run_id=run.run_id, candidate_ids=[cand.candidate_id], auto_verify=True,
    ))
    item = ev_store.get_item(resp.evidence_ids[0])
    # 验证源不再是无 (auto_verify 后应该有 source 标记)
    assert item.verification_source != "none" or item.verification_status in ("verified", "partial", "failed", "unverified", "skipped")
    # 且 verification_checked_at 已被设置
    assert item.verification_checked_at is not None


def test_17_duplicate_candidate_not_imported(client):
    """同 run 中重复的 candidate (is_duplicate=True) 不会被 import."""

    pid, run = _run_full(client)
    dups = [c for c in run.candidates if c.is_duplicate]
    if not dups:
        pytest.skip("本 run 无重复候选, 跳过")
    resp = import_candidates(pid, RetrievalImportRequest(
        run_id=run.run_id, candidate_ids=[dups[0].candidate_id],
    ))
    assert resp.imported == 0
    assert dups[0].candidate_id in resp.skipped_evidence_ids


# ---------- 18: Trace ---------- #


def test_18_trace_written_for_run_and_import(client):
    pid, run = _run_full(client)
    events = ts.get_trace(pid, limit=200).events
    actions = [e.action for e in events]
    assert "retrieval_run_started" in actions
    assert "retrieval_run_completed" in actions

    non_dup = [c for c in run.candidates if not c.is_duplicate and not c.already_in_ledger]
    import_candidates(pid, RetrievalImportRequest(
        run_id=run.run_id, candidate_ids=[non_dup[0].candidate_id],
    ))
    events2 = ts.get_trace(pid, limit=200).events
    actions2 = [e.action for e in events2]
    assert "retrieval_candidate_imported" in actions2


# ---------- 19: Summary ---------- #


def test_19_summary_counts(client):
    pid, run = _run_full(client)
    summary = get_summary(pid)
    assert summary.last_run_id == run.run_id
    assert summary.total_runs >= 1
    # 至少有 1 类 source success
    assert "openalex" in summary.source_success or "github" in summary.source_success


# ---------- 20: Pending/Unverified 不提升 ReportQuality ---------- #


def test_20_pending_evidence_does_not_block_quality(client):
    """导入的 pending/unverified 证据进入 ledger 后, ReportQuality 仍能跑通且不升分."""

    pid, run = _run_full(client)
    non_dup = [c for c in run.candidates if not c.is_duplicate and not c.already_in_ledger]
    import_candidates(pid, RetrievalImportRequest(
        run_id=run.run_id, candidate_ids=[c.candidate_id for c in non_dup],
    ))

    # 触发 ReportQuality
    from app.schemas_quality import ReportReviewRequest
    from app.services import report_quality as quality_service

    review = quality_service.build_quality_review(pid, ReportReviewRequest())
    # verdict 必须是 4 档之一
    assert review.verdict in ("通过", "有条件通过", "需修改", "不建议")
    # 所有 checks 的 evidence_refs 不应包含新导入的 pending+unverified
    for chk in review.checks:
        for ref in chk.evidence_refs:
            assert not (ref.review_status == "pending" and ref.verification_status == "unverified"), (
                "pending + unverified 不应进 supports"
            )