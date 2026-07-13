"""Re8.1 WP5 Task 17: Seeded Research Playwright e2e tests.

Covers:
  SubTask 17.1: DOI input end-to-end (mocked backend)
  SubTask 17.2: Gate repair cycle display (round_idx + verdict trajectory)
  SubTask 17.3: 5 error state scenarios (honest display, not disguised as success)
    - 16.1 backend unavailable
    - 16.2 fused_verdict=BLOCKED
    - 16.3 Gate unresolved (cap reached)
    - 16.4 Seed ambiguous
    - 16.5 network offline mode

Mock strategy:
  All /api/v1/research/seeded, /status, /seeded-summary responses are
  intercepted via ``page.route`` so tests run without a live backend
  (real seeded runs take 5-15 minutes — incompatible with e2e suite).
  Fixture-style summary payloads are constructed in-test to exercise
  specific rendering branches.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Page, Route, expect

pytestmark = pytest.mark.react_web

BASE_URL = "http://127.0.0.1:18183"
SCREENSHOT_DIR = Path("tmp_re81_seeded_screenshots")


# ---------------------------------------------------------------------------
# Mock payload builders
# ---------------------------------------------------------------------------

def _seeded_submit_response(case_id: str = "re81-mock-001") -> dict[str, Any]:
    return {
        "case_id": case_id,
        "status": "running",
        "n_seeds": 2,
        "run_mode": "full_agent",
        "network_policy": "online",
    }


def _status_done(case_id: str = "re81-mock-001") -> dict[str, Any]:
    return {
        "case_id": case_id,
        "status": "done",
        "elapsed_s": 42.5,
        "current_node": "final_review_gate",
    }


def _summary_success(case_id: str = "re81-mock-001") -> dict[str, Any]:
    """A successful seeded run summary (fused_verdict=GO, all gates pass)."""
    return {
        "case_key": case_id,
        "case_id": case_id,
        "topic": "YOLOv8 for real-time steel surface defect detection",
        "n_seeds_input": 2,
        "mode": "seeded_research + full_agent + react_reflection",
        "status": "done",
        "elapsed_s": 42.5,
        "error": None,
        "entry_mode": "seeded_research",
        "run_mode": "full_agent",
        "network_policy": "online",
        "runtime_pass": True,
        "contract_pass": True,
        "contract_pass_reasons": [],
        "quality_pass": True,
        "quality_pass_reasons": [],
        "seed_cards": [
            {
                "seed_id": "S1",
                "resolved_title": "You Only Look Once: Unified, Real-Time Object Detection",
                "existence_status": "verified",
                "role": "classic_anchor",
                "repair_hint": None,
            },
            {
                "seed_id": "S2",
                "resolved_title": "Surface defect detection of hot-rolled steel strip based on deep learning",
                "existence_status": "verified",
                "role": "reproduction_target",
                "repair_hint": None,
            },
        ],
        "n_trace_events": 99,
        "gate_seed_audit_gate": {
            "verdict": "pass",
            "generated_by": "llm",
            "round_idx": 0,
            "rationale": "All seeds verified via Crossref.",
            "re_search_requests": [],
            "unresolved_gaps": [],
            "all_rounds": [
                {"round_idx": 0, "verdict": "pass", "generated_by": "llm",
                 "rationale": "All seeds verified via Crossref."},
            ],
        },
        "gate_tailor_gate": {
            "verdict": "pass",
            "generated_by": "llm",
            "round_idx": 1,
            "rationale": "Tailored method addresses all gaps.",
            "re_search_requests": [],
            "unresolved_gaps": [],
            "all_rounds": [
                {"round_idx": 0, "verdict": "revise", "generated_by": "llm",
                 "rationale": "Missing baseline comparison."},
                {"round_idx": 1, "verdict": "pass", "generated_by": "llm",
                 "rationale": "Tailored method addresses all gaps."},
            ],
        },
        "gate_final_review_gate": {
            "verdict": "pass",
            "generated_by": "llm",
            "round_idx": 0,
            "rationale": "Novel contribution with reproducible plan.",
            "re_search_requests": [],
            "unresolved_gaps": [],
            "all_rounds": [
                {"round_idx": 0, "verdict": "pass", "generated_by": "llm",
                 "rationale": "Novel contribution with reproducible plan."},
            ],
        },
        "n_ledger_entries": 357,
        "n_react_actions": 23,
        "n_errors": 0,
        "error_samples": [],
        "n_verified_papers": 16,
        "n_search_steps": 8,
        "tailored_verdict": "GO",
        "tailored_ablation_rows": 4,
        "tailored_method_summary": {
            "contribution_type": "novel_architecture",
            "core_method": "YOLOv8 with FPN neck adapted for steel defect classes",
            "baseline_model": "YOLOv8n",
        },
        "novelty_review_verdict": "accept",
        "has_falsifiable_hypothesis": True,
        "hypothesis_preview": "YOLOv8-FPN achieves mAP>=0.85 on NEU-DET within 50ms latency.",
        "n_evidence_gaps": 2,
        "gap_statuses": {"satisfied": 2},
        "fused_verdict": "GO",
        "fused_verdict_rationale": "All gates pass, novelty accepted, no open critical gaps.",
        "final_research_package_sections": [
            "seed_audit_summary", "tailor_summary", "gate_results",
            "ledger_entries", "evidence_gap_status",
            "falsifiable_hypothesis", "fused_verdict",
        ],
        "final_research_package_section_count": 7,
        "final_research_package_missing_sections": [],
        "final_rec": {
            "topic": "YOLOv8 for real-time steel surface defect detection",
            "n_papers": 16, "n_baseline": 5, "n_parallel": 11,
            "n_dataset": 3, "n_repo": 12, "n_work_packages": 4,
            "low_bar_status": "pass",
        },
        "error_categories": [],
    }


def _summary_blocked(case_id: str = "re81-mock-blocked") -> dict[str, Any]:
    """Re8.1 Task 16.2: fused_verdict=BLOCKED honest display."""
    s = _summary_success(case_id)
    s["fused_verdict"] = "BLOCKED"
    s["fused_verdict_rationale"] = "seed_audit_gate returned unresolved (cap reached)."
    s["quality_pass"] = False
    s["quality_pass_reasons"] = ["fused_verdict is BLOCKED"]
    s["error_categories"] = ["fused_blocked"]
    return s


def _summary_gate_unresolved(case_id: str = "re81-mock-gate") -> dict[str, Any]:
    """Re8.1 Task 16.3: Gate unresolved (cap reached) honest display."""
    s = _summary_success(case_id)
    s["gate_tailor_gate"] = {
        "verdict": "unresolved",
        "generated_by": "rule",
        "round_idx": 2,
        "rationale": "cap reached: 2/2",
        "re_search_requests": [],
        "unresolved_gaps": ["gap-S1-competing_baseline"],
        "all_rounds": [
            {"round_idx": 0, "verdict": "revise", "generated_by": "llm",
             "rationale": "Missing baseline comparison."},
            {"round_idx": 1, "verdict": "revise", "generated_by": "llm",
             "rationale": "Gap still open."},
            {"round_idx": 2, "verdict": "unresolved", "generated_by": "rule",
             "rationale": "cap reached: 2/2"},
        ],
    }
    s["fused_verdict"] = "BLOCKED"
    s["fused_verdict_rationale"] = "tailor_gate unresolved."
    s["quality_pass"] = False
    s["quality_pass_reasons"] = ["tailor_gate unresolved"]
    s["error_categories"] = ["fused_blocked", "gate_unresolved:tailor_gate"]
    return s


def _summary_seed_ambiguous(case_id: str = "re81-mock-amb") -> dict[str, Any]:
    """Re8.1 Task 16.4: Seed ambiguous honest display."""
    s = _summary_success(case_id)
    for card in s["seed_cards"]:
        card["existence_status"] = "ambiguous"
        card["repair_hint"] = "Multiple Crossref candidates — disambiguate by DOI."
    s["fused_verdict"] = "CONDITIONAL"
    s["fused_verdict_rationale"] = "Seeds ambiguous — manual review required."
    s["quality_pass"] = False
    s["quality_pass_reasons"] = ["ambiguous seeds"]
    s["error_categories"] = ["seed_ambiguous"]
    return s


def _summary_network_offline(case_id: str = "re81-mock-offline") -> dict[str, Any]:
    """Re8.1 Task 16.5: network offline mode honest display."""
    s = _summary_success(case_id)
    s["network_policy"] = "offline"
    s["run_mode"] = "offline_replay"
    s["error_categories"] = ["network_offline"]
    s["fused_verdict"] = "CONDITIONAL"
    s["fused_verdict_rationale"] = "Offline replay — results limited to cache."
    return s


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------

def _install_mock_routes(
    page: Page,
    *,
    submit_response: dict[str, Any] | None = None,
    submit_status: int = 200,
    summary_response: dict[str, Any] | None = None,
    summary_status: int = 200,
    final_status: dict[str, Any] | None = None,
) -> None:
    """Install route interceptors for /seeded, /status, /seeded-summary.

    All non-matched requests pass through unchanged (so static assets,
    /health/providers, etc. still work).
    """
    if submit_response is None:
        submit_response = _seeded_submit_response()
    if summary_response is None:
        summary_response = _summary_success()
    if final_status is None:
        final_status = _status_done(submit_response.get("case_id", "re81-mock-001"))

    def _handle_seeded(route: Route) -> None:
        if submit_status != 200:
            route.fulfill(
                status=submit_status,
                content_type="application/json",
                body=json.dumps({"detail": "mock backend unavailable"}),
            )
            return
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(submit_response),
        )

    def _handle_status(route: Route) -> None:
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(final_status),
        )

    def _handle_summary(route: Route) -> None:
        if summary_status != 200:
            route.fulfill(
                status=summary_status,
                content_type="application/json",
                body=json.dumps({"detail": "summary not found"}),
            )
            return
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(summary_response),
        )

    page.route("**/api/v1/research/seeded", _handle_seeded)
    page.route("**/api/v1/research/*/status", _handle_status)
    page.route("**/api/v1/research/*/seeded-summary", _handle_summary)


def _goto_seeded(page: Page) -> None:
    page.goto(BASE_URL + "/#/seeded-research")
    page.wait_for_load_state("networkidle")


def _fill_doi_seed(page: Page, topic: str = "YOLOv8 steel defect detection") -> None:
    """Fill topic + 2 DOI seeds (the default form)."""
    page.fill("#seeded-topic-input", topic)
    # Default seeds are S1 + S2 with input_form=doi
    page.fill("input.pa-seed-identifier >> nth=0", "10.1000/yolo-v8")
    page.fill("input.pa-seed-identifier >> nth=1", "10.1000/steel-defect-2013")


# ---------------------------------------------------------------------------
# SubTask 17.1: DOI input end-to-end
# ---------------------------------------------------------------------------

class TestSeededDoiInput:
    """SubTask 17.1: DOI input end-to-end test."""

    def test_seeded_page_loads(self, page: Page):
        """页面加载，显示种子录入表单 + 真实 API 按钮。"""
        SCREENSHOT_DIR.mkdir(exist_ok=True)
        _goto_seeded(page)
        expect(page.locator(".workbench-topic")).to_contain_text("Seeded Research")
        expect(page.locator("[data-testid='seeded-run-real']")).to_be_visible()
        expect(page.locator("[data-testid='seeded-topic-input']")).to_be_visible()
        expect(page.locator("[data-testid='seed-list']")).to_be_visible()
        # Default 2 seeds
        expect(page.locator("[data-testid='seed-row-0']")).to_be_visible()
        expect(page.locator("[data-testid='seed-row-1']")).to_be_visible()
        page.screenshot(path=str(SCREENSHOT_DIR / "seeded_initial.png"))

    def test_doi_input_submit_success(self, page: Page):
        """输入 DOI 提交，mock /seeded + /status + /seeded-summary 全成功路径。"""
        _install_mock_routes(page, summary_response=_summary_success())
        _goto_seeded(page)
        _fill_doi_seed(page)

        page.click("[data-testid='seeded-run-real']")

        # Status banner appears
        expect(page.locator("[data-testid='seeded-live-status']")).to_be_visible()

        # Result area appears after mock poll resolves
        expect(page.locator("[data-testid='seeded-result-area']")).to_be_visible(
            timeout=15000
        )

        # Fused verdict shows GO (success, not disguised)
        expect(page.locator("[data-testid='fused-verdict']")).to_contain_text("GO")
        expect(page.locator("[data-testid='pass-tiers']")).to_be_visible()

        page.screenshot(path=str(SCREENSHOT_DIR / "seeded_doi_success.png"))

    def test_seed_add_remove(self, page: Page):
        """种子行增删可用。"""
        _goto_seeded(page)
        # Default 2 seeds
        expect(page.locator("[data-testid^='seed-row-']")).to_have_count(2)
        # Add
        page.click("[data-testid='seed-add']")
        expect(page.locator("[data-testid^='seed-row-']")).to_have_count(3)
        # Remove last
        page.click("[data-testid='seed-remove-2']")
        expect(page.locator("[data-testid^='seed-row-']")).to_have_count(2)

    def test_export_package_button_after_run(self, page: Page):
        """运行完成后导出按钮可见。"""
        _install_mock_routes(page, summary_response=_summary_success())
        _goto_seeded(page)
        _fill_doi_seed(page)
        page.click("[data-testid='seeded-run-real']")
        expect(page.locator("[data-testid='seeded-export-package']")).to_be_visible(
            timeout=15000
        )


# ---------------------------------------------------------------------------
# SubTask 17.2: Gate repair cycle display
# ---------------------------------------------------------------------------

class TestSeededGateRounds:
    """SubTask 17.2: Gate repair cycle display (round_idx + verdict trajectory)."""

    def test_gate_rounds_trajectory_displayed(self, page: Page):
        """Tailor Gate 有 2 轮 (revise → pass)，验证 round chips 显示。"""
        _install_mock_routes(page, summary_response=_summary_success())
        _goto_seeded(page)
        _fill_doi_seed(page)
        page.click("[data-testid='seeded-run-real']")
        expect(page.locator("[data-testid='seeded-result-area']")).to_be_visible(
            timeout=15000
        )

        # Gate rounds trajectory block visible
        rounds = page.locator("[data-testid='gate-rounds-trajectory']")
        expect(rounds).to_be_visible()
        # Tailor gate has 2 rounds (revise + pass) in _summary_success
        expect(rounds.locator(".pa-gate-round-chip")).to_have_count(2)

        # First round chip shows R0 + revise icon
        first_chip = rounds.locator(".pa-gate-round-chip >> nth=0")
        expect(first_chip).to_contain_text("R0")
        expect(first_chip).to_contain_text("⚠️")

        # Second round chip shows R1 + pass icon
        second_chip = rounds.locator(".pa-gate-round-chip >> nth=1")
        expect(second_chip).to_contain_text("R1")
        expect(second_chip).to_contain_text("✅")

        page.screenshot(path=str(SCREENSHOT_DIR / "seeded_gate_rounds.png"))

    def test_gate_verdict_icon_displayed(self, page: Page):
        """每个 Gate 显示 verdict 图标 + verdict 文本。"""
        _install_mock_routes(page, summary_response=_summary_success())
        _goto_seeded(page)
        _fill_doi_seed(page)
        page.click("[data-testid='seeded-run-real']")
        expect(page.locator("[data-testid='seeded-result-area']")).to_be_visible(
            timeout=15000
        )

        # All 3 gates pass — each shows ✅ + "pass"
        gate_cards = page.locator(".pa-gate-card")
        expect(gate_cards).to_have_count(3)
        for i in range(3):
            card = gate_cards.nth(i)
            expect(card).to_contain_text("✅")
            expect(card).to_contain_text("pass")


# ---------------------------------------------------------------------------
# SubTask 17.3: 5 error state scenarios
# ---------------------------------------------------------------------------

class TestSeededErrorStates:
    """SubTask 17.3: 5 error state scenarios — honest display, not disguised as success."""

    def test_error_16_1_backend_unavailable(self, page: Page):
        """Task 16.1: /seeded 返回 500 — 显示 ErrorState，不得显示空成功页。"""
        _install_mock_routes(page, submit_status=500)
        _goto_seeded(page)
        _fill_doi_seed(page)
        page.click("[data-testid='seeded-run-real']")

        # ErrorState component visible (Task 16.1)
        expect(page.locator(".error-state")).to_be_visible(timeout=10000)
        expect(page.locator(".error-state .error-title")).to_contain_text(
            "真实后端调用失败"
        )
        # Status banner shows error state
        expect(page.locator("[data-testid='seeded-live-status']")).to_contain_text(
            "运行失败"
        )
        # Result area must NOT appear (no fake success)
        expect(page.locator("[data-testid='seeded-result-area']")).to_have_count(0)

        page.screenshot(path=str(SCREENSHOT_DIR / "seeded_err_backend.png"))

    def test_error_16_2_fused_blocked(self, page: Page):
        """Task 16.2: fused_verdict=BLOCKED — 显示 BLOCKED + 原因，不伪装为成功。"""
        _install_mock_routes(page, summary_response=_summary_blocked())
        _goto_seeded(page)
        _fill_doi_seed(page)
        page.click("[data-testid='seeded-run-real']")
        expect(page.locator("[data-testid='seeded-result-area']")).to_be_visible(
            timeout=15000
        )

        # Fused verdict shows BLOCKED (not GO)
        expect(page.locator("[data-testid='fused-verdict']")).to_contain_text(
            "BLOCKED"
        )
        # Honest error categories banner visible
        expect(page.locator("[data-testid='seeded-error-categories']")).to_be_visible()
        expect(page.locator("[data-testid='seeded-error-categories']")).to_contain_text(
            "Decision Fusion 阻断"
        )
        # quality_pass tier must show ❌ (not ✅)
        tiers = page.locator(".pa-pass-tier")
        # Find the quality_pass tier — it should have ❌
        quality_tier = page.locator(
            ".pa-pass-tier:has-text('quality_pass')"
        )
        expect(quality_tier.locator(".pa-pass-icon")).to_contain_text("❌")

        page.screenshot(path=str(SCREENSHOT_DIR / "seeded_err_blocked.png"))

    def test_error_16_3_gate_unresolved(self, page: Page):
        """Task 16.3: Gate unresolved (cap reached) — 显示 cap + 最后 verdict。"""
        _install_mock_routes(page, summary_response=_summary_gate_unresolved())
        _goto_seeded(page)
        _fill_doi_seed(page)
        page.click("[data-testid='seeded-run-real']")
        expect(page.locator("[data-testid='seeded-result-area']")).to_be_visible(
            timeout=15000
        )

        # Tailor gate card shows unresolved verdict
        tailor_card = page.locator(".pa-gate-card.verdict-unresolved")
        expect(tailor_card).to_have_count(1)
        expect(tailor_card).to_contain_text("unresolved")
        expect(tailor_card).to_contain_text("cap reached")

        # Honest error categories banner mentions gate_unresolved
        expect(page.locator("[data-testid='seeded-error-categories']")).to_be_visible()
        expect(page.locator("[data-testid='seeded-error-categories']")).to_contain_text(
            "Tailor Gate 未收敛"
        )

        # Gate rounds trajectory shows 3 rounds (revise → revise → unresolved)
        rounds = page.locator("[data-testid='gate-rounds-trajectory']")
        expect(rounds).to_be_visible()
        expect(rounds.locator(".pa-gate-round-chip")).to_have_count(3)
        # Last chip shows R2 + unresolved icon (❌)
        last_chip = rounds.locator(".pa-gate-round-chip >> nth=2")
        expect(last_chip).to_contain_text("R2")
        expect(last_chip).to_contain_text("❌")

        page.screenshot(path=str(SCREENSHOT_DIR / "seeded_err_gate.png"))

    def test_error_16_4_seed_ambiguous(self, page: Page):
        """Task 16.4: Seed ambiguous — 显示 ambiguous + 候选列表。"""
        _install_mock_routes(page, summary_response=_summary_seed_ambiguous())
        _goto_seeded(page)
        _fill_doi_seed(page)
        page.click("[data-testid='seeded-run-real']")
        expect(page.locator("[data-testid='seeded-result-area']")).to_be_visible(
            timeout=15000
        )

        # Seed cards table shows ambiguous status for both seeds
        seed_table = page.locator("table.snapshot-table")
        expect(seed_table).to_contain_text("ambiguous")
        # Both seed cards should be ambiguous (⚠️ icon)
        ambiguous_icons = seed_table.locator("text=⚠️")
        expect(ambiguous_icons).to_have_count(2)

        # Honest error categories banner mentions seed_ambiguous
        expect(page.locator("[data-testid='seeded-error-categories']")).to_be_visible()
        expect(page.locator("[data-testid='seeded-error-categories']")).to_contain_text(
            "种子身份歧义"
        )

        # Fused verdict shows CONDITIONAL (not GO — honest)
        expect(page.locator("[data-testid='fused-verdict']")).to_contain_text(
            "CONDITIONAL"
        )

        page.screenshot(path=str(SCREENSHOT_DIR / "seeded_err_ambiguous.png"))

    def test_error_16_5_network_offline(self, page: Page):
        """Task 16.5: 网络离线模式 — 显示 offline banner。"""
        _install_mock_routes(page, summary_response=_summary_network_offline())
        _goto_seeded(page)
        _fill_doi_seed(page)
        page.click("[data-testid='seeded-run-real']")
        expect(page.locator("[data-testid='seeded-result-area']")).to_be_visible(
            timeout=15000
        )

        # Network offline banner visible
        expect(page.locator("[data-testid='network-offline-banner']")).to_be_visible()
        expect(page.locator("[data-testid='network-offline-banner']")).to_contain_text(
            "网络离线模式已生效"
        )
        expect(page.locator("[data-testid='network-offline-banner']")).to_contain_text(
            "NetworkPolicyGuard"
        )

        # Honest error categories banner mentions network_offline
        expect(page.locator("[data-testid='seeded-error-categories']")).to_be_visible()
        expect(page.locator("[data-testid='seeded-error-categories']")).to_contain_text(
            "网络离线模式"
        )

        page.screenshot(path=str(SCREENSHOT_DIR / "seeded_err_offline.png"))


# ---------------------------------------------------------------------------
# Combined / regression
# ---------------------------------------------------------------------------

class TestSeededFixtureFallback:
    """Regression: fixture load button still works alongside real API button."""

    def test_fixture_load_button_still_works(self, page: Page):
        """旧 fixture 加载按钮保留，作为 fallback 不破坏。"""
        # Intercept fixture fetch (since fixture file exists in /public/fixtures/)
        _goto_seeded(page)
        expect(page.locator("[data-testid='seeded-load-fixture']")).to_be_visible()
        expect(page.locator("[data-testid='seeded-run-real']")).to_be_visible()
        # Both buttons coexist
        page.screenshot(path=str(SCREENSHOT_DIR / "seeded_both_buttons.png"))
