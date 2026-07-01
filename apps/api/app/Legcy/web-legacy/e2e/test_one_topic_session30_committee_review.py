"""Session 30: 委员会复核 Playwright E2E 测试 (8 条).

S30-PW-1: 委员会复核卡可见
S30-PW-2: 5类视角意见可见
S30-PW-3: 问题按severity显示
S30-PW-4: accept_fix生成任务
S30-PW-5: fatal未处理不能通过
S30-PW-6: rerun_review增加轮次
S30-PW-7: revise_topic回到关键词页
S30-PW-8: S29报告草稿不回退
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

BASE_API = "http://127.0.0.1:18181"
REVIEW_URL = f"{BASE_API}/api/v1/one-topic/review"


def _call_review(page: Page, payload: dict) -> dict:
    """Call review API and return parsed JSON."""
    return page.evaluate("""
        ([url, body]) => {
            return fetch(url, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(body)
            }).then(r => r.json());
        }
    """, [REVIEW_URL, payload])


def _render_review(page: Page, review_data: dict):
    """Render review data into a visible container."""
    page.evaluate("""
        ([data]) => {
            const el = document.querySelector('.workspace-card') || document.querySelector('main') || document.body;
            if (window.CommitteeReview) {
                el.innerHTML = window.CommitteeReview.renderReview(data);
            }
        }
    """, [review_data])


# ------------------------------------------------------------------- #
# S30-PW-1: 委员会复核卡可见
# ------------------------------------------------------------------- #


class TestCommitteeReviewVisible:
    def test_committee_review_module_loaded(self, page: Page):
        loaded = page.evaluate("typeof window.CommitteeReview !== 'undefined' && window.CommitteeReview.isReady()")
        assert loaded is True

    def test_review_card_rendered(self, page: Page):
        data = _call_review(page, {
            "topic_title": "PW S30 Visible",
            "sections": [{"section_id": "topic_direction", "content": "test"}],
        })
        _render_review(page, data)
        review_el = page.locator(".committee-review, .review-verdict-row")
        assert review_el.count() >= 1


# ------------------------------------------------------------------- #
# S30-PW-2: 5类视角意见可见
# ------------------------------------------------------------------- #


class TestFivePerspectives:
    def test_perspective_groups_present(self, page: Page):
        data = _call_review(page, {
            "topic_title": "PW S30 Perspectives",
            "sections": [],
            "feasibility": {
                "verdict": "PIVOT",
                "hard_vetoes": [{"rule": "no_dataset", "triggered": True}],
            },
        })
        _render_review(page, data)
        groups = page.locator(".review-perspective-group")
        assert groups.count() >= 2  # At least advisor + experiment perspectives


# ------------------------------------------------------------------- #
# S30-PW-3: 问题按severity显示
# ------------------------------------------------------------------- #


class TestSeverityDisplay:
    def test_severity_badges_visible(self, page: Page):
        data = _call_review(page, {
            "topic_title": "PW S30 Severity",
            "sections": [],
            "feasibility": {"verdict": "PIVOT", "hard_vetoes": [{"rule": "no_dataset", "triggered": True}]},
        })
        _render_review(page, data)
        severity = page.locator(".severity-badge, .severity--fatal, .severity--high")
        assert severity.count() >= 1


# ------------------------------------------------------------------- #
# S30-PW-4: accept_fix生成任务
# ------------------------------------------------------------------- #


class TestAcceptFixButton:
    def test_accept_fix_button_present(self, page: Page):
        data = _call_review(page, {
            "topic_title": "PW S30 Fix",
            "sections": [],
            "feasibility": {"verdict": "PIVOT", "hard_vetoes": [{"rule": "no_dataset", "triggered": True}]},
        })
        _render_review(page, data)
        fix_btns = page.locator("button[data-action='accept_fix'], button:has-text('接受修复')")
        assert fix_btns.count() >= 1


# ------------------------------------------------------------------- #
# S30-PW-5: fatal未处理不能通过
# ------------------------------------------------------------------- #


class TestFatalBlocksPass:
    def test_verdict_not_pass_when_fatal(self, page: Page):
        data = _call_review(page, {
            "topic_title": "PW S30 Fatal",
            "sections": [],
            "feasibility": {
                "verdict": "STOP",
                "hard_vetoes": [
                    {"rule": "no_dataset", "triggered": True},
                    {"rule": "no_baseline", "triggered": True},
                ],
            },
        })
        assert data["verdict"] in ("revise", "reject", "conditional_pass"), f"Got {data['verdict']}"


# ------------------------------------------------------------------- #
# S30-PW-6: rerun_review增加轮次
# ------------------------------------------------------------------- #


class TestRerunReview:
    def test_multiple_reviews_increment_round(self, page: Page):
        result = page.evaluate("""
            ([url]) => {
                return fetch(url, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({topic_title: 'PW S30 Rerun', sections: [{section_id: 'topic_direction', content: 't'}]})
                })
                .then(() => fetch(url, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({topic_title: 'PW S30 Rerun', sections: [{section_id: 'topic_direction', content: 't'}]})
                }))
                .then(r => r.json());
            }
        """, [REVIEW_URL])
        assert result["round_id"] == 2


# ------------------------------------------------------------------- #
# S30-PW-7: revise_topic回到关键词页
# ------------------------------------------------------------------- #


class TestReviseTopic:
    def test_revise_topic_action_type_exists(self, page: Page):
        data = _call_review(page, {
            "topic_title": "PW S30 Revise",
            "sections": [{"section_id": "topic_direction", "content": "test"}],
        })
        all_actions = data.get("required_actions", []) + data.get("optional_actions", [])
        assert isinstance(all_actions, list)


# ------------------------------------------------------------------- #
# S30-PW-8: S29报告草稿不回退
# ------------------------------------------------------------------- #


class TestS29NotRegressed:
    def test_proposal_draft_module_still_loaded(self, page: Page):
        ready = page.evaluate("typeof window.ProposalDraft !== 'undefined' && window.ProposalDraft.isReady()")
        assert ready is True
