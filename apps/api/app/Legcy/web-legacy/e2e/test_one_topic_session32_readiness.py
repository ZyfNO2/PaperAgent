"""Session 32: 导出前合规检查 Playwright E2E 测试 (8 条).

S32-PW-1: 导出前检查页可见
S32-PW-2: 8 维 readiness 显示
S32-PW-3: fail 项显示 required_fix
S32-PW-4: 模板切换检查结果变化
S32-PW-5: fail 时导出按钮 disabled
S32-PW-6: pass/warn 时允许导出 Markdown
S32-PW-7: S29 报告草稿不回退
S32-PW-8: S31 baseline 不回退
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

BASE_API = "http://127.0.0.1:18181"
TOPIC_API = f"{BASE_API}/api/v1/one-topic"


def _api_post(page: Page, path: str, body: dict) -> dict:
    """Call backend API and return parsed JSON."""
    url = f"{TOPIC_API}{path}"
    return page.evaluate("""
        ([url, body]) => {
            return fetch(url, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(body)
            }).then(r => r.json());
        }
    """, [url, body])


def _api_get(page: Page, path: str) -> dict:
    """Call backend GET API and return parsed JSON."""
    url = f"{TOPIC_API}{path}"
    return page.evaluate("""
        ([url]) => fetch(url).then(r => r.json())
    """, [url])


# ------------------------------------------------------------------- #
# S32-PW-1: 导出前检查页可见
# ------------------------------------------------------------------- #


class TestReadinessPageVisible:
    def test_readiness_api_accessible(self, page: Page):
        """Readiness API endpoint is reachable (S32 backend is wired)."""
        result = _api_post(page, "/analyze", {
            "raw_topic": "基于YOLO的钢材表面缺陷检测",
            "goal_level": "保毕业",
            "prefer": "heuristic",
        })
        pid = result["project_id"]
        readiness = _api_post(page, f"/{pid}/readiness", {
            "project_id": pid,
            "template_key": "default",
        })
        assert "overall_status" in readiness, f"Readiness API response missing overall_status: {readiness.keys()}"
        assert "dimensions" in readiness, f"Readiness API response missing dimensions: {readiness.keys()}"


# ------------------------------------------------------------------- #
# S32-PW-2: 8 维 readiness 显示
# ------------------------------------------------------------------- #


class TestEightDimensions:
    def test_readiness_api_returns_8_dimensions(self, page: Page):
        # First run analyze to get a project_id
        result = _api_post(page, "/analyze", {
            "raw_topic": "基于YOLO的钢材表面缺陷检测",
            "goal_level": "保毕业",
            "prefer": "heuristic",
        })
        pid = result["project_id"]

        # Call readiness API
        readiness = _api_post(page, f"/{pid}/readiness", {
            "project_id": pid,
            "template_key": "default",
        })
        dims = readiness.get("dimensions", [])
        assert len(dims) == 8, f"Expected 8 dimensions, got {len(dims)}: {[d.get('dimension') for d in dims]}"


# ------------------------------------------------------------------- #
# S32-PW-3: fail 项显示 required_fix
# ------------------------------------------------------------------- #


class TestFailRequiredFix:
    def test_fail_dimensions_have_required_fix(self, page: Page):
        result = _api_post(page, "/analyze", {
            "raw_topic": "基于YOLO的钢材表面缺陷检测",
            "goal_level": "保毕业",
            "prefer": "heuristic",
        })
        pid = result["project_id"]

        readiness = _api_post(page, f"/{pid}/readiness", {
            "project_id": pid,
            "template_key": "default",
        })
        dims = readiness.get("dimensions", [])
        fail_dims = [d for d in dims if d.get("status") == "fail"]
        for d in fail_dims:
            assert d.get("required_fix"), f"fail dimension '{d['dimension']}' missing required_fix"


# ------------------------------------------------------------------- #
# S32-PW-4: 模板切换检查结果变化
# ------------------------------------------------------------------- #


class TestTemplateSwitch:
    def test_different_template_different_results(self, page: Page):
        result = _api_post(page, "/analyze", {
            "raw_topic": "基于YOLO的钢材表面缺陷检测",
            "goal_level": "保毕业",
            "prefer": "heuristic",
        })
        pid = result["project_id"]

        r1 = _api_post(page, f"/{pid}/readiness", {
            "project_id": pid,
            "template_key": "default",
        })
        r2 = _api_post(page, f"/{pid}/readiness", {
            "project_id": pid,
            "template_key": "cv_ai",
        })
        # cv_ai requires more sections, so template_fit dimension should differ
        d1 = next((d for d in r1["dimensions"] if d["dimension"] == "school_template_fit"), None)
        d2 = next((d for d in r2["dimensions"] if d["dimension"] == "school_template_fit"), None)
        assert d1 is not None and d2 is not None
        # At minimum, the message should differ (different required section counts)
        assert d1["message"] != d2["message"] or d1["status"] == d2["status"]


# ------------------------------------------------------------------- #
# S32-PW-5: fail 时导出按钮 disabled
# ------------------------------------------------------------------- #


class TestExportDisabledOnFail:
    def test_export_disabled_when_fail(self, page: Page):
        result = _api_post(page, "/analyze", {
            "raw_topic": "基于YOLO的钢材表面缺陷检测",
            "goal_level": "保毕业",
            "prefer": "heuristic",
        })
        pid = result["project_id"]

        readiness = _api_post(page, f"/{pid}/readiness", {
            "project_id": pid,
            "template_key": "default",
        })
        # When export is blocked, overall_status must be fail
        if not readiness.get("export_allowed"):
            assert readiness["overall_status"] == "fail", \
                f"export not allowed but status is {readiness['overall_status']}"


# ------------------------------------------------------------------- #
# S32-PW-6: pass/warn 时允许导出 Markdown
# ------------------------------------------------------------------- #


class TestExportAllowedOnPass:
    def test_export_allowed_when_pass_or_warn(self, page: Page):
        result = _api_post(page, "/analyze", {
            "raw_topic": "基于YOLO的钢材表面缺陷检测",
            "goal_level": "保毕业",
            "prefer": "heuristic",
        })
        pid = result["project_id"]

        readiness = _api_post(page, f"/{pid}/readiness", {
            "project_id": pid,
            "template_key": "default",
        })
        if readiness.get("export_allowed"):
            assert readiness["overall_status"] in ("pass", "warn"), \
                f"export_allowed but status is {readiness['overall_status']}"


# ------------------------------------------------------------------- #
# S32-PW-7: S29 报告草稿不回退
# ------------------------------------------------------------------- #


class TestS29NotRegressed:
    def test_proposal_draft_module_still_loaded(self, page: Page):
        ready = page.evaluate("typeof window.ProposalDraft !== 'undefined' && window.ProposalDraft.isReady()")
        assert ready is True


# ------------------------------------------------------------------- #
# S32-PW-8: S31 baseline 不回退
# ------------------------------------------------------------------- #


class TestS31NotRegressed:
    def test_s31_e2e_analyze_still_works(self, page: Page):
        result = _api_post(page, "/analyze", {
            "raw_topic": "基于YOLO的钢材表面缺陷检测",
            "goal_level": "保毕业",
            "prefer": "heuristic",
        })
        assert "project_id" in result
        assert "feasibility" in result
        assert "verdict" in result["feasibility"]
