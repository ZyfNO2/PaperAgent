"""Session 19: 轻量学校模板与开题报告适配 (后端测试).

覆盖:
1. 模板加载 (default / engineering / cv_ai) 元数据正确
2. 未知 template_key 回退 default, 不报错
3. 模板章节顺序不同
4. GET /report/templates 返回 3 模板
5. FinalPackage build 含 template_key + template_hints
6. FinalPackage summary 透传 template_key
7. 模板提示: cv_ai 缺 dataset / baseline 时提示
8. 模板提示: engineering 缺 dataset 时提示
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import report_templates as tmpl_service
from app.services import final_package as fp_service
from app.schemas import FinalPackageBuildOptions


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    tmp_dir = Path(tempfile.mkdtemp(prefix="pa_s19_"))
    monkeypatch.setenv("PAPERAGENT_TRACE_DIR", str(tmp_dir / "traces"))
    monkeypatch.setenv("PAPERAGENT_LOG_DIR", str(tmp_dir / "logs"))
    yield
    import shutil
    try:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception:
        pass


@pytest.fixture
def client():
    return TestClient(app)


# ---------- 1: 模板加载元数据 ---------- #


def test_01_load_default_template():
    t = tmpl_service.load_template("default")
    assert t["template_key"] == "default"
    assert t["name"]
    assert t["version"]
    # 默认模板含"背景"章节或正文中出现"背景"
    assert any("背景" in s for s in t["required_sections"]) or "背景" in t["body"]
    assert t["evidence_required"] is True
    assert "topic" in t["placeholders"]


def test_02_load_engineering_template():
    t = tmpl_service.load_template("engineering")
    assert t["template_key"] == "engineering"
    assert "工程" in t["name"] or "工程" in t["body"]
    assert t["body"]


def test_03_load_cv_ai_template():
    t = tmpl_service.load_template("cv_ai")
    assert t["template_key"] == "cv_ai"
    assert "CV" in t["name"] or "AI" in t["name"] or "视觉" in t["body"]


# ---------- 2: 未知模板回退 ---------- #


def test_04_unknown_template_key_falls_back():
    assert tmpl_service.normalize_template_key("not_exist") == "default"


def test_05_load_missing_file_returns_minimal():
    t = tmpl_service.load_template("missing_key_that_does_not_exist")
    # normalize 后回退 default, 因此加载的是 default 模板文件
    assert t["template_key"] == "default"
    assert t["name"]  # 有名字 (default 模板)
    assert t["body"]  # 有正文


# ---------- 3: 章节顺序 ---------- #


class _FakeSec:
    def __init__(self, key: str, title: str, content: str = ""):
        self.key = key
        self.title = title
        self.content = content
        self.unsupported_claims = []


def test_06_reorder_sections_keeps_citations_last():
    sections = [
        _FakeSec("citations", "引用"),
        _FakeSec("background", "背景"),
        _FakeSec("risks", "风险"),
        _FakeSec("todo", "待补"),
        _FakeSec("work_packages", "工作包"),
        _FakeSec("decision_log", "决策"),
    ]
    ordered = tmpl_service.reorder_sections("default", sections)
    keys = [s.key for s in ordered]
    assert keys.index("background") < keys.index("work_packages")
    assert keys.index("risks") < keys.index("citations")
    assert keys.index("citations") < keys.index("todo")
    assert keys.index("todo") < keys.index("decision_log")


def test_07_cv_ai_template_reorders_differently():
    sections = [
        _FakeSec("background", "背景"),
        _FakeSec("related_work", "现状"),
        _FakeSec("work_packages", "工作包"),
        _FakeSec("innovation", "创新"),
        _FakeSec("citations", "引用"),
    ]
    ordered = tmpl_service.reorder_sections("cv_ai", sections)
    keys = [s.key for s in ordered]
    # cv_ai 里 related_work 排 data 前, 但这里没 data, 至少确认 citations 仍在末尾
    assert keys[-1] == "citations"


# ---------- 4: GET /report/templates 端点 ---------- #


def test_08_list_templates_endpoint(client):
    r = client.get("/api/v1/one-topic/report/templates")
    assert r.status_code == 200
    body = r.json()
    assert "templates" in body
    assert len(body["templates"]) == 4  # default + engineering + cv_ai + paper_extension (S49)
    keys = [t["template_key"] for t in body["templates"]]
    assert "default" in keys
    assert "paper_extension" in keys
    assert "engineering" in keys
    assert "cv_ai" in keys
    assert body["default_key"] == "default"


# ---------- 5: FinalPackage 透传 template_key ---------- #


def _build_pkg_with_template_key(monkeypatch, template_key: str, has_data: bool = True):
    """辅助: 构造一个最小 snapshot 并 build FinalPackage."""
    from app.services import evidence as ev_store
    import shutil
    tmp_dir = Path(tempfile.mkdtemp(prefix="pa_s19_pkg_"))
    monkeypatch.setenv("PAPERAGENT_TRACE_DIR", str(tmp_dir / "traces"))
    monkeypatch.setenv("PAPERAGENT_LOG_DIR", str(tmp_dir / "logs"))
    pid = "ot_s19_template_test"
    papers = []
    datasets = []
    baselines = []
    if has_data:
        papers = [{
            "paper_id": "p1", "title": "Paper One", "authors": [], "year": 2024,
            "url": "https://arxiv.org/abs/1", "source": "arXiv", "relevance_score": 0.8,
            "review_status": "accepted",
        }]
        datasets = [{
            "dataset_id": "d1", "name": "Dataset One", "fit": "高", "source": "public-known",
        }]
        baselines = [{
            "baseline_id": "b1", "name": "Baseline One", "repository_url": "https://github.com/a/b",
            "reproduce_difficulty": "中", "source": "github",
        }]
    snapshot = {
        "feasibility": {
            "verdict": "可做", "reason": "有证据", "paper_status": "有", "dataset_status": "有",
            "baseline_status": "有", "engineering_status": "有", "missing_evidence": [],
            "recommended_next_action": "继续", "evidence_refs": [], "blocking_refs": [],
            "missing_ref_reasons": [], "confidence": 0.8,
        },
        "proposal_recommendation": {
            "recommended_topic": "测试题目", "recommendation_reason": [],
            "work_packages": [], "proposal_outline": [], "pivot_routes": [],
            "topic_evidence_refs": [], "reason_evidence_refs": {},
        },
        "light_review": {"verdict": "通过", "summary": "", "checks": [], "revision_checklist": []},
        "evidence_summary": {
            "papers": papers, "datasets": datasets, "baselines": baselines,
            "metrics": ["mAP"], "paper_count": len(papers), "arxiv_paper_count": len(papers),
            "dataset_count": len(datasets), "baseline_count": len(baselines),
            "has_public_dataset": bool(datasets), "has_repro_baseline": bool(baselines),
            "has_metrics": True,
        },
    }
    ev_store.save_snapshot(pid, snapshot)
    opts = FinalPackageBuildOptions(template_key=template_key)
    pkg = fp_service.build_final_package(pid, opts)
    ev_store.save_final_package(pid, pkg)
    try:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception:
        pass
    return pkg


def test_09_final_package_default_template(monkeypatch):
    pkg = _build_pkg_with_template_key(monkeypatch, "default")
    assert pkg.template_key == "default"
    assert "通用" in pkg.proposal_markdown or "default" in pkg.proposal_markdown
    assert pkg.template_key in pkg.proposal_markdown


def test_10_final_package_cv_ai_template(monkeypatch):
    pkg = _build_pkg_with_template_key(monkeypatch, "cv_ai")
    assert pkg.template_key == "cv_ai"
    assert pkg.template_key in pkg.proposal_markdown


def test_11_final_package_unknown_template_falls_back(monkeypatch):
    pkg = _build_pkg_with_template_key(monkeypatch, "not_exist")
    assert pkg.template_key == "default"


def test_12_final_package_summary_template_fields(monkeypatch):
    pkg = _build_pkg_with_template_key(monkeypatch, "engineering")
    summary = fp_service.build_final_package_summary(pkg.project_id)
    assert summary is not None
    assert summary.template_key == "engineering"


# ---------- 6: 模板缺失提示 ---------- #


def test_13_cv_ai_hints_when_missing_data():
    hints = tmpl_service.check_template_readiness("cv_ai", paper_count=1, dataset_count=0, baseline_count=0)
    assert len(hints) == 2
    assert any("数据集" in h for h in hints)
    assert any("baseline" in h for h in hints)


def test_14_engineering_hints_when_missing_data():
    hints = tmpl_service.check_template_readiness("engineering", paper_count=1, dataset_count=0, baseline_count=1)
    assert len(hints) == 1
    assert "数据" in hints[0]


def test_15_default_no_hints():
    hints = tmpl_service.check_template_readiness("default", paper_count=1, dataset_count=0, baseline_count=0)
    assert hints == []


# ---------- 7: 模板 frontmatter 解析 ---------- #


def test_16_frontmatter_parsing():
    text = """---
template_key: test
name: 测试模板
version: 1.0
applies_to: 测试
required_sections:
  - 背景
  - 现状
placeholders:
  - topic
---

# {{topic}}

正文.
"""
    meta, body = tmpl_service._split_frontmatter(text)
    assert meta["template_key"] == "test"
    assert meta["name"] == "测试模板"
    assert meta["required_sections"] == ["背景", "现状"]
    assert meta["placeholders"] == ["topic"]
    assert "正文" in body


# ---------- 8: 端点 build 带 template_key ---------- #


def test_17_build_endpoint_with_template_key(client, monkeypatch):
    pkg = _build_pkg_with_template_key(monkeypatch, "cv_ai")
    ev_store = pytest.importorskip("app.services.evidence")
    # 让 endpoint 能读到 snapshot
    pid = pkg.project_id
    r = client.post(f"/api/v1/one-topic/{pid}/final-package/build", json={"template_key": "cv_ai"})
    assert r.status_code == 200
    body = r.json()
    assert body["template_key"] == "cv_ai"
    assert "cv_ai" in body["proposal_markdown"]
    # 默认请求也应成功
    r2 = client.post(f"/api/v1/one-topic/{pid}/final-package/build", json={})
    assert r2.status_code == 200
    assert r2.json()["template_key"] == "default"
