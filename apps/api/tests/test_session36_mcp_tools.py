"""Session 36: MCP tools + permission boundary tests (8 个).

S36-1: manifest 可加载
S36-2: 禁止 tool (write_file) 被拒
S36-3: 未在 manifest 的 tool 被拒
S36-4: search_topic_evidence 无 keyword gate 被拒
S36-5: check_export_readiness 无 FinalPackage 被拒
S36-6: 工具调用写 Trace
S36-7: trace 脱敏绝对路径
S36-8: S23 skill registry 默认禁列表不回退
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.mcp import permissions, server as mcp_server
from app.mcp.tools import FORBIDDEN_TOOLS, get_tool, get_tool_manifest, list_tool_names
from app.schemas_mcp import MCPToolCallRequest


# ---------------------------------------------------------------------------
# S36-1: manifest 可加载
# ---------------------------------------------------------------------------


class TestManifestLoadable:
    def test_manifest_has_4_tools(self):
        manifest = mcp_server.get_manifest()
        assert manifest.tool_count == 4
        assert "search_topic_evidence" in manifest.tools
        assert "get_candidate_resources" in manifest.tools
        assert "get_project_trace" in manifest.tools
        assert "check_export_readiness" in manifest.tools

    def test_tools_response_has_forbidden(self):
        resp = mcp_server.list_tools_response()
        assert resp.total == 4
        assert "write_file" in resp.forbidden
        assert "delete_project" in resp.forbidden

    def test_get_tool_returns_metadata(self):
        t = get_tool("search_topic_evidence")
        assert t is not None
        assert t.category == "search"
        assert t.permission.requires_keyword_gate is True


# ---------------------------------------------------------------------------
# S36-2: 禁止 tool 被拒
# ---------------------------------------------------------------------------


class TestForbiddenToolRejected:
    def test_write_file_is_forbidden(self):
        allowed, reason = permissions.check_tool_allowed("write_file")
        assert allowed is False
        assert "forbidden" in reason.lower()

    def test_delete_project_is_forbidden(self):
        allowed, _ = permissions.check_tool_allowed("delete_project")
        assert allowed is False

    def test_promote_candidate_is_forbidden(self):
        allowed, _ = permissions.check_tool_allowed("promote_candidate_to_evidence")
        assert allowed is False

    def test_forbidden_tools_constant_matches_sop(self):
        # SOP §2 列了 6 个 (写操作/破坏性)
        assert "write_file" in FORBIDDEN_TOOLS
        assert "delete_project" in FORBIDDEN_TOOLS
        assert "promote_candidate_to_evidence" in FORBIDDEN_TOOLS
        assert "generate_proposal_draft" in FORBIDDEN_TOOLS


# ---------------------------------------------------------------------------
# S36-3: 未在 manifest 的 tool 被拒
# ---------------------------------------------------------------------------


class TestUnknownToolRejected:
    def test_unknown_tool_rejected(self):
        allowed, reason = permissions.check_tool_allowed("some_random_tool")
        assert allowed is False
        assert "not in MCP tool manifest" in reason

    def test_call_tool_returns_forbidden_error(self):
        req = MCPToolCallRequest(tool_name="write_file", arguments={"project_id": "p1"})
        resp = mcp_server.call_tool(req)
        assert resp.success is False
        assert resp.error.code == "forbidden_tool"


# ---------------------------------------------------------------------------
# S36-4: search_topic_evidence 无 keyword gate 被拒
# ---------------------------------------------------------------------------


class TestKeywordGateEnforced:
    def test_search_requires_keyword_gate(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TOPICPILOT_RUNTIME_ROOT", str(tmp_path / ".runtime"))
        # 没跑过 analyze, 没有 snapshot, 应被拒
        ok, reason = permissions.check_permission("search_topic_evidence", "p_nonexistent")
        assert ok is False
        assert "keyword_review" in reason

    def test_check_readiness_requires_final_package(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TOPICPILOT_RUNTIME_ROOT", str(tmp_path / ".runtime"))
        ok, reason = permissions.check_permission("check_export_readiness", "p_no_pkg")
        assert ok is False
        assert "FinalPackage" in reason

    def test_get_project_trace_no_gate_required(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TOPICPILOT_RUNTIME_ROOT", str(tmp_path / ".runtime"))
        ok, _ = permissions.check_permission("get_project_trace", "p_any")
        assert ok is True


# ---------------------------------------------------------------------------
# S36-5: check_export_readiness 无 FinalPackage 被拒
# ---------------------------------------------------------------------------


class TestReadinessCallReturnsError:
    def test_call_check_export_no_package(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TOPICPILOT_RUNTIME_ROOT", str(tmp_path / ".runtime"))
        req = MCPToolCallRequest(
            tool_name="check_export_readiness", arguments={"project_id": "p_no_pkg"}
        )
        resp = mcp_server.call_tool(req)
        assert resp.success is False
        assert resp.error.code == "permission_denied"


# ---------------------------------------------------------------------------
# S36-6: 工具调用写 Trace
# ---------------------------------------------------------------------------


class TestMCPCallsWriteTrace:
    def test_successful_call_writes_trace(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PAPERAGENT_TRACE_DIR", str(tmp_path / "traces"))
        from app.services.trace_store import reset_traces, get_trace

        reset_traces()
        req = MCPToolCallRequest(
            tool_name="get_candidate_resources",
            arguments={"project_id": "p_trace_test", "source_type": "all"},
        )
        resp = mcp_server.call_tool(req)
        # 不管 success/false, 都应该有 trace_event_id
        assert resp.trace_event_id is not None
        # 实际 trace 应被写入
        trace = get_trace("p_trace_test")
        actions = [e.action for e in trace.events]
        assert "mcp_tool_call" in actions

    def test_forbidden_call_writes_trace(self, tmp_path, monkeypatch):
        monkeypatch.setenv("PAPERAGENT_TRACE_DIR", str(tmp_path / "traces"))
        from app.services.trace_store import reset_traces, get_trace

        reset_traces()
        req = MCPToolCallRequest(tool_name="write_file", arguments={"project_id": "p_forbid"})
        resp = mcp_server.call_tool(req)
        assert resp.trace_event_id is not None
        trace = get_trace("p_forbid")
        actions = [e.action for e in trace.events]
        assert "mcp_tool_call" in actions


# ---------------------------------------------------------------------------
# S36-7: trace 脱敏
# ---------------------------------------------------------------------------


class TestTraceSanitization:
    def test_absolute_path_sanitized(self):
        data = {
            "msg": "Reading C:\\Users\\ZYF\\secret\\file.txt",
            "nested": {"path": "/home/user/.ssh/id_rsa"},
        }
        out = permissions.sanitize_trace_data(data)
        assert "<redacted-path>" in out["msg"]
        assert "<redacted-path>" in out["nested"]["path"]
        # 不要保留原始绝对路径
        assert "secret" not in out["msg"]
        assert ".ssh" not in out["nested"]["path"]

    def test_list_of_strings_sanitized(self):
        out = permissions.sanitize_trace_data(["D:\\data", "safe text"])
        assert out[0] == "<redacted-path>"
        assert out[1] == "safe text"


# ---------------------------------------------------------------------------
# S36-8: S23 skill registry 默认禁列表不回退
# ---------------------------------------------------------------------------


class TestSkillRegistryCompat:
    def test_default_forbidden_unchanged(self):
        from app.services.skill_registry import get_default_forbidden

        forbidden = get_default_forbidden()
        assert "shell_exec" in forbidden
        assert "write_outside_workspace" in forbidden
        # S36 的新禁列表与 S23 不冲突 (MCP 是更高一层)
        assert "write_file" in FORBIDDEN_TOOLS

    def test_list_tool_names_returns_4(self):
        names = list_tool_names()
        assert len(names) == 4
        # 顺序无关紧要, 但都应该是已知的
        for n in names:
            assert get_tool(n) is not None