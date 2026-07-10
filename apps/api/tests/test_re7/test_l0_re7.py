"""Re7.1/7.2/7.4 — L0 unit tests for Job, Feedback, Cross-domain."""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Re7.1 Job Repository
# ---------------------------------------------------------------------------
class TestJobRepository:
    def test_create_job(self):
        from apps.api.app.services.job_repository import JobRepository, JobCreate
        repo = JobRepository(":memory:")
        job = repo.create_job(JobCreate(
            topic="test topic",
            idempotency_key="ik-001",
        ))
        assert job.job_id
        assert job.status == "pending"

    def test_duplicate_idempotency(self):
        from apps.api.app.services.job_repository import JobRepository, JobCreate
        repo = JobRepository(":memory:")
        repo.create_job(JobCreate(topic="t1", idempotency_key="ik-dup"))
        with pytest.raises(ValueError, match="duplicate"):
            repo.create_job(JobCreate(topic="t2", idempotency_key="ik-dup"))

    def test_update_status(self):
        from apps.api.app.services.job_repository import JobRepository, JobCreate
        repo = JobRepository(":memory:")
        job = repo.create_job(JobCreate(topic="t", idempotency_key="k1"))
        assert repo.update_status(job.job_id, "running")
        fetched = repo.get_job(job.job_id)
        assert fetched.status == "running"

    def test_update_status_with_error(self):
        from apps.api.app.services.job_repository import JobRepository, JobCreate
        repo = JobRepository(":memory:")
        job = repo.create_job(JobCreate(topic="t", idempotency_key="k2"))
        repo.update_status(job.job_id, "failed", "connection timeout")
        fetched = repo.get_job(job.job_id)
        assert fetched.error == "connection timeout"

    def test_cancel_job(self):
        from apps.api.app.services.job_repository import JobRepository, JobCreate
        repo = JobRepository(":memory:")
        job = repo.create_job(JobCreate(topic="t", idempotency_key="k3"))
        assert repo.cancel_job(job.job_id)
        assert repo.get_job(job.job_id).status == "cancelled"

    def test_cancel_then_recreate(self):
        from apps.api.app.services.job_repository import JobRepository, JobCreate
        repo = JobRepository(":memory:")
        j1 = repo.create_job(JobCreate(topic="t", idempotency_key="k4"))
        repo.cancel_job(j1.job_id)
        j2 = repo.create_job(JobCreate(topic="t", idempotency_key="k4"))
        assert j2.job_id != j1.job_id

    def test_acquire_lease(self):
        from apps.api.app.services.job_repository import JobRepository, JobCreate
        repo = JobRepository(":memory:")
        job = repo.create_job(JobCreate(topic="t", idempotency_key="k5"))
        assert repo.acquire_lease(job.job_id, "worker-1", lease_seconds=60)
        fetched = repo.get_job(job.job_id)
        assert fetched.worker_lease == "worker-1"

    def test_checkpoint_and_events(self):
        from apps.api.app.services.job_repository import JobRepository, JobCreate
        repo = JobRepository(":memory:")
        job = repo.create_job(JobCreate(topic="t", idempotency_key="k6"))
        repo.update_checkpoint(job.job_id, "search_agent")
        repo.append_event(job.job_id, "node_start", {"node": "search_agent"})
        repo.append_event(job.job_id, "paper_found", {"title": "test"})
        events = repo.get_events(job.job_id)
        assert len(events) == 2
        assert repo.get_job(job.job_id).node_checkpoint == "search_agent"

    def test_get_events_after_seq(self):
        from apps.api.app.services.job_repository import JobRepository, JobCreate
        repo = JobRepository(":memory:")
        job = repo.create_job(JobCreate(topic="t", idempotency_key="k7"))
        repo.append_event(job.job_id, "e1", {})
        repo.append_event(job.job_id, "e2", {})
        events = repo.get_events(job.job_id, after_seq=1)
        assert len(events) == 1
        assert events[0]["type"] == "e2"

    def test_budget_tracking(self):
        from apps.api.app.services.job_repository import JobRepository, JobCreate
        repo = JobRepository(":memory:")
        job = repo.create_job(JobCreate(topic="t", idempotency_key="k8", budget_tokens=100))
        assert repo.update_tokens(job.job_id, 50)
        assert repo.update_tokens(job.job_id, 60) is False  # Exceeds budget


# ---------------------------------------------------------------------------
# Re7.4 Feedback Store
# ---------------------------------------------------------------------------
class TestFeedbackStore:
    def test_save_and_list(self):
        from apps.api.app.services.feedback_store import FeedbackStore, FeedbackCreate
        import tempfile, os
        path = os.path.join(tempfile.gettempdir(), f"test_fb_{os.getpid()}.jsonl")
        try:
            store = FeedbackStore(path)
            fb = FeedbackCreate(
                case_id="case-1", idempotency_key="fbk-1",
                artifact_type="paper", artifact_id="p1",
                verdict="supported", comment="good paper",
            )
            record = store.save(fb)
            assert record.feedback_id

            items = store.list_by_case("case-1")
            assert len(items) == 1
            assert items[0].verdict == "supported"
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_idempotency(self):
        from apps.api.app.services.feedback_store import FeedbackStore, FeedbackCreate
        import tempfile, os
        path = os.path.join(tempfile.gettempdir(), f"test_fb2_{os.getpid()}.jsonl")
        try:
            store = FeedbackStore(path)
            r1 = store.save(FeedbackCreate(
                case_id="c1", idempotency_key="dup-key",
                artifact_type="paper", artifact_id="p1", verdict="supported",
            ))
            r2 = store.save(FeedbackCreate(
                case_id="c1", idempotency_key="dup-key",
                artifact_type="paper", artifact_id="p1", verdict="incorrect",
            ))
            assert r1.feedback_id == r2.feedback_id
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_summary(self):
        from apps.api.app.services.feedback_store import FeedbackStore, FeedbackCreate
        import tempfile, os
        path = os.path.join(tempfile.gettempdir(), f"test_fb3_{os.getpid()}.jsonl")
        try:
            store = FeedbackStore(path)
            store.save(FeedbackCreate(case_id="c1", idempotency_key="s1", artifact_type="paper", artifact_id="p1", verdict="supported"))
            store.save(FeedbackCreate(case_id="c1", idempotency_key="s2", artifact_type="paper", artifact_id="p2", verdict="incorrect"))
            store.save(FeedbackCreate(case_id="c2", idempotency_key="s3", artifact_type="dataset", artifact_id="d1", verdict="unsupported"))
            summary = store.get_summary()
            assert summary.total == 3
            assert summary.unsupported_incorrect == 2
            assert summary.by_artifact.get("paper", 0) == 2
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_delete_by_case(self):
        from apps.api.app.services.feedback_store import FeedbackStore, FeedbackCreate
        import tempfile, os
        path = os.path.join(tempfile.gettempdir(), f"test_fb4_{os.getpid()}.jsonl")
        try:
            store = FeedbackStore(path)
            store.save(FeedbackCreate(case_id="del-1", idempotency_key="d1", artifact_type="paper", artifact_id="p1", verdict="supported"))
            store.save(FeedbackCreate(case_id="del-1", idempotency_key="d2", artifact_type="repo", artifact_id="r1", verdict="incorrect"))
            deleted = store.delete_by_case("del-1")
            assert deleted == 2
            assert len(store.list_by_case("del-1")) == 0
        finally:
            if os.path.exists(path):
                os.remove(path)


# ---------------------------------------------------------------------------
# Re7.2 Cross-domain cases
# ---------------------------------------------------------------------------
class TestCrossDomainCases:
    def test_all_10_cases(self):
        from apps.api.app.services.cross_domain_cases import CROSS_DOMAIN_CASES
        assert len(CROSS_DOMAIN_CASES) == 10
        for c in CROSS_DOMAIN_CASES:
            assert c.case_id.startswith("XD-")
            assert c.topic
            assert c.domain
            assert c.expected_verdict in ("GO", "CONDITIONAL", "RISKY", "STOP", "PIVOT")

    def test_high_risk_cases(self):
        from apps.api.app.services.cross_domain_cases import CROSS_DOMAIN_CASES
        risky = [c for c in CROSS_DOMAIN_CASES if c.expected_verdict in ("RISKY", "STOP")]
        assert len(risky) >= 4
