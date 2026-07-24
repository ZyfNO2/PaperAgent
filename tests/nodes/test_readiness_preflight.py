from __future__ import annotations

import pytest


def _services(fixed_time):
    from paperagent.persistence import InMemoryStateStore
    from paperagent.providers import FakeLLMProvider, FakeSearchProvider
    from paperagent.runtime import RuntimeServices
    from paperagent.testing import FixedClock, SequenceIdFactory

    return RuntimeServices(
        llm=FakeLLMProvider(fixtures={}),
        search=FakeSearchProvider(fixtures={}),
        clock=FixedClock(fixed_time),
        ids=SequenceIdFactory(prefix="readiness"),
        store=InMemoryStateStore(),
    )


def _state(question: str):
    from paperagent.schemas import ExecutionMeta, ResearchRequest

    return {
        "request": ResearchRequest(question=question),
        "execution": ExecutionMeta(status="running", current_node="intake_node"),
    }


@pytest.mark.asyncio
async def test_explicit_split_leakage_short_circuits_to_no_go(fixed_time) -> None:
    from paperagent.nodes.readiness_preflight import (
        readiness_preflight_node,
        readiness_preflight_route,
    )
    from paperagent.state import apply_state_patch

    state = _state(
        "The same protein families appear in both the training set and test set, "
        "so the current score has train-test overlap."
    )
    patch = await readiness_preflight_node(
        state,
        {"configurable": {"services": _services(fixed_time)}},
    )
    resolved = apply_state_patch(state, patch)

    assert patch["scientific_readiness"].explicit_evaluation_protocol_invalid is True
    assert patch["quality"].verdict == "blocked"
    assert patch["final_outcome"].scientific_verdict == "NO_GO"
    assert patch["final_outcome"].report_status == "completed"
    assert readiness_preflight_route(resolved) == "terminal"
    assert [event.event_type for event in patch["trace"]] == [
        "node.started",
        "route.decided",
    ]


@pytest.mark.asyncio
async def test_complete_declaration_short_circuits_to_go_without_external_verification(
    fixed_time,
) -> None:
    from paperagent.nodes.readiness_preflight import (
        readiness_preflight_node,
        readiness_preflight_route,
    )
    from paperagent.state import apply_state_patch

    state = _state(
        "We reproduced and froze the baseline at a pinned version, used an independent "
        "grouped test split, verified a strong comparator under the matched protocol, "
        "confirmed compatible input and output interface semantics, and the isolated "
        "single-module ablation showed stable improvement across multiple seeds. "
        "Failure cases and stop conditions were documented."
    )
    patch = await readiness_preflight_node(
        state,
        {"configurable": {"services": _services(fixed_time)}},
    )
    resolved = apply_state_patch(state, patch)
    signals = patch["scientific_readiness"]

    assert signals.declared_ready is True
    assert signals.basis == "user_declaration"
    assert signals.independently_verified is False
    assert patch["quality"].verdict == "pass"
    assert patch["final_outcome"].scientific_verdict == "GO"
    assert patch["final_outcome"].reason_codes == ["Q_USER_DECLARED_READINESS_COMPLETE"]
    assert readiness_preflight_route(resolved) == "terminal"


@pytest.mark.asyncio
async def test_partial_declaration_continues_to_planning(fixed_time) -> None:
    from paperagent.nodes.readiness_preflight import (
        readiness_preflight_node,
        readiness_preflight_route,
    )
    from paperagent.state import apply_state_patch

    state = _state("We reproduced a baseline but still need a valid independent evaluation.")
    patch = await readiness_preflight_node(
        state,
        {"configurable": {"services": _services(fixed_time)}},
    )
    resolved = apply_state_patch(state, patch)

    assert patch["scientific_readiness"].declared_ready is False
    assert "quality" not in patch
    assert "final_outcome" not in patch
    assert readiness_preflight_route(resolved) == "continue"


def test_readiness_state_round_trip_preserves_declaration_basis() -> None:
    from paperagent.schemas import ExecutionMeta, ResearchRequest
    from paperagent.scientific_readiness import derive_scientific_readiness
    from paperagent.state import state_from_json, state_to_json

    state = {
        "request": ResearchRequest(question="Known train-test leakage invalidates evaluation."),
        "scientific_readiness": derive_scientific_readiness("Known train-test leakage."),
        "execution": ExecutionMeta(status="running"),
    }

    restored = state_from_json(state_to_json(state))

    assert restored["scientific_readiness"].basis == "user_declaration"
    assert restored["scientific_readiness"].independently_verified is False
    assert restored["scientific_readiness"].explicit_evaluation_protocol_invalid is True
