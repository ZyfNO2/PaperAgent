MERGE_CONFLICT_MARKERS = ("<<<<<<<", "=======", ">>>>>>>")


def test_prompt_registry__known_task__returns_versioned_prompt() -> None:
    from paperagent.prompts.registry import get_prompt

    prompt = get_prompt("planning")
    assert prompt.task == "planning"
    assert prompt.version == "planning.v0.1.3"
    assert "Use status=need_human only" in prompt.system
    assert "Choose the number and boundaries of evidence gaps" in prompt.system
    assert "Keep minimum_accepted_items at 1" in prompt.system
    assert "Academic metadata providers predominantly index English" in prompt.system
    assert "JSON" in prompt.system
    assert "hidden chain of thought" not in prompt.system.lower()
    assert not any(marker in prompt.system for marker in MERGE_CONFLICT_MARKERS)


def test_gate_l_runner__source__has_no_merge_conflict_markers() -> None:
    with open("scripts/run_gate_l_execution.py", encoding="utf-8-sig") as handle:
        source = handle.read()
    assert not any(marker in source for marker in MERGE_CONFLICT_MARKERS)


def test_prompt_registry__unknown_task__fails() -> None:
    import pytest

    from paperagent.prompts.registry import PromptNotFoundError, get_prompt

    with pytest.raises(PromptNotFoundError):
        get_prompt("legacy_agent")
