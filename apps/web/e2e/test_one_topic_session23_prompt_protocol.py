"""Session 23: Prompt Protocol & Tool Boundary e2e tests.

覆盖 SOP S23-PW-1~8:
1. S23-PW-1: PromptProtocol 在 window 上可用且含 STEP_CONTRACTS
2. S23-PW-2: validateLLMOutput 通过正常 KeywordReviewCard 数据
3. S23-PW-3: validateLLMOutput 拒绝含 <script> 的输出（安全降级）
4. S23-PW-4: validateLLMOutput 拒绝含 eval() 的输出（安全降级）
5. S23-PW-5: isToolAllowed 在 keyword_review 未确认时拦截 search_papers
6. S23-PW-6: isToolAllowed 在 keyword_review 确认后放行 search_papers
7. S23-PW-7: isToolAllowed 永远拒绝 exec_code
8. S23-PW-8: S21/S22 主流程不回退
"""

from __future__ import annotations

import sys
import re
from pathlib import Path

import pytest
from playwright.sync_api import expect

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps" / "api"))


# ---------- helpers ---------- #


def _goto_step_deck(page):
    page.click("button.tab[data-tab='step-deck']")
    page.wait_for_selector("#page-step-deck:not([hidden])", timeout=15000)
    page.wait_for_function("window.StepDeckUI && window.StepDeckUI.isReady()", timeout=10000)


def _start_mock_and_wait_keyword(page):
    page.click("#btn-sd-start-stream")
    page.wait_for_function(
        """() => {
            const rs = window.StepDeckUI && window.StepDeckUI.ui.runState;
            if (!rs) return false;
            const step = rs.steps['keyword_review'];
            return step && step.status === 'awaiting_review';
        }""",
        timeout=15000,
    )
    page.wait_for_function(
        "window.StepDeckUI && window.StepDeckUI.ui.runState.isStreaming === false",
        timeout=10000,
    )


# ---------- S23-PW-1: PromptProtocol available with contracts ---------- #


def test_pw_01_prompt_protocol_available(page):
    """S23-PW-1: PromptProtocol 在 window 上可用且 STEP_CONTRACTS 含 9 步."""
    _goto_step_deck(page)
    result = page.evaluate("""() => {
        const pp = window.PromptProtocol;
        if (!pp) return { ok: false, reason: 'not loaded' };
        const keys = Object.keys(pp.STEP_CONTRACTS);
        return { ok: true, stepCount: keys.length, steps: keys };
    }""")
    assert result["ok"], f"PromptProtocol not loaded: {result}"
    assert result["stepCount"] == 9, f"Expected 9 step contracts, got {result['stepCount']}"


# ---------- S23-PW-2: validateLLMOutput passes good KeywordReviewCard data ---------- #


def test_pw_02_validate_good_output(page):
    """S23-PW-2: validateLLMOutput 对正常 keyword_review 数据返回 ok."""
    _goto_step_deck(page)
    result = page.evaluate("""() => {
        const pp = window.PromptProtocol;
        const output = {
            keywords: [
                { kind: "method", text: "YOLO" },
                { kind: "task", text: "目标检测" },
            ],
        };
        return pp.validateLLMOutput('keyword_review', output);
    }""")
    assert result["ok"] is True, f"Expected ok, got {result}"
    assert result.get("blocked") is not True


# ---------- S23-PW-3: validateLLMOutput rejects <script> payload ---------- #


def test_pw_03_rejects_script_tag(page):
    """S23-PW-3: validateLLMOutput 拒绝含 <script> 的输出."""
    _goto_step_deck(page)
    result = page.evaluate("""() => {
        const pp = window.PromptProtocol;
        const output = {
            keywords: [{ kind: "method", text: "YOLO" }],
            injected: '<script>alert(1)</script>',
        };
        return pp.validateLLMOutput('keyword_review', output);
    }""")
    assert result["ok"] is False
    assert result.get("securityViolation") is True


# ---------- S23-PW-4: validateLLMOutput rejects eval() payload ---------- #


def test_pw_04_rejects_eval(page):
    """S23-PW-4: validateLLMOutput 拒绝含 eval() 的输出."""
    _goto_step_deck(page)
    result = page.evaluate("""() => {
        const pp = window.PromptProtocol;
        const output = {
            keywords: [{ kind: "method", text: "eval(evil)" }],
        };
        return pp.validateLLMOutput('keyword_review', output);
    }""")
    assert result["ok"] is False
    assert result.get("securityViolation") is True


# ---------- S23-PW-5: search_papers blocked before keyword_review approve ---------- #


def test_pw_05_tool_blocked_before_approve(page):
    """S23-PW-5: keyword_review 未确认时 search_papers 被拦截."""
    _goto_step_deck(page)
    result = page.evaluate("""() => {
        const pp = window.PromptProtocol;
        const rs = window.StepDeck.createRunState();
        return pp.isToolAllowed('search_papers', rs);
    }""")
    assert result["allowed"] is False
    assert "keyword_review" in result.get("reason", "") or "keyword_review" in result.get("blockedBy", "")


# ---------- S23-PW-6: search_papers allowed after keyword_review approve ---------- #


def test_pw_06_tool_allowed_after_approve(page):
    """S23-PW-6: keyword_review 确认后 search_papers 放行."""
    _goto_step_deck(page)
    result = page.evaluate("""() => {
        const pp = window.PromptProtocol;
        const rs = window.StepDeck.createRunState();
        rs.hasApprovedGate2 = true;
        return pp.isToolAllowed('search_papers', rs);
    }""")
    assert result["allowed"] is True


# ---------- S23-PW-7: exec_code always forbidden ---------- #


def test_pw_07_exec_code_forbidden(page):
    """S23-PW-7: isToolAllowed 永远拒绝 exec_code."""
    _goto_step_deck(page)
    result = page.evaluate("""() => {
        const pp = window.PromptProtocol;
        const rs = window.StepDeck.createRunState();
        rs.hasApprovedGate2 = true;
        return pp.isToolAllowed('exec_code', rs);
    }""")
    assert result["allowed"] is False
    assert "forbidden" in result.get("reason", "").lower()


# ---------- S23-PW-8: S21/S22 main flow no regression ---------- #


def test_pw_08_s21_s22_no_regression(page):
    """S23-PW-8: S21/S22 主流程不回退 — rail 9 步、mock 流暂停、通过后推进."""
    _goto_step_deck(page)

    # 1. rail 9 步
    rail_items = page.locator("#step-deck-rail .step-rail__item")
    assert rail_items.count() == 9, f"Expected 9 rail items, got {rail_items.count()}"

    # 2. ComponentRegistry 可用
    cr_ok = page.evaluate("!!window.ComponentRegistry && window.ComponentRegistry.has('KeywordReviewCard')")
    assert cr_ok is True

    # 3. mock 流启动后在 keyword_review 暂停
    _start_mock_and_wait_keyword(page)
    kr_item = page.locator("#step-deck-rail .step-rail__item[data-step-key='keyword_review']")
    expect(kr_item).to_have_class(re.compile(r"is-current"))

    # 4. 通过后推进
    approve_btn = page.locator("[data-gate-action='approve'][data-step-key='keyword_review']").first
    expect(approve_btn).to_be_visible()
    approve_btn.click()
    page.wait_for_function(
        """() => {
            const rs = window.StepDeckUI.ui.runState;
            const s = rs.steps.keyword_review;
            return s && (s.status === 'approved' || s.status === 'completed');
        }""",
        timeout=5000,
    )
