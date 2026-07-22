from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path
from types import ModuleType
from urllib.error import HTTPError

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


def test_chat_probe_requires_a_choice_object() -> None:
    module = _load_script()
    assert module._chat_completion_accessible({"choices": [{"message": {"content": "OK"}}]})
    assert not module._chat_completion_accessible({"choices": []})
    assert not module._chat_completion_accessible({"choices": ["bad"]})


def test_credential_diagnostics_detect_assignment_and_whitespace_without_value() -> None:
    module = _load_script()
    diagnostics = module._credential_diagnostics(
        "  OPENCODE_API_KEY=super-secret-value\n", "OPENCODE_API_KEY"
    )

    assert diagnostics == {
        "credential_present": True,
        "credential_had_outer_whitespace": True,
        "credential_contains_env_assignment": True,
    }
    assert "super-secret-value" not in repr(diagnostics)


def test_http_error_details_preserve_provider_reason_and_redact_key() -> None:
    module = _load_script()
    api_key = "sk-secret-material-123456"
    body = json.dumps(
        {
            "error": {
                "code": "invalid_api_key",
                "message": f"API key {api_key} is not authorized for this workspace",
            }
        }
    ).encode()
    error = HTTPError(
        "https://opencode.ai/zen/v1/chat/completions",
        403,
        "Forbidden",
        hdrs=None,
        fp=io.BytesIO(body),
    )

    details = module._http_error_details(error, api_key=api_key)

    assert details["provider_error_code"] == "invalid_api_key"
    assert api_key not in details["provider_error_message"]
    assert "[REDACTED]" in details["provider_error_message"]


def test_redacted_result_never_contains_credential_material() -> None:
    module = _load_script()
    result = module._result(
        provider="openai",
        model="z-ai/glm-5.2",
        base_url="https://integrate.api.nvidia.com/v1",
        probe_mode="chat",
        status="authentication",
        http_status=401,
        credential_diagnostics={
            "credential_present": True,
            "credential_had_outer_whitespace": False,
            "credential_contains_env_assignment": False,
        },
        provider_error={
            "provider_error_code": "invalid_api_key",
            "provider_error_message": "credential rejected",
        },
    )
    assert result["base_url_host"] == "integrate.api.nvidia.com"
    assert result["probe_mode"] == "chat"
    assert "api_key" not in result
    assert "authorization" not in result
