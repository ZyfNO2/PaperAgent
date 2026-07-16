from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator

from paperagent.schemas.base import FrozenModel


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for raw in values:
        value = raw.strip()
        if value and value not in seen:
            seen.add(value)
            output.append(value)
    return output


class ResearchRequest(FrozenModel):
    question: str = Field(min_length=3, max_length=4000)
    domain_hint: str | None = None
    required_constraints: list[str] = Field(default_factory=list)
    optional_preferences: list[str] = Field(default_factory=list)
    user_material_refs: list[str] = Field(default_factory=list)
    clarification_answer: str | None = None

    @field_validator("question", mode="before")
    @classmethod
    def normalize_question(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @field_validator(
        "required_constraints",
        "optional_preferences",
        "user_material_refs",
        mode="before",
    )
    @classmethod
    def normalize_lists(cls, value: Any) -> Any:
        if value is None:
            return []
        if isinstance(value, list):
            return _dedupe_strings(value)
        return value

    @field_validator("domain_hint", "clarification_answer", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: Any) -> Any:
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value
