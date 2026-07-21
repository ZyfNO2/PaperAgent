from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel

from paperagent.method_design_draft import MethodDesignDraft
from paperagent.nodes._shared import json_message
from paperagent.nodes.evidence_synthesis import _constrained_synthesis_schema
from paperagent.prompts import get_prompt
from paperagent.providers.structured_output import (
    StructuredOutputFailure,
    validate_structured_response,
)
from paperagent.schemas import FinalReport, ResearchPlan

_SAFE_HEADERS = {
    "content-type",
    "date",
    "server",
    "x-request-id",
    "nvcf-reqid",
    "x-nv-request-id",
    "x-envoy-upstream-service-time",
}
_REASONING_KEYS = ("reasoning_content", "reasoning", "analysis")


@dataclass(frozen=True, slots=True)
class NodeProbe:
    task: str
    schema: type[BaseModel]
    payload: dict[str, Any]
    max_tokens: int


def _planning_probe() -> NodeProbe:
    return NodeProbe(
        task="planning",
        schema=ResearchPlan,
        max_tokens=2400,
        payload={
            "request": {
                "question": (
                    "Design a reproducible CIFAR-10 image-classification study comparing "
                    "a ResNet-18 baseline with one lightweight attention module."
                ),
                "required_constraints": [
                    "Use public data and public implementations.",
                    "Report accuracy, latency, ablations, and stopping criteria.",
                ],
                "user_material_refs": [],
            },
            "budgets": {
                "max_queries_per_round": 3,
                "max_retrieval_rounds": 2,
                "max_llm_calls": 10,
                "max_method_repairs": 1,
            },
            "available_source_types": [
                "paper",
                "dataset",
                "repository",
                "web",
                "user_material",
            ],
        },
    )


def _evidence_synthesis_probe() -> NodeProbe:
    schema = _constrained_synthesis_schema(
        accepted_evidence_ids=("ev-baseline", "ev-dataset", "ev-module"),
        gap_ids=("gap-baseline", "gap-dataset", "gap-module"),
    )
    return NodeProbe(
        task="evidence_synthesis",
        schema=schema,
        max_tokens=2600,
        payload={
            "plan": {
                "problem_statement": (
                    "Evaluate whether a lightweight attention module improves a ResNet-18 "
                    "baseline on CIFAR-10 without unacceptable latency."
                ),
                "evidence_gap_ids": ["gap-baseline", "gap-dataset", "gap-module"],
            },
            "allowed_evidence_ids": ["ev-baseline", "ev-dataset", "ev-module"],
            "identifier_rule": (
                "Copy evidence_id values exactly from allowed_evidence_ids. Do not invent IDs."
            ),
            "accepted_evidence": [
                {
                    "evidence_id": "ev-baseline",
                    "source_type": "paper",
                    "title": "Deep Residual Learning for Image Recognition",
                    "locator": "https://example.test/resnet",
                    "verification_status": "accepted",
                    "supports_gap_ids": ["gap-baseline"],
                    "summary": "Defines residual networks and the ResNet family.",
                },
                {
                    "evidence_id": "ev-dataset",
                    "source_type": "dataset",
                    "title": "CIFAR-10",
                    "locator": "https://example.test/cifar10",
                    "verification_status": "accepted",
                    "supports_gap_ids": ["gap-dataset"],
                    "summary": "Public ten-class image-classification benchmark.",
                },
                {
                    "evidence_id": "ev-module",
                    "source_type": "paper",
                    "title": "A Lightweight Channel Attention Module",
                    "locator": "https://example.test/attention",
                    "verification_status": "accepted",
                    "supports_gap_ids": ["gap-module"],
                    "summary": "Describes a low-overhead channel-attention component.",
                },
            ],
            "coverage_by_gap": {
                "gap-baseline": 1,
                "gap-dataset": 1,
                "gap-module": 1,
            },
            "conflicts": [],
        },
    )


def _method_design_probe() -> NodeProbe:
    return NodeProbe(
        task="method_design",
        schema=MethodDesignDraft,
        max_tokens=3600,
        payload={
            "user_request": (
                "Design a reproducible CIFAR-10 experiment comparing ResNet-18 with one "
                "lightweight attention module."
            ),
            "problem_statement": (
                "Test whether the module improves classification while preserving latency."
            ),
            "scope": "CIFAR-10, ResNet-18, one module, fixed training budget.",
            "verified_findings": [
                {
                    "claim_id": "claim-baseline",
                    "text": "ResNet-18 is the development baseline.",
                    "evidence_ids": ["ev-baseline"],
                },
                {
                    "claim_id": "claim-dataset",
                    "text": "CIFAR-10 is the public evaluation dataset.",
                    "evidence_ids": ["ev-dataset"],
                },
                {
                    "claim_id": "claim-module",
                    "text": "The candidate module is designed for low overhead.",
                    "evidence_ids": ["ev-module"],
                },
            ],
            "gap_assessments": [
                {
                    "gap_id": "gap-baseline",
                    "status": "supported",
                    "evidence_ids": ["ev-baseline"],
                    "summary": "Baseline identity is supported.",
                    "limitations": [],
                },
                {
                    "gap_id": "gap-dataset",
                    "status": "supported",
                    "evidence_ids": ["ev-dataset"],
                    "summary": "Dataset identity is supported.",
                    "limitations": [],
                },
                {
                    "gap_id": "gap-module",
                    "status": "supported",
                    "evidence_ids": ["ev-module"],
                    "summary": "Module identity is supported.",
                    "limitations": ["Exact latency must be measured in the target environment."],
                },
            ],
            "accepted_evidence_ledger": [
                {
                    "evidence_id": "ev-baseline",
                    "source_type": "paper",
                    "title": "Deep Residual Learning for Image Recognition",
                    "supports_gap_ids": ["gap-baseline"],
                },
                {
                    "evidence_id": "ev-dataset",
                    "source_type": "dataset",
                    "title": "CIFAR-10",
                    "supports_gap_ids": ["gap-dataset"],
                },
                {
                    "evidence_id": "ev-module",
                    "source_type": "paper",
                    "title": "A Lightweight Channel Attention Module",
                    "supports_gap_ids": ["gap-module"],
                },
            ],
            "constraints": [
                "Use three random seeds.",
                "Keep optimizer, augmentation, and epoch budget fixed across arms.",
            ],
            "risks": ["Hardware-dependent latency."],
            "clarification_question": None,
            "repair_reason": None,
        },
    )


def _report_probe() -> NodeProbe:
    return NodeProbe(
        task="report",
        schema=FinalReport,
        max_tokens=2400,
        payload={
            "final_outcome": {
                "scientific_verdict": "GO",
                "report_status": "completed",
                "reason_codes": [],
                "recommended_next_actions": [
                    "Run the preregistered three-seed experiment and report confidence intervals."
                ],
            },
            "quality": {"verdict": "pass", "reason_codes": []},
            "accepted_evidence_ids": ["ev-baseline", "ev-dataset", "ev-module"],
            "method_status": "ready",
        },
    )


def _probe_for(node: str) -> NodeProbe:
    builders = {
        "planning": _planning_probe,
        "evidence_synthesis": _evidence_synthesis_probe,
        "method_design": _method_design_probe,
        "report": _report_probe,
    }
    return builders[node]()


def _schema_hint(schema: type[BaseModel]) -> str:
    return (
        "\n\nReturn only one JSON object that validates against this JSON Schema:\n"
        + json.dumps(schema.model_json_schema(), ensure_ascii=False, sort_keys=True)
    )


def _safe_headers(response: httpx.Response) -> dict[str, str]:
    return {
        key.casefold(): value
        for key, value in response.headers.items()
        if key.casefold() in _SAFE_HEADERS
    }


def _text_metadata(value: object, *, preview_limit: int = 1200) -> dict[str, object]:
    if isinstance(value, str):
        return {
            "type": "str",
            "chars": len(value),
            "preview": value[:preview_limit],
        }
    if isinstance(value, list):
        return {
            "type": "list",
            "items": len(value),
            "item_types": [type(item).__name__ for item in value[:10]],
            "preview": value[:3],
        }
    if isinstance(value, dict):
        return {
            "type": "dict",
            "keys": sorted(str(key) for key in value),
            "preview": value,
        }
    return {"type": type(value).__name__, "preview": value}


def _reasoning_metadata(message: dict[str, Any], schema: type[BaseModel]) -> dict[str, object]:
    metadata: dict[str, object] = {}
    for key in _REASONING_KEYS:
        if key not in message:
            continue
        value = message[key]
        item = _text_metadata(value, preview_limit=0)
        body = {"choices": [{"message": {"content": value}}]}
        try:
            validate_structured_response(body, schema)
        except StructuredOutputFailure as exc:
            item["contains_schema_valid_payload"] = False
            item["parse_code"] = exc.code
        else:
            item["contains_schema_valid_payload"] = True
        item.pop("preview", None)
        metadata[key] = item
    return metadata


def _response_shape(body: object, schema: type[BaseModel]) -> dict[str, object]:
    if not isinstance(body, dict):
        return {"body_type": type(body).__name__}
    result: dict[str, object] = {
        "top_level_keys": sorted(str(key) for key in body),
    }
    usage = body.get("usage")
    if isinstance(usage, dict):
        result["usage"] = {
            "keys": sorted(str(key) for key in usage),
            "values": usage,
        }
    choices = body.get("choices")
    if isinstance(choices, list) and choices:
        choice = choices[0]
        if isinstance(choice, dict):
            result["choice_keys"] = sorted(str(key) for key in choice)
            result["finish_reason"] = choice.get("finish_reason")
            message = choice.get("message")
            if isinstance(message, dict):
                result["message_keys"] = sorted(str(key) for key in message)
                result["content"] = _text_metadata(message.get("content"))
                result["reasoning_fields"] = _reasoning_metadata(message, schema)
                if "tool_calls" in message:
                    result["tool_calls"] = _text_metadata(message.get("tool_calls"))
                if "function_call" in message:
                    result["function_call"] = _text_metadata(message.get("function_call"))
    try:
        parsed = validate_structured_response(body, schema)
    except StructuredOutputFailure as exc:
        result["parser"] = {
            "success": False,
            "code": exc.code,
            "message": str(exc),
        }
    else:
        result["parser"] = {
            "success": True,
            "model": type(parsed).__name__,
        }
    return result


def _payload_for_mode(probe: NodeProbe, mode: str, model: str) -> dict[str, Any]:
    prompt = get_prompt(probe.task)
    user_content = json_message(probe.payload)
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt.system},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0,
        "max_tokens": probe.max_tokens,
        "stream": False,
    }
    if mode == "json_schema":
        payload["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": probe.schema.__name__,
                "schema": probe.schema.model_json_schema(),
                "strict": False,
            },
        }
    elif mode == "json_object":
        payload["messages"][-1]["content"] += _schema_hint(probe.schema)
        payload["response_format"] = {"type": "json_object"}
    elif mode == "plain_schema_hint":
        payload["messages"][-1]["content"] += _schema_hint(probe.schema)
    else:
        raise ValueError(f"unsupported mode: {mode}")
    return payload


def _run_mode(
    client: httpx.Client,
    *,
    url: str,
    headers: dict[str, str],
    probe: NodeProbe,
    mode: str,
    model: str,
) -> dict[str, object]:
    payload = _payload_for_mode(probe, mode, model)
    started = time.perf_counter()
    response = client.post(url, headers=headers, json=payload)
    latency_ms = int((time.perf_counter() - started) * 1000)
    record: dict[str, object] = {
        "mode": mode,
        "http_status": response.status_code,
        "latency_ms": latency_ms,
        "headers": _safe_headers(response),
    }
    try:
        body = response.json()
    except ValueError:
        record["body_json"] = False
        record["body_preview"] = response.text[:1200]
    else:
        record["body_json"] = True
        record["shape"] = _response_shape(body, probe.schema)
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--node",
        required=True,
        choices=("planning", "evidence_synthesis", "method_design", "report"),
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="z-ai/glm-5.2")
    parser.add_argument("--base-url", default="https://integrate.api.nvidia.com/v1")
    parser.add_argument("--api-key-env", default="NVIDIA_API_KEY")
    args = parser.parse_args()

    api_key = os.getenv(args.api_key_env, "")
    if not api_key:
        raise SystemExit(f"missing credential in {args.api_key_env}")

    probe = _probe_for(args.node)
    url = f"{args.base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    report: dict[str, object] = {
        "schema": "paperagent.nvidia-node-output-probe.v1",
        "provider": "nvidia-nim",
        "endpoint_host": "integrate.api.nvidia.com",
        "model": args.model,
        "node": args.node,
        "task": probe.task,
        "output_schema": probe.schema.__name__,
        "modes": [],
    }
    timeout = httpx.Timeout(360.0, connect=15.0, read=300.0, write=60.0, pool=15.0)
    with httpx.Client(timeout=timeout) as client:
        for index, mode in enumerate(("json_schema", "json_object", "plain_schema_hint")):
            if index:
                time.sleep(1.6)
            try:
                result = _run_mode(
                    client,
                    url=url,
                    headers=headers,
                    probe=probe,
                    mode=mode,
                    model=args.model,
                )
            except Exception as exc:
                result = {
                    "mode": mode,
                    "exception_type": type(exc).__name__,
                    "exception": str(exc),
                }
            modes = report["modes"]
            assert isinstance(modes, list)
            modes.append(result)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    successful = any(
        isinstance(item, dict)
        and isinstance(item.get("shape"), dict)
        and isinstance(item["shape"].get("parser"), dict)
        and item["shape"]["parser"].get("success") is True
        for item in report["modes"]
    )
    return 0 if successful else 1


if __name__ == "__main__":
    raise SystemExit(main())
