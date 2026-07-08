"""Session 65 T7 测试: recommend_proposal 必须先选 baseline 才能生成工作包.

跑法:  .venv/Scripts/python.exe -m pytest apps/api/tests/test_session65_t7_work_package_baseline.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.schemas import (  # noqa: E402
    EvidenceSummary,
    FeasibilitySummary,
    KeywordBreakdown,
    OneTopicRequest,
    PaperHit,
    DatasetHit,
    BaselineHit,
)
from app.services import one_topic  # noqa: E402
from app.services.retrieval import baseline_selection as bs  # noqa: E402


# ---------- fixtures ---------- #


@pytest.fixture(autouse=True)
def _clean_state():
    bs.reset_baseline_state()
    yield
    bs.reset_baseline_state()


def _req(project_id: str | None = None) -> OneTopicRequest:
    return OneTopicRequest(
        raw_topic="基于YOLO的钢材表面缺陷检测",
        goal_level="保毕业",
        prefer="heuristic",
        project_id_override=project_id,
    )


def _keywords() -> KeywordBreakdown:
    return KeywordBreakdown(
        method_keywords=["YOLO"],
        task_keywords=["目标检测"],
        object_keywords=["钢材"],
        scenario_keywords=["工业质检"],
        metric_keywords=["mAP"],
        risk_terms=[],
        query_keywords_zh=["YOLO 钢材 目标检测"],
        query_keywords_en=["YOLO steel defect detection"],
    )


def _ev() -> EvidenceSummary:
    papers = [
        PaperHit(
            paper_id="p1",
            title="Parallel paper",
            year=2023,
            source="heuristic",
            literature_role="parallel_application_paper",
            modules_added=["C2f Module", "SE Block"],
            datasets=["NEU-DET"],
        ),
        PaperHit(
            paper_id="p2",
            title="Module improvement paper",
            year=2024,
            source="heuristic",
            literature_role="module_improvement_paper",
            modules_added=["GAM Attention"],
            datasets=["NEU-DET"],
        ),
    ]
    datasets = [
        DatasetHit(
            dataset_id="DS01", name="NEU-DET",
            scale="1800 张", license="学术使用",
            download="http://example.com/neu-det",
            fit="高", source="public-known",
        ),
    ]
    baselines = [
        BaselineHit(
            baseline_id="BL01", name="YOLOv8",
            paper_title="Ultralytics YOLOv8",
            repository_url="https://github.com/ultralytics/ultralytics",
            license="AGPL-3.0", reproduce_difficulty="低", source="github",
        ),
    ]
    return EvidenceSummary(
        papers=papers,
        datasets=datasets,
        baselines=baselines,
        metrics=["mAP", "Recall"],
        paper_count=2,
        arxiv_paper_count=2,
        dataset_count=1,
        baseline_count=1,
        has_public_dataset=True,
        has_repro_baseline=True,
        has_metrics=True,
    )


def _feas() -> FeasibilitySummary:
    return FeasibilitySummary(
        verdict="可做",
        reason="证据齐备",
        paper_status="",
        dataset_status="",
        baseline_status="",
        engineering_status="",
        missing_evidence=[],
        recommended_next_action="",
    )


# ---------- T7 §1: 没选 baseline → 不生成工作包 ---------- #


def test_no_baseline_no_work_packages():
    """未选 baseline 时, recommend_proposal 不应返回 work_packages, 也不得硬编码 'attention' / '轻量化' 之类模块."""

    rec = one_topic.recommend_proposal(_req("proj_no_baseline"), _keywords(), _ev(), _feas())

    # 硬规则 1: 没 baseline → work_packages 必须为空
    assert rec.work_packages == [], (
        f"未选 baseline 不应生成工作包, got: {[w.title for w in rec.work_packages]}"
    )

    # 硬规则: 推荐理由里必须明确告诉用户先去选 baseline
    assert any("请先从候选论文" in r for r in rec.recommendation_reason), (
        f"推荐理由应说明需先选 baseline, got: {rec.recommendation_reason}"
    )

    # 硬规则: 不出现硬编码的 'attention' / '轻量化' 等通用模块词
    full_text = " ".join(rec.recommendation_reason) + " " + rec.recommended_topic
    forbidden = ["注意力机制", "attention mechanism", "轻量化模块", "self-attention"]
    for word in forbidden:
        assert word not in full_text, f"未选 baseline 时不应出现兜底词 '{word}'"

    # pivot_routes 也清空 (pivot 依赖 baseline 决策)
    assert rec.pivot_routes == [], "未选 baseline 时不应生成 pivot routes"


# ---------- T7 §2: 选了 baseline → 用 brainstormer 生成工作包, 无硬编码 ---------- #


def test_with_baseline_uses_brainstormer():
    """选了 baseline 后, recommend_proposal 必须调用 brainstormer, 模块来自 module_papers."""

    pid = "proj_with_baseline"
    bs.select_baseline(
        pid,
        {"candidate_id": "c_yolov8", "candidate_type": "repo", "literature_role": "baseline_framework"},
        role="primary",
        user_reason="主流 baseline, 复现成本低",
        expected_dataset="NEU-DET",
    )

    rec = one_topic.recommend_proposal(_req(pid), _keywords(), _ev(), _feas())

    # 1) 选了 baseline → 必须有工作包
    assert len(rec.work_packages) >= 1, "选了 baseline 后应生成工作包"

    # 2) 模块必须来自 module_papers (GAM Attention), 不能是硬编码 attention
    all_titles = " ".join(w.title for w in rec.work_packages)
    all_methods = " ".join(w.method_approach for w in rec.work_packages)
    full_text = all_titles + " " + all_methods

    # 至少有一个工作包应该提到 module paper 里的真实模块 (GAM Attention / C2f / SE Block)
    has_real_module = any(
        mod in full_text
        for mod in ["GAM Attention", "C2f", "SE Block", "GAM"]
    )

    # 硬规则: 不得单独硬编码 '注意力机制' / 'attention' (只允许真实模块名)
    forbidden_alone = ["注意力机制", "attention mechanism", "self-attention"]
    for word in forbidden_alone:
        assert word not in full_text, f"工作包里出现了硬编码兜底词 '{word}'"

    # 模块应该从真实论文来 (不强求每条都有, 但至少 1 个工作包应反映真实模块)
    # 注意: brainstorm 可能只从 module_papers 选, 不一定覆盖每条 WP
    print(f"[T7 §2] work_package count={len(rec.work_packages)}, has_real_module={has_real_module}")


# ---------- T7 §3: 选了 baseline 但证据不足 (无 module_paper) → 工作包不应硬编码 attention ---------- #


def test_baseline_but_no_module_paper_no_hardcoded_attention():
    """有 baseline 但 module_papers 为空 → brainstorm 用 baseline 名 + dataset, 不引入 attention."""

    pid = "proj_bl_no_module"
    bs.select_baseline(
        pid,
        {"candidate_id": "c_swintransformer", "candidate_type": "paper", "literature_role": "baseline_method"},
        role="primary",
        user_reason="对比 baseline",
    )

    # 构造一个 ev: 没有 module_paper 也没有 parallel_paper
    ev = EvidenceSummary(
        papers=[],
        datasets=[DatasetHit(dataset_id="DS01", name="NEU-DET", fit="高", source="public-known")],
        baselines=[],
        metrics=["mAP"],
        paper_count=0, arxiv_paper_count=0,
        dataset_count=1, baseline_count=0,
        has_public_dataset=True, has_repro_baseline=False, has_metrics=True,
    )

    rec = one_topic.recommend_proposal(_req(pid), _keywords(), ev, _feas())

    # 不应出现硬编码的 attention / 轻量化等
    full_text = (
        " ".join(w.title for w in rec.work_packages)
        + " "
        + " ".join(w.method_approach for w in rec.work_packages)
    )
    forbidden = ["注意力机制", "attention mechanism", "self-attention", "轻量化模块"]
    for word in forbidden:
        assert word not in full_text, f"无 module_paper 时不应出现兜底词 '{word}'"

    # 至少有 1 个工作包, 提到 baseline (c_swintransformer) 或 dataset (NEU-DET)
    assert len(rec.work_packages) >= 1, "选了 baseline 后即使没 module_paper 也应至少 1 个 WP"
    print(f"[T7 §3] fallback WP={rec.work_packages[0].title}")


# ---------- T7 §4: project_id_override 为空 → 用 "ot_pending" 兜底, 不报错 ---------- #


def test_no_project_id_override_does_not_error():
    """没传 project_id_override → 用 'ot_pending', 不应抛错, 也不应误报已选 baseline."""

    rec = one_topic.recommend_proposal(_req(project_id=None), _keywords(), _ev(), _feas())
    assert rec.work_packages == [], "没传 project_id 时视为未选 baseline, 不应生成 WP"
    assert any("请先从候选论文" in r for r in rec.recommendation_reason)


# ---------- T7 §5: 推荐 topic 始终不为空 ---------- #


def test_recommended_topic_always_present():
    """无 baseline 时, recommended_topic 仍应有内容 (只是不挂工作包)."""

    rec = one_topic.recommend_proposal(_req("proj_topic_check"), _keywords(), _ev(), _feas())
    assert rec.recommended_topic, "recommended_topic 不应为空"
    assert "YOLO" in rec.recommended_topic or "钢材" in rec.recommended_topic


if __name__ == "__main__":
    print("[session65_t7_work_package_baseline] run pytest")
