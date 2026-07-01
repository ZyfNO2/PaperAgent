"""Session 50: RAG Evaluation Baseline Storage + Diff.

save_baseline: 把当前 RagEvalReport 存为 baseline.json
load_baseline: 从磁盘读 baseline
diff_against_baseline: 比较当前 report 与 baseline, 返回 per-metric delta + regressions 列表

回归判定 (regressions):
- recall_at_5 下降 > 0.05
- mrr 下降 > 0.05
- ndcg_at_5 下降 > 0.05
- hit_rate 下降 > 0.05
- citation_precision 下降 > 0.05
- evidence_coverage 下降 > 0.05
- unsupported_claim_rate 上升 > 0.05
- faithfulness 下降 > 0.05
- latency_p95 上升 > 100ms
- fallback_rate 上升 > 0.05
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ...schemas_paper_rag_eval import RagEvalReport


# 回归阈值 (回归 = 变差超过该阈值)
# 指标方向: ↑ = 越大越好, ↓ = 越小越好
REGRESSION_THRESHOLDS: dict[str, dict[str, float]] = {
    # metric: { direction: "up"/"down", threshold: 0.05 }
    "recall_at_5": {"direction": "down", "threshold": 0.05},
    "mrr": {"direction": "down", "threshold": 0.05},
    "ndcg_at_5": {"direction": "down", "threshold": 0.05},
    "hit_rate": {"direction": "down", "threshold": 0.05},
    "citation_precision": {"direction": "down", "threshold": 0.05},
    "evidence_coverage": {"direction": "down", "threshold": 0.05},
    "unsupported_claim_rate": {"direction": "up", "threshold": 0.05},
    "faithfulness": {"direction": "down", "threshold": 0.05},
    "latency_p50_ms": {"direction": "up", "threshold": 50.0},
    "latency_p95_ms": {"direction": "up", "threshold": 100.0},
    "fallback_rate": {"direction": "up", "threshold": 0.05},
}


def _default_baseline_path() -> Path:
    return Path(os.environ.get("PAPERAGENT_PAPER_EVAL_DIR", "data/paper_library_eval")) / "baseline.json"


def save_baseline(
    report: RagEvalReport,
    path: str | Path | None = None,
) -> str:
    """把 report 存为 baseline.json.

    Args:
        report: RagEvalReport
        path: 自定义路径, 默认 data/paper_library_eval/baseline.json

    Returns:
        实际保存路径 (str)
    """

    target = Path(path) if path else _default_baseline_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": report.run_id,
        "created_at": report.created_at.isoformat() if hasattr(report.created_at, "isoformat") else str(report.created_at),
        "aggregate_retrieval": report.aggregate_retrieval.model_dump(),
        "aggregate_answer": report.aggregate_answer.model_dump(),
        "aggregate_system": report.aggregate_system.model_dump(),
        "item_count": len(report.items),
    }
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(target)


def load_baseline(path: str | Path | None = None) -> dict[str, Any]:
    """从磁盘读 baseline. 不存在 → 返回空 dict.

    Args:
        path: 自定义路径, 默认 data/paper_library_eval/baseline.json

    Returns:
        baseline 字典 (空 if 不存在)
    """

    target = Path(path) if path else _default_baseline_path()
    if not target.exists():
        return {}
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def diff_against_baseline(
    current: RagEvalReport,
    baseline: dict[str, Any],
) -> dict[str, Any]:
    """比较 current report 与 baseline, 返回 per-metric delta + regressions.

    Args:
        current: 当前的 RagEvalReport
        baseline: load_baseline() 返回的 dict (可能为空)

    Returns:
        {
            "baseline_run_id": str | None,
            "deltas": {
                "recall_at_5": {"baseline": 0.7, "current": 0.65, "delta": -0.05, "direction": "down"},
                ...
            },
            "regressions": ["recall_at_5 dropped by 0.05 (>0.05)", ...]
        }
    """

    result: dict[str, Any] = {
        "baseline_run_id": baseline.get("run_id"),
        "deltas": {},
        "regressions": [],
    }

    if not baseline:
        return result

    base_r = baseline.get("aggregate_retrieval", {}) or {}
    base_a = baseline.get("aggregate_answer", {}) or {}
    base_s = baseline.get("aggregate_system", {}) or {}
    cur_r = current.aggregate_retrieval.model_dump()
    cur_a = current.aggregate_answer.model_dump()
    cur_s = current.aggregate_system.model_dump()

    # 合并所有指标 (retrieval + answer + system)
    metrics_to_check: dict[str, tuple[float, float]] = {}
    for key in cur_r:
        if key in base_r:
            metrics_to_check[key] = (float(base_r[key]), float(cur_r[key]))
    for key in cur_a:
        if key in base_a:
            metrics_to_check[key] = (float(base_a[key]), float(cur_a[key]))
    for key in cur_s:
        if key in base_s:
            metrics_to_check[key] = (float(base_s[key]), float(cur_s[key]))

    for metric, (b_val, c_val) in metrics_to_check.items():
        delta = round(c_val - b_val, 4)
        cfg = REGRESSION_THRESHOLDS.get(metric, {"direction": "down", "threshold": 0.05})
        direction = cfg["direction"]
        threshold = cfg["threshold"]

        result["deltas"][metric] = {
            "baseline": round(b_val, 4),
            "current": round(c_val, 4),
            "delta": delta,
            "direction": direction,
        }

        # 判定回归
        is_regression = False
        if direction == "down":
            # 指标越低越差: delta 负 → 退化
            if delta < -threshold:
                is_regression = True
        elif direction == "up":
            # 指标越高越差 (latency / unsupported rate): delta 正 → 退化
            if delta > threshold:
                is_regression = True

        if is_regression:
            verb = "dropped" if direction == "down" else "rose"
            result["regressions"].append(
                f"{metric} {verb} by {abs(delta):.4f} (>{threshold})"
            )

    return result


__all__ = [
    "REGRESSION_THRESHOLDS",
    "diff_against_baseline",
    "load_baseline",
    "save_baseline",
]
