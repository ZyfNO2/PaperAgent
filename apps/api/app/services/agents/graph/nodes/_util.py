"""Shared trace helpers for graph nodes — eliminates 34 copy-pasted defs."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def emit_trace(
    node: str,
    t0: float,
    ins: dict,
    out: dict,
    tools: list,
    prov: str,
    errs: list,
    state_keys: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "node": node,
        "started_at": now_iso(),
        "input_summary": ins,
        "output_summary": out,
        "tool_calls": tools,
        "errors": errs,
        "provider": prov,
        "ended_at": now_iso(),
        "elapsed_s": round(time.time() - t0, 3),
        "state_keys": state_keys or [],
    }


def probe_cancel_budget(state: dict[str, Any], repo: Any) -> None:
    """Cooperative cancel/budget probe for graph nodes.

    Reads `job_id` from state and queries the job repository.  If the job
    has been cancelled or the budget is exhausted, raises the corresponding
    exception so the worker can catch and handle it.

    If `job_id` is absent from state, this is a no-op (graph invoked without
    a worker context).
    """
    job_id = (state.get("job_id") or "").strip()
    if not job_id:
        return  # no worker context — skip probe

    try:
        if repo.is_cancelled(job_id):
            raise JobCancelledError(f"job {job_id} was cancelled")
        if repo.is_budget_exhausted(job_id):
            raise BudgetExceededError(f"job {job_id} budget exhausted")
    except (JobCancelledError, BudgetExceededError):
        raise
    except Exception as exc:
        logger.warning("probe_cancel_budget for %s failed: %s — skipping probe", job_id, exc)


# Import at module level to avoid circular imports in node files.
from apps.api.app.services.job_repository import JobCancelledError, BudgetExceededError
