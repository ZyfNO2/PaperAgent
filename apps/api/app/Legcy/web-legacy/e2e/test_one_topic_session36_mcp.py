"""Session 36: MCP server Playwright E2E (6 条).

S36-PW-1: GET /api/v1/mcp/manifest 返回 4 个 tool
S36-PW-2: GET /api/v1/mcp/tools 返回 forbidden 列表
S36-PW-3: POST /api/v1/mcp/call 写 file 被拒
S36-PW-4: search_topic_evidence 无 keyword gate 返回 permission_denied
S36-PW-5: check_export_readiness 无 FinalPackage 返回 permission_denied
S36-PW-6: MCP_FunctionCalling_Explainer 文档存在
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from playwright.sync_api import Page

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps" / "api"))

BASE_API = "http://127.0.0.1:18181"
MCP_API = f"{BASE_API}/api/v1/mcp"


def _api_post(page: Page, path: str, body: dict) -> dict:
    return page.evaluate("""
        ([url, body]) => fetch(url, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body)
        }).then(r => r.json())
    """, [f"{MCP_API}{path}", body])


def _api_get(page: Page, path: str) -> dict:
    return page.evaluate("""
        ([url]) => fetch(url).then(r => r.json())
    """, [f"{MCP_API}{path}"])


# ------------------------------------------------------------------- #
# S36-PW-1: manifest 返回 4 tool
# ------------------------------------------------------------------- #


class TestMCPServerManifest:
    def test_manifest_has_4_tools(self, page: Page):
        result = _api_get(page, "/manifest")
        assert result["tool_count"] == 4
        assert "search_topic_evidence" in result["tools"]


# ------------------------------------------------------------------- #
# S36-PW-2: forbidden 列表存在
# ------------------------------------------------------------------- #


class TestMCPForbiddenListed:
    def test_tools_endpoint_returns_forbidden(self, page: Page):
        result = _api_get(page, "/tools")
        assert result["total"] == 4
        assert "write_file" in result["forbidden"]
        assert "delete_project" in result["forbidden"]


# ------------------------------------------------------------------- #
# S36-PW-3: 写操作被拒
# ------------------------------------------------------------------- #


class TestMCPWriteFileRejected:
    def test_write_file_returns_forbidden(self, page: Page):
        result = _api_post(page, "/call", {
            "tool_name": "write_file",
            "arguments": {"project_id": "p1", "path": "/etc/passwd"},
            "actor": "external_agent",
        })
        assert result["success"] is False
        assert result["error"]["code"] == "forbidden_tool"
        # trace_event_id 仍存在
        assert result["trace_event_id"] is not None


# ------------------------------------------------------------------- #
# S36-PW-4: search 无 keyword gate 被拒
# ------------------------------------------------------------------- #


class TestMCPSearchPermissionDenied:
    def test_search_without_keyword_gate_denied(self, page: Page):
        result = _api_post(page, "/call", {
            "tool_name": "search_topic_evidence",
            "arguments": {"project_id": "p_never_existed", "top_k": 5},
            "actor": "external_agent",
        })
        assert result["success"] is False
        assert result["error"]["code"] == "permission_denied"
        assert "keyword_review" in result["error"]["message"]


# ------------------------------------------------------------------- #
# S36-PW-5: check_export_readiness 无 FinalPackage 被拒
# ------------------------------------------------------------------- #


class TestMCPReadinessPermissionDenied:
    def test_check_export_without_final_package_denied(self, page: Page):
        result = _api_post(page, "/call", {
            "tool_name": "check_export_readiness",
            "arguments": {"project_id": "p_no_pkg"},
            "actor": "external_agent",
        })
        assert result["success"] is False
        assert result["error"]["code"] == "permission_denied"


# ------------------------------------------------------------------- #
# S36-PW-6: 文档存在
# ------------------------------------------------------------------- #


class TestMCPExplainerDoc:
    def test_explainer_doc_exists(self):
        doc = ROOT / "docs" / "interview" / "MCP_FunctionCalling_Explainer.md"
        assert doc.exists(), f"MCP_FunctionCalling_Explainer.md missing at {doc}"
        content = doc.read_text(encoding="utf-8")
        assert "MCP" in content or "mcp" in content
        assert "Function Calling" in content or "function calling" in content.lower()
        assert "tool" in content.lower()