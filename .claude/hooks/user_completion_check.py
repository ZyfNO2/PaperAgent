#!/usr/bin/env python3
"""Stop hook: 自检本轮对话里所有用户输入是否已完整实现.

行为:
1. 解析当前对话 transcript 里的 User 消息
2. 对每条 user message:
   - 列已 commit 的 git log (最近 20 个 commit)
   - 列已生成的 trace / report 文件
   - 简单判定: 标题里出现的关键名词是否能匹配到 commit message 或 trace file
3. 输出完成度摘要到 stderr (不阻断, exit 0)

设计动机: 在 Re01 用户反复提「有错漏自己汇报」「做完汇报」时, Stop hook
应当帮 agent (人类) 做"对话输入 ↔ 已交付物"自检, 而非过时的 phase check.
取代 .claude/settings.json 里的 `post_phase_check.py` 引用.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _git_log(n: int = 20) -> list[str]:
    try:
        out = subprocess.run(
            ["git", "log", f"-{n}", "--oneline"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        if out.returncode != 0:
            return []
        return [line.strip() for line in out.stdout.splitlines() if line.strip()]
    except Exception:  # noqa: BLE001
        return []


def _traces_and_reports() -> list[str]:
    files: list[str] = []
    for sub in ("tmp_s66v_traces", "Plan/reports"):
        base = REPO / sub
        if not base.exists():
            continue
        for p in base.glob("*.json"):
            files.append(str(p.relative_to(REPO)))
        for p in base.glob("*.md"):
            files.append(str(p.relative_to(REPO)))
    return files


def _extract_keywords(msg: str) -> list[str]:
    """Pull coarse keywords from a user message for matching against deliverables."""
    msg = msg.lower()
    # 1) explicit file / commit ref
    paths = re.findall(r"[a-z_/]+\.(?:py|md|json|ya?ml|toml)", msg)
    # 2) commit-prefix refs (Re00, Re01, Re02 ...)
    commits = re.findall(r"\bre0[0-9]\b", msg, flags=re.IGNORECASE)
    # 3) topic keywords (Chinese / English noun-phrases; keep ≥ 2 chars)
    cn = re.findall(r"[一-鿿]{2,}", msg)
    en_words = re.findall(r"\b[a-z][a-z0-9-]{3,}\b", msg)
    return list({*paths, *commits, *cn, *en_words})


def _transcript_user_messages() -> list[str]:
    """Pull the latest few User messages from the current conversation
    transcript. Claude Code stores them as JSONL under
    ~/.claude/projects/<project-slug>/<conv-uuid>.jsonl.

    Resolution order (most specific first):
      1. env $CLAUDE_PROJECT_DIR → project-slug derived from path
      2. cwd → project-slug derived from path
      3. last-resort: scan all *.jsonl under ~/.claude/projects/, pick newest
    """
    home = Path.home()
    candidates: list[Path] = []

    # 1 + 2: derive project-slug from cwd or env
    cwd = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd()).resolve()
    # Git root of cwd (handles worktrees)
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
        if out.returncode == 0 and out.stdout.strip():
            cwd = Path(out.stdout.strip()).resolve()
    except Exception:  # noqa: BLE001
        pass
    # Windows path "G:\PaperAgent" → slug "G--PaperAgent"
    # Algorithm: replace drive colon + backslashes first, then
    # replace forward slashes with `--`. Result: "G:\PaperAgent"
    # → "G\PaperAgent" → "G--PaperAgent".
    slug_candidate = (
        str(cwd)
        .replace(":", "")
        .replace("\\", "/")
        .replace("/", "--")
        .strip("-")
    )
    projects_dir = home / ".claude" / "projects"
    if projects_dir.exists():
        exact = projects_dir / slug_candidate
        if exact.exists():
            for p in exact.glob("*.jsonl"):
                if p.is_file():
                    candidates.append(p)

    # 3: last-resort scan
    if not candidates:
        try:
            for p in projects_dir.rglob("*.jsonl"):
                if p.is_file():
                    candidates.append(p)
        except Exception:  # noqa: BLE001
            pass

    if not candidates:
        return []
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    msgs: list[str] = []
    try:
        with candidates[0].open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                role = row.get("role") or row.get("type") or ""
                if role in ("user", "human"):
                    content = row.get("content") or ""
                    if isinstance(content, list):
                        content = " ".join(
                            (c.get("text") or "") for c in content if isinstance(c, dict)
                        )
                    if isinstance(content, str) and content.strip():
                        msgs.append(content.strip())
    except Exception:  # noqa: BLE001
        return []
    return msgs[-10:]


def main() -> int:
    print("=" * 60, file=sys.stderr)
    print("[user_completion_check] Stop-hook self-audit", file=sys.stderr)
    print("=" * 60, file=sys.stderr)

    commits = _git_log(20)
    print(f"\n[Recent commits ({len(commits)})]", file=sys.stderr)
    for line in commits:
        print(f"  {line}", file=sys.stderr)

    artifacts = _traces_and_reports()
    print(f"\n[Traces / reports on disk ({len(artifacts)})]", file=sys.stderr)
    for f in sorted(artifacts)[:30]:
        print(f"  {f}", file=sys.stderr)

    user_msgs = _transcript_user_messages()
    if not user_msgs:
        print("\n[User messages] (transcript not accessible from this hook)", file=sys.stderr)
    else:
        print(f"\n[Recent user messages ({len(user_msgs)})]", file=sys.stderr)
        for i, m in enumerate(user_msgs[-3:], 1):
            head = re.sub(r"\s+", " ", m[:120])
            print(f"  #{i}: {head}{'...' if len(m) > 120 else ''}", file=sys.stderr)

        # Cross-match: keywords from each user message vs deliverables
        print("\n[Keyword vs deliverable cross-match]", file=sys.stderr)
        corpus = " ".join(commits + artifacts).lower()
        for i, m in enumerate(user_msgs, 1):
            kws = _extract_keywords(m)
            hits = [k for k in kws if k.lower() in corpus]
            print(
                f"  user #{i}: {len(kws)} keywords, {len(hits)} match -> {hits[:6]}",
                file=sys.stderr,
            )

    print(
        "\n[user_completion_check] OK (non-blocking, exit 0)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
