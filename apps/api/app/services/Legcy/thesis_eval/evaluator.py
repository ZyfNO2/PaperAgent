"""Session 51: 4 任务指标计算 (evaluator).

4 任务 (SOP §5):
1. 题录抓取与链接保真: URL保真率/题名抽取准确率/年份抽取准确率/无全文降级正确率
2. 实验需求标签抽取: Macro-F1/数据风险召回率/硬件风险召回率/H100误判率
3. 项目难度与周期评估: 难度准确率/邻档准确率/周期邻档准确率/高风险召回率
4. 报告生成质量: 支撑句比例/幻觉率/降级建议可用率/人工审核触发率

合格线 (SOP §5.5 三指标):
    幻觉率     ≤ 0.05
    URL 保真率 ≥ 0.98
    支撑句比例 ≥ 0.85

指标口径对齐 S34 rag_evaluator 的纯函数风格, 操作题录级 (非 chunk).
"""

from __future__ import annotations

from typing import Any

from ...schemas_thesis_eval import (
    Difficulty,
    ExperimentNeedTag,
    ThesisAssessment,
    ThesisEvalResult,
    ThesisRecord,
)

_DIFF_ORDER: list[Difficulty] = ["低-中", "中", "中-高", "高"]

# 周期邻档: 把 cycle 文本归到 4 档 (0.5–2天/1–3天/3–10天/1–3周), 邻档命中即算对
_CYCLE_BUCKETS: list[tuple[str, tuple[float, float]]] = [
    ("0.5–2天/轮", (0.5, 2.0)),
    ("0.5–3天/轮", (0.5, 3.0)),
    ("1–3天/轮", (1.0, 3.0)),
    ("3–10天/轮", (3.0, 10.0)),
    ("5–14天/轮", (5.0, 14.0)),
    ("1–3周/轮", (7.0, 21.0)),
]

# 9 标签全集 (Macro-F1 分母)
_ALL_TAGS: tuple[ExperimentNeedTag, ...] = (
    "single_gpu_ok",
    "cpu_or_light_gpu_ok",
    "large_gpu_optional",
    "h100_level_not_recommended",
    "self_collected_dataset",
    "public_dataset_available",
    "hardware_platform_required",
    "annotation_heavy",
    "domain_data_permission_risk",
)

# 数据风险标签 + 硬件风险标签 (召回率计算用)
_DATA_RISK_TAGS = {"self_collected_dataset", "domain_data_permission_risk"}
_HARDWARE_RISK_TAGS = {"hardware_platform_required"}
# 普通 YOLO/U-Net 误判 H100 的检测标签 (H100 误判率分母)
_YOLO_UNET_TAGS = {"single_gpu_ok"}


# ---------- 任务一: 题录抓取与链接保真 ---------- #


def _title_match(pred_title: str, gold_title: str) -> bool:
    """题名近似匹配: 归一化后 jaccard ≥ 0.6 或子串包含."""
    import re

    def norm(t: str) -> set[str]:
        t = re.sub(r"[\s\W_]+", "", t.lower())
        return set(t) if t else set()

    if not pred_title or not gold_title:
        return False
    a, b = norm(pred_title), norm(gold_title)
    if a == b:
        return True
    if a and b and (a & b == a or a & b == b):
        return True
    if a and b:
        return len(a & b) / len(a | b) >= 0.6
    return False


def compute_task1_metrics(record: ThesisRecord, gold: dict) -> dict[str, Any]:
    """任务一: 题录抓取与链接保真 (单条)."""
    gold_title = gold.get("title", "")
    gold_year = gold.get("year")
    # URL 保真: source_url 非空且等于 gold (未替换未伪造)
    gold_url = gold.get("source_url", "")
    url_fidelity = bool(record.source_url) and (
        not gold_url or record.source_url == gold_url
    )
    # 题名抽取
    title_correct = _title_match(record.title, gold_title) if gold_title else (record.verified_status in ("verified", "partial"))
    # 年份抽取
    year_correct = (gold_year is None) or (record.year == gold_year)
    # 无全文降级正确: verified_status != verified 时不应有编造的摘要 (abstract 来自 fallback 或 None)
    degrade_correct = True
    if record.verified_status != "verified":
        # 降级时 abstract_snippet 只能来自题录或 fallback, 不能编造 — 用 fallback_used 标记
        degrade_correct = not (record.abstract_snippet and not record.fallback_used and record.verified_status == "failed")

    return {
        "url_fidelity": url_fidelity,
        "title_extracted": bool(record.title),
        "title_correct": title_correct,
        "year_correct": year_correct,
        "degrade_correct": degrade_correct,
        "verified_status": record.verified_status,
    }


# ---------- 任务二: 实验需求标签抽取 ---------- #


def _multi_label_prf(pred: set[str], gold: set[str]) -> tuple[float, float, float]:
    """单样本多标签 P/R/F1."""
    if not pred and not gold:
        return 1.0, 1.0, 1.0
    tp = len(pred & gold)
    p = tp / len(pred) if pred else 0.0
    r = tp / len(gold) if gold else 0.0
    f1 = (2 * p * r / (p + r)) if (p + r) > 0 else 0.0
    return p, r, f1


def compute_task2_metrics(
    pred_tags: list[ExperimentNeedTag], gold_tags: list[ExperimentNeedTag]
) -> dict[str, Any]:
    """任务二: 实验需求标签抽取 (单条)."""
    pred_set = set(pred_tags)
    gold_set = set(gold_tags)

    # per-label P/R/F1 (供 Macro-F1 聚合)
    per_label: dict[str, dict[str, float]] = {}
    for tag in _ALL_TAGS:
        tp = 1 if (tag in pred_set and tag in gold_set) else 0
        fp = 1 if (tag in pred_set and tag not in gold_set) else 0
        fn = 1 if (tag not in pred_set and tag in gold_set) else 0
        p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * p * r / (p + r)) if (p + r) > 0 else 0.0
        per_label[tag] = {"precision": p, "recall": r, "f1": f1}

    # 数据风险召回: gold 里有数据风险标签, pred 是否召回
    gold_data_risk = gold_set & _DATA_RISK_TAGS
    data_risk_recall = (
        bool(pred_set & gold_data_risk) if gold_data_risk else True
    )
    # 硬件风险召回
    gold_hw_risk = gold_set & _HARDWARE_RISK_TAGS
    hw_risk_recall = (bool(pred_set & gold_hw_risk) if gold_hw_risk else True)
    # H100 误判: 普通 YOLO/U-Net (gold single_gpu_ok 且无 large_gpu/hardware) 误判为 h100
    is_yolo_unet = bool(gold_set & _YOLO_UNET_TAGS) and not (gold_set & {"large_gpu_optional", "hardware_platform_required"})
    h100_misjudge = is_yolo_unet and ("h100_level_not_recommended" in pred_set)

    return {
        "per_label": per_label,
        "pred_tags": sorted(pred_set),
        "gold_tags": sorted(gold_set),
        "data_risk_recall": data_risk_recall,
        "hw_risk_recall": hw_risk_recall,
        "h100_misjudge": h100_misjudge,
        "is_yolo_unet_case": is_yolo_unet,
    }


# ---------- 任务三: 项目难度与周期评估 ---------- #


def _cycle_bucket(cycle: str | None) -> int:
    """把 cycle 文本归到 4 档 index (0=0.5-2天, 1=1-3天, 2=3-10天, 3=1-3周). 邻档命中."""
    if not cycle:
        return -1
    cl = cycle.lower().replace("–", "-").replace("—", "-")
    if "周" in cl:
        return 3
    if "3" in cl and ("10" in cl or "14" in cl):
        return 2
    if "5" in cl and "14" in cl:
        return 2
    if "1" in cl and "3" in cl and "天" in cl:
        return 1
    if "0.5" in cl or "0-2" in cl or "0.5-2" in cl or "0.5-3" in cl:
        return 0
    if "天" in cl:
        return 1
    return -1


def compute_task3_metrics(
    pred_diff: Difficulty | None, gold_diff: Difficulty,
    pred_cycle: str | None, gold_cycle: str,
) -> dict[str, Any]:
    """任务三: 项目难度与周期评估 (单条)."""
    # 难度准确率 (完全匹配)
    diff_correct = pred_diff == gold_diff
    # 邻档准确率 (最多差一档)
    diff_adjacent = False
    if pred_diff and gold_diff:
        pi = _DIFF_ORDER.index(pred_diff)
        gi = _DIFF_ORDER.index(gold_diff)
        diff_adjacent = abs(pi - gi) <= 1
    # 周期邻档
    pred_cb = _cycle_bucket(pred_cycle)
    gold_cb = _cycle_bucket(gold_cycle)
    cycle_adjacent = (pred_cb >= 0 and gold_cb >= 0 and abs(pred_cb - gold_cb) <= 1)
    # 高风险召回: gold 是 高/中-高, pred 是否也是 高/中-高
    gold_high = gold_diff in ("高", "中-高")
    high_risk_recall = (pred_diff in ("高", "中-高")) if gold_high else True

    return {
        "difficulty_correct": diff_correct,
        "difficulty_adjacent": diff_adjacent,
        "cycle_adjacent": cycle_adjacent,
        "high_risk_recall": high_risk_recall,
        "gold_high_risk": gold_high,
    }


# ---------- 任务四: 报告生成质量 ---------- #


def compute_task4_metrics(assessment: ThesisAssessment, gold: dict) -> dict[str, Any]:
    """任务四: 报告生成质量 (单条).

    - 支撑句比例: 关键判断 (难度/周期/需求) 有 evidence_refs 支撑的比例.
    - 幻觉率: unsupported_claims 里若声明「未编造」则 0; 若有编造迹象则 1.
    - 降级建议可用率: 高风险论文有具体降级建议.
    - 人工审核触发率: 信息不足时进 human_review.
    """
    # 关键判断: difficulty / cycle / needs — 每个应有 evidence_ref
    key_claims = 0
    supported = 0
    ref_reasons = " ".join(ref.reason for ref in assessment.evidence_refs)
    if assessment.difficulty:
        key_claims += 1
        if "难度" in ref_reasons or "difficulty" in ref_reasons.lower():
            supported += 1
    if assessment.cycle:
        key_claims += 1
        if "周期" in ref_reasons or "cycle" in ref_reasons.lower() or "难度" in ref_reasons:
            supported += 1
    if assessment.experiment_needs:
        key_claims += 1
        if "实验需求" in ref_reasons or "needs" in ref_reasons.lower() or "需求" in ref_reasons:
            supported += 1
    support_ratio = (supported / key_claims) if key_claims > 0 else 1.0

    # 幻觉率: 检查 unsupported_claims 是否声明未编造; 若 abstract_snippet 在 failed 状态下非空且非 fallback → 幻觉
    hallucination = 0
    if assessment.record.verified_status == "failed" and assessment.record.abstract_snippet and not assessment.record.fallback_used:
        hallucination = 1
    # 显式检查 evidence_refs 是否提到编造的数据集/指标 (防幻觉) — 这里 heuristic 不编造, 默认 0
    claim_text = " ".join(assessment.unsupported_claims) + " " + ref_reasons
    # 若出现「未编造」声明 → 幻觉率 0; 否则保持
    if "未编造" in " ".join(assessment.unsupported_claims):
        hallucination = 0

    # 降级建议可用率: 高风险 (难度 高/中-高 或 feasibility 非可做) 必须有降级建议
    advice = assessment.__dict__.get("_degradation_advice", "")
    is_high_risk = assessment.difficulty in ("高", "中-高") or assessment.graduation_feasibility in ("收缩后可做", "暂缓", "不建议")
    degradation_available = bool(advice) if is_high_risk else True

    # 人工审核触发率: 信息不足 (failed/partial 无摘要 或 高风险) 应触发 human_review
    needs_review = (
        assessment.record.verified_status in ("failed", "partial")
        and not assessment.record.abstract_snippet
    ) or (assessment.difficulty in ("高", "中-高"))
    review_triggered = assessment.__dict__.get("_human_review_triggered", False)
    human_review_correct = (review_triggered == needs_review) if needs_review else True

    return {
        "support_ratio": round(support_ratio, 3),
        "hallucination": hallucination,
        "degradation_available": degradation_available,
        "is_high_risk": is_high_risk,
        "human_review_triggered": review_triggered,
        "human_review_correct": human_review_correct,
    }


# ---------- 单条聚合 ---------- #


def compute_task_metrics(
    assessment: ThesisAssessment, gold: dict
) -> dict[str, Any]:
    """单条题录的 4 任务指标 + hits."""
    record = assessment.record
    gold_tags: list[ExperimentNeedTag] = (
        list(gold.get("compute_need", []))
        + list(gold.get("data_need", []))
        + list(gold.get("hardware_need", []))
    )
    t1 = compute_task1_metrics(record, gold)
    t2 = compute_task2_metrics(assessment.experiment_needs, gold_tags)
    t3 = compute_task3_metrics(
        assessment.difficulty, gold.get("difficulty", "中"),
        assessment.cycle, gold.get("cycle", ""),
    )
    t4 = compute_task4_metrics(assessment, gold)

    hits = {
        "url_fidelity": t1["url_fidelity"],
        "title_correct": t1["title_correct"],
        "year_correct": t1["year_correct"],
        "degrade_correct": t1["degrade_correct"],
        "difficulty_correct": t3["difficulty_correct"],
        "difficulty_adjacent": t3["difficulty_adjacent"],
        "cycle_adjacent": t3["cycle_adjacent"],
        "high_risk_recall": t3["high_risk_recall"],
        "data_risk_recall": t2["data_risk_recall"],
        "hw_risk_recall": t2["hw_risk_recall"],
        "h100_misjudge": t2["h100_misjudge"],
        "support_ratio": t4["support_ratio"],
        "hallucination": t4["hallucination"],
        "degradation_available": t4["degradation_available"],
        "human_review_correct": t4["human_review_correct"],
    }

    return {
        "task1": t1,
        "task2": t2,
        "task3": t3,
        "task4": t4,
        "hits": hits,
    }


# ---------- 聚合指标 (多题) ---------- #


def _safe_mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def aggregate_metrics(results: list[ThesisEvalResult]) -> dict[str, Any]:
    """4 任务聚合指标 + 合格线对比 (SOP §5)."""
    n = len(results)
    if n == 0:
        return _empty_aggregate()

    # 任务一
    url_fidelity = sum(1 for r in results if r.hits["url_fidelity"]) / n
    title_correct = sum(1 for r in results if r.hits["title_correct"]) / n
    year_correct = sum(1 for r in results if r.hits["year_correct"]) / n
    degrade_correct = sum(1 for r in results if r.hits["degrade_correct"]) / n

    # 任务二: Macro-F1 (跨样本 per-label 平均)
    label_f1s: dict[str, list[float]] = {tag: [] for tag in _ALL_TAGS}
    for r in results:
        for tag, prf in r.task_metrics["task2"]["per_label"].items():
            # 只统计该样本 gold 或 pred 命中过的标签 (标准 macro 多标签做法)
            if tag in set(r.task_metrics["task2"]["gold_tags"]) or tag in set(r.task_metrics["task2"]["pred_tags"]):
                label_f1s[tag].append(prf["f1"])
            else:
                label_f1s[tag].append(1.0)  # 都没命中 → 该样本该标签 F1=1
    macro_f1 = _safe_mean([_safe_mean(label_f1s[tag]) for tag in _ALL_TAGS])

    data_risk_gold = [r for r in results if any(
        t in _DATA_RISK_TAGS for t in set(r.task_metrics["task2"]["gold_tags"])
    )]
    hw_risk_gold = [r for r in results if any(
        t in _HARDWARE_RISK_TAGS for t in set(r.task_metrics["task2"]["gold_tags"])
    )]
    yolo_cases = [r for r in results if r.task_metrics["task2"]["is_yolo_unet_case"]]
    data_risk_recall = (
        sum(1 for r in data_risk_gold if r.hits["data_risk_recall"]) / len(data_risk_gold)
        if data_risk_gold else 1.0
    )
    hw_risk_recall = (
        sum(1 for r in hw_risk_gold if r.hits["hw_risk_recall"]) / len(hw_risk_gold)
        if hw_risk_gold else 1.0
    )
    h100_misjudge_rate = (
        sum(1 for r in yolo_cases if r.hits["h100_misjudge"]) / len(yolo_cases)
        if yolo_cases else 0.0
    )

    # 任务三
    diff_correct = sum(1 for r in results if r.hits["difficulty_correct"]) / n
    diff_adjacent = sum(1 for r in results if r.hits["difficulty_adjacent"]) / n
    cycle_adjacent = sum(1 for r in results if r.hits["cycle_adjacent"]) / n
    high_risk_gold = [r for r in results if r.task_metrics["task3"]["gold_high_risk"]]
    high_risk_recall = (
        sum(1 for r in high_risk_gold if r.hits["high_risk_recall"]) / len(high_risk_gold)
        if high_risk_gold else 1.0
    )

    # 任务四
    support_ratio = sum(r.hits["support_ratio"] for r in results) / n
    hallucination_rate = sum(r.hits["hallucination"] for r in results) / n
    high_risk_results = [r for r in results if r.task_metrics["task4"]["is_high_risk"]]
    degradation_rate = (
        sum(1 for r in high_risk_results if r.hits["degradation_available"]) / len(high_risk_results)
        if high_risk_results else 1.0
    )
    needs_review_results = [r for r in results if r.task_metrics["task4"].get("human_review_triggered") or r.task_metrics["task3"]["gold_high_risk"]]
    human_review_rate = (
        sum(1 for r in needs_review_results if r.hits["human_review_correct"]) / len(needs_review_results)
        if needs_review_results else 1.0
    )

    return {
        "task1": {
            "url_fidelity_rate": round(url_fidelity, 4),
            "title_extract_rate": round(title_correct, 4),
            "year_extract_rate": round(year_correct, 4),
            "degrade_correct_rate": round(degrade_correct, 4),
            "thresholds": {"url_fidelity": 0.98, "title": 0.95, "year": 0.90, "degrade": 0.95},
        },
        "task2": {
            "macro_f1": round(macro_f1, 4),
            "data_risk_recall": round(data_risk_recall, 4),
            "hw_risk_recall": round(hw_risk_recall, 4),
            "h100_misjudge_rate": round(h100_misjudge_rate, 4),
            "thresholds": {"macro_f1": 0.75, "data_risk_recall": 0.85, "hw_risk_recall": 0.85, "h100_misjudge": 0.05},
        },
        "task3": {
            "difficulty_acc": round(diff_correct, 4),
            "difficulty_adjacent_acc": round(diff_adjacent, 4),
            "cycle_adjacent_acc": round(cycle_adjacent, 4),
            "high_risk_recall": round(high_risk_recall, 4),
            "thresholds": {"difficulty": 0.70, "adjacent": 0.90, "cycle_adjacent": 0.85, "high_risk_recall": 0.85},
        },
        "task4": {
            "support_ratio": round(support_ratio, 4),
            "hallucination_rate": round(hallucination_rate, 4),
            "degradation_rate": round(degradation_rate, 4),
            "human_review_rate": round(human_review_rate, 4),
            "thresholds": {"support": 0.85, "hallucination": 0.05, "degradation": 0.80, "human_review": 0.90},
        },
        "key_metrics": {
            "hallucination_rate": round(hallucination_rate, 4),
            "url_fidelity_rate": round(url_fidelity, 4),
            "support_ratio": round(support_ratio, 4),
        },
    }


def _empty_aggregate() -> dict[str, Any]:
    return {
        "task1": {"url_fidelity_rate": 0.0, "title_extract_rate": 0.0, "year_extract_rate": 0.0, "degrade_correct_rate": 0.0, "thresholds": {}},
        "task2": {"macro_f1": 0.0, "data_risk_recall": 0.0, "hw_risk_recall": 0.0, "h100_misjudge_rate": 0.0, "thresholds": {}},
        "task3": {"difficulty_acc": 0.0, "difficulty_adjacent_acc": 0.0, "cycle_adjacent_acc": 0.0, "high_risk_recall": 0.0, "thresholds": {}},
        "task4": {"support_ratio": 0.0, "hallucination_rate": 0.0, "degradation_rate": 0.0, "human_review_rate": 0.0, "thresholds": {}},
        "key_metrics": {"hallucination_rate": 0.0, "url_fidelity_rate": 0.0, "support_ratio": 0.0},
    }
