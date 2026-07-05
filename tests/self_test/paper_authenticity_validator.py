"""Self-test validator: paper authenticity — verifies quality_filter results."""
from __future__ import annotations

import re
import json
from pathlib import Path
from typing import Any


KNOWN_POLLUTION = [
    "Question Answering Input Classification",
    "Question Answering and Knowledge Bases Core Concepts",
    "Deep Learning Core Term Entry",
    "Deep Learning Term Entry",
    "Deep Learning Core Concept Entry",
    "Deep Term Entry",
    "Deep Learning Technical Term Entry",
    "Indoor Environment Term Entry",
    "Indoor Input Term Assessment",
    "Indoor Term Assessment",
    "Table 2: Accuracy comparison between YOLOv5 and SDG-YOLOv5",
    "Figure 3: YOLOv5 model.",
    "Figure 3: YOLOv5 architecture.",
    "Figure 6: Improved YOLOv5 model.",
    "Supplemental Information 2: Code of yolov5.",
]

KNOWN_REAL = [
    "YOLOv5s-GTB: light-weighted and improved YOLOv5s for bridge crack detection",
    "HIC-YOLOv5: Improved YOLOv5 For Small Object Detection",
    "TPH-YOLOv5: Improved YOLOv5 Based on Transformer Prediction Head",
    "MonoIndoor++:Towards Better Practice of Self-Supervised Monocular Depth Estimation",
]

POLLUTION_PATTERNS = [
    r"Term Entry", r"Core Concept", r"Input Classification",
    r"Terminology Entry", r"Concept Entry", r"Term Assessment",
    r"Term List", r"Term Validation", r"Input Evaluation",
    r"Input Technical Keywords", r"Figure \d+", r"Table \d+:",
    r"Supplemental Information",
]


def validate_paper_authenticity(state: dict[str, Any]) -> dict[str, Any]:
    """Validate quality_filter results against known pollution patterns."""
    report: dict[str, Any] = {
        "pollution_check": {"total": len(KNOWN_POLLUTION), "filtered": 0, "leaked": []},
        "real_check": {"total": len(KNOWN_REAL), "kept": 0, "wrongly_dropped": []},
        "verified_papers_check": {"total": 0, "non_paper_leaked": []},
    }

    filter_results = state.get("filter_results", {})
    dropped_titles = {d.get("title", "") for d in filter_results.get("dropped_items", [])}
    for title in KNOWN_POLLUTION:
        if title in dropped_titles:
            report["pollution_check"]["filtered"] += 1

    kept_titles = {p.get("title", "") for p in state.get("paper_candidates", [])}
    for title in KNOWN_REAL:
        if title in kept_titles:
            report["real_check"]["kept"] += 1

    verified = state.get("verified_papers", [])
    report["verified_papers_check"]["total"] = len(verified)
    for p in verified:
        title = p.get("title", "")
        for pattern in POLLUTION_PATTERNS:
            if re.search(pattern, title, re.IGNORECASE):
                report["verified_papers_check"]["non_paper_leaked"].append(title)
                break

    return report
