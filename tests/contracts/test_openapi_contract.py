from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from paperagent.api import create_app
from paperagent.demo import DemoTaskExecutor


def test_required_openapi_operations_and_schemas_are_stable(tmp_path: Path) -> None:
    contract = cast(
        dict[str, Any],
        json.loads(Path("contracts/openapi-v1.json").read_text(encoding="utf-8")),
    )
    app = create_app(
        executor=DemoTaskExecutor(delay_seconds=0),
        database_path=tmp_path / "paperagent.db",
    )
    schema = app.openapi()
    paths = cast(dict[str, dict[str, Any]], schema["paths"])

    for path, methods in cast(dict[str, list[str]], contract["required_operations"]).items():
        assert path in paths
        for method in methods:
            assert method in paths[path]

    component_schemas = cast(
        dict[str, Any],
        cast(dict[str, Any], schema["components"])["schemas"],
    )
    for name in cast(list[str], contract["required_schemas"]):
        assert name in component_schemas
