from __future__ import annotations

from pydantic import Field, model_validator

from paperagent.schemas.base import FrozenModel
from paperagent.schemas.request import ResearchRequest


class BenchmarkInput(FrozenModel):
    """Gold-independent input contract for benchmark execution.

    The executor receives only information that is part of the user-visible request.
    Expected decisions, hypotheses, experiment plans, stop conditions, and special
    assertions are intentionally absent from this model.
    """

    user_input: str = Field(min_length=1)
    supplied_material_titles: tuple[str, ...] = ()
    user_declared_roles: tuple[str, ...] = ()
    declared_constraints: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_material_alignment(self) -> BenchmarkInput:
        if len(self.supplied_material_titles) != len(self.user_declared_roles):
            raise ValueError("supplied material titles and declared roles must align")
        if len(self.supplied_material_titles) > 2:
            raise ValueError("benchmark input supports at most two supplied materials")
        return self


def benchmark_input_to_request(value: BenchmarkInput) -> ResearchRequest:
    material_refs = [
        f"{title} [declared role: {role}]"
        for title, role in zip(
            value.supplied_material_titles,
            value.user_declared_roles,
            strict=True,
        )
    ]
    return ResearchRequest(
        question=value.user_input,
        required_constraints=list(value.declared_constraints),
        user_material_refs=material_refs,
    )


__all__ = ["BenchmarkInput", "benchmark_input_to_request"]
