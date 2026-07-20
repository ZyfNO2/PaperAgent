from __future__ import annotations

from paperagent.benchmark_input import BenchmarkInput
from paperagent.claw_academic_benchmark import GoldCase


def benchmark_input_from_gold(case: GoldCase) -> BenchmarkInput:
    """Project a gold case onto the executor-visible input contract."""

    return BenchmarkInput(
        user_input=case.user_input,
        supplied_material_titles=tuple(material.title for material in case.supplied_materials),
        user_declared_roles=tuple(
            material.declared_role for material in case.supplied_materials
        ),
    )


__all__ = ["benchmark_input_from_gold"]
