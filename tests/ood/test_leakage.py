from __future__ import annotations

from pathlib import Path


def test_source_and_prompt_files__contain_no_legacy_fixture_markers() -> None:
    forbidden = {"Re8", "ResearchState", "Nobel Prize in Physics 2024", "golden_answer"}
    paths = [*Path("src/paperagent").rglob("*.py"), *Path("src/paperagent/prompts").rglob("*.md")]
    text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    for marker in forbidden:
        assert marker.lower() not in text.lower()
