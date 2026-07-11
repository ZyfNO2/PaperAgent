"""Re5.X: Replay fixture framework for A/B/C experiment comparison.

Provides a frozen set of adapter responses so that all experiment arms
(control, A, B, C) run against identical inputs, isolating the variable
being tested (the prompt/controller).
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


class ReplayFixture:
    """A frozen set of adapter responses for a single topic.

    Structure:
    {
      "topic": "...",
      "atoms": {...},
      "adapter_responses": {
        "arxiv": {"query1": [results], "query2": [results]},
        "openalex": {...},
      },
      "gold": {
        "required_roles": {"core": 2, "baseline": 1},
        "optional_roles": {"parallel": 1, "dataset": 1, "repo": 1},
        "relevant_candidate_ids": [...],
        "noise_titles": [...],
        "acceptable_routes": {"disabled": ["semantic_scholar"], "empty_queries": [...]},
        "stop_with_gap_acceptable": false
      }
    }
    """

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data
        self.topic = data.get("topic", "")
        self.atoms = data.get("atoms", {})
        self.adapter_responses = data.get("adapter_responses", {})
        self.gold = data.get("gold", {})

    def get_adapter_response(self, source: str, query: str) -> list[dict[str, Any]]:
        """Get frozen response for a (source, query) pair."""
        source_data = self.adapter_responses.get(source, {})
        # Try exact match first, then normalized match
        if query in source_data:
            return source_data[query]
        # Try normalized (lowercase, stripped)
        for key, val in source_data.items():
            if key.strip().lower() == query.strip().lower():
                return val
        return []  # empty = query miss (NOT failure)

    def required_roles(self) -> dict[str, int]:
        return self.gold.get("required_roles", {"core": 2, "baseline": 1})

    def optional_roles(self) -> dict[str, int]:
        return self.gold.get("optional_roles", {})

    def relevant_ids(self) -> set[str]:
        return set(self.gold.get("relevant_candidate_ids", []))

    def noise_titles(self) -> set[str]:
        return set(t.lower() for t in self.gold.get("noise_titles", []))

    @property
    def fixture_hash(self) -> str:
        """Deterministic hash of the fixture content."""
        raw = json.dumps(self.data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


# Dev fixture set (20 topics, synthetic for prompt/schema testing)
DEV_FIXTURES: list[dict[str, Any]] = [
    {
        "topic": "基于YOLO的钢材表面缺陷检测",
        "atoms": {"method": ["YOLO"], "object": ["钢材表面缺陷"], "task": ["检测"], "domain": "computer_vision"},
        "adapter_responses": {
            "arxiv": {"YOLO steel defect detection": [
                {"title": "YOLO-World: Real-Time Open-Vocabulary Object Detection", "doi": "10.48550/arXiv.2401.17270"},
                {"title": "Surface Defect Detection with Deep Learning", "doi": "10.1016/j.jmatprotec.2023.01.001"},
            ]},
            "github": {"YOLO steel defect": [
                {"full_name": "ultralytics/ultralytics", "url": "https://github.com/ultralytics/ultralytics"},
            ]},
        },
        "gold": {
            "required_roles": {"core": 2, "baseline": 1},
            "optional_roles": {"parallel": 1, "dataset": 1, "repo": 1},
            "relevant_candidate_ids": ["10.48550/arXiv.2401.17270", "10.1016/j.jmatprotec.2023.01.001"],
            "noise_titles": [],
            "acceptable_routes": {"disabled": ["semantic_scholar"]},
            "stop_with_gap_acceptable": False,
        },
    },
    {
        "topic": "基于大语言模型的医学问答可信度评估",
        "atoms": {"method": ["大语言模型"], "object": ["医学问答"], "task": ["可信度评估"], "domain": "medical_ai"},
        "adapter_responses": {
            "pubmed": {"LLM medical question answering trustworthiness": [
                {"title": "Evaluating LLM Trustworthiness in Medical QA", "doi": "10.1038/s41591-024-02891.1"},
            ]},
            "arxiv": {"LLM medical trustworthiness evaluation": [
                {"title": "Trustworthy Medical LLM: A Survey", "doi": "10.48550/arXiv.2402.01001"},
            ]},
        },
        "gold": {
            "required_roles": {"core": 2, "baseline": 1},
            "optional_roles": {"parallel": 1, "dataset": 0, "repo": 0},
            "relevant_candidate_ids": ["10.1038/s41591-024-02891.1"],
            "noise_titles": ["irrelevant NLP paper"],
            "acceptable_routes": {"disabled": ["semantic_scholar", "openalex"]},
            "stop_with_gap_acceptable": False,
        },
    },
    {
        "topic": "Bridge crack detection using semantic segmentation",
        "atoms": {"method": ["semantic segmentation"], "object": ["bridge crack"], "task": ["detection"], "domain": "civil_engineering"},
        "adapter_responses": {
            "arxiv": {"semantic segmentation bridge crack": [
                {"title": "DeepCrack: A Cracks Dataset for Bridge Health Monitoring", "doi": "10.48550/arXiv.2304.01001"},
            ]},
            "crossref": {"bridge crack segmentation": [
                {"title": "Concrete Surface Crack Detection Using CNN", "doi": "10.1016/j.compstruct.2023.01.001"},
            ]},
        },
        "gold": {
            "required_roles": {"core": 2, "baseline": 1},
            "optional_roles": {"parallel": 1, "dataset": 1, "repo": 1},
            "relevant_candidate_ids": ["10.48550/arXiv.2304.01001", "10.1016/j.compstruct.2023.01.001"],
            "noise_titles": [],
            "acceptable_routes": {"disabled": ["semantic_scholar"]},
            "stop_with_gap_acceptable": False,
        },
    },
]


def load_dev_fixtures() -> list[ReplayFixture]:
    """Load dev fixture set."""
    return [ReplayFixture(f) for f in DEV_FIXTURES]


def compute_metrics(
    ledger_entries: list[dict[str, Any]],
    coverage_result: dict[str, Any],
    fixture: ReplayFixture,
) -> dict[str, Any]:
    """Compute evaluation metrics for a single case run.

    Args:
        ledger_entries: query_ledger.as_list()
        coverage_result: CoverageGate.model_dump()
        fixture: the replay fixture with gold labels

    Returns per-case metrics dict.
    """
    # Contract violations
    violations: list[str] = []
    fingerprints = set()
    for e in ledger_entries:
        fp = e.get("fingerprint", "")
        if fp in fingerprints:
            violations.append(f"duplicate_fingerprint:{fp}")
        fingerprints.add(fp)
        if e.get("source_status") == "empty":
            # empty should NOT be treated as failure
            pass  # correct behavior
        if not e.get("query"):
            violations.append(f"empty_query:{e.get('card_id')}")

    # Role coverage
    current = coverage_result.get("current_coverage", {})
    required = fixture.required_roles()
    roles_met = sum(1 for r, n in required.items() if current.get(r, 0) >= n)
    coverage_rate = roles_met / len(required) if required else 1.0

    # False stop
    decision = coverage_result.get("decision", "")
    gaps = coverage_result.get("gaps", [])
    false_stop = decision == "pass" and any(
        current.get(r, 0) < n for r, n in required.items()
    )

    # Duplicate/useless query rate
    n_total = len(ledger_entries)
    n_duplicate = len(violations)  # approximate
    dup_rate = n_duplicate / n_total if n_total > 0 else 0

    return {
        "topic": fixture.topic,
        "n_queries": n_total,
        "coverage_rate": round(coverage_rate, 2),
        "roles_met": roles_met,
        "roles_required": len(required),
        "decision": decision,
        "gaps": gaps,
        "false_stop": false_stop,
        "contract_violations": violations,
        "duplicate_query_rate": round(dup_rate, 2),
        "fixture_hash": fixture.fixture_hash,
    }
