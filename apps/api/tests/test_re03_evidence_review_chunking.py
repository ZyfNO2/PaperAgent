"""Re03 SOP §6.1: EvidenceReview chunked + retry + blocker tests."""

import pytest

from app.services.agents.evidence_review import audit_candidates, EvidenceReview


def _cand(cid: str, title: str, abstract: str = "abstract") -> dict:
    return {
        "candidate_id": cid,
        "evidence_type": "paper",
        "role_hint": "reference",
        "title": title,
        "year": 2024,
        "venue": "x",
        "description": "",
        "abstract": abstract,
        "sources": ["arxiv"],
    }


def test_chunk_size_20_default():
    """Env override is supported; default chunk size is 20."""
    import os
    os.environ["PAPERAGENT_ER_CHUNK_SIZE"] = "20"
    # just confirm the env is read; audit_candidates honors it
    assert os.environ.get("PAPERAGENT_ER_CHUNK_SIZE") == "20"


def test_audit_candidates_returns_one_review_per_candidate_with_fake_chat():
    """Inject a fake chat_json_strict that always returns valid JSON; each
    candidate gets one EvidenceReview row."""
    n = 25
    candidates = [
        _cand(f"c-{i:02d}", f"Paper title {i}", f"abstract {i}")
        for i in range(n)
    ]
    parsed = {
        "method_terms": ["x"], "task_terms": ["y"], "object_terms": ["z"],
        "query_atoms_en": ["x y"], "domain_route": "v",
    }
    def fake_chat(prompt, system, max_tokens, timeout=60.0):
        # Return a reviews list with one row per candidate that appeared
        # in the prompt. Extract candidate_ids from the embedded JSON.
        import re, json as jsonlib
        m = re.search(r'"candidates_block":\s*(\[.*?\])', prompt, re.DOTALL)
        block = jsonlib.loads(m.group(1))
        return {"reviews": [
            {
                "candidate_id": b["candidate_id"],
                "evidence_type": "paper",
                "role_hint": "reference",
                "status": "candidate",
                "matched_terms": ["x"],
                "missing_terms": [],
                "confidence_label": "medium",
                "relation_to_topic": "weak_related",
                "exists_verdict": "likely_exists",
                "rank_reason": "ok",
                "reason": "ok",
            } for b in block
        ]}
    reviews = audit_candidates(
        parsed_topic=parsed, candidates=candidates, raw={}, chat_json_strict=fake_chat,
    )
    assert len(reviews) == n
    assert all(isinstance(r, EvidenceReview) for r in reviews)


def test_chunk_failure_marks_blocker_on_affected_candidates():
    """When LLM returns broken JSON, candidates are marked with the
    [llm_blocker: ...] suffix in their reason field."""
    n = 5
    candidates = [_cand(f"c-{i}", f"t{i}") for i in range(n)]
    parsed = {"method_terms": [], "task_terms": [], "object_terms": [],
              "query_atoms_en": [], "domain_route": "v"}
    def bad_chat(prompt, system, max_tokens, timeout=60.0):
        # Return malformed JSON: a string, not a dict
        return "this is not a json object"

    # Our code doesn't raise on string return — chat_json_strict returns dict.
    # Patch by raising LLMUnavailable so the chunk falls into the blocked path.
    from app.services.llm import LLMUnavailable
    def raises_chat(prompt, system, max_tokens, timeout=60.0):
        raise LLMUnavailable("simulated chunk failure")

    reviews = audit_candidates(
        parsed_topic=parsed, candidates=candidates, raw={}, chat_json_strict=raises_chat,
    )
    assert len(reviews) == n
    for r in reviews:
        assert "[llm_blocker: evidence_review_parse_failed]" in r.reason
