from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from paperagent.academic_tailoring import TailoringTask


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def load_tailoring_task_bundle(root: Path) -> TailoringTask:
    idea = cast(dict[str, Any], _load_json(root / "idea.json"))
    papers = cast(list[dict[str, Any]], _load_json(root / "papers.json"))
    reproduction = cast(dict[str, Any], _load_json(root / "reproduction.json"))
    expected_results = cast(list[dict[str, Any]], _load_json(root / "expected_results.json"))
    protocol = cast(dict[str, Any], _load_json(root / "protocol.json"))
    module_paths = sorted(root.glob("module_*.json"))
    if not module_paths:
        raise ValueError("tailoring fixture bundle contains no module cards")
    modules = [cast(dict[str, Any], _load_json(path)) for path in module_paths]
    payload: dict[str, Any] = {
        **idea,
        "papers": papers,
        "reproduction": reproduction,
        "module_intents": modules,
        "expected_results": expected_results,
        **protocol,
    }
    return TailoringTask.model_validate(payload)
