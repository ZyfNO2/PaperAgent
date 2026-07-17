from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections.abc import Sequence
from pathlib import Path
from typing import cast

import uvicorn

from paperagent.api import create_app
from paperagent.api.executor import TaskExecutor
from paperagent.api.real_executor import build_real_task_executor
from paperagent.demo import DemoTaskExecutor
from paperagent.literature.factory import LiteratureProviderSettings
from paperagent.llm_smoke import run_llm_smoke
from paperagent.plugins.cli import configure_plugin_parser, run_plugin_cli
from paperagent.pricing import load_price_table
from paperagent.provider_smoke import run_provider_smoke
from paperagent.providers.config import load_provider_config
from paperagent.providers.openai_llm import OpenAILLMProvider

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _non_negative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be non-negative")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="paperagent",
        description=(
            "PaperAgent bounded research utilities with v0.6 real LLM support, "
            "v0.7 local plugins, and the v0.8 academic method auditor."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve = subparsers.add_parser(
        "serve",
        help="serve the API and PWA shell with an explicit demo or real executor",
    )
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument(
        "--database",
        type=Path,
        default=Path(os.getenv("PAPERAGENT_DATABASE", "paperagent.db")),
    )
    serve.add_argument("--executor", choices=("demo", "real"), default="demo")
    serve.add_argument("--demo-delay", type=_non_negative_float, default=0.02)
    serve.add_argument("--llm-provider", default=None)
    serve.add_argument("--llm-model", default=None)
    serve.add_argument("--llm-base-url", default=None)
    serve.add_argument(
        "--llm-price-table",
        type=Path,
        default=(
            Path(os.environ["PAPERAGENT_LLM_PRICE_TABLE"])
            if os.getenv("PAPERAGENT_LLM_PRICE_TABLE")
            else None
        ),
    )
    serve.add_argument("--log-level", default="info")
    serve.add_argument(
        "--allow-public-bind",
        action="store_true",
        help="allow a non-loopback bind; still not a public multi-tenant security claim",
    )

    smoke = subparsers.add_parser(
        "provider-smoke",
        help="run live OpenAlex, arXiv, Crossref, and DataCite checks",
    )
    smoke.add_argument(
        "--contact-email",
        default=os.getenv("PAPERAGENT_CONTACT_EMAIL"),
    )
    smoke.add_argument("--timeout", type=_non_negative_float, default=20.0)

    llm_smoke = subparsers.add_parser(
        "llm-smoke",
        help="run an OpenAI-compatible smoke across the four structured nodes",
    )
    llm_smoke.add_argument(
        "--api-key",
        default=os.getenv("PAPERAGENT_OPENAI_API_KEY"),
        help="defaults to PAPERAGENT_OPENAI_API_KEY",
    )
    llm_smoke.add_argument(
        "--model",
        default=os.getenv("PAPERAGENT_OPENAI_MODEL", "gpt-4o-mini"),
    )
    llm_smoke.add_argument(
        "--base-url",
        default=os.getenv("PAPERAGENT_OPENAI_BASE_URL", "https://api.openai.com/v1"),
    )
    llm_smoke.add_argument("--timeout", type=_non_negative_float, default=60.0)
    llm_smoke.add_argument("--question", default=None)

    configure_plugin_parser(subparsers)
    return parser


def _serve(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    host = cast(str, args.host)
    port = cast(int, args.port)
    database = cast(Path, args.database)
    executor_name = cast(str, args.executor)
    delay = cast(float, args.demo_delay)
    allow_public_bind = cast(bool, args.allow_public_bind)
    log_level = cast(str, args.log_level)

    if not 1 <= port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if host not in _LOCAL_HOSTS and not allow_public_bind:
        parser.error(
            "non-loopback binds require --allow-public-bind; this release has no authentication"
        )

    executor: TaskExecutor
    if executor_name == "demo":
        executor = DemoTaskExecutor(delay_seconds=delay)
    else:
        try:
            provider_config = load_provider_config(
                provider=cast(str | None, args.llm_provider),
                model=cast(str | None, args.llm_model),
                base_url=cast(str | None, args.llm_base_url),
            )
            price_path = cast(Path | None, args.llm_price_table)
            price_table = load_price_table(price_path) if price_path is not None else None
            executor = build_real_task_executor(
                provider_config,
                literature_settings=LiteratureProviderSettings(
                    contact_email=os.getenv("PAPERAGENT_CONTACT_EMAIL"),
                    semantic_scholar_api_key=os.getenv("SEMANTIC_SCHOLAR_API_KEY"),
                ),
                price_table=price_table,
            )
        except (OSError, ValueError) as exc:
            parser.error(str(exc))

    app = create_app(
        executor=executor,
        database_path=database,
        sse_poll_seconds=0.05,
        sse_heartbeat_seconds=5.0,
    )
    uvicorn.run(app, host=host, port=port, log_level=log_level)
    return 0


def _provider_smoke(args: argparse.Namespace) -> int:
    contact_email = cast(str | None, args.contact_email)
    timeout = cast(float, args.timeout)
    if timeout <= 0:
        raise SystemExit("--timeout must be greater than zero")
    summary = asyncio.run(
        run_provider_smoke(
            contact_email=contact_email,
            timeout_seconds=timeout,
        )
    )
    print(json.dumps(summary.as_dict(), indent=2, sort_keys=True))
    return 0 if summary.passed else 1


def _llm_smoke(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    api_key = cast(str | None, args.api_key)
    if not api_key:
        parser.error(
            "--api-key is required (or set PAPERAGENT_OPENAI_API_KEY in the environment)"
        )
    timeout = cast(float, args.timeout)
    if timeout <= 0:
        raise SystemExit("--timeout must be greater than zero")
    provider = OpenAILLMProvider(
        api_key=api_key,
        model=cast(str, args.model),
        base_url=cast(str, args.base_url),
        timeout_seconds=timeout,
    )
    summary = asyncio.run(
        run_llm_smoke(provider, question=cast(str | None, args.question))
    )
    print(json.dumps(summary.as_dict(), indent=2, sort_keys=True))
    return 0 if summary.passed else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    command = cast(str, args.command)
    if command == "serve":
        return _serve(parser, args)
    if command == "provider-smoke":
        return _provider_smoke(args)
    if command == "llm-smoke":
        return _llm_smoke(parser, args)
    if command == "plugins":
        return run_plugin_cli(args)
    parser.error(f"unsupported command: {command}")
