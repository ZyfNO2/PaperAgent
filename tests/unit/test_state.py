from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime


def _event(event_id: str):
    from paperagent.schemas import TraceEvent

    return TraceEvent(
        event_id=event_id,
        run_id="run-1",
        span_id=f"span-{event_id}",
        event_type="node.completed",
        node="test",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        status="completed",
    )


def test_apply_state_patch__trace__appends_without_mutating_input() -> None:
    from paperagent.state import apply_state_patch

    state = {"trace": [_event("e1")], "plan": None}
    before = deepcopy(state)
    updated = apply_state_patch(state, {"trace": [_event("e2")]})
    assert [event.event_id for event in updated["trace"]] == ["e1", "e2"]
    assert state == before


def test_apply_state_patch__artifact__replaces_instead_of_deep_merging() -> None:
    from paperagent.schemas import ExecutionMeta
    from paperagent.state import apply_state_patch

    state = {"execution": ExecutionMeta(status="running", llm_call_count=3)}
    replacement = ExecutionMeta(status="blocked")
    updated = apply_state_patch(state, {"execution": replacement})
    assert updated["execution"] == replacement
    assert updated["execution"].llm_call_count == 0


def test_state_json__round_trip__preserves_typed_artifacts() -> None:
    from paperagent.schemas import ExecutionMeta, ResearchRequest
    from paperagent.state import state_from_json, state_to_json

    state = {
        "request": ResearchRequest(question="evaluate citations"),
        "execution": ExecutionMeta(status="running"),
        "trace": [],
    }
    restored = state_from_json(state_to_json(state))
    assert restored["request"] == state["request"]
    assert restored["execution"] == state["execution"]
