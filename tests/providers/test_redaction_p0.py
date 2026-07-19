from __future__ import annotations

from paperagent.telemetry.redaction import redact


def test_redaction_covers_prefixed_keys_and_embedded_credentials() -> None:
    payload = {
        "MISTRAL_API_KEY": "secret-key",
        "x-api-key": "other-secret",
        "message": (
            "Authorization: Bearer live-token "
            "url=https://example.test/path?access_token=query-secret&safe=1 "
            "PAPERAGENT_API_KEY=assigned-secret"
        ),
        "token_usage": {"input_tokens": 10, "output_tokens": 2},
    }

    result = redact(payload)

    assert result["MISTRAL_API_KEY"] == "[REDACTED]"
    assert result["x-api-key"] == "[REDACTED]"
    assert result["token_usage"] == {"input_tokens": 10, "output_tokens": 2}
    message = result["message"]
    assert isinstance(message, str)
    assert "live-token" not in message
    assert "query-secret" not in message
    assert "assigned-secret" not in message
    assert "Bearer [REDACTED]" in message
    assert "access_token=[REDACTED]" in message
    assert "PAPERAGENT_API_KEY=[REDACTED]" in message
