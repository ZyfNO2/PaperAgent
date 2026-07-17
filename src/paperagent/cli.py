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
from paperagent.demo import DemoTaskExecutor
from paperagent.provider_smoke import run_provider_smoke

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _non_negative_float(value: str) -> float:
    parsed = float(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be non-negative")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="paperagent",
        description="PaperAgent v0.5.1 single-user release utilities.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve = subparsers.add_parser(
        "serve",
        help="serve the deterministic demo API and PWA shell",
    )
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument(
        "--database",
        type=Path,
        default=Path(os.getenv("PAPERAGENT_DATABASE", "paperagent.db")),
    )
    serve.add_argument("--demo-delay", type=_non_negative_float, default=0.02)
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
    return parser


def _serve(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    host = cast(str, args.host)
    port = cast(int, args.port)
    database = cast(Path, args.database)
    delay = cast(float, args.demo_delay)
    allow_public_bind = cast(bool, args.allow_public_bind)
    log_level = cast(str, args.log_level)

    if not 1 <= port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if host not in _LOCAL_HOSTS and not allow_public_bind:
        parser.error(
            "non-loopback binds require --allow-public-bind; this release has no authentication"
        )

    app = create_app(
        executor=DemoTaskExecutor(delay_seconds=delay),
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


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    command = cast(str, args.command)
    if command == "serve":
        return _serve(parser, args)
    if command == "provider-smoke":
        return _provider_smoke(args)
    parser.error(f"unsupported command: {command}")
