from __future__ import annotations


def test_hash_payload__mapping_order__is_stable() -> None:
    from paperagent.telemetry.hashing import hash_payload

    assert hash_payload({"b": 2, "a": 1}) == hash_payload({"a": 1, "b": 2})


def test_hash_payload__secret_fields__are_redacted_before_hashing() -> None:
    from paperagent.telemetry.hashing import canonical_payload

    payload = canonical_payload({"api_key": "secret", "nested": {"token": "secret-2"}})
    assert "secret" not in payload
    assert payload.count("[REDACTED]") == 2
