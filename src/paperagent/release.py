from __future__ import annotations

import sqlite3
from importlib.resources import files
from pathlib import Path
from typing import Any

_REQUIRED_WEB_ASSETS = (
    "index.html",
    "manifest.webmanifest",
    "service-worker.js",
    "icon.svg",
    "css/tokens.css",
    "css/base.css",
    "css/components.css",
    "css/pages.css",
    "css/intro.css",
    "js/data.js",
    "js/ui.js",
    "js/intro.js",
    "js/views/core.js",
    "js/views/research.js",
    "js/views/design.js",
    "js/views/review.js",
    "js/app.js",
)


def release_readiness(database_path: str | Path) -> dict[str, Any]:
    checks: dict[str, Any] = {}

    try:
        connection = sqlite3.connect(str(database_path), timeout=5.0)
        try:
            row = connection.execute("PRAGMA quick_check").fetchone()
            database_ok = row is not None and row[0] == "ok"
        finally:
            connection.close()
        checks["sqlite"] = {"ok": database_ok}
    except sqlite3.Error as exc:
        checks["sqlite"] = {"ok": False, "error": type(exc).__name__}

    asset_root = Path(str(files("paperagent.web").joinpath("assets")))
    missing = [name for name in _REQUIRED_WEB_ASSETS if not (asset_root / name).is_file()]
    checks["web_assets"] = {
        "ok": not missing,
        "required": len(_REQUIRED_WEB_ASSETS),
        "missing": missing,
    }

    ready = all(bool(value.get("ok")) for value in checks.values())
    return {
        "status": "ready" if ready else "not_ready",
        "release_contract": "v0.5.1",
        "checks": checks,
    }
