from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import statistics
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, Field

from paperagent.providers.endpoint import (
    EndpointCapabilities,
    EndpointConfig,
    EndpointLimits,
    EndpointProtocol,
    ProviderPool,
    RoutedEndpoint,
)
from paperagent.providers.openai_llm import OpenAILLMProvider
from paperagent.providers.router import RoutingLLMProvider
from paperagent.schemas import Message

T = TypeVar("T", bound=BaseModel)


class ProbeResponse(BaseModel):
    nonce: str = Field(min_length=1)
    ok: bool


@dataclass(slots=True)
class EndpointStats:
    calls: int = 0
    successes: int = 0
    failures: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    error_codes: Counter[str] = field(default_factory=Counter)


class InstrumentedProvider:
    """Record delegate-level outcomes without relying on router-global last_* fields."""

    def __init__(self, endpoint_id: str, delegate: OpenAILLMProvider) -> None:
        self.endpoint_id = endpoint_id
        self.delegate = delegate
        self.stats = EndpointStats()
        self._lock = asyncio.Lock()

    @property
    def model_name(self) -> str:
        return self.delegate.model_name

    @property
    def last_usage(self):  # noqa: ANN201 - compatibility property
        return self.delegate.last_usage

    @property
    def last_latency_ms(self) -> int:
        return self.delegate.last_latency_ms

    async def generate_structured(
        self,
        *,
        task: str,
        scenario: str,
        call_index: int,
        fixture_version: str,
        schema: type[T],
        messages: list[Message],
    ) -> T:
        started = time.perf_counter()
        async with self._lock:
            self.stats.calls += 1
        try:
            result = await self.delegate.generate_structured(
                task=task,
                scenario=scenario,
                call_index=call_index,
                fixture_version=fixture_version,
                schema=schema,
                messages=messages,
            )
        except Exception as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            code = str(getattr(exc, "code", type(exc).__name__))
            async with self._lock:
                self.stats.failures += 1
                self.stats.latencies_ms.append(latency_ms)
                self.stats.error_codes[code] += 1
            raise
        latency_ms = (time.perf_counter() - started) * 1000
        async with self._lock:
            self.stats.successes += 1
            self.stats.latencies_ms.append(latency_ms)
        return result

    async def aclose(self) -> None:
        closer = getattr(self.delegate, "aclose", None)
        if closer is not None:
            result = closer()
            if asyncio.iscoroutine(result):
                await result


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def _load_config(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("pools"), list):
        raise ValueError("config root must contain a pools list")
    return raw


def _required_text(raw: dict[str, Any], key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"endpoint field {key!r} must be a non-empty string")
    return value.strip()


def _resolve_model(raw: dict[str, Any]) -> str:
    model = raw.get("model")
    model_env = raw.get("model_env")
    if isinstance(model, str) and model.strip():
        return model.strip()
    if isinstance(model_env, str) and model_env.strip():
        value = os.getenv(model_env.strip(), "").strip()
        if value:
            return value
        raise ValueError(f"model environment variable {model_env!r} is not set")
    raise ValueError("each endpoint requires model or model_env")


def _build_router(
    raw: dict[str, Any],
) -> tuple[RoutingLLMProvider, dict[str, InstrumentedProvider]]:
    pools: list[ProviderPool] = []
    delegates: dict[str, InstrumentedProvider] = {}
    for pool_raw in raw["pools"]:
        if not isinstance(pool_raw, dict):
            raise ValueError("each pool must be an object")
        pool_id = _required_text(pool_raw, "pool_id")
        endpoint_rows = pool_raw.get("endpoints")
        if not isinstance(endpoint_rows, list) or not endpoint_rows:
            raise ValueError(f"pool {pool_id!r} must contain endpoints")
        endpoints: list[RoutedEndpoint] = []
        for endpoint_raw in endpoint_rows:
            if not isinstance(endpoint_raw, dict):
                raise ValueError("each endpoint must be an object")
            endpoint_id = _required_text(endpoint_raw, "endpoint_id")
            key_env = _required_text(endpoint_raw, "api_key_env")
            api_key = os.getenv(key_env, "").strip()
            if not api_key:
                raise ValueError(f"API key environment variable {key_env!r} is not set")
            protocol = EndpointProtocol(
                endpoint_raw.get("protocol", EndpointProtocol.OPENAI_CHAT_COMPLETIONS)
            )
            limits = EndpointLimits(
                max_concurrency=int(endpoint_raw.get("max_concurrency", 1)),
                requests_per_minute=(
                    int(endpoint_raw["requests_per_minute"])
                    if endpoint_raw.get("requests_per_minute") is not None
                    else None
                ),
                request_timeout_seconds=float(endpoint_raw.get("timeout_seconds", 60.0)),
            )
            capabilities = EndpointCapabilities(
                native_json_schema=endpoint_raw.get("native_json_schema"),
                json_object=endpoint_raw.get("json_object"),
                prompt_injected_schema=bool(endpoint_raw.get("prompt_injected_schema", True)),
            )
            config = EndpointConfig(
                endpoint_id=endpoint_id,
                vendor=_required_text(endpoint_raw, "vendor"),
                protocol=protocol,
                model=_resolve_model(endpoint_raw),
                base_url=_required_text(endpoint_raw, "base_url").rstrip("/"),
                api_key_env=key_env,
                capabilities=capabilities,
                limits=limits,
                failure_threshold=int(endpoint_raw.get("failure_threshold", 2)),
                cooldown_seconds=float(endpoint_raw.get("cooldown_seconds", 30.0)),
                disabled=bool(endpoint_raw.get("disabled", False)),
            )
            provider = OpenAILLMProvider(
                api_key=api_key,
                model=config.model,
                base_url=config.base_url,
                timeout_seconds=config.limits.request_timeout_seconds,
                max_retries=0,
                max_requests_per_minute=config.limits.requests_per_minute,
                temperature=0.0,
                max_output_tokens=int(endpoint_raw.get("max_output_tokens", 64)),
                native_json_schema=bool(config.capabilities.native_json_schema),
                allow_schema_repair=bool(endpoint_raw.get("allow_schema_repair", True)),
            )
            instrumented = InstrumentedProvider(endpoint_id, provider)
            delegates[endpoint_id] = instrumented
            endpoints.append(RoutedEndpoint(config=config, provider=instrumented))
        pools.append(ProviderPool(pool_id=pool_id, endpoints=tuple(endpoints)))
    router = RoutingLLMProvider(
        pools,
        max_total_attempts=(
            int(raw["max_total_attempts"])
            if raw.get("max_total_attempts") is not None
            else None
        ),
        ewma_alpha=float(raw.get("ewma_alpha", 0.2)),
    )
    return router, delegates


async def _run_probe(
    router: RoutingLLMProvider,
    index: int,
    semaphore: asyncio.Semaphore,
) -> dict[str, Any]:
    nonce = f"probe-{index:04d}"
    messages = [
        Message(
            role="system",
            content="Return only JSON matching the requested schema. Do not add prose.",
        ),
        Message(
            role="user",
            content=(
                f'Return {{"nonce":"{nonce}","ok":true}} exactly. '
                "This is a provider-router load probe."
            ),
        ),
    ]
    started = time.perf_counter()
    async with semaphore:
        try:
            response = await router.generate_structured(
                task=f"router-load-{index}",
                scenario="live_router_load_test",
                call_index=index,
                fixture_version="router-load-v1",
                schema=ProbeResponse,
                messages=messages,
            )
        except Exception as exc:
            return {
                "index": index,
                "ok": False,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                "error_type": type(exc).__name__,
                "error_code": getattr(exc, "code", None),
                "error": str(exc)[:500],
            }
    return {
        "index": index,
        "ok": response.ok and response.nonce == nonce,
        "schema_ok": True,
        "echo_ok": response.nonce == nonce,
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
    }


async def _main_async(args: argparse.Namespace) -> int:
    raw = _load_config(args.config)
    router, delegates = _build_router(raw)
    if args.validate_only:
        print(
            json.dumps(
                {
                    "status": "configuration_valid",
                    "pools": [pool["pool_id"] for pool in raw["pools"]],
                    "endpoints": sorted(delegates),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        await router.aclose()
        return 0

    semaphore = asyncio.Semaphore(args.concurrency)
    started = time.perf_counter()
    results = await asyncio.gather(
        *(_run_probe(router, index, semaphore) for index in range(args.requests))
    )
    wall_seconds = time.perf_counter() - started
    snapshots = await router.snapshots()
    await router.aclose()

    successful = [item for item in results if item["ok"]]
    failed = [item for item in results if not item["ok"]]
    request_latencies = [float(item["latency_ms"]) for item in results]
    endpoint_report: dict[str, Any] = {}
    for endpoint_id, provider in delegates.items():
        stats = provider.stats
        endpoint_report[endpoint_id] = {
            "calls": stats.calls,
            "successes": stats.successes,
            "failures": stats.failures,
            "success_rate": round(stats.successes / stats.calls, 4) if stats.calls else None,
            "latency_ms": {
                "mean": round(statistics.fmean(stats.latencies_ms), 2)
                if stats.latencies_ms
                else None,
                "p50": round(_percentile(stats.latencies_ms, 0.50) or 0, 2)
                if stats.latencies_ms
                else None,
                "p95": round(_percentile(stats.latencies_ms, 0.95) or 0, 2)
                if stats.latencies_ms
                else None,
            },
            "error_codes": dict(stats.error_codes),
        }

    report = {
        "status": "passed" if not failed else "failed",
        "requests": args.requests,
        "concurrency": args.concurrency,
        "successes": len(successful),
        "failures": len(failed),
        "success_rate": round(len(successful) / len(results), 4) if results else 0,
        "wall_seconds": round(wall_seconds, 3),
        "throughput_requests_per_second": round(len(results) / wall_seconds, 3)
        if wall_seconds
        else None,
        "request_latency_ms": {
            "mean": round(statistics.fmean(request_latencies), 2)
            if request_latencies
            else None,
            "p50": round(_percentile(request_latencies, 0.50) or 0, 2)
            if request_latencies
            else None,
            "p95": round(_percentile(request_latencies, 0.95) or 0, 2)
            if request_latencies
            else None,
        },
        "endpoints": endpoint_report,
        "router_snapshots": [
            {
                **asdict(snapshot),
                "state": snapshot.state.value,
            }
            for snapshot in snapshots
        ],
        "failed_samples": failed[:10],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not failed else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run live concurrent load/fallback probes through RoutingLLMProvider."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/provider-router-load.example.json"),
    )
    parser.add_argument("--requests", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/provider-router-load-report.json"),
    )
    parser.add_argument("--validate-only", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.requests <= 0:
        raise ValueError("--requests must be positive")
    if args.concurrency <= 0:
        raise ValueError("--concurrency must be positive")
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
