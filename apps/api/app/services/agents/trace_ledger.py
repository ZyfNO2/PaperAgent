"""Re10 TraceLedger — SOP §5.

Per-case trace ledger that writes ``<case_id>.json`` atomically under
``tmp_re04_eval/balanced40_re10_reflection/traces/``. The Trace is a
first-class product of Re10 (not a log) — every round is appended to
in-memory state and persisted via temp-file + rename.

ponytail:
- Atomic write via tempfile + rename so a crashed runner never leaves a
  half-written trace.
- One file per case, never one giant dump. Stays under 350 lines because
  schema lives in research_agent SOP §5 not here.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TraceLedger:
    """In-memory + on-disk trace for one Re10 case.

    Args:
      out_dir:    base directory (e.g. ``tmp_re04_eval/balanced40_re10_reflection``).
      case_id:    identifier (becomes the file name).
      topic:      human-readable topic string.
      seed_sources: dict with ``re08_candidates_n`` / ``re09_candidates_n``.
      max_rounds: 1..3 inclusive; recorded but not enforced here.
    """

    def __init__(
        self,
        out_dir: str,
        case_id: str,
        topic: str = "",
        seed_sources: dict | None = None,
        max_rounds: int = 3,
    ) -> None:
        self.case_id = case_id
        self.max_rounds = max_rounds
        self.out_dir = Path(out_dir)
        self.trace_dir = self.out_dir / "traces"
        self.trace_dir.mkdir(parents=True, exist_ok=True)
        self.trace_path = self.trace_dir / f"{case_id}.json"
        self._doc: dict[str, Any] = {
            "case_id": case_id,
            "topic": topic,
            "max_rounds": max_rounds,
            "seed_sources": dict(seed_sources or {}),
            "rounds": [],
            "final": None,
        }
        # Best-effort: load any existing trace (e.g. rerun over the same
        # case).  We never silently overwrite — append rounds only.
        if self.trace_path.exists():
            try:
                with self.trace_path.open("r", encoding="utf-8") as f:
                    prior = json.load(f)
                if isinstance(prior, dict) and prior.get("case_id") == case_id:
                    self._doc = prior
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("TraceLedger %s: ignoring unreadable prior trace: %s", case_id, exc)
        self._persist()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_round(
        self,
        case_id: str,
        round_num: int,
        agent: str,
        input_summary: dict,
        actions: list[dict],
        observations: dict,
        reflection: dict,
        new_candidates_n: int = 0,
        accepted_n: int = 0,
        rejected_n: int = 0,
        url_repair_n: int = 0,
        query_repair_n: int = 0,
        tool_stats: dict | None = None,
    ) -> None:
        """Append a single round to the trace.

        Any of the *_n counters may be 0 when unknown. Idempotent w.r.t.
        round_num — if a round with the same number already exists it is
        replaced (this lets the runner retry a round without duplicating).
        """
        round_doc = {
            "round": int(round_num),
            "agent": str(agent),
            "input_summary": dict(input_summary or {}),
            "actions": list(actions or []),
            "observations": dict(observations or {}),
            "reflection": dict(reflection or {}),
            "new_candidates_n": int(new_candidates_n),
            "accepted_candidates_n": int(accepted_n),
            # Keep ``accepted_n`` as the validator-facing alias (see
            # validate_re10_reflection_search._derive_evidence L118).
            "accepted_n": int(accepted_n),
            "rejected_candidates_n": int(rejected_n),
            "url_repair_n": int(url_repair_n),
            "query_repair_n": int(query_repair_n),
            "tool_stats": dict(tool_stats or {}),
        }
        rounds: list[dict] = self._doc.setdefault("rounds", [])
        replaced = False
        for i, r in enumerate(rounds):
            if r.get("round") == round_num:
                rounds[i] = round_doc
                replaced = True
                break
        if not replaced:
            rounds.append(round_doc)
        rounds.sort(key=lambda r: r.get("round", 0))
        self._persist()

    def finalize(
        self,
        case_id: str,
        stop_reason: str,
        paper_n: int = 0,
        baseline_n: int = 0,
        parallel_n: int = 0,
        dataset_n: int = 0,
        repo_n: int = 0,
        remaining_gaps: list[str] | None = None,
    ) -> None:
        """Write the terminal ``final`` block of the trace."""
        self._doc["final"] = {
            "stop_reason": stop_reason,
            "paper_n": int(paper_n),
            "baseline_n": int(baseline_n),
            "parallel_n": int(parallel_n),
            "dataset_n": int(dataset_n),
            "repo_n": int(repo_n),
            "remaining_gaps": list(remaining_gaps or []),
        }
        self._persist()

    # ------------------------------------------------------------------
    # Persistence helper
    # ------------------------------------------------------------------

    def _persist(self) -> None:
        """Atomic write: temp file in same dir, then rename.

        ponytail: on Windows, antivirus / OneDrive can briefly hold a
        handle on the previous trace file, so ``os.replace`` raises
        ``WinError 5``.  Retry up to 3 times with a short backoff and
        remove a stale ``*.json.tmp`` if it lingers.
        """
        import time as _t
        data = json.dumps(self._doc, ensure_ascii=False, indent=2, default=str)
        for attempt in range(3):
            fd, tmp_name = tempfile.mkstemp(
                prefix=f".{self.case_id}.", suffix=".json.tmp",
                dir=str(self.trace_dir),
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(data)
                try:
                    os.replace(tmp_name, self.trace_path)
                    return
                except (PermissionError, OSError) as exc:  # WinError 5 等
                    if attempt == 2:
                        raise
                    logger.warning(
                        "TraceLedger %s persist retry %d: %s",
                        self.case_id, attempt + 1, exc,
                    )
                    try:
                        os.unlink(tmp_name)
                    except OSError:
                        pass
                    _t.sleep(0.3 * (attempt + 1))
            except Exception:
                # Best effort cleanup on partial failure.
                try:
                    os.unlink(tmp_name)
                except OSError:
                    pass
                if attempt == 2:
                    raise


__all__ = ["TraceLedger"]
