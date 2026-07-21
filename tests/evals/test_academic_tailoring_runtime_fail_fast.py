from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

SCRIPT = Path(__file__).parents[2] / "scripts" / "run_academic_tailoring_retrieval_v1.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("run_academic_tailoring_retrieval_v1", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fatal_authentication_trace_is_detected() -> None:
    module = _load_script()
    assert (
        module._fatal_provider_error_code_from_trace(
            {"module_defer_reason": "LLM_AUTHENTICATION", "trace_error_codes": []}
        )
        == "LLM_AUTHENTICATION"
    )


def test_fatal_permission_code_is_detected_from_trace_errors() -> None:
    module = _load_script()
    assert (
        module._fatal_provider_error_code_from_trace(
            {"module_defer_reason": None, "trace_error_codes": ["LLM_PERMISSION"]}
        )
        == "LLM_PERMISSION"
    )


def test_transient_and_scientific_codes_do_not_abort_the_suite() -> None:
    module = _load_script()
    assert (
        module._fatal_provider_error_code_from_trace(
            {
                "module_defer_reason": "LLM_RATE_LIMITED",
                "trace_error_codes": ["NOT_EVALUATED", "FINAL_OUTCOME_AND_REPORT_PRESENT"],
            }
        )
        is None
    )
