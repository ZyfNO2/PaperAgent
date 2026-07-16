from __future__ import annotations

from paperagent.prompts.registry import all_prompts


def test_prompt_files__all_tasks__load_versioned_nonempty_content() -> None:
    prompts = {prompt.task: prompt for prompt in all_prompts()}
    assert set(prompts) == {"planning", "evidence_synthesis", "method_design", "report"}
    for task, prompt in prompts.items():
        assert prompt.version.startswith(f"{task}.v0.1.")
        assert len(prompt.system) > 120
        assert "JSON" in prompt.system
        assert "hidden chain-of-thought" in prompt.system


def test_prompt_files__production_content__contains_no_fixture_answer_ids() -> None:
    text = "\n".join(prompt.system for prompt in all_prompts()).lower()
    for marker in ("ev-support-001", "gap-support", "0.15", "happy_path"):
        assert marker not in text
