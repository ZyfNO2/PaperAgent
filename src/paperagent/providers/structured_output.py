from __future__ import annotations

import ast
import json
import re
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

_FENCE_RE = re.compile(r"```(?:json|javascript|js)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")
_MAX_REPAIR_SOURCE_CHARS = 12_000


@dataclass(frozen=True, slots=True)
class StructuredOutputFailure(Exception):
    message: str
    code: str
    raw_output: str | None = None

    def __str__(self) -> str:
        return self.message


def _append_unique(values: list[Any], value: Any) -> None:
    try:
        fingerprint = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):
        fingerprint = repr(value)
    for existing in values:
        try:
            existing_fingerprint = json.dumps(
                existing, ensure_ascii=False, sort_keys=True, default=str
            )
        except (TypeError, ValueError):
            existing_fingerprint = repr(existing)
        if fingerprint == existing_fingerprint:
            return
    values.append(value)


def _flatten_block(block: dict[str, Any]) -> tuple[list[object], list[str]]:
    values: list[object] = []
    text_parts: list[str] = []
    for key in ("parsed", "json", "arguments"):
        candidate = block.get(key)
        if isinstance(candidate, str | dict | list):
            values.append(candidate)
    for key in ("text", "content", "value"):
        candidate = block.get(key)
        if isinstance(candidate, str):
            text_parts.append(candidate)
        elif isinstance(candidate, dict):
            nested = candidate.get("value") or candidate.get("text")
            if isinstance(nested, str):
                text_parts.append(nested)
    return values, text_parts


def _flatten_content(value: object) -> list[object]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        flattened, text_parts = _flatten_block(value)
        if text_parts:
            flattened.append("".join(text_parts))
        return flattened or [value]
    if not isinstance(value, list):
        return []

    flattened: list[object] = []
    text_parts: list[str] = []
    for block in value:
        if isinstance(block, str):
            text_parts.append(block)
            continue
        if not isinstance(block, dict):
            continue
        block_values, block_text = _flatten_block(block)
        flattened.extend(block_values)
        text_parts.extend(block_text)
    if text_parts:
        flattened.append("".join(text_parts))
    return flattened


def response_payloads(body: object) -> list[object]:
    """Extract candidate payloads from common OpenAI-compatible response shapes."""
    if not isinstance(body, dict):
        return []

    payloads: list[object] = []
    choices = body.get("choices")
    if isinstance(choices, list) and choices:
        choice = choices[0]
        if isinstance(choice, dict):
            message = choice.get("message")
            if isinstance(message, dict):
                parsed = message.get("parsed")
                if isinstance(parsed, dict | list | str):
                    payloads.append(parsed)
                payloads.extend(_flatten_content(message.get("content")))

                function_call = message.get("function_call")
                if isinstance(function_call, dict):
                    arguments = function_call.get("arguments")
                    if isinstance(arguments, str | dict | list):
                        payloads.append(arguments)

                tool_calls = message.get("tool_calls")
                if isinstance(tool_calls, list):
                    for tool_call in tool_calls:
                        if not isinstance(tool_call, dict):
                            continue
                        function = tool_call.get("function")
                        if isinstance(function, dict):
                            arguments = function.get("arguments")
                            if isinstance(arguments, str | dict | list):
                                payloads.append(arguments)
            text = choice.get("text")
            if isinstance(text, str):
                payloads.append(text)

    output_text = body.get("output_text")
    if isinstance(output_text, str):
        payloads.append(output_text)

    output = body.get("output")
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            payloads.extend(_flatten_content(item.get("content")))

    return payloads


def _string_variants(raw: str) -> list[str]:
    stripped = raw.lstrip("\ufeff").strip()
    if not stripped:
        return []
    variants = [stripped]
    if stripped.casefold().startswith("json\n"):
        variants.append(stripped[5:].strip())
    variants.extend(match.strip() for match in _FENCE_RE.findall(stripped) if match.strip())
    return list(dict.fromkeys(variants))


def _decode_direct(value: str) -> list[Any]:
    decoded: list[Any] = []
    for candidate in _string_variants(value):
        for text in (candidate, _TRAILING_COMMA_RE.sub(r"\1", candidate)):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = None
            if parsed is not None:
                if isinstance(parsed, str):
                    with suppress(json.JSONDecodeError):
                        parsed = json.loads(parsed)
                _append_unique(decoded, parsed)

        try:
            literal = ast.literal_eval(candidate)
        except (ValueError, SyntaxError):
            literal = None
        if isinstance(literal, dict | list):
            _append_unique(decoded, literal)
    return decoded


def _decode_embedded(value: str) -> list[Any]:
    decoded: list[Any] = []
    decoder = json.JSONDecoder()
    for candidate in _string_variants(value):
        for index, char in enumerate(candidate):
            if char not in "[{":
                continue
            try:
                parsed, _ = decoder.raw_decode(candidate[index:])
            except json.JSONDecodeError:
                continue
            _append_unique(decoded, parsed)
    return decoded


def decoded_candidates(payloads: list[object]) -> list[Any]:
    decoded: list[Any] = []
    for payload in payloads:
        if isinstance(payload, dict | list):
            _append_unique(decoded, payload)
            continue
        if not isinstance(payload, str):
            continue
        for candidate in (*_decode_direct(payload), *_decode_embedded(payload)):
            _append_unique(decoded, candidate)
    return decoded


def repair_source(payloads: list[object]) -> str | None:
    for payload in payloads:
        if isinstance(payload, str) and payload.strip():
            return payload[:_MAX_REPAIR_SOURCE_CHARS]
        if isinstance(payload, dict | list):
            return json.dumps(payload, ensure_ascii=False)[:_MAX_REPAIR_SOURCE_CHARS]
    return None


def validate_structured_response(body: object, schema: type[T]) -> T:
    payloads = response_payloads(body)
    candidates = decoded_candidates(payloads)
    if not candidates:
        raise StructuredOutputFailure(
            "response contains no parseable structured payload",
            code="LLM_RESPONSE_JSON_INVALID",
            raw_output=repair_source(payloads),
        )

    validation_error: ValidationError | None = None
    for candidate in candidates:
        try:
            return schema.model_validate(candidate)
        except ValidationError as exc:
            validation_error = exc

    raise StructuredOutputFailure(
        "response structured payload failed schema validation",
        code="LLM_RESPONSE_SCHEMA_INVALID",
        raw_output=repair_source(payloads),
    ) from validation_error


__all__ = [
    "StructuredOutputFailure",
    "decoded_candidates",
    "repair_source",
    "response_payloads",
    "validate_structured_response",
]
