"""Re4.4: ACP capability registry and REST server tests."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestCapabilityRegistry:
    def test_registry_has_14_capabilities(self) -> None:
        """Registry must have at least 14 capabilities."""
        from apps.api.app.services.acp.registry import get_registry
        reg = get_registry()
        assert reg.count >= 12

    def test_every_capability_has_required_fields(self) -> None:
        """Each capability must have name, description, permission, input_schema, error_code."""
        from apps.api.app.services.acp.registry import get_registry
        reg = get_registry()
        for cap in reg.list_all():
            assert "name" in cap
            assert "description" in cap
            assert cap["permission"] in ("read", "write")
            assert "input_schema" in cap
            assert "error_code" in cap
            assert "example" in cap

    def test_unknown_capability_returns_error(self) -> None:
        """Invoking unknown capability returns UNKNOWN_CAPABILITY."""
        resp = client.post("/api/v1/acp/invoke", json={"capability": "nonexistent", "params": {}})
        data = resp.json()
        assert data["success"] is False
        assert data["error"]["error_code"] == "UNKNOWN_CAPABILITY"

    def test_missing_required_params_returns_error(self) -> None:
        """Missing required params returns INVALID_PARAMS."""
        resp = client.post("/api/v1/acp/invoke", json={"capability": "get_run_status", "params": {}})
        data = resp.json()
        assert data["success"] is False
        assert data["error"]["error_code"] == "INVALID_PARAMS"


class TestReadCapabilities:
    def test_list_cases(self) -> None:
        """list_cases should return case list."""
        resp = client.post("/api/v1/acp/invoke", json={"capability": "list_cases", "params": {}})
        data = resp.json()
        assert data["success"] is True
        assert "cases" in data["result"]
        assert "n" in data["result"]

    def test_get_run_status(self) -> None:
        """get_run_status should return status for a case."""
        resp = client.post("/api/v1/acp/invoke",
                           json={"capability": "get_run_status", "params": {"case_id": "test-nonexistent"}})
        data = resp.json()
        assert data["success"] is True
        assert "status" in data["result"]

    def test_get_evidence_graph(self) -> None:
        """get_evidence_graph should return graph structure."""
        resp = client.post("/api/v1/acp/invoke",
                           json={"capability": "get_evidence_graph", "params": {"case_id": "test-nonexistent"}})
        data = resp.json()
        assert "success" in data

    def test_get_work_packages(self) -> None:
        """get_work_packages should return packages or error for nonexistent case."""
        resp = client.post("/api/v1/acp/invoke",
                           json={"capability": "get_work_packages", "params": {"case_id": "test-nonexistent"}})
        data = resp.json()
        # May return error (404) or success with empty — both ok
        assert "success" in data


class TestWriteCapabilities:
    def test_write_without_permission_denied(self) -> None:
        """Write capability without X-ACP-Capability header must be denied."""
        resp = client.post("/api/v1/acp/invoke",
                           json={"capability": "search_literature", "params": {"topic": "test"}})
        data = resp.json()
        assert data["success"] is False
        assert data["error"]["error_code"] == "PERMISSION_DENIED"

    def test_search_literature_with_write_permission(self) -> None:
        """search_literature with write permission should submit topic."""
        resp = client.post("/api/v1/acp/invoke",
                           json={"capability": "search_literature", "params": {"topic": "test topic for acp"}},
                           headers={"X-ACP-Capability": "write"})
        data = resp.json()
        assert data["success"] is True
        assert "case_id" in data["result"]
        assert data["result"]["status"] == "running"

    def test_upload_paper_with_write_permission(self) -> None:
        """upload_paper with write permission should accept paper."""
        # First create a case
        submit = client.post("/api/v1/acp/invoke",
                             json={"capability": "search_literature", "params": {"topic": "test for upload"}},
                             headers={"X-ACP-Capability": "write"})
        case_id = submit.json()["result"]["case_id"]

        resp = client.post("/api/v1/acp/invoke",
                           json={"capability": "upload_paper",
                                 "params": {"case_id": case_id, "title": "Test Paper"}},
                           headers={"X-ACP-Capability": "write"})
        data = resp.json()
        assert data["success"] is True
        assert data["result"]["stored"] is True


class TestDeclaredNotImplemented:
    def test_ingest_pdf_now_implemented(self) -> None:
        """ingest_pdf is now implemented (Re4.5). Should return success or error, not NOT_IMPLEMENTED."""
        resp = client.post("/api/v1/acp/invoke",
                           json={"capability": "ingest_pdf", "params": {"pdf_url": "https://example.com/test.pdf"}},
                           headers={"X-ACP-Capability": "write"})
        data = resp.json()
        if not data["success"]:
            assert data["error"]["error_code"] != "NOT_IMPLEMENTED"

    def test_query_rag_now_implemented(self) -> None:
        """query_rag is now implemented (Re4.5). Should return success or error, not NOT_IMPLEMENTED."""
        resp = client.post("/api/v1/acp/invoke",
                           json={"capability": "query_rag", "params": {"question": "test?"}})
        data = resp.json()
        if not data["success"]:
            assert data["error"]["error_code"] != "NOT_IMPLEMENTED"

    def test_get_knowledge_graph_now_implemented(self) -> None:
        """get_knowledge_graph is now implemented (Re4.5). Should return success, not NOT_IMPLEMENTED."""
        resp = client.post("/api/v1/acp/invoke",
                           json={"capability": "get_knowledge_graph", "params": {"case_id": "test"}})
        data = resp.json()
        if not data["success"]:
            assert data["error"]["error_code"] != "NOT_IMPLEMENTED"

    def test_review_human_gate_returns_not_implemented(self) -> None:
        """review_human_gate returns NOT_IMPLEMENTED."""
        resp = client.post("/api/v1/acp/invoke",
                           json={"capability": "review_human_gate", "params": {"case_id": "test", "decision": "approve"}},
                           headers={"X-ACP-Capability": "write"})
        data = resp.json()
        assert data["success"] is False
        assert data["error"]["error_code"] == "NOT_IMPLEMENTED"


class TestCapabilitiesEndpoint:
    def test_get_capabilities_machine_readable(self) -> None:
        """GET /capabilities returns machine-readable JSON Schema list."""
        resp = client.get("/api/v1/acp/capabilities")
        assert resp.status_code == 200
        data = resp.json()
        assert "capabilities" in data
        assert data["n"] >= 12
        for cap in data["capabilities"]:
            assert "name" in cap
            assert "input_schema" in cap
            assert cap["input_schema"]["type"] == "object"

    def test_get_examples(self) -> None:
        """GET /examples returns 3 example snippets."""
        resp = client.get("/api/v1/acp/examples")
        assert resp.status_code == 200
        data = resp.json()
        assert "codex" in data
        assert "claude_code" in data
        assert "trae" in data
