from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

_V2_PATH = Path(__file__).with_name("apply_artifact_driven_fixes_v2.py")


def _load_v2() -> ModuleType:
    spec = importlib.util.spec_from_file_location("artifact_fix_v2", _V2_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {_V2_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def patch_graph_recursion_budget(v2: ModuleType) -> None:
    path = "src/paperagent/claw_benchmark_runtime.py"
    v2.replace_once(
        path,
        "    max_method_repairs: int = 1,\n"
        "    max_evidence_items: int = 30,\n"
        ") -> tuple[dict[str, Any], PaperAgentState]:\n",
        "    max_method_repairs: int = 1,\n"
        "    max_evidence_items: int = 30,\n"
        "    recursion_limit: int = 100,\n"
        ") -> tuple[dict[str, Any], PaperAgentState]:\n",
    )
    v2.replace_once(
        path,
        "    services = RuntimeServices(\n",
        "    if recursion_limit < 1:\n"
        '        raise ValueError("recursion_limit must be positive")\n'
        "\n"
        "    services = RuntimeServices(\n",
    )
    v2.replace_once(
        path,
        '                "human_review_policy": "block",\n'
        "            }\n"
        "        },\n",
        '                "human_review_policy": "block",\n'
        "            },\n"
        '            "recursion_limit": recursion_limit,\n'
        "        },\n",
    )
    v2.replace_once(
        path,
        "    max_method_repairs: int = 1,\n"
        "    max_evidence_items: int = 30,\n"
        ") -> tuple[dict[str, Any], AcademicTailoringRunTrace]:\n",
        "    max_method_repairs: int = 1,\n"
        "    max_evidence_items: int = 30,\n"
        "    recursion_limit: int = 100,\n"
        ") -> tuple[dict[str, Any], AcademicTailoringRunTrace]:\n",
    )
    v2.replace_once(
        path,
        "        max_llm_calls=max_llm_calls,\n"
        "        task_id=task_id,\n"
        "        max_retrieval_rounds=max_retrieval_rounds,\n"
        "        max_queries_per_round=max_queries_per_round,\n"
        "        max_method_repairs=max_method_repairs,\n"
        "        max_evidence_items=max_evidence_items,\n"
        "    )\n",
        "        max_llm_calls=max_llm_calls,\n"
        "        task_id=task_id,\n"
        "        max_retrieval_rounds=max_retrieval_rounds,\n"
        "        max_queries_per_round=max_queries_per_round,\n"
        "        max_method_repairs=max_method_repairs,\n"
        "        max_evidence_items=max_evidence_items,\n"
        "        recursion_limit=recursion_limit,\n"
        "    )\n",
    )


def main() -> None:
    v2 = _load_v2()
    v2.patch_dataset_relation_priority()
    v2.patch_repository_backed_baseline()
    v2.patch_scorer_baseline_acceptance()
    patch_graph_recursion_budget(v2)
    v2.patch_runner_recursion_budget()
    v2.patch_tests()


if __name__ == "__main__":
    main()
