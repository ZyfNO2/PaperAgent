"""Loop 3: SSE Stream endpoint test — verify endpoint structure and helpers."""
from __future__ import annotations

from unittest.mock import patch
from pathlib import Path
import tempfile

from fastapi.testclient import TestClient


def test_sse_endpoint_exists():
    """Test that the SSE stream endpoint is registered."""
    from apps.api.app.main import app
    routes = [r.path for r in app.routes]
    assert any("stream" in r for r in routes), "SSE stream endpoint not found"


def test_expanded_endpoint_exists():
    """Test that the expanded endpoint is registered."""
    from apps.api.app.main import app
    routes = [r.path for r in app.routes]
    assert any("expanded" in r for r in routes), "Expanded endpoint not found"


def test_expanded_endpoint_404():
    """Test 404 when state doesn't exist."""
    from apps.api.app.main import app
    client = TestClient(app)

    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("apps.api.app.api.v1.research._case_dir") as mock_case_dir:
            mock_case_dir.return_value = Path(tmpdir)  # No state.json
            response = client.get("/api/v1/research/nonexistent/expanded")
            assert response.status_code == 404


def test_sse_event_format():
    """Test that _sse_event formats correctly."""
    from apps.api.app.api.v1.research import _sse_event
    result = _sse_event("test_event", {"key": "value"})
    assert "event: test_event" in result
    assert "data:" in result
    assert '"key": "value"' in result
    assert result.endswith("\n\n")


def test_sse_event_types_defined():
    """Test that the SSE endpoint code defines expected event types."""
    import inspect
    from apps.api.app.api.v1 import research
    source = inspect.getsource(research)
    expected_events = [
        "search_started", "filter_result", "verify_completed",
        "expansion_started", "expansion_completed", "node_complete", "done", "error",
    ]
    for evt in expected_events:
        assert evt in source, f"SSE event type '{evt}' not found in research.py source"


def test_streaming_response_used():
    """Test that StreamingResponse is imported and used."""
    from apps.api.app.api.v1 import research
    assert hasattr(research, "StreamingResponse")
    import inspect
    source = inspect.getsource(research)
    assert "StreamingResponse" in source
    assert "text/event-stream" in source
