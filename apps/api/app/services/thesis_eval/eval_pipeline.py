"""Session 51: 评估管线 (跑测试集 → 聚合 → baseline 对比 → 回归警告).

流程 (SOP §12 Task 8):
    load thesis_seed_100.jsonl → 按 subset 选子集
        ↓
    对每条: crawl → extract_needs → score_difficulty → build_assessment_report
        ↓
    compute_task_metrics (predicted vs gold) → ThesisEvalResult
        ↓
    aggregate_metrics (4 任务聚合)
        ↓
    diff_against_baseline → regressions (不 fail pytest, 只警告)
        ↓
    ThesisEvalReport

测试集抓取在测试里必须 mock (避免依赖网络). 评估不依赖外部 API.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...schemas_thesis_eval import (
    SubsetName,
    ThesisAssessment,
    ThesisEvalReport,
    ThesisEvalResult,
)
from .baseline import diff_against_baseline, load_baseline
from .crawler import crawl_thesis_record
from .difficulty_scorer import score_difficulty
from .evaluator import aggregate_metrics, compute_task_metrics
from .need_extractor import extract_experiment_needs
from .report_builder import build_assessment_report

logger = logging.getLogger(__name__)

_SEED_FILE = Path("data/thesis_eval/thesis_seed_100.jsonl")
_SMOKE_FILE = Path("data/thesis_eval/smoke_20.txt")

# 子集定义 (测试集文档 §3)
_SUBSET_FILTERS: dict[str, Any] = {
    "smoke_20": "smoke",
    "all_100": "all",
}


def load_seed(path: Path = _SEED_FILE) -> list[dict[str, Any]]:
    """加载 100 条题录种子 (含 gold)."""
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _load_smoke_ids(path: Path = _SMOKE_FILE) -> set[str]:
    if not path.exists():
        return set()
    return {ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()}


def select_subset(seed: list[dict[str, Any]], subset: SubsetName) -> list[dict[str, Any]]:
    """按子集筛选 (smoke_20 / regression_60 / hard_20 / all_100).

    - smoke_20: smoke_20.txt 的 20 个 id
    - all_100: 全部 100 条
    - regression_60: 非 smoke 且非 hard 的 60 条
    - hard_20: 高风险 (gold difficulty 高/中-高) 的 20 条
    """
    if subset == "all_100":
        return list(seed)
    if subset == "smoke_20":
        smoke_ids = _load_smoke_ids()
        return [s for s in seed if s["id"] in smoke_ids]
    if subset == "hard_20":
        hard = [s for s in seed if s.get("gold", {}).get("difficulty") in ("高", "中-高")]
        return hard[:20]
    if subset == "regression_60":
        smoke_ids = _load_smoke_ids()
        hard_ids = {s["id"] for s in seed if s.get("gold", {}).get("difficulty") in ("高", "中-高")}
        reg = [s for s in seed if s["id"] not in smoke_ids and s["id"] not in hard_ids]
        return reg[:60]
    return list(seed)


def assess_single(
    thesis: dict[str, Any],
    *,
    use_llm: bool = False,
    http_client: Any = None,
) -> ThesisAssessment:
    """对单条题录跑完整评估链: crawl → needs → difficulty → report.

    抓取失败自动降级为题录级证据 (用测试集已给字段), 不崩不编造.
    """
    thesis_id = thesis["id"]
    source_url = thesis.get("source_url", "")
    fallback = {
        "title": thesis.get("title", ""),
        "year": thesis.get("year"),
        "abstract_snippet": thesis.get("experiment_need"),  # 测试集 experiment_need 当摘要片段降级
        "domain": thesis.get("domain"),
    }
    record = crawl_thesis_record(
        thesis_id, source_url, fallback=fallback, http_client=http_client
    )

    # needs + difficulty 基于题名+摘要片段 (摘要缺失时用 experiment_need 兜底文本)
    text_for_inference = record.abstract_snippet or thesis.get("experiment_need", "")
    needs, mode = extract_experiment_needs(record.title or thesis.get("title", ""), text_for_inference, use_llm=use_llm)
    difficulty_info = score_difficulty(
        record.title or thesis.get("title", ""), text_for_inference, needs
    )

    assessment = build_assessment_report(
        thesis_id, record, needs, difficulty_info, assessment_mode=mode
    )
    return assessment


def run_thesis_eval(
    subset: SubsetName = "smoke_20",
    *,
    use_llm: bool = False,
    save_baseline_flag: bool = False,
    seed_path: Path = _SEED_FILE,
    http_client: Any = None,
) -> ThesisEvalReport:
    """跑一个子集的完整评估 → ThesisEvalReport.

    Args:
        subset: smoke_20 / regression_60 / hard_20 / all_100
        use_llm: 是否启用 LLM 抽标签 (失败自动 fallback heuristic)
        save_baseline_flag: True 则把当前 run 存为 baseline
        seed_path: 测试集 jsonl 路径 (测试可注入)
        http_client: 可注入 httpx.Client (测试 mock)

    Returns:
        ThesisEvalReport
    """
    seed = load_seed(seed_path)
    selected = select_subset(seed, subset)

    results: list[ThesisEvalResult] = []
    for thesis in selected:
        try:
            assessment = assess_single(thesis, use_llm=use_llm, http_client=http_client)
        except Exception as exc:  # noqa: BLE001 — 单条失败不阻断整批
            logger.warning("assess %s failed: %s, skip", thesis.get("id"), exc)
            continue
        gold = thesis.get("gold", {})
        # gold 补 title/year/source_url (供任务一比对)
        gold_with_meta = {
            "title": thesis.get("title", ""),
            "year": thesis.get("year"),
            "source_url": thesis.get("source_url", ""),
            **gold,
        }
        task_metrics = compute_task_metrics(assessment, gold_with_meta)
        results.append(
            ThesisEvalResult(
                thesis_id=thesis["id"],
                predicted=assessment,
                gold=gold_with_meta,
                task_metrics=task_metrics,
                hits=task_metrics["hits"],
            )
        )

    agg = aggregate_metrics(results)

    # baseline 对比
    baseline = load_baseline() if not save_baseline_flag else None
    baseline_diff, regressions = diff_against_baseline(agg, baseline)

    if save_baseline_flag:
        from .baseline import save_baseline
        save_baseline(agg, subset=subset)

    return ThesisEvalReport(
        run_id=f"thesis_eval_{uuid.uuid4().hex[:8]}",
        created_at=datetime.now(timezone.utc).isoformat(),
        subset=subset,
        thesis_count=len(results),
        results=results,
        aggregate_metrics=agg,
        baseline_diff=baseline_diff,
        regressions=regressions,
    )
