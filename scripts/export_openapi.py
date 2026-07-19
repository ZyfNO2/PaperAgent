from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from paperagent.api import create_app
from paperagent.demo import DemoTaskExecutor


def export_openapi(output: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="paperagent-openapi-") as directory:
        app = create_app(
            executor=DemoTaskExecutor(delay_seconds=0),
            database_path=Path(directory) / "paperagent.db",
        )
        schema = app.openapi()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the current PaperAgent OpenAPI schema")
    parser.add_argument("--output", type=Path, default=Path("build/openapi.json"))
    args = parser.parse_args()
    export_openapi(args.output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
