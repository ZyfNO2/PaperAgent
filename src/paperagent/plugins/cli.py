from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from paperagent.plugins import build_default_registry
from paperagent.plugins.contracts import PluginError, PluginRequest


def _add_external_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--enable-external-plugin",
        action="append",
        default=[],
        metavar="ENTRY_POINT_NAME",
        help="explicitly authorize one installed paperagent.plugins entry point",
    )


def configure_plugin_parser(subparsers: Any) -> None:
    plugins = subparsers.add_parser(
        "plugins",
        help="list, inspect, or explicitly invoke local PaperAgent plugins",
    )
    plugin_commands = plugins.add_subparsers(dest="plugin_command", required=True)

    list_command = plugin_commands.add_parser("list", help="list available plugin manifests")
    _add_external_options(list_command)

    inspect_command = plugin_commands.add_parser("inspect", help="inspect one plugin manifest")
    inspect_command.add_argument("name")
    _add_external_options(inspect_command)

    run_command = plugin_commands.add_parser("run", help="invoke one plugin operation")
    run_command.add_argument("name")
    run_command.add_argument("--operation", required=True)
    run_command.add_argument("--input", type=Path, required=True)
    run_command.add_argument("--output", type=Path, required=True)
    run_command.add_argument("--request-id", default=None)
    run_command.add_argument("--overwrite", action="store_true")
    _add_external_options(run_command)


def _load_payload(path: Path) -> dict[str, object]:
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("plugin input must be a JSON object")
    return cast(dict[str, object], parsed)


def _stable_request_id(name: str, operation: str, payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(f"{name}\0{operation}\0{canonical}".encode()).hexdigest()
    return f"plugin-{digest[:24]}"


def _write_atomic_json(path: Path, value: object, *, overwrite: bool) -> None:
    if not path.parent.exists():
        raise ValueError(f"output parent directory does not exist: {path.parent}")
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    payload = json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    try:
        temporary.write_text(payload, encoding="utf-8")
        if overwrite:
            temporary.replace(path)
            return
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise ValueError(f"output already exists: {path}") from exc
    finally:
        temporary.unlink(missing_ok=True)


def _allowed_names(args: argparse.Namespace) -> set[str]:
    return set(cast(list[str], args.enable_external_plugin))


def _print_error(exc: Exception) -> None:
    if isinstance(exc, PluginError):
        payload = {
            "error": exc.code.value,
            "message": exc.message,
            "plugin": exc.plugin_name,
        }
    else:
        payload = {"error": type(exc).__name__, "message": str(exc)}
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True), file=sys.stderr)


def run_plugin_cli(args: argparse.Namespace) -> int:
    try:
        registry, failures = build_default_registry(allowed_external_names=_allowed_names(args))
        command = cast(str, args.plugin_command)
        if command == "list":
            list_payload: dict[str, object] = {
                "plugins": [manifest.model_dump(mode="json") for manifest in registry.manifests()],
                "load_failures": [failure.model_dump(mode="json") for failure in failures],
            }
            print(json.dumps(list_payload, ensure_ascii=False, indent=2, sort_keys=True))
            return 1 if failures else 0
        if failures:
            raise ValueError(
                "one or more explicitly authorized external plugins failed to load: "
                + ", ".join(failure.entry_point for failure in failures)
            )
        name = cast(str, args.name)
        if command == "inspect":
            manifest = registry.resolve(name).manifest
            print(
                json.dumps(
                    manifest.model_dump(mode="json"),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if command == "run":
            operation = cast(str, args.operation)
            input_path = cast(Path, args.input)
            output_path = cast(Path, args.output)
            request_payload = _load_payload(input_path)
            request_id = cast(str | None, args.request_id) or _stable_request_id(
                name,
                operation,
                request_payload,
            )
            result = registry.invoke(
                name,
                PluginRequest(
                    request_id=request_id,
                    operation=operation,
                    payload=request_payload,
                ),
            )
            _write_atomic_json(
                output_path,
                result.model_dump(mode="json"),
                overwrite=cast(bool, args.overwrite),
            )
            print(str(output_path))
            return 0
        raise ValueError(f"unsupported plugin command: {command}")
    except (OSError, ValueError, PluginError) as exc:
        _print_error(exc)
        return 2
