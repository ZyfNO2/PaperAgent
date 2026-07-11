"""Re5.X: Replay fixture + metrics computation tests."""
from __future__ import annotations

from apps.api.app.services.agents.graph.validators.replay_fixture import (
    load_dev_fixtures, compute_metrics, ReplayFixture, DEV_FIXTURES,
)


class TestReplayFixture:
    def test_load_dev_fixtures(self):
        fixtures = load_dev_fixtures()
        assert len(fixtures) >= 3
        assert all(isinstance(f, ReplayFixture) for f in fixtures)

    def test_fixture_has_topic(self):
        fixtures = load_dev_fixtures()
        assert "YOLO" in fixtures[0].topic or "钢材" in fixtures[0].topic

    def test_get_adapter_response(self):
        f = load_dev_fixtures()[0]
        results = f.get_adapter_response("arxiv", "YOLO steel defect detection")
        assert len(results) == 2
        assert "YOLO" in results[0]["title"]

    def test_get_adapter_response_miss(self):
        """Query miss should return empty list, not error."""
        f = load_dev_fixtures()[0]
        results = f.get_adapter_response("arxiv", "completely different query")
        assert results == []

    def test_fixture_hash_deterministic(self):
        f1 = ReplayFixture(DEV_FIXTURES[0])
        f2 = ReplayFixture(DEV_FIXTURES[0])
        assert f1.fixture_hash == f2.fixture_hash

    def test_gold_roles(self):
        f = load_dev_fixtures()[0]
        assert f.required_roles()["core"] == 2
        assert "repo" in f.optional_roles()


class TestComputeMetrics:
    def test_no_violations_clean_run(self):
        f = load_dev_fixtures()[0]
        ledger = [
            {"fingerprint": "abc1", "query": "YOLO detection", "source_status": "success", "card_id": "sc-1"},
            {"fingerprint": "abc2", "query": "steel defect", "source_status": "success", "card_id": "sc-2"},
        ]
        coverage = {
            "current_coverage": {"core": 3, "baseline": 2, "parallel": 1, "dataset": 1, "repo": 1},
            "decision": "pass",
            "gaps": [],
        }
        metrics = compute_metrics(ledger, coverage, f)
        assert metrics["contract_violations"] == []
        assert metrics["coverage_rate"] == 1.0
        assert metrics["false_stop"] is False

    def test_duplicate_fingerprint_detected(self):
        f = load_dev_fixtures()[0]
        ledger = [
            {"fingerprint": "abc1", "query": "YOLO", "source_status": "success", "card_id": "sc-1"},
            {"fingerprint": "abc1", "query": "YOLO", "source_status": "success", "card_id": "sc-2"},
        ]
        coverage = {"current_coverage": {}, "decision": "pass", "gaps": []}
        metrics = compute_metrics(ledger, coverage, f)
        assert len(metrics["contract_violations"]) > 0

    def test_false_stop_detected(self):
        """Decision=pass but required roles not met → false_stop."""
        f = load_dev_fixtures()[0]
        ledger = [{"fingerprint": "abc1", "query": "test", "source_status": "success", "card_id": "sc-1"}]
        coverage = {
            "current_coverage": {"core": 0, "baseline": 0},  # nothing met
            "decision": "pass",  # but decided to pass!
            "gaps": [],
        }
        metrics = compute_metrics(ledger, coverage, f)
        assert metrics["false_stop"] is True
