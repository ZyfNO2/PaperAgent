from __future__ import annotations

from paperagent.providers.openai_llm import _request_headers


def test_openai_compatible_headers_use_stable_api_client_identity() -> None:
    headers = _request_headers("test-key")

    assert headers["Authorization"] == "Bearer test-key"
    assert headers["Accept"] == "application/json"
    assert headers["Content-Type"] == "application/json"
    assert headers["User-Agent"].startswith("PaperAgent/")
    assert "httpx" not in headers["User-Agent"].casefold()
