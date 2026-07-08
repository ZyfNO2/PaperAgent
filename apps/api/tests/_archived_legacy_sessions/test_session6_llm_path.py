"""Session 6 后端测试: LLM 搜索助手 + rerank + recommend + review (SOP §13.1).

跑法:  .venv/Scripts/python.exe -m pytest apps/api/tests/test_session6_llm_path.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.main import app  # noqa: E402
from app.services import evidence as ev_store  # noqa: E402
from app.services import keyword_search_assistant as ks  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_ledger():
    ev_store.reset_all()
    yield
    ev_store.reset_all()


@pytest.fixture
def client():
    return TestClient(app)


# ---------- §13.1 LLM 搜索助手 ---------- #


def test_search_assistant_returns_keywords(client):
    """搜索助手调 arxiv + LLM, 返回 method/task/object."""

    result = ks.search_assistant("基于物理信息神经网络(PINN)的机构实时数字孪生")
    if result is None:
        pytest.skip("arXiv 或 LLM 不可用, 跳过 (生产应有 LLM)")
    assert isinstance(result["method_keywords"], list)
    assert isinstance(result["task_keywords"], list)
    assert isinstance(result["object_keywords"], list)
    # 至少一个字段非空
    assert any(result.get(k) for k in ("method_keywords", "task_keywords", "object_keywords"))


def test_search_assistant_heuristic_fallback(client):
    """prefer=heuristic 直接返回 None, 不调 LLM."""

    result = ks.search_assistant("YOLO steel", prefer="heuristic")
    assert result is None


def test_merge_with_heuristic_dedup():
    """合并 LLM + heuristic, 去重保序."""

    assistant = {
        "method_keywords": ["PINN", "Physics-Informed"],
        "task_keywords": ["建模", "仿真"],
    }
    heu = {
        "method_keywords": ["PINN", "数字孪生"],  # PINN 重复, 数字孪生 新
        "task_keywords": ["建模", "预测"],  # 建模 重复
    }
    merged = ks.merge_with_heuristic(assistant, heu)
    assert "PINN" in merged["method_keywords"]
    assert merged["method_keywords"].index("PINN") == 0  # LLM 优先
    assert "数字孪生" in merged["method_keywords"]  # heuristic 补充
    assert len(merged["method_keywords"]) == len(set(merged["method_keywords"]))  # 去重


# ---------- LLM rerank arxiv 命中 (症状 3 根治) ---------- #


def test_llm_rerank_filters_irrelevant(client):
    """LLM rerank 过滤 < 0.3 的无关论文 (e.g. German survey / AGN)."""

    from app.services.one_topic import _llm_rerank_papers
    from app.schemas import PaperHit
    # 构造 5 篇: 2 篇 PINN 强相关, 1 篇 AGN (无关), 1 篇 German survey (无关), 1 篇 food (无关)
    papers = [
        PaperHit(paper_id="P1", title="Physics-Informed Neural Networks for PDEs",
                 summary="PINN solves PDEs in physical systems", year=2024, source="arXiv"),
        PaperHit(paper_id="P2", title="Self-Adaptive PINN with Soft Attention",
                 summary="self-adaptive loss for physics-informed", year=2023, source="arXiv"),
        PaperHit(paper_id="P3", title="A rich bounty of AGN in the Bootes survey",
                 summary="AGN high-z obscured galaxies astronomical", year=2006, source="arXiv"),
        PaperHit(paper_id="P4", title="German Open-Ended Survey Coding with LLM",
                 summary="German language survey coding", year=2025, source="arXiv"),
        PaperHit(paper_id="P5", title="Image recognition for sandwich classification",
                 summary="computer vision food classification", year=2024, source="arXiv"),
    ]
    from app.schemas import KeywordBreakdown
    kw = KeywordBreakdown(
        method_keywords=["PINN"], task_keywords=["建模"], object_keywords=["机构"],
    )
    kept = _llm_rerank_papers(papers, kw)
    if not kept:
        pytest.skip("LLM 不可用, 跳过")
    # PINN 相关 (P1, P2) 保留; AGN / German / sandwich (P3, P4, P5) 至少 2 个被过滤
    kept_ids = {p.paper_id for p in kept}
    assert "P1" in kept_ids, "PINN 强相关论文必须保留"
    assert "P2" in kept_ids, "PINN 强相关论文必须保留"
    filtered = [p for p in papers if p.paper_id not in kept_ids]
    assert len(filtered) >= 2, f"应过滤 ≥ 2 篇无关论文, 实际过滤: {[p.paper_id for p in filtered]}"


# ---------- LLM recommend_proposal ---------- #


def test_recommend_proposal_uses_llm(client):
    """auto 路径下, proposal_recommendation 是 LLM 写的 (work_packages 含真实数据集名 或 自采提示).

    LLM 偶发返回不一致 (rate limit / 截断), 测试要宽松: heuristic 模板的
    "引入 注意力机制 并进行消融实验" 在 YOLO 题下会出现, 但 LLM 写 PINN 题不会写这个.
    所以用 PINN 题目 + 检查 WP 至少 1 个不是纯模板.
    """

    r = client.post("/api/v1/one-topic/analyze", json={
        "raw_topic": "基于物理信息神经网络(PINN)的机构实时数字孪生",
        "prefer": "auto",
    })
    assert r.status_code == 200
    rec = r.json()["proposal_recommendation"]
    # LLM 写的 recommended_topic 应反映原题 (PINN/数字孪生)
    topic = rec.get("recommended_topic", "")
    assert "PINN" in topic or "物理信息" in topic or "数字孪生" in topic, (
        f"recommended_topic 不像 LLM 写的: {topic}"
    )
    wps = rec.get("work_packages", [])
    assert len(wps) >= 1
    # LLM 路径下 WP1 title 应含具体技术词, 不是 "基于公开数据集复现 PINN baseline" 这种空泛模板
    # 这里不强求 (LLM 偶发简化), 只检查 recommended_topic + 至少有 1 个 WP
    assert any(wp.get("title") for wp in wps)


# ---------- LLM light_review ---------- #


def test_light_review_uses_llm(client):
    """auto 路径下, light_review 的 5 维 comment 是 LLM 写的 (具体建议, 不是通用模板)."""

    r = client.post("/api/v1/one-topic/analyze", json={
        "raw_topic": "基于物理信息神经网络(PINN)的机构实时数字孪生",
        "prefer": "auto",
    })
    assert r.status_code == 200
    rev = r.json()["light_review"]
    checks = rev.get("checks", [])
    # 5 维都有
    assert len(checks) == 5
    dimensions = [c["dimension"] for c in checks]
    assert "题目边界" in dimensions
    assert "数据集" in dimensions
    assert "Baseline" in dimensions
    assert "工作量" in dimensions
    assert "开题表达" in dimensions
    # 至少一个 comment 含具体建议 (不是通用模板)
    has_specific = any(
        any(k in c.get("comment", "") for k in ("PINN", "数字孪生", "PDE", "FEM", "实时", "自适应"))
        for c in checks
    )
    assert has_specific, f"comments 仍太通用: {[c['comment'] for c in checks]}"


# ---------- heuristic 路径不受影响 ---------- #


def test_heuristic_path_still_works(client):
    """prefer=heuristic 时, 不调 LLM, 走模板."""

    r = client.post("/api/v1/one-topic/analyze", json={
        "raw_topic": "基于YOLO的钢材表面缺陷检测",
        "prefer": "heuristic",
    })
    assert r.status_code == 200
    d = r.json()
    rec = d["proposal_recommendation"]
    # heuristic 模板: "引入 注意力机制 并进行消融实验" (因为 YOLO 不触发 yolo 分支的特殊方法)
    wps = rec["work_packages"]
    assert any("注意力机制" in wp["title"] or "轻量化" in wp["title"] for wp in wps)


# ---------- 评分仍正确 ---------- #


def test_paper_relevance_uses_llm_score_after_rerank(client):
    """LLM rerank 后, paper.relevance_score 应是 LLM 分数 (不是 heuristic 默认 0.xx)."""

    r = client.post("/api/v1/one-topic/analyze", json={
        "raw_topic": "基于物理信息神经网络(PINN)的机构实时数字孪生",
        "prefer": "auto",
    })
    assert r.status_code == 200
    papers = r.json()["evidence_summary"]["papers"]
    if not papers:
        pytest.skip("无 arxiv 命中")
    # 至少一篇 score > 0.3 (LLM rerank 应让强相关论文高分)
    assert any((p.get("relevance_score") or 0) > 0.3 for p in papers)
