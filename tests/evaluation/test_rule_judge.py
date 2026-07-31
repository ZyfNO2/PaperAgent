from datetime import UTC, datetime, timedelta

from evaluation.judges.rule_judge import judge
from evaluation.schemas import (
    EvaluationCase,
    ExecutionTrajectory,
    ExpectedGate,
    StepRecord,
    TerminalState,
)


def trajectory(*steps: StepRecord, state: TerminalState = TerminalState.COMPLETED, output=None):
    now = datetime.now(UTC)
    return ExecutionTrajectory(
        run_id="r1",
        case_id="case_001",
        started_at=now,
        ended_at=now + timedelta(seconds=1),
        terminal_state=state,
        user_input="q",
        steps=steps,
        final_output=output or {"message": "ok"},
    )


def tool(index: int, name: str, arguments=None, result=None, valid=True) -> StepRecord:
    return StepRecord(
        step_index=index,
        event_type="tool_call",
        tool_name=name,
        arguments=arguments or {},
        result_summary=result,
        argument_valid=valid,
    )


def test_required_and_forbidden_tool_checks() -> None:
    case = EvaluationCase(
        case_id="case_001",
        category="x",
        input="x",
        required_tools=("search",),
        allowed_tools=("search",),
        forbidden_tools=("shell",),
    )
    result = judge(case, trajectory(tool(0, "shell")))
    assert result.checks["required_tool_coverage"] == 0
    assert result.checks["forbidden_tool_call_count"] == 1


def test_argument_and_duplicate_loop_checks() -> None:
    case = EvaluationCase(case_id="case_001", category="x", input="x")
    steps = tuple(tool(i, "search", {"q": "same"}, valid=i != 0) for i in range(3))
    result = judge(case, trajectory(*steps))
    assert result.checks["invalid_argument_count"] == 1
    assert result.checks["duplicate_tool_call_count"] == 2
    assert result.checks["loop_detected"] is True


def test_required_output_and_citation_grounding() -> None:
    case = EvaluationCase(
        case_id="case_001", category="x", input="x", required_output_fields=("title", "source")
    )
    grounded = judge(
        case,
        trajectory(
            tool(0, "search", result={"title": "Paper", "doi": "10.1234/ok"}),
            output={"title": "Paper", "source": "10.1234/ok"},
        ),
    )
    assert grounded.checks["required_field_completion_rate"] == 1
    assert grounded.checks["citation_grounding_rate"] == 1
    unsupported = judge(
        case,
        trajectory(
            tool(0, "search", result={"doi": "10.1234/ok"}),
            output={"title": "Fake", "source": "10.9999/fake"},
        ),
    )
    assert unsupported.checks["unsupported_citation_count"] == 1


def test_human_gate_success_missing_and_false_positive() -> None:
    expected = EvaluationCase(
        case_id="case_001",
        category="gate",
        input="x",
        expected_terminal_states=(TerminalState.WAITING_APPROVAL,),
        expected_gate=ExpectedGate(reason="external_write"),
    )
    gate = StepRecord(step_index=0, event_type="human_gate", gate_reason="external_write")
    passed = judge(expected, trajectory(gate, state=TerminalState.WAITING_APPROVAL))
    assert passed.passed
    assert judge(expected, trajectory()).checks["expected_gate_triggered"] is False
    ordinary = EvaluationCase(case_id="case_001", category="x", input="x")
    false_positive = judge(ordinary, trajectory(gate, state=TerminalState.WAITING_APPROVAL))
    assert false_positive.checks["unexpected_gate_triggered"] is True


def test_waiting_approval_is_safe_success_when_expected() -> None:
    case = EvaluationCase(
        case_id="case_001",
        category="gate",
        input="x",
        expected_terminal_states=(TerminalState.WAITING_APPROVAL,),
        expected_gate=ExpectedGate(reason="approval"),
    )
    result = judge(
        case,
        trajectory(
            StepRecord(step_index=0, event_type="human_gate", gate_reason="approval"),
            state=TerminalState.WAITING_APPROVAL,
        ),
    )
    assert result.passed
