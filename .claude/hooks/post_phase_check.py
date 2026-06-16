#!/usr/bin/env python3
"""Stop hook: 检查未提交改动是否包含 Phase 完工所需的全部产物。

不阻断 (exit 0)，仅输出提醒到 stderr，让 Claude 在 Stop 时看到提示。
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
REPORTS_DIR = REPO / "Plan" / "reports"


def _git(*args: str) -> str:
    try:
        out = subprocess.check_output(
            ["git", *args],
            cwd=REPO,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
        return out.decode("utf-8", errors="replace").strip()
    except Exception:
        return ""


def _git_diff_shortstat() -> str:
    return _git("diff", "--shortstat")


def _git_status_short() -> str:
    return _git("status", "--short")


def _git_log_recent(n: int = 5) -> str:
    return _git("log", f"-n{n}", "--oneline")


def _has_uncommitted_phase_work() -> bool:
    """粗略：diff 非空 + 改动包含 packages/ 或 apps/ 即视为新阶段工作。"""

    if not _git_diff_shortstat():
        return False
    diff_names = _git("diff", "--name-only", "HEAD")
    return any(p.startswith(("packages/", "apps/")) for p in diff_names.splitlines())


def _existing_phase_reports() -> set[str]:
    if not REPORTS_DIR.exists():
        return set()
    return {p.name for p in REPORTS_DIR.glob("Phase_*_*.md")}


def _extract_phase_numbers(commit_msgs: list[str]) -> set[str]:
    nums: set[str] = set()
    for m in commit_msgs:
        m = re.sub(r"^[0-9a-f]+\s+", "", m)
        m_match = re.match(r"Phase\s+(\d+)", m, re.IGNORECASE)
        if m_match:
            nums.add(m_match.group(1))
    return nums


def main() -> int:
    print("=" * 60, file=sys.stderr)
    print("[post_phase_check] TopicPilot-CN Stop hook", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    # 1. 工作区是否脏
    if not _has_uncommitted_phase_work() and not _git_status_short():
        print("[ok] 无未提交改动", file=sys.stderr)
        return 0

    # 2. 最近 commit 列表
    recent = _git_log_recent(10).splitlines()
    committed_phases = _extract_phase_numbers(recent)
    print(f"[info] 最近 commit 包含的 Phase: {sorted(committed_phases) or '∅'}",
          file=sys.stderr)

    # 3. 已存在的报告
    reports = _existing_phase_reports()
    print(f"[info] 现有报告: {sorted(reports) or '∅'}", file=sys.stderr)

    # 4. 缺哪些 Phase 的报告
    missing = []
    for p in sorted(committed_phases):
        candidates = [
            f"Phase_{int(p):02d}_完工报告.md",
            f"Phase_{int(p):02d}_Demo案例集报告.md",
        ]
        if not any(c in reports for c in candidates):
            missing.append(p)
    if missing:
        print(f"[WARN] Phase {missing} 已 commit 但缺少验收报告 (Plan/reports/Phase_XX_*.md)",
              file=sys.stderr)

    # 5. 工作区脏
    if _git_status_short():
        print("[WARN] 工作区有未提交改动:", file=sys.stderr)
        for line in _git_status_short().splitlines()[:20]:
            print(f"    {line}", file=sys.stderr)

    # 6. 测试是否最新
    print("[hint] 建议运行: uv run pytest", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
