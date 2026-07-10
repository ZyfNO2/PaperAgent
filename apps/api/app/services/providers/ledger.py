"""Provider Ledger — append-only JSONL audit log.

Re6.1 Provider Core. Records every provider operation (create/update/delete/
discover/probe/switch) as a JSON line. Does NOT store raw API keys — only
provider_id, config_version, event type, and metadata.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _ledger_path() -> str:
    data_dir = os.environ.get("PAPERAGENT_DATA_DIR", "data")
    return os.path.join(data_dir, "provider_ledger.jsonl")


def _write_line(entry: dict) -> None:
    """Append a single JSON line to the ledger."""
    lpath = _ledger_path()
    os.makedirs(os.path.dirname(lpath) or ".", exist_ok=True)
    try:
        with open(lpath, "a", encoding="utf-8", newline="\n") as fh:
            json.dump(entry, fh, ensure_ascii=False)
            fh.write("\n")
    except Exception as exc:
        logger.warning("ledger write failed: %s", exc)


def record_event(
    event: str,
    provider_id: str,
    config_version: str = "",
    actor: str = "user",
    details: dict | None = None,
) -> None:
    """Record a provider event in the ledger.

    Args:
        event: One of "created", "updated", "deleted", "probed",
               "discovered", "switched", "validated".
        provider_id: The provider's unique ID.
        config_version: The provider's config_version at the time.
        actor: "user" or "system".
        details: Additional metadata (error_type, model_id, etc.).
                 Must NOT contain raw API keys.
    """
    entry = {
        "event": event,
        "provider_id": provider_id,
        "config_version": config_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "details": details or {},
    }
    _write_line(entry)


def record_deleted_tombstone(provider_id: str, config_version: str = "") -> None:
    """Record a tombstone entry when a provider profile is deleted.

    The tombstone signals that the profile existed but was intentionally
    removed; this is important for audit trails and to distinguish "never
    existed" from "existed and was deleted".
    """
    record_event(
        event="deleted",
        provider_id=provider_id,
        config_version=config_version,
        actor="user",
        details={"secret_purged": True},
    )


def read_ledger(
    provider_id: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Read recent entries from the ledger, optionally filtered by provider_id."""
    lpath = _ledger_path()
    if not os.path.exists(lpath):
        return []

    lines: list[dict] = []
    try:
        with open(lpath, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if provider_id and entry.get("provider_id") != provider_id:
                    continue
                lines.append(entry)
    except Exception as exc:
        logger.warning("ledger read failed: %s", exc)

    return lines[-limit:]
