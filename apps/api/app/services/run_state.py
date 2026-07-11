"""Run state model + atomic JSON write helper.

Provides:
  - RunState: metadata about a single research run (case_id, status, timestamps)
  - atomic_write_json: write-to-temp-then-rename for crash safety
  - RunLedger: append-only event log (inspired by Draftpaper passport.py)

This is the interface that Day 5's SQLite migration will implement.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class RunState:
    """Metadata for a single research run."""
    case_id: str
    status: str = "pending"  # pending → running → completed | failed | cancelled
    started_at: float = 0.0
    finished_at: float | None = None
    current_node: str | None = None
    error: str | None = None
    source_policy_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RunState:
        return cls(**{k: d.get(k) for k in cls.__dataclass_fields__})


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """Write JSON atomically: write to temp file, then rename.

    Guarantees:
    - Reader never sees a partial file
    - Crash during write leaves previous version intact
    - Windows-safe: retries os.replace on PermissionError
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent),
        suffix=".tmp",
        prefix=path.stem,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        # Windows: os.replace may fail if target is briefly locked; retry
        for _attempt in range(3):
            try:
                os.replace(tmp_path, str(path))
                break
            except PermissionError:
                import time as _time
                _time.sleep(0.05)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


class RunLedger:
    """Append-only event log for a single run.

    Inspired by Draftpaper_loop passport.py's checkpoint_ledger.jsonl.
    Each entry is a JSON line with timestamp, event_type, and payload.
    """

    def __init__(self, ledger_path: Path) -> None:
        self.path = ledger_path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event_type: str, payload: dict[str, Any]) -> None:
        entry = {
            "ts": time.time(),
            "event": event_type,
            "payload": payload,
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with open(self.path, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
