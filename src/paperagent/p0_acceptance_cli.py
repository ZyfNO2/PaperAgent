"""Operator CLI for the deterministic, fail-closed P0 report projection."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from paperagent.academic.p0_acceptance import (
    build_blocked_report,
    load_protocol,
    render_report_markdown,
    verify_file_digest,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="paperagent-p0-acceptance")
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    args = parser.parse_args(argv)
    protocol = load_protocol(args.protocol)
    contract_files = protocol.get("contract_files")
    if isinstance(contract_files, dict):
        for name in ("schema", "golden"):
            resource = contract_files.get(name)
            if isinstance(resource, dict):
                path = Path(str(resource["path"]))
                verify_file_digest(path, str(resource["sha256"]))
    report = build_blocked_report(protocol)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.markdown_output.write_text(render_report_markdown(report), encoding="utf-8")
    print(json.dumps({"status": report["p0_release"], "json": str(args.json_output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
