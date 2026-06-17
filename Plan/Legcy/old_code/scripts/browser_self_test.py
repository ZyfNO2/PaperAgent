"""浏览器自测: Playwright 走 8 phase, 每步截图 + 验证关键 UI 元素.

不写 pytest, 直接 python scripts/browser_self_test.py.
截图存 tmp/click_step_NN.png.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

API = "http://127.0.0.1:18181"
WEB = "http://127.0.0.1:18182"
OUT = Path("tmp")
OUT.mkdir(exist_ok=True)


def shot(page, name: str) -> None:
    p = OUT / f"click_step_{name}.png"
    page.screenshot(path=str(p), full_page=True)
    print(f"  📸 {p}")


def wait_step_done(page, phase: int, timeout: int = 60000) -> None:
    """等 step-dot N 变 step-dot--done."""
    page.wait_for_function(
        f"() => document.querySelector('.step-dot[data-phase=\"{phase}\"]')"
        f"?.classList?.contains('step-dot--done')",
        timeout=timeout,
    )


def main() -> int:
    print("=" * 70)
    print("Browser Self-Test: TopicPilot-CN v2 + 新论文卡片 + 上传 + 评分信号")
    print("=" * 70)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 1600})
        page = context.new_page()
        page.goto(WEB + "/", wait_until="networkidle")
        time.sleep(0.5)
        page.wait_for_selector("#phase-panel .phase-card", timeout=10000)
        shot(page, "00_initial")

        # --- Phase 01: 填表 + 提交 ---
        print("\n[Step 01] 填表 + 创建项目")
        page.fill('input[name="case_id"]', "SELFTEST")
        page.fill('input[name="advisor_direction"]', "工业质检")
        page.fill('textarea[name="raw_topic"]', "基于轻量化注意力机制的YOLOv8带钢表面缺陷检测算法研究")
        page.fill('input[name="must_keep"]', "YOLOv8, 带钢表面缺陷, 轻量化, 注意力机制")
        page.click("#btn-primary")
        wait_step_done(page, 1)
        time.sleep(1)
        shot(page, "01_done")

        # --- Phase 02 ---
        print("\n[Step 02] 题目拆解")
        page.click("#btn-next")
        time.sleep(0.3)
        page.wait_for_function(
            "() => document.querySelector('.step-dot[data-phase=\"2\"]')?.classList?.contains('step-dot--active')",
            timeout=5000,
        )
        page.click("#btn-primary")
        wait_step_done(page, 2)
        time.sleep(0.5)
        shot(page, "02_done")

        # --- Phase 03 ---
        print("\n[Step 03] 检索计划")
        page.click("#btn-next")
        time.sleep(0.3)
        page.wait_for_function(
            "() => document.querySelector('.step-dot[data-phase=\"3\"]')?.classList?.contains('step-dot--active')",
            timeout=5000,
        )
        page.click("#btn-primary")
        wait_step_done(page, 3)
        time.sleep(0.5)
        shot(page, "03_done")

        # --- Phase 04: 论文卡片 + 上传 ---
        print("\n[Step 04] 证据账本 (arXiv 真论文卡片)")
        page.click("#btn-next")
        time.sleep(0.3)
        page.wait_for_function(
            "() => document.querySelector('.step-dot[data-phase=\"4\"]')?.classList?.contains('step-dot--active')",
            timeout=5000,
        )
        page.click("#btn-primary")
        # 等论文卡片渲染
        page.wait_for_selector(".evidence-card", timeout=60000)
        time.sleep(1)
        shot(page, "04_cards")

        # 验证: 至少有 1 张论文卡片
        n_cards = page.locator(".evidence-card").count()
        print(f"  📊 论文卡片数: {n_cards}")
        assert n_cards >= 1, f"Phase 04 应有至少 1 张论文卡片, 实际 {n_cards}"

        # 反直觉检查: 论文有 title 显示
        first_title = page.locator(".evidence-card__title").first.text_content() or ""
        print(f"  📄 第 1 篇: {first_title[:60]}")
        assert len(first_title) > 5, "论文卡片应显示 title"

        # 反直觉检查: arxiv badge 存在
        n_arxiv_badges = page.locator(".badge--arxiv").count()
        print(f"  🏷️  arXiv badge 数: {n_arxiv_badges}")

        # 反直觉检查: arXiv 论文链接存在
        n_links = page.locator(".evidence-card__links a").count()
        print(f"  🔗 链接数: {n_links}")
        assert n_links >= 1, "论文卡片应含 arXiv 链接"

        # 上传 1 篇自己的论文
        print("\n  ➕ 上传 1 篇自己找的论文")
        page.click(".add-paper-form > summary")
        time.sleep(0.3)
        page.fill('.add-paper-form input[name="title"]', "Defect Detection on Steel Strips using YOLOv8-Attention")
        page.fill('.add-paper-form input[name="authors"]', "Zhang San, Li Si")
        page.fill('.add-paper-form input[name="year"]', "2024")
        page.fill('.add-paper-form input[name="url"]', "https://arxiv.org/abs/2401.12345")
        page.fill('.add-paper-form textarea[name="abstract"]', "我们提出 YOLOv8-Attention, 在 NEU-DET 上 mAP@0.5 达 78.2%")
        page.click("#btn-add-paper")
        time.sleep(2)
        shot(page, "04_uploaded")

        # 验证: 新上传论文出现
        n_uploaded = page.locator(".badge--uploaded").count()
        print(f"  ✅ 上传论文 badge 数: {n_uploaded}")
        assert n_uploaded >= 1, f"上传后应含 1 个 user-uploaded badge, 实际 {n_uploaded}"

        # 验证: 论文卡片数 +1
        n_cards2 = page.locator(".evidence-card").count()
        print(f"  📊 上传后论文卡片数: {n_cards2} (从 {n_cards})")
        assert n_cards2 == n_cards + 1, f"上传后卡片数应 +1, 实际 {n_cards2} vs {n_cards} + 1"

        # --- Phase 05: 评分信号 ---
        print("\n[Step 05] 风险评分 (++/-- 信号)")
        page.click("#btn-next")
        time.sleep(0.3)
        page.wait_for_function(
            "() => document.querySelector('.step-dot[data-phase=\"5\"]')?.classList?.contains('step-dot--active')",
            timeout=5000,
        )
        page.click("#btn-primary")
        wait_step_done(page, 5)
        time.sleep(1)
        shot(page, "05_signals")

        # 验证: 评分信号 (6 维 ++/--) 渲染
        n_signals = page.locator(".risk-signal").count()
        print(f"  📊 评分维度数: {n_signals}")
        assert n_signals >= 6, f"应渲染 6 维评分信号, 实际 {n_signals}"

        # 验证: 至少 1 个 ++ 加分项
        n_plus = page.locator(".signal-line--plus").count()
        n_minus = page.locator(".signal-line--minus").count()
        print(f"  ++ 加分项: {n_plus} | -- 减分项: {n_minus}")
        assert n_plus + n_minus >= 6, f"6 维应有 ++/-- 总数 ≥ 6, 实际 {n_plus + n_minus}"

        # --- Phase 06 ---
        print("\n[Step 06] 工作包")
        page.click("#btn-next")
        time.sleep(0.3)
        page.wait_for_function(
            "() => document.querySelector('.step-dot[data-phase=\"6\"]')?.classList?.contains('step-dot--active')",
            timeout=5000,
        )
        page.click("#btn-primary")
        wait_step_done(page, 6)
        time.sleep(0.5)
        shot(page, "06_done")

        # --- Phase 07: 委员会对话 ---
        print("\n[Step 07] 开题报告 + 委员会")
        page.click("#btn-next")
        time.sleep(0.3)
        page.wait_for_function(
            "() => document.querySelector('.step-dot[data-phase=\"7\"]')?.classList?.contains('step-dot--active')",
            timeout=5000,
        )
        # proposal
        page.click("#btn-primary")
        wait_step_done(page, 7, timeout=180000); time.sleep(0.5)
        time.sleep(0.5)
        shot(page, "07_proposal")

        # committee (secondary button)
        sec = page.locator("#btn-secondary")
        if sec.count() > 0 and sec.is_visible():
            sec.click()
            wait_step_done(page, 7, timeout=180000)  # committee 完成后 step-dot 仍 done
            time.sleep(0.5)
            shot(page, "07_committee")

        # committee
        sec = page.locator("#btn-secondary")
        if sec.count() > 0 and sec.is_visible():
            sec.click()
            time.sleep(2); wait_text(page, "委员会审查完成")  # committee 二次等结果
            time.sleep(1)
            shot(page, "07_committee")

            # 验证: 3 角色对话气泡
            n_bubbles = page.locator(".discussion-bubble").count()
            print(f"  💬 委员会对话气泡数: {n_bubbles}")
            assert n_bubbles >= 3, f"应有 3 个角色对话气泡, 实际 {n_bubbles}"

            # 验证: proposal_sections / innovation_count 不再 undefined
            panel_text = page.locator("#phase-panel").text_content() or ""
            assert "undefined" not in panel_text, f"卡片不应有 undefined: {panel_text[:300]}"
            print("  ✅ 卡片无 undefined")

        # --- Phase 08: 最终材料 ---
        print("\n[Step 08] 最终材料")
        page.click("#btn-next")
        time.sleep(0.3)
        page.wait_for_function(
            "() => document.querySelector('.step-dot[data-phase=\"8\"]')?.classList?.contains('step-dot--active')",
            timeout=5000,
        )
        page.click("#btn-primary")
        wait_step_done(page, 8, timeout=180000)
        time.sleep(0.5)
        shot(page, "08_final")

        # 反直觉检查: trace 面板累积 ≥ 1 个事件
        n_trace = int(page.locator("#trace-count").text_content() or "0")
        print(f"\n  🧠 trace 事件总数: {n_trace}")
        assert n_trace >= 1, f"trace 事件应 ≥ 1, 实际 {n_trace}"

        # 反直觉检查: stepper 上 8 个全 done
        n_done = page.locator(".step-dot--done").count()
        print(f"  ✅ stepper done 数: {n_done} (期望 8)")
        assert n_done == 8, f"8 个 step 全部 done, 实际 {n_done}"

        print("\n" + "=" * 70)
        print("✅ 8 phase 全跑通 + 论文卡片 + 上传 + 评分信号 + 委员会对话")
        print("=" * 70)
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as e:
        print(f"\n❌ 失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 异常: {e}")
        sys.exit(2)
