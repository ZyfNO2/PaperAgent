"""Self-test validator: frontend — verifies index.html structure."""
from __future__ import annotations

import re
from pathlib import Path


def validate_frontend(html_path: str) -> dict[str, Any]:
    """Validate frontend index.html basic correctness."""
    content = Path(html_path).read_text(encoding="utf-8")

    report: dict[str, Any] = {"checks": [], "passed": 0, "failed": []}

    external_scripts = re.findall(r'<script\s+src=["\']https?://', content)
    external_links = re.findall(r'<link\s+.*href=["\']https?://', content)
    if not external_scripts and not external_links:
        report["checks"].append("no_external_dependencies")
        report["passed"] += 1
    else:
        report["failed"].append({
            "check": "no_external_dependencies",
            "issue": f"found {len(external_scripts)} external scripts, {len(external_links)} external links"
        })

    if "EventSource" in content:
        report["checks"].append("uses_eventsource")
        report["passed"] += 1
    else:
        report["failed"].append({"check": "uses_eventsource", "issue": "no EventSource found"})

    if "topic" in content.lower() and ("input" in content.lower() or "textarea" in content.lower()):
        report["checks"].append("has_topic_input")
        report["passed"] += 1
    else:
        report["failed"].append({"check": "has_topic_input", "issue": "no topic input found"})

    sse_events = re.findall(r'addEventListener\(["\'](\w+)["\']', content)
    expected_events = ["adapter_result", "verify_result", "node_complete", "done"]
    # Also accept generic event handling
    all_listeners = re.findall(r'addEventListener\(\s*["\']([^"\']+)["\']', content)
    for evt in expected_events:
        if evt not in all_listeners:
            report["failed"].append({
                "check": "sse_event_listener",
                "issue": f"missing addEventListener for '{evt}'"
            })
    if not any(f["check"] == "sse_event_listener" for f in report["failed"]):
        report["checks"].append("sse_event_listeners")
        report["passed"] += 1

    if "setInterval" in content or "setTimeout" in content or "poll" in content.lower():
        report["checks"].append("has_polling_fallback")
        report["passed"] += 1
    else:
        report["failed"].append({"check": "has_polling_fallback", "issue": "no polling fallback found"})

    return report


# Type alias for the return type
from typing import Any
