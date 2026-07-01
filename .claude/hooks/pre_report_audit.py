#!/usr/bin/env python3
"""Pre-write self-audit hook for `*完工报告*.md` files.

Triggered by Claude Code PreToolUse on `Write`. When the model is about to
write a 完工报告 (deliverable report), this hook inspects the candidate
report and demands the model justify "why the data is what it is" before
saving.

Re03 upgrade (2026-07-02):
  1. Per-call data delta detection — every Re02/Re03 完工报告 MUST contain
     a per-round or per-step data delta table. The hook now detects
     whether the report has it and warns if missing.
  2. Bad-data diagnose — the hook scans the report text for known bad
     data markers (LLM-dead-path fallback, all-candidate tier, generic
     ML paper titles) AND requires the model to pick A/B/C:
        A) CODE BUG  — pipeline bug; show path + fix + retry
        B) PLANNED   — SOP scope; cite clause
        C) BLOCKED-AFTER-5  — 5 attempts done; show I/O + next human action
  3. Hard BLOCKER check — the report must mention `审计结论` or
     `B) PLANNED-AS-IS` / `A) CODE BUG` / `C) BLOCKED-AFTER-5` to be
     considered audited. The hook flags missing audit.

The hook is non-blocking (exit 0). It writes the audit to stderr; the
harness surfaces stderr to the user.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

FINAL_REPORT_RE = re.compile(
    r"(?:^|[\\/])[A-Za-z_]*差工[^\/]*\.md$|PaperAgent_Re\d+_(?:差工|完工报告)|差工报告|完工报告",
    re.IGNORECASE,
)

# Heuristic: if the report text mentions these phrases paired with bad-data
# indicators, the model is probably writing LLM-dead-path output as if it
# were real. Print a STRONG warning.
DEAD_PATH_PATTERNS = [
    (r"LLM 不可用.*?fallback", "LLM-unavailable fallback data"),
    (r"heuristic fallback 返回", "heuristic-fallback data"),
    (r"0 core / \d+ candidate", "all-defaulted candidate tier (EvidenceReview LLM 挂)"),
    (r"changing[\s_-]?data[\s_-]?sources[\s_-]?in[\s_-]?the[\s_-]?age", "well-known generic ML paper (sign of fallback)"),
    (r"awesome[\s_-]?machine[\s_-]?learning", "generic ML awesome-list repo (sign of fallback)"),
    (r"Bee[\s_-]?Movie", "Bee Movie noise (Case A citation_expand seed 选错)"),
    (r"cosmic[\s_-]?rays?[\s_-]?(at|with|in)[\s_-]?(CERN|cloud[\s_-]?chamber)", "cosmic ray 噪声 (Case A 离题 seed)"),
    (r"brown[\s_-]?dwarfs?", "棕矮星噪声 (Case A 离题 seed)"),
    (r"honey[\s_-]?bee", "蜜蜂噪声 (Case A citation 污染)"),
]

GOOD_DATA_MARKERS = [
    r"domain_route\s*[:=]\s*['\"]?vision_[23]d['\"]?",
    r"query_atoms_en\s*[:=].*?(?:U-Net|YOLOv|nnU-Net|COLMAP|sensor|fault|crack|steel|defect)",
    r"baseline_options\s*[:=].*?c-[0-9a-f]{8}",
    r"can_continue_to_opening_report['\"]?\s*[:=]\s*true",
    r"llm_calls['\"]?\s*[:=]\s*[3-9]",
]

# Per-round data delta — every Re02+ 完工报告 MUST contain a "每轮数据" or
# "round_delta" or "R1/R2/R3/R4/R5" structure. Re03 SOP §1.6 强制要求。
PER_ROUND_DELTA_PATTERNS = [
    r"每轮数据",
    r"round[\s_-]?delta",
    r"R1[\s_-].*?R2[\s_-].*?R3",
    r"Round[\s_ ]+1[\s_].*?Round[\s_ ]+2",
    r"round.*?增量",
    r"SourceLedger.*?stats",
    r"per[\s_-]?round.*?delta",
]

# 3-choose-1 audit conclusion MUST be present. The model must explicitly
# pick A/B/C.
AUDIT_CHOICE_PATTERNS = [
    r"\bA\)\s*CODE\s*BUG",
    r"\bB\)\s*PLANNED",
    r"\bC\)\s*BLOCKED",
    r"诊断.{0,5}(BUG|PLANNED|BLOCKED)",
    r"pre_report_audit.{0,40}(结论|选择|判定)",
]


def _read_payload() -> dict | None:
    try:
        return json.load(sys.stdin)
    except Exception:
        return None


def _is_final_report(path: str) -> bool:
    name = Path(path).name
    return bool(FINAL_REPORT_RE.search(name)) or ("差工报告" in name)


def _extract_text(payload: dict) -> str:
    tool_input = payload.get("tool_input") or {}
    content = tool_input.get("content")
    return content if isinstance(content, str) else ""


def _scan(text: str) -> dict:
    """Run all pattern groups against the candidate report text."""
    return {
        "dead_hits": [label for pat, label in DEAD_PATH_PATTERNS
                      if re.search(pat, text, re.IGNORECASE | re.DOTALL)],
        "good_hits": [pat for pat in GOOD_DATA_MARKERS
                      if re.search(pat, text, re.IGNORECASE | re.DOTALL)],
        "per_round_hits": [pat for pat in PER_ROUND_DELTA_PATTERNS
                           if re.search(pat, text, re.IGNORECASE | re.DOTALL)],
        "audit_hits": [pat for pat in AUDIT_CHOICE_PATTERNS
                       if re.search(pat, text, re.IGNORECASE | re.DOTALL)],
    }


def _emit(line: str) -> None:
    """Emit a one-line audit message to BOTH stderr and stdout, with
    a small sleep so the harness's pipe reader has time to flush
    before the script exits.

    Why dual: the harness sometimes reports "No stderr output" for hooks
    that only print to stderr (timing-window race on Windows console).
    Why sleep: the harness captures the stream asynchronously; if the
    script exits within 200ms, the line never reaches the UI.
    """
    print(line, file=sys.stderr, flush=True)
    try:
        print(line, flush=True)
    except Exception:
        pass
    import time as _t
    _t.sleep(0.05)


def _emit_end_of_audit() -> None:
    """Final marker that the harness can use to detect hook completion.

    Three NEW LINES at the end so the agent (and the user) know the
    audit is done and can decide whether to continue writing the
    report or stop and fix a blocker.
    """
    print("=" * 70, file=sys.stderr, flush=True)
    print("=" * 70, flush=True)
    print("[pre_report_audit] END OF AUDIT", file=sys.stderr, flush=True)
    print("[pre_report_audit] END OF AUDIT", flush=True)
    print("=" * 70, file=sys.stderr, flush=True)
    print("=" * 70, flush=True)
    import time as _t
    _t.sleep(0.5)


def main() -> int:
    _emit("[pre_report_audit] running")
    payload = _read_payload()
    if payload is None:
        _emit("[pre_report_audit] no payload; pass-through")
        _emit_end_of_audit()
        return 0
    tool_name = payload.get("tool_name") or ""
    if tool_name != "Write":
        _emit(f"[pre_report_audit] non-Write tool {tool_name!r}; pass-through")
        _emit_end_of_audit()
        return 0

    tool_input = payload.get("tool_input") or {}
    path = str(tool_input.get("file_path") or "")
    if not _is_final_report(path):
        _emit(f"[pre_report_audit] {path!r} not a 完工报告; pass-through")
        _emit_end_of_audit()
        return 0

    text = _extract_text(payload)
    scan = _scan(text)
    dead = scan["dead_hits"]
    good = scan["good_hits"]
    delta = scan["per_round_hits"]
    audit = scan["audit_hits"]

    print("=" * 70, file=sys.stderr)
    print("[pre_report_audit] Pre-write self-audit on 完工报告", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    print(f"  file: {path}", file=sys.stderr)
    print(f"  bytes: {len(text)}", file=sys.stderr)
    print(f"  dead-path markers ({len(dead)}): {dead}", file=sys.stderr)
    print(f"  good-data markers ({len(good)} matched): "
          f"{[m[:40] for m in good]}", file=sys.stderr)
    print(f"  per-round data delta section ({len(delta)} matched): "
          f"{'YES' if delta else '⚠️ MISSING'}", file=sys.stderr)
    print(f"  3-choose-1 audit conclusion ({len(audit)} matched): "
          f"{'YES' if audit else '⚠️ MISSING'}", file=sys.stderr)
    print("", file=sys.stderr)

    # Blockers
    blockers = []
    if not delta:
        blockers.append("per-round data delta section missing (Re02 SOP §3.7 / Re03 SOP §1.6 强制要求)")
    if not audit:
        blockers.append("3-choose-1 audit conclusion missing (CODE BUG / PLANNED-AS-IS / BLOCKED-AFTER-5)")

    if dead and not good:
        print("  ⚠️  STRONG WARNING: report looks like it contains heuristic-fallback data.", file=sys.stderr)
        print("     LLM-dead-path output is for connectivity smoke only — not for delivery.", file=sys.stderr)
        print("     Re-run with LLM online (no SESSION66_LLM_BUDGET=0) and dump real data.", file=sys.stderr)
        blockers.append("heuristic-fallback data detected in candidate report")

    if blockers:
        print(f"  ⚠️  {len(blockers)} BLOCKER(S):", file=sys.stderr)
        for b in blockers:
            print(f"     - {b}", file=sys.stderr)
    else:
        print("  ✓  no blockers — report passes the audit checklist", file=sys.stderr)

    print("", file=sys.stderr)
    print("  Before saving this 完工报告, choose ONE of:", file=sys.stderr)
    print("    A) CODE BUG         — data is bad due to a bug in the pipeline;", file=sys.stderr)
    print("                           show the suspect code path + minimal fix + retry plan.", file=sys.stderr)
    print("    B) PLANNED-AS-IS    — data is intentionally limited by current SOP scope;", file=sys.stderr)
    print("                           cite the SOP clause + why no further work now.", file=sys.stderr)
    print("    C) BLOCKED-AFTER-5  — task cannot be completed this session;", file=sys.stderr)
    print("                           show all 5 attempt inputs / outputs / error guesses /", file=sys.stderr)
    print("                           what the human must do next.", file=sys.stderr)
    print("", file=sys.stderr)
    print("  Embed the chosen justification + evidence directly in the report.", file=sys.stderr)
    print("  Per-round data delta table is mandatory (per Re03 SOP §1.6).", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    _emit_end_of_audit()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"[pre_report_audit] CRASH: {exc!r}", file=sys.stderr)
        sys.stderr.flush()
        sys.exit(0)
