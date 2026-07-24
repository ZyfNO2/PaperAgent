from __future__ import annotations


def test_node_error__serialization__is_stable_and_redacted() -> None:
    from paperagent.errors import NodeError

    error = NodeError(
        code="LLM_TIMEOUT",
        message="provider failed",
        node="planning_node",
        retryable=True,
        details={"api_key": "secret", "attempt": 2},
    )
    record = error.to_record()
    assert record.code == "LLM_TIMEOUT"
    assert record.details == {"api_key": "[REDACTED]", "attempt": 2}
    assert record.model_dump_json() == record.model_dump_json()
