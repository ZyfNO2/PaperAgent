"""Re03 SOP §6.1: Low-bar v3 llm_blocker enforcement tests (SOP §4.4)."""


from app.services.agents.low_bar_reviewer import (
    _deterministic_verdict,
    run_low_bar_review,
)


def _ok_synth():
    return {
        "direction_recommendation": "Use U-Net",
        "baseline_options": ["c-1"],
        "paper_groups": {
            "baseline": [{"title": "U-Net steel"}],
            "parallel": [],
            "reference": [],
            "long_tail_candidates": [],
        },
        "evidence_gaps": [],
        "work_suggestions": ["Reproduce U-Net"],
        "manual_questions": [],
    }


def test_llm_returns_pass_but_blocker_set_is_overridden_to_needs_revision():
    """Even if the LLM says pass, llm_blocker forces needs_revision."""
    def fake_chat(prompt, system, max_tokens, timeout=60.0):
        return {
            "review_verdict": "pass",
            "blocking_questions": [],
            "weak_points": [],
            "can_continue_to_opening_report": True,
            "summary": "all good",
        }
    v = run_low_bar_review(
        parsed_topic={}, synthesize_output=_ok_synth(),
        evidence_review_stats={"core": 1, "candidate": 0, "rejected": 0, "needs_manual": 0},
        candidate_pool_stats={"paper": 1, "dataset": 0, "repo": 0},
        chat_json_strict=fake_chat,
        llm_blocker="evidence_review_parse_failed",
    )
    assert v.review_verdict == "needs_revision", \
        f"expected needs_revision, got {v.review_verdict}"
    assert v.can_continue_to_opening_report is False
    assert any("llm_blocker" in wp for wp in v.weak_points)


def test_deterministic_path_respects_blocker():
    """When LLM is dead, deterministic fallback must also refuse pass if
    llm_blocker is set."""
    synth = _ok_synth()
    synth["paper_groups"]["reference"] = []  # ensure reference is non-empty
    v = _deterministic_verdict(
        synthesize_output=synth,
        er_stats={"core": 1, "candidate": 0, "rejected": 0, "needs_manual": 0},
        cp_stats={"paper": 1, "dataset": 0, "repo": 0},
        llm_blocker="evidence_review_parse_failed",
    )
    assert v.review_verdict == "needs_revision"
    assert v.can_continue_to_opening_report is False


def test_no_blocker_deterministic_can_pass():
    synth = _ok_synth()
    v = _deterministic_verdict(
        synthesize_output=synth,
        er_stats={"core": 1, "candidate": 5, "rejected": 1, "needs_manual": 0},
        cp_stats={"paper": 5, "dataset": 1, "repo": 1},
    )
    assert v.review_verdict == "pass"
    assert v.can_continue_to_opening_report is True


def test_no_blocker_llm_pass_is_kept():
    def fake_chat(prompt, system, max_tokens, timeout=60.0):
        return {
            "review_verdict": "pass",
            "blocking_questions": [],
            "weak_points": [],
            "can_continue_to_opening_report": True,
            "summary": "all good",
        }
    v = run_low_bar_review(
        parsed_topic={}, synthesize_output=_ok_synth(),
        evidence_review_stats={"core": 1, "candidate": 0, "rejected": 0, "needs_manual": 0},
        candidate_pool_stats={"paper": 1, "dataset": 0, "repo": 0},
        chat_json_strict=fake_chat,
    )
    assert v.review_verdict == "pass"
    assert v.can_continue_to_opening_report is True
