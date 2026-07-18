from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "llm" / "v0_1"


def load_llm_raw(task: str, scenario: str, call_index: int = 0) -> str:
    return (FIXTURE_ROOT / task / f"{scenario}__call_{call_index}.json").read_text(encoding="utf-8")


@pytest.fixture
def fixed_time() -> datetime:
    return datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
def accepted_evidence_payload() -> dict:
    return {
        "items": [
            {
                "evidence_id": "ev-support-001",
                "source_type": "user_material",
                "title": "Synthetic Claim-Support Note",
                "locator": "fixture://evidence/ev-support-001",
                "retrieved_at": "2026-01-01T00:01:00Z",
                "verification_status": "accepted",
                "supports_gap_ids": ["gap-support"],
                "summary": "Claim-level support labels yield a support rate.",
                "content_hash": "sha256:test-support",
                "provider": "fake_search",
                "metadata": {"license": "MIT"},
            },
            {
                "evidence_id": "ev-ablation-001",
                "source_type": "user_material",
                "title": "Synthetic Ablation Note",
                "locator": "fixture://evidence/ev-ablation-001",
                "retrieved_at": "2026-01-01T00:01:01Z",
                "verification_status": "accepted",
                "supports_gap_ids": ["gap-ablation"],
                "summary": "Gold, retrieved and shuffled context separate errors.",
                "content_hash": "sha256:test-ablation",
                "provider": "fake_search",
                "metadata": {"license": "MIT"},
            },
            {
                "evidence_id": "ev-rejected-001",
                "source_type": "web",
                "title": "Rejected Marketing Note",
                "locator": "fixture://evidence/ev-rejected-001",
                "retrieved_at": "2026-01-01T00:01:02Z",
                "verification_status": "rejected",
                "supports_gap_ids": ["gap-support"],
                "summary": "Unverified claim.",
                "content_hash": "sha256:test-rejected",
            },
        ],
        "accepted_ids": ["ev-support-001", "ev-ablation-001"],
        "rejected_ids": ["ev-rejected-001"],
        "pending_ids": [],
        "failed_verification_ids": [],
        "coverage_by_gap": {"gap-support": 1, "gap-ablation": 1},
        "conflicts": [],
    }
