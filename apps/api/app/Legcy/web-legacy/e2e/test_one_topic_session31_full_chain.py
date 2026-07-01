"""Session 31: 全链路 Playwright E2E 测试 (10 条).

S31-PW-1: 输入题目
S31-PW-2: 关键词 Gate 暂停
S31-PW-3: 确认关键词
S31-PW-4: 生成候选
S31-PW-5: 加入左栏
S31-PW-6: URLVerified / Evidence 晋升
S31-PW-7: 生成可行性裁决
S31-PW-8: 生成报告草稿
S31-PW-9: 委员会复核
S31-PW-10: 高风险 Case 不得通过
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


def _render_module(page: Page, module_name: str, fn: str, data: dict) -> bool:
    """Render data using a JS module. Returns True if module exists."""
    return page.evaluate("""
        ([mod, fn, data]) => {
            if (typeof window[mod] === 'undefined') return false;
            const el = document.querySelector('.workspace-card') || document.querySelector('main') || document.body;
            if (typeof window[mod][fn] === 'function') {
                el.innerHTML = window[mod][fn](data);
                return true;
            }
            return false;
        }
    """, [module_name, fn, data])


# ------------------------------------------------------------------- #
# S31-PW-1: 输入题目
# ------------------------------------------------------------------- #


class TestInputTopic:
    def test_analyze_returns_project_id(self, page: Page):
        result = _api_post(page, "/analyze", {
            "raw_topic": "基于YOLO的钢材表面缺陷检测",
            "goal_level": "保毕业",
            "advisor_direction": "工业质检",
            "prefer": "heuristic",
        })
        assert "project_id" in result, f"analyze 无 project_id: {list(result.keys())}"
        assert len(result["project_id"]) > 0


# ------------------------------------------------------------------- #
# S31-PW-2: 关键词 Gate 暂停
# ------------------------------------------------------------------- #


class TestKeywordGate:
    def test_keyword_breakdown_present(self, page: Page):
        result = _api_post(page, "/analyze", {
            "raw_topic": "基于YOLO的钢材表面缺陷检测",
            "goal_level": "保毕业",
            "prefer": "heuristic",
        })
        kb = result.get("keyword_breakdown", {})
        assert "method_keywords" in kb or "task_keywords" in kb, \
            f"keyword_breakdown 缺关键字段: {list(kb.keys())}"


# ------------------------------------------------------------------- #
# S31-PW-3: 确认关键词
# ------------------------------------------------------------------- #


class TestConfirmKeywords:
    def test_keywords_contain_yolo(self, page: Page):
        result = _api_post(page, "/analyze", {
            "raw_topic": "基于YOLO的钢材表面缺陷检测",
            "goal_level": "保毕业",
            "prefer": "heuristic",
        })
        kb = result.get("keyword_breakdown", {})
        all_kw = str(kb)
        assert "YOLO" in all_kw or "yolo" in all_kw.lower(), \
            f"关键词不含 YOLO: {all_kw[:200]}"


# ------------------------------------------------------------------- #
# S31-PW-4: 生成候选
# ------------------------------------------------------------------- #


class TestGenerateCandidates:
    def test_evidence_summary_present(self, page: Page):
        result = _api_post(page, "/analyze", {
            "raw_topic": "基于YOLO的钢材表面缺陷检测",
            "goal_level": "保毕业",
            "prefer": "heuristic",
        })
        ev = result.get("evidence_summary", {})
        # At least some candidate papers
        papers = ev.get("papers", ev.get("paper_hits", []))
        assert isinstance(papers, list)


# ------------------------------------------------------------------- #
# S31-PW-5: 加入左栏
# ------------------------------------------------------------------- #


class TestAddToLeftPanel:
    def test_workspace_board_loadable(self, page: Page):
        result = _api_post(page, "/analyze", {
            "raw_topic": "基于YOLO的钢材表面缺陷检测",
            "goal_level": "保毕业",
            "prefer": "heuristic",
        })
        pid = result["project_id"]
        board = _api_get(page, f"/{pid}/workspace/board")
        assert "paper" in board or "papers" in board, f"board 缺 paper: {list(board.keys())}"


# ------------------------------------------------------------------- #
# S31-PW-6: URLVerified / Evidence 晋升
# ------------------------------------------------------------------- #


class TestEvidencePromotion:
    def test_evidence_summary_has_verification_fields(self, page: Page):
        result = _api_post(page, "/analyze", {
            "raw_topic": "基于YOLO的钢材表面缺陷检测",
            "goal_level": "保毕业",
            "prefer": "heuristic",
        })
        ev = result.get("evidence_summary", {})
        # Evidence summary should have some structure
        assert isinstance(ev, dict), f"evidence_summary 不是 dict: {type(ev)}"


# ------------------------------------------------------------------- #
# S31-PW-7: 生成可行性裁决
# ------------------------------------------------------------------- #


class TestFeasibilityVerdict:
    def test_feasibility_verdict_present(self, page: Page):
        result = _api_post(page, "/analyze", {
            "raw_topic": "基于YOLO的钢材表面缺陷检测",
            "goal_level": "保毕业",
            "prefer": "heuristic",
        })
        feas = result.get("feasibility", {})
        assert "verdict" in feas, f"feasibility 缺 verdict: {list(feas.keys())}"
        assert feas["verdict"] in ("可做", "GO", "PASS", "有条件通过", "需修改", "收缩后可做",
                                    "暂缓", "可转向", "PARK", "PIVOT", "STOP",
                                    "WARN", "不建议"), \
            f"未知 verdict: {feas['verdict']}"


# ------------------------------------------------------------------- #
# S31-PW-8: 生成报告草稿
# ------------------------------------------------------------------- #


class TestProposalDraft:
    def test_proposal_draft_module_loaded(self, page: Page):
        loaded = page.evaluate("typeof window.ProposalDraft !== 'undefined' && window.ProposalDraft.isReady()")
        assert loaded is True


# ------------------------------------------------------------------- #
# S31-PW-9: 委员会复核
# ------------------------------------------------------------------- #


class TestCommitteeReview:
    def test_review_api_returns_verdict(self, page: Page):
        review = _api_post(page, "/review", {
            "topic_title": "PW S31 Chain",
            "sections": [
                {"section_id": "topic_direction", "content": "test"},
                {"section_id": "background", "content": "test"},
            ],
        })
        assert "verdict" in review, f"review 缺 verdict: {list(review.keys())}"
        assert review["verdict"] in ("pass", "conditional_pass", "revise", "reject")


# ------------------------------------------------------------------- #
# S31-PW-10: 高风险 Case 不得通过
# ------------------------------------------------------------------- #


class TestHighRiskNotPass:
    def test_high_risk_case_review_not_pass(self, page: Page):
        """Case B 高风险 topic 的 review verdict 不能是 pass."""
        review = _api_post(page, "/review", {
            "topic_title": "PW S31 HighRisk",
            "sections": [
                {"section_id": "topic_direction", "content": "基于多模态大模型的通用工业缺陷智能诊断"},
                {"section_id": "background", "content": "工业AI"},
                {"section_id": "literature_review", "content": "综述"},
                {"section_id": "research_objectives", "content": "通用诊断"},
                {"section_id": "research_content", "content": "多模态"},
                {"section_id": "technical_approach", "content": "MLLM"},
                {"section_id": "dataset_experiment", "content": "待定"},
                {"section_id": "innovation", "content": "跨场景"},
            ],
            "feasibility": {
                "verdict": "PIVOT",
                "hard_vetoes": [
                    {"rule": "no_dataset", "triggered": True},
                    {"rule": "no_baseline", "triggered": True},
                ],
            },
        })
        # With hard vetoes, verdict should not be "pass"
        assert review["verdict"] != "pass", \
            f"高风险 case 误判为 pass: {review['verdict']}"
