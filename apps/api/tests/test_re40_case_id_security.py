"""Re4.1: case_id path security tests."""
from __future__ import annotations

import re

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

_CASE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-]{0,63}$")


class TestCaseIdSecurity:
    def test_path_traversal_rejected(self) -> None:
        """../ traversal must be rejected (400 by validator or 404 by router)."""
        for malicious in ["../etc", "..\\windows", "a/b/c", "....//"]:
            resp = client.get(f"/api/v1/research/{malicious}/status")
            assert resp.status_code in (400, 404), f"should reject: {malicious}, got {resp.status_code}"

    def test_special_chars_rejected(self) -> None:
        """Special filesystem chars must be rejected (400 or 404)."""
        for bad in ["test:file", "test<file", "test>file", "test|file", 'test"file',
                    "test*file", "test?file"]:
            resp = client.get(f"/api/v1/research/{bad}/status")
            assert resp.status_code in (400, 404), f"should reject: {bad}, got {resp.status_code}"

    def test_hidden_file_rejected(self) -> None:
        """Hidden file patterns (starting with .) must be rejected."""
        for bad in [".env", ".git", ".ssh"]:
            resp = client.get(f"/api/v1/research/{bad}/status")
            assert resp.status_code == 400, f"should reject: {bad}"

    def test_overlength_rejected(self) -> None:
        """case_id > 64 chars must be rejected."""
        long_id = "a" * 65
        resp = client.get(f"/api/v1/research/{long_id}/status")
        assert resp.status_code == 400

    def test_valid_case_id_accepted(self) -> None:
        """Valid slug pattern should pass validation (404 is ok, 400 is not)."""
        resp = client.get("/api/v1/research/valid_case_id_123/status")
        assert resp.status_code != 400  # 404 ok (no such case)

    def test_hyphen_case_id_accepted(self) -> None:
        """Hyphenated case_id should pass validation."""
        resp = client.get("/api/v1/research/R36-021/status")
        assert resp.status_code != 400

    def test_auto_uuid_when_not_provided(self) -> None:
        """POST without case_id should generate one."""
        resp = client.post("/api/v1/research/", json={"topic": "test"})
        assert resp.status_code == 200
        data = resp.json()
        assert "case_id" in data
        cid = data["case_id"]
        assert _CASE_ID_PATTERN.match(cid), f"generated case_id {cid!r} doesn't match safe pattern"
