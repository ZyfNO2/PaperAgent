"""Re7.6 Job Worker MVP — single-worker poll/lease/checkpoint/cancel/budget.

Executes graph jobs asynchronously outside the HTTP request lifecycle.
Single-worker via SQLite transactional lease; no distributed coordination.

Flow: poll queued -> acquire lease -> running -> execute graph node by node
  -> checkpoint completed state/event
  -> probe cancel/budget before node and before external/LLM call
  -> succeeded | cancelled | partial_budget | failed | resumable
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from apps.api.app.services.job_repository import JobRecord, JobRepository, JobCancelledError, BudgetExceededError

logger = logging.getLogger(__name__)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobWorker:
    """Single worker that consumes jobs from a JobRepository.

    The worker polls for pending jobs, acquires a SQLite lease, and executes
    a node-by-node pipeline. Cooperative cancel/budget checks are performed
    before each node and before LLM calls.
    """

    def __init__(
        self,
        repo: JobRepository,
        worker_id: str | None = None,
        poll_interval_s: float = 2.0,
        lease_seconds: int = 300,
        max_graph_nodes: int = 20,
    ):
        self._repo = repo
        self._worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self._poll_interval_s = poll_interval_s
        self._lease_seconds = lease_seconds
        self._max_graph_nodes = max_graph_nodes
        self._stop_event = threading.Event()
        self._thread: threading.Event | None = None

    @property
    def worker_id(self) -> str:
        return self._worker_id

    def process_one(self) -> str | None:
        """Process one queued job. Returns job_id or None if nothing pending."""
        pending = self._repo.list_jobs(status="pending")
        for job in pending:
            if self._stop_event.is_set():
                return None
            acquired = self._repo.acquire_lease(job.job_id, self._worker_id, self._lease_seconds)
            if not acquired:
                continue
            self._repo.update_status(job.job_id, "running")
            self._repo.append_event(job.job_id, "started", {"worker": self._worker_id})
            self._execute_job(job)
            return job.job_id
        return None

    def _execute_job(self, job: JobRecord) -> None:
        """Execute the graph for a single job with cancel/budget probes."""
        job_id = job.job_id
        try:
            state: dict[str, Any] = {
                "topic": job.topic,
                "case_id": job.case_id,
                "job_id": job_id,
                "trace_events": [],
                "errors": [],
            }
            node_count = 0
            graph = self._build_graph(job)

            for node_name, node_fn in graph:
                if self._stop_event.is_set():
                    self._repo.update_status(job_id, "cancelled", "worker stopped")
                    self._repo.append_event(job_id, "cancelled", {"reason": "worker_stopped"})
                    return

                if self._is_cancelled(job_id):
                    self._repo.update_status(job_id, "cancelled", "user requested cancellation")
                    self._repo.append_event(job_id, "cancelled", {"at_node": node_name})
                    return

                if not self._check_budget(job_id):
                    self._repo.update_status(job_id, "resumable", "budget exhausted")
                    self._repo.append_event(job_id, "partial_budget", {
                        "completed_node": node_name,
                        "node_count": node_count,
                    })
                    return

                if node_count >= self._max_graph_nodes:
                    self._repo.update_status(job_id, "resumable", "node limit reached")
                    self._repo.append_event(job_id, "node_limit", {"count": node_count})
                    return

                # Re7.6: cooperative cancel/budget probe via graph-internal _util
                try:
                    from apps.api.app.services.agents.graph.nodes._util import probe_cancel_budget
                    probe_cancel_budget(state, self._repo)
                except JobCancelledError:
                    self._repo.update_status(job_id, "cancelled", "probe detected cancellation")
                    self._repo.append_event(job_id, "cancelled", {"at_node": node_name, "source": "probe"})
                    return
                except BudgetExceededError:
                    self._repo.update_status(job_id, "resumable", "probe detected budget exhausted")
                    self._repo.append_event(job_id, "partial_budget", {
                        "completed_node": node_name,
                        "node_count": node_count,
                        "source": "probe",
                    })
                    return

                self._repo.update_checkpoint(job_id, node_name)
                self._repo.append_event(job_id, "node_start", {"node": node_name})

                try:
                    partial = node_fn(state)
                    if isinstance(partial, dict):
                        state.update(partial)
                    self._repo.append_event(job_id, "node_complete", {
                        "node": node_name, "state_keys": list(partial.keys()) if isinstance(partial, dict) else [],
                    })
                except Exception as exc:
                    logger.exception("job %s node %s failed", job_id, node_name)
                    self._repo.update_status(job_id, "failed", f"{node_name}:{type(exc).__name__}")
                    self._repo.append_event(job_id, "node_error", {
                        "node": node_name, "error": f"{type(exc).__name__}",
                    })
                    return

                node_count += 1

            self._repo.update_status(job_id, "completed")
            self._repo.append_event(job_id, "completed", {"nodes_executed": node_count})

        except Exception as exc:
            logger.exception("job %s crashed", job_id)
            self._repo.update_status(job_id, "failed", f"worker_crash:{type(exc).__name__}")
            self._repo.append_event(job_id, "crash", {"error": f"{type(exc).__name__}"})

    def _build_graph(self, job: JobRecord) -> list[tuple[str, Callable]]:
        """Build the node pipeline for a job. Override for custom pipelines."""
        try:
            from apps.api.app.services.agents.graph.research_graph import build_graph
            compiled = build_graph()
            return [("research_graph", lambda s: self._invoke_graph(compiled, s))]
        except Exception as exc:
            logger.warning("failed to build research_graph: %s — using identity", exc)
            return [("identity", lambda s: {})]

    def _invoke_graph(self, compiled: Any, state: dict[str, Any]) -> dict[str, Any]:
        """Invoke the compiled LangGraph and return the final state diff."""
        try:
            result = compiled.invoke(state, config={"configurable": {"thread_id": state.get("job_id", "default")}})
            return {k: v for k, v in result.items() if v is not None}
        except Exception:
            logger.exception("graph invoke failed")
            return {}

    def _is_cancelled(self, job_id: str) -> bool:
        """Check if the job has been cancelled (cooperative probe)."""
        record = self._repo.get_job(job_id)
        return record is not None and record.status == "cancelled"

    def _check_budget(self, job_id: str) -> bool:
        """Check if the job still has budget. Returns False if budget exceeded."""
        record = self._repo.get_job(job_id)
        if record is None:
            return False
        if record.budget_tokens > 0 and record.tokens_used >= record.budget_tokens:
            return False
        return True

    def record_token_usage(self, job_id: str, tokens: int) -> bool:
        """Record token usage. Returns True if budget not exceeded."""
        return self._repo.update_tokens(job_id, tokens)

    def start(self) -> None:
        """Start the worker in a background thread."""
        if self._thread is not None:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("job worker %s started", self._worker_id)

    def stop(self, timeout_s: float = 10.0) -> None:
        """Signal the worker to stop and wait for it to finish."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout_s)
            self._thread = None
        logger.info("job worker %s stopped", self._worker_id)

    def _run_loop(self) -> None:
        """Main poll loop."""
        while not self._stop_event.is_set():
            try:
                processed = self.process_one()
                if processed is None:
                    time.sleep(self._poll_interval_s)
            except Exception:
                logger.exception("worker poll loop error")
                time.sleep(self._poll_interval_s)
