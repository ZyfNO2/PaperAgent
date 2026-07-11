"""Re4.1: RunState + atomic_write_json tests."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from apps.api.app.services.run_state import (
    RunLedger,
    RunState,
    atomic_write_json,
)


class TestAtomicWriteJson:
    def test_atomic_write_creates_file(self, tmp_path: Path) -> None:
        path = tmp_path / "state.json"
        atomic_write_json(path, {"key": "value"})
        assert path.exists()
        assert json.loads(path.read_text())["key"] == "value"

    def test_atomic_write_no_partial_on_crash(self, tmp_path: Path) -> None:
        """Atomic write should not leave partial files."""
        path = tmp_path / "state.json"
        atomic_write_json(path, {"version": 1})
        with pytest.raises(RuntimeError):
            with patch("json.dump", side_effect=RuntimeError("crash")):
                atomic_write_json(path, {"version": 2})
        assert json.loads(path.read_text())["version"] == 1

    def test_atomic_write_creates_parent_dir(self, tmp_path: Path) -> None:
        path = tmp_path / "subdir" / "nested" / "state.json"
        atomic_write_json(path, {"key": "value"})
        assert path.exists()

    def test_atomic_write_overwrites_existing(self, tmp_path: Path) -> None:
        path = tmp_path / "state.json"
        atomic_write_json(path, {"version": 1})
        atomic_write_json(path, {"version": 2})
        assert json.loads(path.read_text())["version"] == 2


class TestRunState:
    def test_default_values(self) -> None:
        rs = RunState(case_id="test123")
        assert rs.case_id == "test123"
        assert rs.status == "pending"
        assert rs.started_at == 0.0
        assert rs.finished_at is None
        assert rs.current_node is None
        assert rs.error is None
        assert rs.source_policy_summary == {}

    def test_to_dict_and_back(self) -> None:
        rs = RunState(
            case_id="abc",
            status="running",
            started_at=123.0,
            current_node="verify",
        )
        d = rs.to_dict()
        assert d["case_id"] == "abc"
        assert d["status"] == "running"
        rs2 = RunState.from_dict(d)
        assert rs2.case_id == "abc"
        assert rs2.status == "running"
        assert rs2.current_node == "verify"

    def test_from_dict_ignores_extra_keys(self) -> None:
        d = {"case_id": "x", "status": "done", "extra_key": "ignored"}
        rs = RunState.from_dict(d)
        assert rs.case_id == "x"
        assert rs.status == "done"


class TestRunLedger:
    def test_append_and_read(self, tmp_path: Path) -> None:
        ledger = RunLedger(tmp_path / "ledger.jsonl")
        ledger.append("node_start", {"node": "intake"})
        ledger.append("node_end", {"node": "intake", "status": "ok"})
        entries = ledger.read_all()
        assert len(entries) == 2
        assert entries[0]["event"] == "node_start"
        assert entries[1]["payload"]["status"] == "ok"

    def test_read_empty_when_no_file(self, tmp_path: Path) -> None:
        ledger = RunLedger(tmp_path / "nonexistent.jsonl")
        assert ledger.read_all() == []

    def test_creates_parent_dir(self, tmp_path: Path) -> None:
        ledger = RunLedger(tmp_path / "subdir" / "ledger.jsonl")
        ledger.append("test", {"x": 1})
        assert (tmp_path / "subdir" / "ledger.jsonl").exists()

    def test_entries_have_timestamp(self, tmp_path: Path) -> None:
        ledger = RunLedger(tmp_path / "ledger.jsonl")
        ledger.append("test", {})
        entries = ledger.read_all()
        assert "ts" in entries[0]
        assert isinstance(entries[0]["ts"], float)
