"""Canonical baseline method-name registry — Re05 task B (SOP §3).

Loader for `data/canonical_baselines.yaml`. Per the user decision in
session S66v + Re05 SOP §3.1, these entries ONLY seed baseline queries;
they MUST NEVER be injected into the candidate pool.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# ponytail: yaml only if available; fall back to a tiny parser so we don't
# drag PyYAML just for one file the SOP defines. (stdlib-first.)
try:  # pragma: no cover — exercised via PyYAML when present
    import yaml as _yaml  # type: ignore[import-untyped]

    _HAS_YAML = True
except Exception:  # noqa: BLE001
    _yaml = None
    _HAS_YAML = False

_YAML_PATH = Path(__file__).parent / "canonical_baselines.yaml"


def _parse_yaml(text: str) -> dict[str, Any]:
    if _HAS_YAML and _yaml is not None:
        data = _yaml.safe_load(text) or {}
        if isinstance(data, dict):
            return data
    # ponytail: ultra-minimal fallback parser sufficient for this file's
    # `domains: { <name>: { canonical_baselines: [..], keywords: [..] } }`
    # shape. If the file grows beyond this, install PyYAML.
    out: dict[str, Any] = {}
    cur_domain: str | None = None
    cur_field: str | None = None
    list_buf: list[str] = []
    collecting = False
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" "):
            # top-level key
            if collecting and cur_domain and cur_field:
                out.setdefault(cur_domain, {})[cur_field] = list_buf
            collecting = False
            list_buf = []
            cur_domain = None
            cur_field = None
            if ":" in line:
                k, _, _ = line.partition(":")
                k = k.strip()
                if k == "domains":
                    pass  # container; its children handled below
                else:
                    # ignore stray top-level keys
                    pass
            continue
        stripped = line.strip()
        # domain key (2-space indent, ends with ":")
        if line.startswith("  ") and not line.startswith("    ") and stripped.endswith(":"):
            if collecting and cur_domain and cur_field:
                out.setdefault(cur_domain, {})[cur_field] = list_buf
            list_buf = []
            cur_domain = stripped[:-1]
            cur_field = None
            collecting = False
            continue
        # field key (4-space indent, ends with ":")
        if line.startswith("    ") and not line.startswith("      ") and stripped.endswith(":"):
            if collecting and cur_domain and cur_field:
                out.setdefault(cur_domain, {})[cur_field] = list_buf
            cur_field = stripped[:-1]
            collecting = True
            list_buf = []
            continue
        # list item
        if collecting and stripped.startswith("- "):
            list_buf.append(stripped[2:].strip().strip('"').strip("'"))
    if collecting and cur_domain and cur_field:
        out.setdefault(cur_domain, {})[cur_field] = list_buf
    return {"domains": out} if out else {}


def _load_yaml() -> dict[str, Any]:
    try:
        with _YAML_PATH.open("r", encoding="utf-8") as f:
            return _parse_yaml(f.read())
    except Exception:  # noqa: BLE001 — ponytail: never crash callers
        return {}


_DATA_CACHE: dict[str, Any] | None = None


def _get_data() -> dict[str, Any]:
    global _DATA_CACHE
    if _DATA_CACHE is None:
        _DATA_CACHE = _load_yaml()
    return _DATA_CACHE


def load_canonical_baselines(domain: str) -> list[str]:
    """Return canonical baseline method-names for `domain`, or [] if unknown."""
    if not domain:
        return []
    data = _get_data()
    if os.environ.get("PAPERAGENT_RELOAD_CANONICAL"):
        # ponytail: explicit reload hook for tests
        global _DATA_CACHE
        _DATA_CACHE = None
        data = _get_data()
    domains = data.get("domains") or {}
    entry = domains.get(domain) or {}
    names = entry.get("canonical_baselines") or []
    return [str(n) for n in names if n]


def load_keywords(domain: str) -> list[str]:
    """Return canonical keywords for `domain`, or [] if unknown."""
    if not domain:
        return []
    data = _get_data()
    domains = data.get("domains") or {}
    entry = domains.get(domain) or {}
    kws = entry.get("keywords") or []
    return [str(k) for k in kws if k]
