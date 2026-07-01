"""Session 2: 证据工作台 UI + 审核 e2e.

跑法: 先起 start_all.bat (后端 18181 + 前端 18182), 再跑这个.
"""

from __future__ import annotations

import time

import pytest


def _click_tab(page, name: str) -> None:
    page.click(f'.tab[data-tab="{name}"]')
    page.wait_for_selector(f"#page-{name}:not([hidden])", state="attached", timeout=5000)


def test_evidence_tab_visible_after_analyze(page) -> None:
    page.fill("#input-topic", "基于YOLO的钢材表面缺陷检测")
    page.click("#btn-analyze")
    page.wait_for_selector("#result-grid:not([hidden])", timeout=30000)
    _click_tab(page, "evidence")
    # evidence page visible
    page.wait_for_selector("#ev-paper-list", state="attached", timeout=10000)
    # auto-ingest should fill the list
    page.wait_for_selector("#ev-paper-list .ev-card", timeout=10000, state="attached")
    n_papers = len(page.locator("#ev-paper-list .ev-card").all())
    n_datasets = len(page.locator("#ev-dataset-list .ev-card").all())
    n_repos = len(page.locator("#ev-repo-list .ev-card").all())
    assert n_papers >= 1, f"no auto papers: papers={n_papers}"
    assert n_datasets >= 1, f"no auto datasets: datasets={n_datasets}"
    assert n_repos >= 1, f"no auto repos: repos={n_repos}"


def test_summary_cells_match_lists(page) -> None:
    page.fill("#input-topic", "基于YOLO的钢材表面缺陷检测")
    page.click("#btn-analyze")
    page.wait_for_selector("#result-grid:not([hidden])", timeout=30000)
    _click_tab(page, "evidence")
    page.wait_for_selector("#ev-paper-list .ev-card", timeout=10000, state="attached")
    n_papers = int(page.inner_text("#sum-paper"))
    n_datasets = int(page.inner_text("#sum-dataset"))
    n_repos = int(page.inner_text("#sum-repo"))
    # 与 list 渲染的卡片数一致
    assert n_papers == len(page.locator("#ev-paper-list .ev-card").all())
    assert n_datasets == len(page.locator("#ev-dataset-list .ev-card").all())
    assert n_repos == len(page.locator("#ev-repo-list .ev-card").all())


def test_patch_review_button_changes_status(page) -> None:
    page.fill("#input-topic", "基于YOLO的钢材表面缺陷检测")
    page.click("#btn-analyze")
    page.wait_for_selector("#result-grid:not([hidden])", timeout=30000)
    _click_tab(page, "evidence")
    page.wait_for_selector("#ev-paper-list .ev-card", timeout=10000, state="attached")
    # 拿第一条 paper
    first_card = page.locator("#ev-paper-list .ev-card").first
    eid = first_card.get_attribute("data-ev-id")
    # 找 core 按钮
    page.click(f'#ev-paper-list .ev-card[data-ev-id="{eid}"] [data-action="review"][data-status="core"]')
    # 等 summary 计数更新 (10s)
    try:
        page.wait_for_function(
            "() => parseInt(document.getElementById('sum-core').textContent) >= 1",
            timeout=10000,
        )
    except Exception:
        import sys
        msgs = page.evaluate("() => Array.from(document.querySelectorAll('.trace-item__detail')).map(e=>e.textContent).join(' || ')")
        sum_text = page.evaluate("() => ({paper: document.getElementById('sum-paper').textContent, dataset: document.getElementById('sum-dataset').textContent, repo: document.getElementById('sum-repo').textContent, accepted: document.getElementById('sum-accepted').textContent, core: document.getElementById('sum-core').textContent, rejected: document.getElementById('sum-rejected').textContent})")
        sys.stderr.write("\n=== SUMMARY === " + str(sum_text) + "\n")
        sys.stderr.write("=== TRACE === " + msgs.encode("ascii", "replace").decode() + "\n")
        sys.stderr.flush()
        raise
    n_core = int(page.inner_text("#sum-core"))
    assert n_core >= 1


def test_reject_button_marks_rejected(page) -> None:
    page.fill("#input-topic", "基于YOLO的钢材表面缺陷检测")
    page.click("#btn-analyze")
    page.wait_for_selector("#result-grid:not([hidden])", timeout=30000)
    _click_tab(page, "evidence")
    page.wait_for_selector("#ev-paper-list .ev-card", timeout=10000, state="attached")
    first_card = page.locator("#ev-paper-list .ev-card").first
    eid = first_card.get_attribute("data-ev-id")
    page.click(f'#ev-paper-list .ev-card[data-ev-id="{eid}"] [data-action="review"][data-status="rejected"]')
    page.wait_for_function(
        "() => parseInt(document.getElementById('sum-rejected').textContent) >= 1",
        timeout=10000,
    )
    n_rejected = int(page.inner_text("#sum-rejected"))
    assert n_rejected >= 1


def test_manual_add_paper_modal(page) -> None:
    page.fill("#input-topic", "基于YOLO的钢材表面缺陷检测")
    page.click("#btn-analyze")
    page.wait_for_selector("#result-grid:not([hidden])", timeout=30000)
    _click_tab(page, "evidence")
    page.wait_for_selector("#ev-paper-list .ev-card", timeout=10000, state="attached")
    # 打开弹窗
    page.click("#btn-add-paper")
    page.wait_for_selector("#modal-add-paper:not([hidden])", timeout=5000, state="attached")
    page.fill("#mp-title", "Lightweight Attention YOLOv8 for Steel Defects (User Upload)")
    page.fill("#mp-authors", "Zhang, S., Wang, Y.")
    page.fill("#mp-year", "2024")
    page.fill("#mp-doi", "10.5555/test-user-paper-1")
    page.fill("#mp-note", "E2E 测试用")
    page.click("#mp-save")
    # 弹窗关闭 + 新卡片出现
    page.wait_for_selector("#modal-add-paper[hidden]", state="attached", timeout=5000)
    # 等 refresh
    time.sleep(0.5)
    html = page.inner_html("#ev-paper-list")
    assert "Lightweight Attention YOLOv8" in html


def test_manual_add_paper_dedup_by_doi(page) -> None:
    """手动加同 DOI 应提示重复 (不入池)."""

    page.fill("#input-topic", "基于YOLO的钢材表面缺陷检测")
    page.click("#btn-analyze")
    page.wait_for_selector("#result-grid:not([hidden])", timeout=30000)
    _click_tab(page, "evidence")
    page.wait_for_selector("#ev-paper-list .ev-card", timeout=10000, state="attached")
    # 第一次加
    page.click("#btn-add-paper")
    page.wait_for_selector("#modal-add-paper:not([hidden])", timeout=5000, state="attached")
    page.fill("#mp-title", "Some Unique DOI Paper")
    page.fill("#mp-doi", "10.9999/e2e-dedup-test-001")
    page.click("#mp-save")
    page.wait_for_selector("#modal-add-paper[hidden]", state="attached", timeout=5000)
    time.sleep(0.3)
    n_before = len(page.locator("#ev-paper-list .ev-card").all())
    # 第二次加同样 DOI
    page.click("#btn-add-paper")
    page.wait_for_selector("#modal-add-paper:not([hidden])", timeout=5000, state="attached")
    page.fill("#mp-title", "Some Unique DOI Paper (dup)")
    page.fill("#mp-doi", "10.9999/e2e-dedup-test-001")
    # 点保存应弹 alert (因为 ok=False)
    page.on("dialog", lambda d: d.accept())
    page.click("#mp-save")
    time.sleep(0.5)
    n_after = len(page.locator("#ev-paper-list .ev-card").all())
    assert n_after == n_before, f"dedup fail: {n_before} -> {n_after}"


def test_delete_button_confirms_and_removes(page) -> None:
    """删除一条手动加的 paper, 列表减少 1."""

    page.fill("#input-topic", "基于YOLO的钢材表面缺陷检测")
    page.click("#btn-analyze")
    page.wait_for_selector("#result-grid:not([hidden])", timeout=30000)
    _click_tab(page, "evidence")
    page.wait_for_selector("#ev-paper-list .ev-card", timeout=10000, state="attached")
    # 先加一条
    page.click("#btn-add-paper")
    page.wait_for_selector("#modal-add-paper:not([hidden])", timeout=5000, state="attached")
    page.fill("#mp-title", "Delete Me Test Paper")
    page.fill("#mp-doi", "10.9999/e2e-delete-test")
    page.click("#mp-save")
    page.wait_for_selector("#modal-add-paper[hidden]", state="attached", timeout=5000)
    time.sleep(0.3)
    n_before = len(page.locator("#ev-paper-list .ev-card").all())
    # 弹窗 accept confirm
    page.on("dialog", lambda d: d.accept())
    # 找这条 paper 的删除按钮
    page.click(f'#ev-paper-list .ev-card:has-text("Delete Me Test Paper") [data-action="delete"]')
    time.sleep(0.8)
    n_after = len(page.locator("#ev-paper-list .ev-card").all())
    assert n_after == n_before - 1, f"delete fail: {n_before} -> {n_after}"


def test_dataset_modal_add(page) -> None:
    page.fill("#input-topic", "基于YOLO的钢材表面缺陷检测")
    page.click("#btn-analyze")
    page.wait_for_selector("#result-grid:not([hidden])", timeout=30000)
    _click_tab(page, "evidence")
    page.wait_for_selector("#ev-dataset-list .ev-card", timeout=10000, state="attached")
    page.click("#btn-add-dataset")
    page.wait_for_selector("#modal-add-dataset:not([hidden])", timeout=5000, state="attached")
    page.fill("#md-name", "Severstal Test Dataset")
    page.fill("#md-scale", "12000 张")
    page.fill("#md-license", "CC BY-NC")
    page.click("#md-save")
    page.wait_for_selector("#modal-add-dataset[hidden]", state="attached", timeout=5000)
    time.sleep(0.5)
    html = page.inner_html("#ev-dataset-list")
    assert "Severstal Test Dataset" in html


def test_repo_modal_add(page) -> None:
    page.fill("#input-topic", "基于YOLO的钢材表面缺陷检测")
    page.click("#btn-analyze")
    page.wait_for_selector("#result-grid:not([hidden])", timeout=30000)
    _click_tab(page, "evidence")
    page.wait_for_selector("#ev-repo-list .ev-card", timeout=10000, state="attached")
    page.click("#btn-add-repo")
    page.wait_for_selector("#modal-add-repo:not([hidden])", timeout=5000, state="attached")
    page.fill("#mr-name", "YOLOv8 Steel Fork Test")
    page.fill("#mr-url", "https://github.com/example/yolov8-steel-test")
    page.check("#mr-readme")
    page.check("#mr-train")
    page.click("#mr-save")
    page.wait_for_selector("#modal-add-repo[hidden]", state="attached", timeout=5000)
    time.sleep(0.5)
    html = page.inner_html("#ev-repo-list")
    assert "YOLOv8 Steel Fork Test" in html
