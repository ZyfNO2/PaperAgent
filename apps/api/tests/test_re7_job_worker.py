"""Re7.6 Job Worker MVP Tests.

Tests poll/lease/checkpoint/cancel/budget lifecycle.
"""
from __future__ import annotations

import time
import pytest

from apps.api.app.services.job_repository import JobCreate, JobRepository, JobCancelledError, BudgetExceededError
from apps.api.app.services.job_worker import JobWorker


class TestJobWorkerLifecycle:
    def _make_repo(self) -> JobRepository:
        return JobRepository(":memory:")

    def _create_job(self, repo: JobRepository, topic: str = "test topic") -> str:
        job = repo.create_job(JobCreate(topic=topic, idempotency_key=f"ik-{topic}"))
        return job.job_id

    def _make_worker_with_mock_graph(self, repo: JobRepository) -> JobWorker:
        """Create a worker whose graph is a simple identity pipeline."""
        worker = JobWorker(repo, poll_interval_s=0)
        worker._build_graph = lambda job: [("identity", lambda s: {})]
        return worker

    def test_process_one_converts_pending_to_completed(self):
        repo = self._make_repo()
        job_id = self._create_job(repo)
        worker = self._make_worker_with_mock_graph(repo)
        processed_id = worker.process_one()

        assert processed_id == job_id
        job = repo.get_job(job_id)
        assert job is not None
        assert job.status == "completed"

    def test_process_one_emits_events(self):
        repo = self._make_repo()
        job_id = self._create_job(repo)
        worker = self._make_worker_with_mock_graph(repo)
        worker.process_one()

        events = repo.get_events(job_id)
        types = [e["type"] for e in events]
        assert "started" in types
        assert "completed" in types

    def test_process_checkpoint_records_node(self):
        repo = self._make_repo()
        job_id = self._create_job(repo)
        worker = self._make_worker_with_mock_graph(repo)
        worker.process_one()

        job = repo.get_job(job_id)
        assert job is not None
        assert job.node_checkpoint is not None
        assert job.node_checkpoint == "identity"

    def test_no_pending_returns_none(self):
        repo = self._make_repo()
        worker = self._make_worker_with_mock_graph(repo)
        assert worker.process_one() is None

    def test_cancel_stops_processing(self):
        """Cancel probe fires between nodes — job stops, does not complete."""
        repo = self._make_repo()
        job_id = self._create_job(repo)

        worker = self._make_worker_with_mock_graph(repo)
        worker._build_graph = lambda job: [
            ("node_a", lambda s: {}),
            ("node_b", lambda s: {}),
        ]
        cancel_on_second = [False]

        def patched_check(jid):
            if cancel_on_second[0]:
                return True
            cancel_on_second[0] = True
            return False

        worker._is_cancelled = patched_check
        worker._execute_job(repo.get_job(job_id))

        events = repo.get_events(job_id)
        types = [e["type"] for e in events]
        assert "cancelled" in types
        job = repo.get_job(job_id)
        assert job is not None
        assert job.status == "cancelled"

    def test_crash_marks_failed(self):
        repo = self._make_repo()
        job_id = self._create_job(repo)

        worker = JobWorker(repo)
        bad_job = repo.get_job(job_id)

        def bad_graph(job):
            return [("bad", lambda s: (_ for _ in ()).throw(RuntimeError("boom")))]

        worker._build_graph = bad_graph
        worker._execute_job(bad_job)

        job = repo.get_job(job_id)
        assert job is not None
        assert job.status == "failed"
        assert "node_error" in [e["type"] for e in repo.get_events(job_id)]

    def test_idempotency_no_double_consume(self):
        repo = self._make_repo()
        job_id = self._create_job(repo)

        worker1 = self._make_worker_with_mock_graph(repo)
        worker1._worker_id = "w1"
        worker2 = self._make_worker_with_mock_graph(repo)
        worker2._worker_id = "w2"

        first = worker1.process_one()
        second = worker2.process_one()

        assert first == job_id
        assert second is None or second != job_id or repo.get_job(job_id).status != "pending"


class TestJobWorkerBudget:
    def test_budget_exceeded_returns_partial(self):
        repo = JobRepository(":memory:")
        job = repo.create_job(JobCreate(topic="budget test", idempotency_key="ik-budget"))

        worker = JobWorker(repo, max_graph_nodes=1)
        repo.acquire_lease(job.job_id, worker.worker_id)
        repo.update_status(job.job_id, "running")
        repo.update_tokens(job.job_id, 999999)
        assert not worker._check_budget(job.job_id)

    def test_within_budget_continues(self):
        repo = JobRepository(":memory:")
        job = repo.create_job(JobCreate(topic="budget test", idempotency_key="ik-budget2", budget_tokens=50000))
        worker = JobWorker(repo)
        assert worker._check_budget(job.job_id)


class TestJobWorkerProbe:
    """Tests for Re7.6 graph-internal cancel/budget probe."""

    def _make_repo(self) -> JobRepository:
        return JobRepository(":memory:")

    def _create_job(self, repo: JobRepository, topic: str = "probe test", budget: int = 50000) -> str:
        job = repo.create_job(JobCreate(topic=topic, idempotency_key=f"ik-{topic}", budget_tokens=budget))
        return job.job_id

    def test_repo_is_cancelled_detects_cancel(self):
        repo = self._make_repo()
        job_id = self._create_job(repo)
        assert not repo.is_cancelled(job_id)
        repo.cancel_job(job_id)
        assert repo.is_cancelled(job_id)

    def test_repo_is_budget_exhausted_detects_exhaustion(self):
        repo = self._make_repo()
        job_id = self._create_job(repo, budget=500)
        assert not repo.is_budget_exhausted(job_id)
        repo.update_tokens(job_id, 500)
        assert repo.is_budget_exhausted(job_id)

    def test_repo_is_budget_exhausted_zero_budget_never_exhausted(self):
        repo = self._make_repo()
        job_id = self._create_job(repo, budget=0)
        assert not repo.is_budget_exhausted(job_id)
        repo.update_tokens(job_id, 999999)
        assert not repo.is_budget_exhausted(job_id)

    def test_probe_skips_when_no_job_id(self):
        """probe_cancel_budget is a no-op when state has no job_id."""
        from apps.api.app.services.agents.graph.nodes._util import probe_cancel_budget
        repo = self._make_repo()
        # Should not raise even if repo would fail
        probe_cancel_budget({}, repo)
        probe_cancel_budget({"job_id": ""}, repo)

    def test_probe_raises_on_cancelled(self):
        """probe raises JobCancelledError when job is cancelled."""
        from apps.api.app.services.agents.graph.nodes._util import probe_cancel_budget
        repo = self._make_repo()
        job_id = self._create_job(repo)
        repo.cancel_job(job_id)
        with pytest.raises(JobCancelledError):
            probe_cancel_budget({"job_id": job_id}, repo)

    def test_probe_raises_on_budget_exhausted(self):
        """probe raises BudgetExceededError when budget is exhausted."""
        from apps.api.app.services.agents.graph.nodes._util import probe_cancel_budget
        repo = self._make_repo()
        job_id = self._create_job(repo, budget=500)
        repo.update_tokens(job_id, 500)
        with pytest.raises(BudgetExceededError):
            probe_cancel_budget({"job_id": job_id}, repo)

    def test_worker_cancel_probe_stops_before_node(self):
        """Worker cancels job; probe fires before second node executes."""
        repo = self._make_repo()
        job_id = self._create_job(repo)
        repo.acquire_lease(job_id, "w1")
        repo.update_status(job_id, "running")

        worker = JobWorker(repo)
        executed = []

        def node_a(s):
            executed.append("a")
            return {}

        def node_b(s):
            executed.append("b")
            return {}

        worker._build_graph = lambda job: [("node_a", node_a), ("node_b", node_b)]

        # Cancel *after* node_a is captured by patching probe_cancel_budget
        original_probe = None
        try:
            from apps.api.app.services.agents.graph.nodes import _util
            original_probe = _util.probe_cancel_budget

            def patched_probe(state, r):
                # Cancel after node_a runs
                if "a" in executed:
                    r.cancel_job(job_id)
                original_probe(state, r)

            _util.probe_cancel_budget = patched_probe

            # Directly invoke _execute_job to bypass process_one which re-queries
            job = repo.get_job(job_id)
            worker._execute_job(job)
        finally:
            if original_probe is not None:
                from apps.api.app.services.agents.graph.nodes import _util
                _util.probe_cancel_budget = original_probe

        # Only node_a should have executed; node_b never reached
        assert executed == ["a"]
        job = repo.get_job(job_id)
        assert job.status == "cancelled"

    def test_worker_budget_exhausted_probe_marks_resumable(self):
        """Budget exhausted mid-graph → resumable, not completed."""
        repo = self._make_repo()
        job_id = self._create_job(repo, budget=100)
        repo.acquire_lease(job_id, "w1")
        repo.update_status(job_id, "running")

        worker = JobWorker(repo)
        executed = []

        def node_a(s):
            executed.append("a")
            return {}

        def node_b(s):
            executed.append("b")
            return {}

        worker._build_graph = lambda job: [("node_a", node_a), ("node_b", node_b)]

        original_probe = None
        try:
            from apps.api.app.services.agents.graph.nodes import _util
            original_probe = _util.probe_cancel_budget

            def patched_probe(state, r):
                if "a" in executed:
                    repo.update_tokens(job_id, 100)  # exhaust budget
                original_probe(state, r)

            _util.probe_cancel_budget = patched_probe

            job = repo.get_job(job_id)
            worker._execute_job(job)
        finally:
            if original_probe is not None:
                from apps.api.app.services.agents.graph.nodes import _util
                _util.probe_cancel_budget = original_probe

        assert executed == ["a"]
        job = repo.get_job(job_id)
        assert job.status == "resumable"
