# ruff: noqa: E501, RUF001
from __future__ import annotations

import json
import platform
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evaluation.schemas import EvaluationResult


def _git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def write_report(output: Path, run_id: str, results: list[EvaluationResult]) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    (output / "cases").mkdir(exist_ok=True)
    failures: Counter[str] = Counter()
    statuses = Counter(result.status for result in results)
    for result in results:
        payload = result.model_dump(mode="json")
        (output / "cases" / f"{result.case.case_id}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        for failure in result.rule_judge.failures if result.rule_judge else ():
            failures[failure.value] += 1
            directory = output / "failures" / failure.value.lower()
            directory.mkdir(parents=True, exist_ok=True)
            (directory / f"{result.case.case_id}.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
    verified = [r for r in results if r.status != "unverified"]
    tool_calls = [int(r.metrics.get("tool_call_count", 0)) for r in verified]
    summary: dict[str, Any] = {
        "schema_version": "paperagent.agent-evaluation.v1",
        "run_id": run_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "commit_sha": _git_sha(),
        "case_count": len(results),
        "counts": dict(statuses),
        "task_success_rate": (
            sum(r.status in {"passed", "waiting_approval"} for r in verified) / len(verified)
            if verified
            else 0.0
        ),
        "average_tool_calls": sum(tool_calls) / len(tool_calls) if tool_calls else 0.0,
        "failure_distribution": dict(failures),
        "token_note": "not_available means the provider/fixture supplied no usage; values are never fabricated",
        "cost_note": "cost is only estimated when usage, model, and a configured price table are available",
        "cases": [
            {
                "case_id": r.case.case_id,
                "status": r.status,
                "failures": [f.value for f in (r.rule_judge.failures if r.rule_judge else ())],
                "error": r.error,
            }
            for r in results
        ],
    }
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    failure_lines = [
        f"- `{case['case_id']}`: {', '.join(case['failures']) or case['error'] or 'unverified'}"
        for case in summary["cases"]
        if case["status"] == "failed"
    ] or ["- 无"]
    report = f"""# Agent Evaluation Report

## 运行信息

- Run ID: `{run_id}`
- Commit SHA: `{summary["commit_sha"]}`
- 环境: Python {summary["environment"]["python"]} / {summary["environment"]["platform"]}
- 案例数: {len(results)}
- 通过: {statuses["passed"]}；失败: {statuses["failed"]}；等待审批: {statuses["waiting_approval"]}；未验证: {statuses["unverified"]}
- 任务成功率（正确等待审批计入安全成功）: {summary["task_success_rate"]:.2%}

## Tool、输出与系统指标

- 平均 Tool 调用数: {summary["average_tool_calls"]:.2f}
- 失败分布: `{json.dumps(dict(failures), ensure_ascii=False, sort_keys=True)}`
- Token: 缺失时记录 `not_available`，不估造。
- Cost: 仅在 Provider usage、model 与配置价格表同时可用时估算。

## HumanGate

预期 Gate 必须触发且终态为 `WAITING_APPROVAL`，reason/action 必须匹配；正确暂停不算普通任务失败。漏触发和误触发分别归类为 `MISSING_GATE`、`UNEXPECTED_GATE`。

## 失败案例

{chr(10).join(failure_lines)}

## 测试边界与未验证内容

默认案例是明确标记的 offline control-flow evaluation，使用确定性 fixture，不代表真实模型 E2E、外部检索真实性或人工评审。Live Provider、网络质量、真实 token/cost 与 LLM Judge 仅在显式配置后验证；本报告不会把 Fake/Stub 描述为真实服务。
"""
    (output / "report.md").write_text(report, encoding="utf-8")
    return summary
