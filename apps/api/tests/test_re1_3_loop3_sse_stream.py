"""Loop 3: SSE Stream endpoint test."""
from __future__ import annotations

import json
import pytest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient


def test_sse_endpoint_returns_stream():
    """Test that the SSE endpoint returns a streaming response."""
    from apps.api.app.main import app

    # Create a test client
    client = TestClient(app)

    # Mock the run status to return "done" immediately
    with patch("apps.api.app.api.v1.research._RUN_STATUS", {"test-case": {"status": "done"}}):
        with patch("apps.api.app.api.v1.research._case_dir") as mock_case_dir:
            # Mock case_dir to return a path with trace.json
            from pathlib import Path
            import tempfile, os

            with tempfile.TemporaryDirectory() as tmpdir:
                from pathlib import Path
                mock_dir = MagicMock()
                mock_dir.__truediv__ = lambda self, x: Path(tmpdir) / x

                # Write a minimal trace.json
                trace_data = [
                    {"node": "quality_filter", "output_summary": {"kept": 5, "dropped": 2}, "elapsed_s": 1.5},
                    {"node": "verify", "input_summary": {"round": 1}, "output_summary": {"n_accept": 3, "n_reject_or_weak": 2}, "elapsed_s": 10.0},
                    {"node": "citation_expander", "input_summary": {"n_seeds": 2, "seed_titles": ["Paper A", "Paper B"]},
                     "output_summary": {"n_expanded": 20, "n_surveys": 2, "n_repos": 1}, "elapsed_s": 15.0},
                    {"node": "baseline_classifier", "output_summary": {"n_baseline": 3}, "elapsed_s": 0.5},
                ]
                (Path(tmpdir) / "trace.json").write_text(json.dumps(trace_data))

                # Write state.json for done event
                state_data = {"elapsed_s": 120.5}
                (Path(tmpdir) / "state.json").write_text(json.dumps(state_data))

                mock_case_dir.return_value = Path(tmpdir)

                # Use the test client to get the stream
                response = client.get("/api/v1/research/test-case/stream")

                assert response.status_code == 200
                assert "text/event-stream" in response.headers.get("content-type", "")

                # Parse SSE events from response text
                text = response.text
                assert "event: search_started" in text
                assert "event: filter_result" in text
                assert "event: verify_completed" in text
                assert "event: expansion_started" in text
                assert "event: expansion_completed" in text
                assert "event: node_complete" in text
                assert "event: done" in text


def test_expanded_endpoint():
    """Test the /expanded endpoint returns expansion data."""
    from apps.api.app.main import app
    client = TestClient(app)

    import tempfile, json
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        state_data = {
            "seed_papers": [{"title": "Seed Paper", "relevance_score": 10}],
            "expanded_papers": [{"title": "Expanded Paper", "paper_id": "exp1"}],
            "surveys_found": [{"title": "Survey"}],
            "repos_found": [{"url": "https://github.com/user/repo"}],
            "trace_events": [{"node": "citation_expander", "output_summary": {"n_expanded": 5}}],
        }

        with patch("apps.api.app.api.v1.research._case_dir") as mock_case_dir:
            mock_case_dir.return_value = Path(tmpdir)
            (Path(tmpdir) / "state.json").write_text(json.dumps(state_data))

            response = client.get("/api/v1/research/test-case/expanded")

            assert response.status_code == 200
            data = response.json()
            assert len(data["seed_papers"]) == 1
            assert len(data["expanded_papers"]) == 1
            assert len(data["surveys_found"]) == 1
            assert len(data["repos_found"]) == 1


def test_expanded_endpoint_404():
    """Test 404 when state doesn't exist."""
    from apps.api.app.main import app
    client = TestClient(app)

    with patch("apps.api.app.api.v1.research._case_dir") as mock_case_dir:
        from pathlib import Path
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_case_dir.return_value = Path(tmpdir)  # No state.json
            response = client.get("/api/v1/research/nonexistent/expanded")
            assert response.status_code == 404
