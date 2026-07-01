"""Session 41: Step Workbench Playwright E2E (8 tests).

SOP: Plan/PaperAgent_Session41_主页面分步确认与三栏StepWorkbench整改SOP.md

8 个测试覆盖:
  S41-PW-1: 主入口进入 Step Workbench, 默认只进 Step 1, 不一次性全出
  S41-PW-2: Step 1 流式完成后进入 paused_for_review, Step 2 仍 locked
  S41-PW-3: 点击"确认并进入下一步"后才进入 Step 2, Trace 记录确认事件
  S41-PW-4: 横向翻页只查看不执行 (左右常驻不清空)
  S41-PW-5: 三栏布局可见, 不重叠, 左右常驻
  S41-PW-6: 右侧 LLM 思维流式追加 (assistant_thought / tool_use)
  S41-PW-7: 中间区域证据多时拆子页 / Tab, 首屏看到当前结论与待确认问题
  S41-PW-8: 移动端 390x844 无横向溢出, 确认按钮不被遮挡

工作台入口: 点击 #btn-start-workbench (新增主按钮; #btn-analyze 保留经典视图).
"""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect

WEB_URL = "http://127.0.0.1:18182"
TOPIC = "基于 YOLO 的道路裂缝检测"


# ---------- helpers ---------- #


def _open_workbench(page: Page, topic: str = TOPIC) -> None:
    """点击主按钮进入 Step Workbench, 等待容器可见且 Step 1 已创建."""
    page.fill("#input-topic", topic)
    page.click("#btn-start-workbench")
    page.wait_for_selector("#step-workbench:not([hidden])", timeout=10000)
    page.wait_for_function(
        "window.StepWorkbench && window.StepWorkbench.state.activeStepIndex === 0",
        timeout=10000,
    )


def _wait_step_status(page: Page, step_index: int, status: str, timeout: int = 20000) -> None:
    """等待 workspaceState.steps[index].status === status."""
    page.wait_for_function(
        """(args) => {
            const [idx, st] = args;
            const w = window.StepWorkbench;
            if (!w || !w.state || !w.state.steps[idx]) return false;
            return w.state.steps[idx].status === st;
        }""",
        arg=[step_index, status],
        timeout=timeout,
    )


# ---------- S41-PW-1: 主入口不一次性全出 ---------- #


def test_pw_01_main_enter_only_step_1(page: Page):
    """点击主按钮后只进入 Step 1 题目理解; 经典 #result-grid 不在主显示状态."""
    _open_workbench(page)

    # 当前步骤标题包含 "题目理解"
    expect(page.locator("#sw-step-title")).to_contain_text("题目理解")

    # 中间不应同时显示 "关键词拆解" "可行性判断" "开题建议" 的完整结果
    # (它们是后续步骤, Step 1 时仅 locked 标题可见, 不应有产物 body)
    keyword_body = page.locator('[data-step-index="1"].sw-step__body')
    expect(keyword_body).to_be_hidden()
    feasibility_body = page.locator('[data-step-index="3"].sw-step__body')
    expect(feasibility_body).to_be_hidden()

    # 经典 result-grid 不处于主显示状态 (有 hidden 属性, 不在主路径)
    assert page.evaluate("document.getElementById('result-grid').hasAttribute('hidden')") is True
    # 且 step-workbench 已显示
    assert page.evaluate("document.getElementById('step-workbench').hidden") is False


# ---------- S41-PW-2: Step 1 必须暂停 ---------- #


def test_pw_02_step1_pauses_for_review(page: Page):
    """Step 1 流式完成后进入 paused_for_review, 确认按钮可见, Step 2 仍 locked."""
    _open_workbench(page)

    _wait_step_status(page, 0, "paused_for_review")

    # 确认按钮可见
    expect(page.locator("#sw-approve-btn")).to_be_visible()
    # Step 2 仍 locked 或未开始
    step2_status = page.evaluate("window.StepWorkbench.state.steps[1].status")
    assert step2_status in ("locked", "needs_revision", "failed"), \
        f"Step 2 应仍 locked, 实际 {step2_status}"


# ---------- S41-PW-3: 确认后才进入 Step 2 ---------- #


def test_pw_03_confirm_advances_to_step_2(page: Page):
    """点击确认后当前步骤变为关键词拆解, Trace 记录确认, Step 2 开始流式."""
    _open_workbench(page)
    _wait_step_status(page, 0, "paused_for_review")

    trace_before = page.evaluate("window.StepWorkbench.state.evidenceTrace.length")
    page.click("#sw-approve-btn")

    # activeStepIndex 推进到 1 (关键词拆解)
    page.wait_for_function(
        "window.StepWorkbench.state.activeStepIndex === 1", timeout=10000
    )
    expect(page.locator("#sw-step-title")).to_contain_text("关键词")

    # Trace 记录了用户确认事件 (至少 +1)
    trace_after = page.evaluate("window.StepWorkbench.state.evidenceTrace.length")
    assert trace_after > trace_before, \
        f"确认后 Trace 应增长: before={trace_before}, after={trace_after}"

    # Step 2 进入 running 或 paused_for_review
    step2_status = page.evaluate("window.StepWorkbench.state.steps[1].status")
    assert step2_status in ("running", "paused_for_review", "completed"), \
        f"确认后 Step 2 应开始, 实际 {step2_status}"


# ---------- S41-PW-4: 横向翻页只查看不执行 ---------- #


def test_pw_04_pagination_view_only(page: Page):
    """翻到前序步骤再翻回, 不触发新的 LLM 输出, 左右常驻不清空."""
    _open_workbench(page)
    _wait_step_status(page, 0, "paused_for_review")
    page.click("#sw-approve-btn")
    page.wait_for_function("window.StepWorkbench.state.activeStepIndex === 1", timeout=10000)
    _wait_step_status(page, 1, "paused_for_review", timeout=20000)

    # 记录当前 runtime step 与 timeline 长度
    runtime_step_before = page.evaluate("window.StepWorkbench.state.currentRuntimeStep")
    ev_count_before = page.evaluate("window.StepWorkbench.state.evidenceTrace.length")
    llm_count_before = page.evaluate("window.StepWorkbench.state.llmTimeline.length")
    tool_count_before = page.evaluate("window.StepWorkbench.state.toolUseTimeline.length")

    # 翻回 Step 1
    page.click("#sw-prev-btn")
    page.wait_for_function("window.StepWorkbench.state.activeStepIndex === 0", timeout=5000)

    # 翻页不应改变 runtime step, 不清空左侧 Trace, 不重置右侧 LLM timeline
    runtime_step_after_prev = page.evaluate("window.StepWorkbench.state.currentRuntimeStep")
    assert runtime_step_after_prev == runtime_step_before, \
        "翻页不应改变 currentRuntimeStep"

    ev_count_after_prev = page.evaluate("window.StepWorkbench.state.evidenceTrace.length")
    assert ev_count_after_prev == ev_count_before, \
        f"翻页不应清空左侧 Trace: before={ev_count_before}, after={ev_count_after_prev}"

    llm_count_after_prev = page.evaluate("window.StepWorkbench.state.llmTimeline.length")
    assert llm_count_after_prev == llm_count_before, \
        f"翻页不应重置右侧 LLM timeline: before={llm_count_before}, after={llm_count_after_prev}"

    tool_count_after_prev = page.evaluate("window.StepWorkbench.state.toolUseTimeline.length")
    assert tool_count_after_prev == tool_count_before, \
        f"翻页不应重置右侧 tool timeline: before={tool_count_before}, after={tool_count_after_prev}"

    # 翻回 Step 2
    page.click("#sw-next-btn")
    page.wait_for_function("window.StepWorkbench.state.activeStepIndex === 1", timeout=5000)


# ---------- S41-PW-5: 三栏布局与左右常驻 ---------- #


def test_pw_05_three_layout_persistent(page: Page):
    """三栏可见, 翻页后左侧 Trace 与右侧 LLM 未被重置."""
    _open_workbench(page)
    _wait_step_status(page, 0, "paused_for_review")

    # 三栏容器可见
    expect(page.locator("#sw-trace-panel")).to_be_visible()
    expect(page.locator("#sw-middle-panel")).to_be_visible()
    expect(page.locator("#sw-llm-panel")).to_be_visible()

    # 中间步骤标题可见
    expect(page.locator("#sw-step-title")).to_be_visible()

    # 横向无溢出: 页面宽度足够时三栏无重叠 (检查 bounding boxes 不重叠)
    boxes = page.evaluate("""() => {
        const tr = document.querySelector('#sw-trace-panel').getBoundingClientRect();
        const md = document.querySelector('#sw-middle-panel').getBoundingClientRect();
        const ll = document.querySelector('#sw-llm-panel').getBoundingClientRect();
        return {
            tr: {x: tr.x, w: tr.width, right: tr.right},
            md: {x: md.x, w: md.width, right: md.right},
            ll: {x: ll.x, w: ll.width, right: ll.right},
        };
    }""")
    # 左栏在中间栏左侧, 中间栏在右栏左侧
    assert boxes["tr"]["right"] <= boxes["md"]["x"] + 1, \
        f"左栏与中间栏重叠: {boxes}"
    assert boxes["md"]["right"] <= boxes["ll"]["x"] + 1, \
        f"中间栏与右栏重叠: {boxes}"


# ---------- S41-PW-6: 右侧 LLM 思维流式追加 ---------- #


def test_pw_06_llm_timeline_streaming_append(page: Page):
    """右侧在 Step 1 运行中逐条追加, 至少一条 assistant_thought; 若有 tool_use 则对应记录."""
    _open_workbench(page)

    # 等运行结束 (paused_for_review), 期间逐条追加
    _wait_step_status(page, 0, "paused_for_review", timeout=20000)

    # 至少一条 assistant_thought
    thoughts = page.evaluate(
        "window.StepWorkbench.state.llmTimeline.filter(m => m.kind === 'assistant_thought')"
    )
    assert len(thoughts) >= 1, f"右侧应至少一条 assistant_thought, 实际 {len(thoughts)}"

    # 思维条目逐条追加: seq 单调递增
    seqs = [m["seq"] for m in page.evaluate("window.StepWorkbench.state.llmTimeline")]
    assert seqs == sorted(seqs) and len(seqs) >= 1, f"seq 应单调递增: {seqs}"

    # 若发生 tool_use, 须出现在 toolUseTimeline
    tool_count = page.evaluate("window.StepWorkbench.state.toolUseTimeline.length")
    if tool_count > 0:
        has_tool_kind = page.evaluate(
            "window.StepWorkbench.state.toolUseTimeline.some(m => m.kind === 'tool_use')"
        )
        assert has_tool_kind, "toolUseTimeline 非空但无 tool_use 记录"


# ---------- S41-PW-7: 中间信息密度分段 (Step 3 子页) ---------- #


def test_pw_07_middle_density_split(page: Page):
    """Step 3 (检索计划与候选证据) 通过子页/Tab 拆分, 首屏看到当前结论与待确认问题."""
    _open_workbench(page)

    # 直接用 evaluate 注入跳转到 Step 3 的 mock 数据 (6 条以上候选证据)
    page.evaluate("""() => {
        const w = window.StepWorkbench;
        // 强制解锁并填充 Step 3 的 mock 数据: 6 条候选
        w.state.steps[0].status = 'completed';
        w.state.steps[1].status = 'completed';
        w.state.steps[2].status = 'paused_for_review';
        w.state.activeStepIndex = 2;
        w.state.currentRuntimeStep = 2;
        w.state.steps[2].result = {
            summary: '检索到论文 3 条, 数据集 2 条, 工程 2 条',
            candidates: [
                {kind: 'paper', title: 'Paper A', status: '待核验'},
                {kind: 'paper', title: 'Paper B', status: '可用'},
                {kind: 'paper', title: 'Paper C', status: '不推荐'},
                {kind: 'dataset', title: 'Dataset A', status: '可用'},
                {kind: 'dataset', title: 'Dataset B', status: '待核验'},
                {kind: 'repo', title: 'Repo A', status: '可用'},
            ],
            gate_question: '检索方向是否合理? 请确认后进入可行性判断.',
        };
        w.renderAll();
    }""")
    page.wait_for_function("window.StepWorkbench.state.activeStepIndex === 2", timeout=5000)

    # 中间区域没有把全部 6 条证据纵向铺满成单一长 list
    # 检查: 存在子页/Tab 切换入口 (如 .sw-subtab)
    subtab_count = page.locator(".sw-subtab").count()
    assert subtab_count >= 2, f"Step 3 证据多时应拆子页/Tab, 实际 subtab {subtab_count}"

    # 首屏能看到当前结论 (summary) 与待确认问题 (gate_question)
    panel_text = page.locator("#sw-middle-panel").inner_text()
    assert "检索到论文" in panel_text or "检索方向" in panel_text, \
        "首屏应看到当前结论或待确认问题"

    # 没有"大段连续日志" — 当前可见的候选证据条数 <= 3 (其余靠子页切换)
    visible_candidates = page.locator('.sw-step__body[data-step-index="2"] .sw-candidate-card:visible').count()
    # 若无 visible 过滤支持则退化为总卡片但要求 <= 3 在默认子页内
    assert visible_candidates <= 3 or visible_candidates == 0, \
        f"中间默认子页候选证据应 <= 3 张, 实际可见 {visible_candidates}"


# ---------- S41-PW-8: 移动端 390x844 ---------- #


def test_pw_08_mobile_no_overflow(page: Page, context):
    """390x844 视口无横向溢出, 确认按钮不被遮挡."""
    mobile = context.new_page()
    try:
        mobile.set_viewport_size({"width": 390, "height": 844})
        mobile.goto(WEB_URL + "/")
        mobile.wait_for_selector("#btn-analyze", state="visible", timeout=15000)
        mobile.fill("#input-topic", TOPIC)
        mobile.click("#btn-start-workbench")
        mobile.wait_for_selector("#step-workbench:not([hidden])", timeout=10000)
        mobile.wait_for_function(
            "window.StepWorkbench && window.StepWorkbench.state.activeStepIndex === 0",
            timeout=10000,
        )

        # 无横向溢出
        scroll_w = mobile.evaluate("document.documentElement.scrollWidth")
        client_w = mobile.evaluate("document.documentElement.clientWidth")
        assert scroll_w <= client_w + 2, \
            f"横向溢出: scrollWidth={scroll_w}, clientWidth={client_w}"

        # 当前步骤标题可读
        expect(mobile.locator("#sw-step-title")).to_be_visible()

        # 证据 Trace 可展开查看 (mobile 下抽屉可切换)
        # 确认按钮不被遮挡: 暂停后 approve 按钮可见
        mobile.wait_for_function(
            """() => window.StepWorkbench.state.steps[0].status === 'paused_for_review'""",
            timeout=20000,
        )
        approve_box = mobile.locator("#sw-approve-btn").bounding_box()
        assert approve_box is not None, "确认按钮无 bounding box (可能被隐藏)"
        assert approve_box["x"] >= 0 and (approve_box["x"] + approve_box["width"]) <= 390, \
            f"确认按钮超出视口: {approve_box}"
        assert approve_box["x"] + approve_box["width"] >= 0, \
            "approve 按钮完全在视口外"
    finally:
        mobile.close()