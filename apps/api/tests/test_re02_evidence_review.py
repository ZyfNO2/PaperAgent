"""Re02 EvidenceReview tests (apps/api/app/services/agents/evidence_review).

Covers:
1. audit_candidates returns one row per input candidate
2. default tier for an unreviewed candidate is 'candidate'
3. exists_verdict enum enforced (invalid -> 'likely_exists')
4. stats() counts
5. status enums are exactly {core, candidate, needs_manual, rejected}
"""

from __future__ import annotations

import pytest

from app.services.agents.evidence_review import (
    EvidenceReview,
    VALID_STATUS,
    audit_candidates,
    by_status,
    stats,
)


pytestmark = pytest.mark.re02


def _fake_chat_factory(reviews_per_call: list[dict]):
    """Return a chat_json_strict that yields ``reviews_per_call`` per invocation."""
    calls = {"n": 0}

    def _fn(_prompt, _system, **_kw):
        calls["n"] += 1
        idx = min(calls["n"] - 1, len(reviews_per_call) - 1)
        return {"reviews": reviews_per_call[idx]}

    return _fn


def _cand(cid: str, title: str = "T", et: str = "paper", role: str = "reference") -> dict:
    return {
        "candidate_id": cid,
        "evidence_type": et,
        "role_hint": role,
        "title": title,
        "year": 2023,
        "venue": "ICML",
        "description": "",
        "abstract": "",
        "sources": ["arxiv"],
    }


def test_audit_candidates_returns_one_row_per_input():
    rows = [
        {"candidate_id": "a", "status": "core",     "exists_verdict": "exists"},
        {"candidate_id": "b", "status": "candidate", "exists_verdict": "likely_exists"},
    ]
    chat = _fake_chat_factory([rows])
    cands = [_cand("a"), _cand("b")]
    reviews = audit_candidates(parsed_topic={}, candidates=cands, raw={}, chat_json_strict=chat)
    assert len(reviews) == 2


def test_audit_candidates_default_tier_is_candidate():
    """When the LLM never returns a row for a candidate, we default to 'candidate' (NOT 'rejected')."""
    def chat(*a, **kw):
        return {"reviews": []}  # LLM returns nothing
    cands = [_cand("orphan1"), _cand("orphan2")]
    reviews = audit_candidates(parsed_topic={}, candidates=cands, raw={}, chat_json_strict=chat)
    assert len(reviews) == 2
    for r in reviews:
        assert r.status == "candidate"


def test_audit_candidates_invalid_exists_verdict_falls_back():
    def chat(*a, **kw):
        return {"reviews": [
            {"candidate_id": "x", "status": "core", "exists_verdict": "WHATEVER_NONSENSE"},
        ]}
    reviews = audit_candidates(parsed_topic={}, candidates=[_cand("x")], raw={}, chat_json_strict=chat)
    assert reviews[0].exists_verdict == "likely_exists"


def test_stats_returns_valid_status_counts():
    reviews = [
        EvidenceReview(candidate_id="1", status="core"),
        EvidenceReview(candidate_id="2", status="candidate"),
        EvidenceReview(candidate_id="3", status="needs_manual"),
        EvidenceReview(candidate_id="4", status="rejected"),
        EvidenceReview(candidate_id="5", status="core"),
    ]
    s = stats(reviews)
    assert s["core"] == 2
    assert s["candidate"] == 1
    assert s["needs_manual"] == 1
    assert s["rejected"] == 1


def test_status_enum_is_exactly_expected_set():
    rows = [
        {"candidate_id": "a", "status": "core",         "exists_verdict": "exists"},
        {"candidate_id": "b", "status": "candidate",    "exists_verdict": "likely_exists"},
        {"candidate_id": "c", "status": "needs_manual", "exists_verdict": "not_found"},
        {"candidate_id": "d", "status": "rejected",     "exists_verdict": "metadata_mismatch"},
    ]
    chat = _fake_chat_factory([rows])
    cands = [_cand(cid) for cid in ("a", "b", "c", "d")]
    reviews = audit_candidates(parsed_topic={}, candidates=cands, raw={}, chat_json_strict=chat)
    seen = {r.status for r in reviews}
    assert seen <= VALID_STATUS
    assert by_status(reviews)["core"][0].candidate_id == "a"
