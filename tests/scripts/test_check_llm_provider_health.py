from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

SCRIPT = Path(__file__).parents[2] / "scripts" / "check_llm_provider_health.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_llm_provider_health", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_health_status_classification_is_precise() -> None:
    module = _load_script()
    assert module._status_name(401) == "authentication"
    assert module._status_name(403) == "permission"
    assert module._status_name(429) == "rate_limited"
    assert module._status_name(503) == "provider_5xx"
    assert module._status_name(400) == "invalid_request"
    assert module._status_name(200) == "ok"


def test_model_ids_ignore_malformed_entries() -> None:
    module = _load_script()
    assert module._model_ids(
        {"data": [{"id": "mistral-small-latest"}, {"name": "missing-id"}, "bad"]}
    ) == {"mistral-small-latest"}


def test_redacted_result_never_contains_credential_material() -> None:
    module = _load_script()
    result = module._result(
        provider="mistral",
        model="mistral-small-latest",
        base_url="https://api.mistral.ai/v1",
        status="authentication",
        http_status=401,
    )
    assert result["base_url_host"] == "api.mistral.ai"
    assert "api_key" not in result
    assert "authorization" not in result
