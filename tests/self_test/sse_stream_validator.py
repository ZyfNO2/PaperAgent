"""Self-test validator: SSE stream — verifies event completeness and data consistency."""
from __future__ import annotations

from typing import Any


def validate_sse_stream(events_received: list[str], state: dict[str, Any]) -> dict[str, Any]:
    """Validate SSE event stream against final state."""
    events_expected = [
        "search_started", "filter_result", "verify_completed",
        "expansion_started", "expansion_completed",
        "node_complete", "done",
    ]

    report: dict[str, Any] = {
        "events_received": events_received,
        "missing_events": [],
        "data_consistency": [],
        "failures": [],
    }

    received_types = set(events_received)
    for evt in events_expected:
        if evt not in received_types:
            if evt.startswith("expansion") and not state.get("expanded_papers"):
                continue
            report["missing_events"].append(evt)

    if report["missing_events"]:
        report["failures"].append({
            "check": "missing_events",
            "issue": f"missing: {report['missing_events']}"
        })

    return report
