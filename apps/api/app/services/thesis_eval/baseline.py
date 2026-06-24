"""Session 51: baseline 存读 + 对比 (SOP §12 Task 8).

baseline 存到 data/thesis_eval/outputs/baseline.json.
对比规则 (测试集文档 §10):
    幻觉率上升          → 红线警告
    URL 保真率下降 > 0.02 → 红线警告
    支撑句比例下降 > 0.05 → 警告
    高风险召回率下降 > 0.05 → 警告
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_BASELINE_DIR = Path("data/thesis_eval/outputs")
_BASELINE_FILE = _BASELINE_DIR / "baseline.json"


def save_baseline(aggregate: dict[str, Any], subset: str = "smoke_20") -> Path:
    """把当前 run 的聚合指标存为 baseline."""
    _BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "subset": subset,
        "aggregate_metrics": aggregate,
        "key_metrics": aggregate.get("key_metrics", {}),
    }
    _BASELINE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("baseline saved to %s (subset=%s)", _BASELINE_FILE, subset)
    return _BASELINE_FILE


def load_baseline() -> dict[str, Any] | None:
    """读 baseline, 不存在返回 None."""
    if not _BASELINE_FILE.exists():
        return None
    try:
        return json.loads(_BASELINE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("baseline load failed: %s", exc)
        return None


def diff_against_baseline(
    current: dict[str, Any], baseline: dict[str, Any] | None
) -> tuple[dict[str, Any], list[str]]:
    """对比当前 run 与 baseline, 返回 (diff, regressions).

    regressions 是退化项的人类可读描述 (不 fail pytest, 只警告).
    """
    if baseline is None:
        return {}, []

    cur_key = current.get("key_metrics", {})
    base_key = baseline.get("key_metrics", {}) or (
        baseline.get("aggregate_metrics", {}).get("key_metrics", {})
    )

    diff: dict[str, Any] = {}
    regressions: list[str] = []

    # 幻觉率: 上升 → 红线
    cur_hall = cur_key.get("hallucination_rate", 0.0)
    base_hall = base_key.get("hallucination_rate", 0.0)
    diff["hallucination_rate"] = {"baseline": base_hall, "current": cur_hall, "delta": round(cur_hall - base_hall, 4)}
    if cur_hall > base_hall:
        regressions.append(f"幻觉率上升: {base_hall} → {cur_hall} (红线)")

    # URL 保真率: 下降 > 0.02 → 红线
    cur_url = cur_key.get("url_fidelity_rate", 0.0)
    base_url = base_key.get("url_fidelity_rate", 0.0)
    diff["url_fidelity_rate"] = {"baseline": base_url, "current": cur_url, "delta": round(cur_url - base_url, 4)}
    if base_url - cur_url > 0.02:
        regressions.append(f"URL保真率下降 > 0.02: {base_url} → {cur_url} (红线)")

    # 支撑句比例: 下降 > 0.05 → 警告
    cur_sup = cur_key.get("support_ratio", 0.0)
    base_sup = base_key.get("support_ratio", 0.0)
    diff["support_ratio"] = {"baseline": base_sup, "current": cur_sup, "delta": round(cur_sup - base_sup, 4)}
    if base_sup - cur_sup > 0.05:
        regressions.append(f"支撑句比例下降 > 0.05: {base_sup} → {cur_sup}")

    # 高风险召回率: 下降 > 0.05 → 警告
    cur_hr = current.get("task3", {}).get("high_risk_recall", 0.0)
    base_hr = (baseline.get("aggregate_metrics", {}) or {}).get("task3", {}).get("high_risk_recall", 0.0)
    diff["high_risk_recall"] = {"baseline": base_hr, "current": cur_hr, "delta": round(cur_hr - base_hr, 4)}
    if base_hr - cur_hr > 0.05:
        regressions.append(f"高风险召回率下降 > 0.05: {base_hr} → {cur_hr}")

    return diff, regressions
