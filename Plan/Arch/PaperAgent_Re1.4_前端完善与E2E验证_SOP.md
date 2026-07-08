# PaperAgent Re1.4 前端完善与 E2E 验证 SOP

> 承接：`PaperAgent_Re1.3_完工报告.md`（25/25 验收通过）
> 本轮原则：前端能用、SSE 真能流、数据真对得上、用户真看得懂。

## 0. Re1.3 审核结论

Re1.3 已通过 25/25 验收。后端链路完整，前端代码存在但**未经真实浏览器验证**。

已完成：

- quality_filter + citation_expander + verify 批量化 + weak_papers 分离。
- SSE 端点 `GET /api/v1/research/{case_id}/stream` 代码存在。
- `apps/web/index.html` 存在（单文件 HTML+CSS+JS）。
- FastAPI 静态托管 `app.mount("/web", ...)`。
- v3 E2E：87-106s/case，3/3 graph 完成。

主要问题：

- **前端从未在浏览器中真实跑过**。Loop 4 报告写的是 "code_path_verified"，不是手动验证。
- SSE 端点是**轮询 trace.json 文件**实现的（非 LangGraph stream_mode），有 0.5s 延迟。
- 前端没有显示 evidence_graph。
- 前端没有显示 work_packages 详情。
- 前端没有显示种子论文的 relevance_score。
- 前端 `done` 事件后调用 `fetchPapers()` 拉全量 state，但论文卡片是覆盖式的，SSE 期间流入的卡片会被清空。
- SSE 的 `verify_result` 事件没有发送（SSE 端点只发 `verify_completed`，不发逐条 verdict）。
- `adapter_result` 事件没有发送（SSE 端点没有解析 retrieve 节点的 raw_results）。
- 无历史 case 列表页面。
- `.env.example` 缺少 DeepSeek 配置示例。

## 1. 本轮目标

Re1.4 做一件事：**让前端真正能用**。

必须完成：

1. **SSE 事件补全**：补发 `adapter_result`（逐适配器论文流入）和 `verify_result`（逐条 verdict），使前端能看到论文逐条流入。
2. **前端修复**：修复卡片覆盖问题、补全 evidence_graph 面板、work_packages 面板、种子论文 score 展示。
3. **历史 case 列表**：首页显示已有 case 列表，可点击查看历史结果。
4. **真实浏览器 E2E**：用浏览器打开 `http://127.0.0.1:18181/web/`，提交题目，观察全流程，确认无 JS 报错。
5. **DeepSeek 配置**：`.env.example` 补全 DeepSeek 配置项。

不做：

- Re2 的 6 个分析节点。
- 图谱可视化（D3/Cytoscape 等）——evidence_graph 用列表/树形展示即可。
- 多档位支持。
- 手动种子论文上传。

## 2. 模型策略

不变，沿用 Re1.3：

```text
FAST_JSON_PRIMARY=deepseek
STEPFUN_MODEL=step-3.7-flash
LLM_PROFILE=deepseek
```

## 3. Re1.3 遗留坑

### P0-1：SSE 事件不完整

位置：

- `apps/api/app/api/v1/research.py` — `case_stream()` 函数

现状：

SSE 端点通过轮询 `trace.json` 文件实现（0.5s 间隔），只发送 `node_complete` 类事件。以下事件**缺失或错误**：

| 应有事件 | 现状 | 问题 |
|---|---|---|
| `adapter_result` | ❌ 未发送 | retrieve 节点 trace 的 raw_results 未被解析为逐适配器事件 |
| `verify_result` | ❌ 未发送 | verify 节点 trace 只有汇总 (n_accept/n_reject)，没有逐条 verdict |
| `filter_result` | ✅ 已发送 | 但只发 kept/dropped，没有 dropped_samples |
| `expansion_started` | ✅ 已发送 | 但 seed_titles 可能为空 (trace 中 input_summary 不含 seed_titles) |
| `expansion_result` | ❌ 未发送 | 只有 expansion_completed 汇总，没有逐种子扩展结果 |
| `verify_completed` | ⚠ 不完整 | n_reject_or_weak 字段名已改为 n_weak_reject + n_reject，SSE 未同步 |
| `done` | ✅ 已发送 | |

Re1.4 要求：

- 补发 `adapter_result`：从 retrieve 节点 trace 的 `tool_calls` 字段解析。
- 补发 `verify_result`：从 verify 节点 trace 的 `output_summary` 中读取，或在 verify 节点本身记录逐条 verdict 到 trace。
- 补发 `expansion_result`：从 citation_expander 节点 trace 的 `output_summary` 中解析逐种子结果。
- 修复 `verify_completed` 字段名。
- `filter_result` 增加 `dropped_samples`。
- `expansion_started` 确保 `seed_titles` 和 `seed_scores` 从 state.json 中读取。

### P0-2：前端卡片覆盖

位置：

- `apps/web/index.html` — `fetchPapers()` 函数

现状：

SSE 期间 `verify_result` 事件逐条追加论文卡片到 `#paperList`。但 `done` 事件后调用 `fetchPapers()`，该函数用 `innerHTML = html` 覆盖了整个列表，导致 SSE 期间流入的卡片被清空替换。

Re1.4 要求：

- `fetchPapers()` 不再覆盖，而是与已有卡片合并（去重）。
- 或者：SSE 期间不追加卡片，只在 `done` 后用 `fetchPapers()` 一次性渲染。选择后者更简单。

### P0-3：前端缺少关键面板

现状：

- 没有 evidence_graph 展示。
- 没有 work_packages 详情展示（只显示节点名 + 耗时）。
- 没有种子论文 score 展示。
- 没有 weak_papers 分离展示。
- final_report 只显示 "研究完成" + 耗时，不显示实际推荐内容。

Re1.4 要求：

- 新增 evidence_graph 面板：从 `/api/v1/research/{case_id}/evidence-graph` 拉取，以分组列表展示（baseline / parallel / survey / dataset / repo）。
- work_packages 面板：从 state.json 读取 work_packages，展示每个工作包的标题 + 描述。
- 种子论文面板：展示 seed_papers 的 title + relevance_score + seed_selection_reason。
- final_report 面板：展示 final_recommendation 的完整内容（Markdown 渲染为简单 HTML）。

## 4. SSE 事件补全设计

### 4.1 修改 SSE 端点

文件：

- `apps/api/app/api/v1/research.py` — `case_stream()` 函数

修改策略：

当前 SSE 通过轮询 `trace.json` 文件实现。保留这一架构（不改为 LangGraph stream_mode，因为 graph 在后台线程跑），但增强事件解析：

```python
# 在 new_traces 循环中，为每个 trace 节点生成更细粒度的事件

if node == "retrieve":
    # 解析 raw_results，逐适配器发送
    tool_calls = t.get("tool_calls", [])
    for tc in tool_calls:
        tool = tc.get("tool", "")
        n = tc.get("n", 0)
        yield _sse_event("adapter_result", {
            "adapter": tool,
            "count": n,
        })
    # 同时发一个 search_completed
    total = sum(tc.get("n", 0) for tc in tool_calls)
    yield _sse_event("search_completed", {"total_raw": total})

elif node == "quality_filter":
    yield _sse_event("filter_result", {
        "kept": output_summary.get("kept", 0),
        "dropped": output_summary.get("dropped", 0),
        "pre_filter_keep": output_summary.get("pre_filter_keep", 0),
        "pre_filter_drop": output_summary.get("pre_filter_drop", 0),
        "llm_judged": output_summary.get("llm_judged", 0),
    })

elif node == "verify":
    round_n = t.get("input_summary", {}).get("round", 1)
    n_accept = output_summary.get("n_accept", 0)
    n_weak = output_summary.get("n_weak_reject", 0)
    n_reject = output_summary.get("n_reject", 0)
    yield _sse_event("verify_completed", {
        "accepted": n_accept,
        "weak_reject": n_weak,
        "rejected": n_reject,
        "round": round_n,
    })
    # 逐条 verdict 从 state.json 读取 (在 done 后才有完整数据)
    # SSE 期间无法逐条发送 (trace 不含逐条 verdict)
    # → 改为在 done 事件后一次性发送全部论文列表

elif node == "citation_expander":
    # 读取 state.json 获取种子详情
    state_path = _case_dir(case_id) / "state.json"
    if state_path.exists():
        st = json.loads(state_path.read_text(encoding="utf-8"))
        seeds = st.get("seed_papers") or []
        yield _sse_event("expansion_started", {
            "n_seeds": len(seeds),
            "seed_titles": [s.get("title", "")[:80] for s in seeds],
            "seed_scores": [s.get("relevance_score", 0) for s in seeds],
        })
    yield _sse_event("expansion_completed", {
        "total_expanded": output_summary.get("n_expanded", 0),
        "n_surveys": output_summary.get("n_surveys", 0),
        "n_repos": output_summary.get("n_repos", 0),
    })
```

### 4.2 done 事件增强

`done` 事件后，前端调用 `/api/v1/research/{case_id}/state` 拉取完整 state，一次性渲染所有面板。

```python
yield _sse_event("done", {
    "case_id": case_id,
    "total_elapsed_s": elapsed,
    "total_events": sent_events,
    "n_verified": len(st.get("verified_papers") or []),
    "n_weak": len(st.get("weak_papers") or []),
    "n_expanded": len(st.get("expanded_papers") or []),
    "n_work_packages": len(st.get("work_packages") or []),
    "n_baseline": len(st.get("baseline_candidates") or []),
})
```

## 5. 前端修改设计

### 5.1 页面布局

```
┌──────────────────────────────────────────────────────────────┐
│  PaperAgent — 题目研究助手                    [历史 Case ▼]  │
│                                                              │
│  题目: [____________________________________________]        │
│                                              [开始研究]      │
│                                                              │
│  ── 进度 ────────────────────────────────────────────        │
│  ████████████████░░░░ 75% (87s) — verify 第二轮             │
│                                                              │
│  ── 搜索阶段 ──────────────────────────────────────         │
│  ✅ arxiv     8 篇                                           │
│  ✅ openalex  8 篇                                           │
│  ✅ crossref  8 篇                                           │
│  ✅ github    8 篇                                           │
│  ✅ 质量过滤: 保留 24 篇, 丢弃 8 篇 (pre_filter: 24 直留,    │
│     0 丢弃, 8 篇 LLM 判断)                                   │
│  ✅ 第一轮验证: 3 accept, 8 weak_reject, 13 reject           │
│                                                              │
│  ── 引文扩展 ──────────────────────────────────────         │
│  种子 1: Large language models encode... (score=9, top1)     │
│  种子 2: Performance of ChatGPT on USMLE... (score=7, top2)  │
│  ✅ 扩展完成: 59 篇新论文, 5 篇综述, 2 个 repo               │
│  ✅ 第二轮验证: 6 accept, 31 weak_reject, 22 reject          │
│                                                              │
│  ── 论文列表 ──────────────────────────────────────         │
│  [Accept 9] [Weak 39] [Reject 35]  ← 筛选 tab               │
│  ┌────────────────────────────────────────────────────┐     │
│  │ ✓ Large language models encode clinical knowledge   │     │
│  │   baseline · DOI: 10.1038/s41586-023-06291-2        │     │
│  │   hit: LLM, clinical, medical                       │     │
│  │   "The paper is a real academic paper..."            │     │
│  ├────────────────────────────────────────────────────┤     │
│  │ ⚠ ChatGPT for good? On opportunities...             │     │
│  │   survey · weak_reject                              │     │
│  │   hit: LLM, education                               │     │
│  └────────────────────────────────────────────────────┘     │
│                                                              │
│  ── 证据图谱 ──────────────────────────────────────         │
│  Baseline (9):  Large language models encode..., ...        │
│  Parallel (0):  (无)                                         │
│  Survey (5):    A Survey on Evaluation of LLMs, ...         │
│  Dataset (0):   (无)                                         │
│  Repo (2):      github.com/michiyasunaga/dragon, ...         │
│                                                              │
│  ── 工作包 ────────────────────────────────────────         │
│  1. 医学问答置信度校准与可信度评估框架                        │
│  2. 基于思维链推理的医学问答可信度增强                        │
│  3. 医学问答可信度评估的基准数据集构建                        │
│                                                              │
│  ── 最终结果 ──────────────────────────────────────         │
│  [final_recommendation 完整内容]                              │
└──────────────────────────────────────────────────────────────┘
```

### 5.2 前端修改清单

| # | 修改 | 说明 |
|---|---|---|
| 1 | 进度条 | 根据 node_complete 事件计算进度百分比 (已完成节点 / 17) |
| 2 | 论文列表 tab 筛选 | Accept / Weak / Reject 三个 tab，点击切换显示 |
| 3 | 论文卡片增强 | 显示 DOI、relation_to_topic、reason |
| 4 | 种子论文 score 展示 | expansion_started 事件的 seed_scores 渲染 |
| 5 | evidence_graph 面板 | done 后从 state.json 拉取 evidence_graph，按 role 分组列表 |
| 6 | work_packages 面板 | done 后从 state.json 拉取 work_packages，逐个展示 |
| 7 | final_recommendation 面板 | done 后从 state.json 拉取 final_recommendation 完整展示 |
| 8 | 历史 case 列表 | 首页下拉菜单，从 `GET /api/v1/research/` 拉取已有 case 列表 |
| 9 | 卡片覆盖修复 | done 后不再调 fetchPapers() 覆盖；改为在 done 事件中一次性渲染全部面板 |
| 10 | adapter_result 展示 | 逐适配器流入显示 (已有但需确认事件正确发送) |
| 11 | weak_papers 分离展示 | 论文列表中 accept 和 weak_reject 分开展示 |
| 12 | 错误处理增强 | SSE error 事件显示具体错误信息 |

### 5.3 历史 Case 查看

点击首页 "历史 Case" 下拉：

```javascript
function loadHistory() {
    fetch('/api/v1/research/').then(r => r.json()).then(d => {
        // d.cases = [{case_id, status, mtime}, ...]
        var html = '';
        for (var c of d.cases) {
            html += '<option value="'+c.case_id+'">'+c.case_id+' ('+c.status+')</option>';
        }
        document.getElementById('historySelect').innerHTML = html;
    });
}

function viewCase(caseId) {
    // 直接拉取 state.json + evidence_graph.json 渲染全部面板
    fetchStateAndRender(caseId);
}
```

### 5.4 技术约束

- **不引入任何外部依赖**——纯 HTML + CSS + JS。
- 文件大小控制在 800 行以内（含 CSS + JS）。
- CSS 用 flexbox，不用 grid（兼容性更好）。
- 不用模板引擎——直接字符串拼接。
- Markdown 渲染：简单的 `\n` → `<br>` + `**text**` → `<strong>text</strong>`，不引入 marked.js。

## 6. .env.example 补全

```env
# === LLM Provider ===
# Primary: stepfun (step-3.7-flash, RPM=10)
# Alternative: deepseek (faster, 87-106s/case in Re1.3 v3)
FAST_JSON_PRIMARY=deepseek
LLM_PROFILE=deepseek

# === StepFun ===
STEPFUN_API_KEY=your_stepfun_key
STEPFUN_MODEL=step-3.7-flash
STEPFUN_BASE_URL=https://api.stepfun.com/v1
STEPFUN_RPM_LIMIT=10

# === DeepSeek ===
DEEPSEEK_API_KEY=your_deepseek_key
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# === Semantic Scholar (optional, for citation expansion) ===
# S2_API_KEY=your_s2_api_key

# === Graph config ===
PAPERAGENT_MAX_REPAIR_ROUNDS=2
VERIFIER_BATCH_SIZE=8
VERIFIER_MAX_WORKERS=4
```

## 7. 测试要求

### Loop 0：静态审计

- `apps/web/index.html` 存在且无外部依赖。
- SSE 端点发送 `adapter_result`、`filter_result`、`verify_completed`、`expansion_started`、`expansion_completed`、`node_complete`、`done` 事件。
- `verify_completed` 事件包含 `accepted`、`weak_reject`、`rejected` 字段（不是旧的 `n_reject_or_weak`）。
- `.env.example` 包含 DeepSeek 配置。
- 前端代码无 `fetchPapers()` 覆盖问题。

### Loop 1：SSE 事件验证

用 `httpx` 连接 SSE 端点，验证事件序列：

```
search_started → adapter_result (×4) → search_completed →
filter_result → verify_completed (round=1) →
expansion_started → expansion_completed →
verify_completed (round=2) →
node_complete (×N) → done
```

通过条件：

- `adapter_result` 的 count 与 retrieve trace 的 tool_calls 一致。
- `verify_completed` 的 accepted/weak_reject/rejected 与 state.json 一致。
- `expansion_started` 的 seed_titles 和 seed_scores 非空（当有种子时）。
- `done` 事件包含 n_verified、n_weak、n_expanded、n_work_packages。

### Loop 2：Playwright 浏览器 E2E + 截图验证

**必须用 Playwright 自动化测试，返回真实截图作为验证产物**。

Playwright 已在 `pyproject.toml` 的 dev 依赖中 (`playwright>=1.40`)。

测试脚本：

- `apps/web/e2e/test_re1_4_frontend.py` 🆕

#### 测试前置

```bash
# 确保浏览器已安装
python -m playwright install chromium

# 确保有一个已完成的 case 用于历史加载测试
# (可复用 tmp_re13_eval/re13-medical-llm-v3 的 case_id)
```

#### 测试流程

```python
# apps/web/e2e/test_re1_4_frontend.py

"""Re1.4 Playwright E2E — 截图验证前端全流程。

运行方式:
    # 先启动 API 服务
    cd apps/api && python -m uvicorn app.main:app --host 0.0.0.0 --port 18181 &
    
    # 再运行测试
    python -m pytest apps/web/e2e/test_re1_4_frontend.py -s --tb=short
"""

import asyncio
import os
import time
from pathlib import Path

import pytest
from playwright.async_api import async_playwright

BASE_URL = "http://127.0.0.1:18181"
SCREENSHOT_DIR = Path("tmp_re14_screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)

# 用于历史加载测试的已有 case
HISTORY_CASE_ID = os.environ.get("RE14_HISTORY_CASE", "re13-medical-llm-v3")


@pytest.fixture
async def page():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="zh-CN",
        )
        page = await context.new_page()
        # 捕获 console error
        errors = []
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: errors.append(str(err)))
        yield page, errors
        await browser.close()


class TestFrontendE2E:
    """17 项 Playwright E2E 测试，每步截图。"""

    @pytest.mark.asyncio
    async def test_01_page_loads(self, page):
        """页面正常加载，无 JS 报错。"""
        page, errors = page
        await page.goto(f"{BASE_URL}/web/")
        await page.wait_for_selector("h1", timeout=10000)
        await page.screenshot(path=str(SCREENSHOT_DIR / "01_page_load.png"))
        assert len(errors) == 0, f"Console errors: {errors}"
        assert await page.title() == "PaperAgent — 题目研究助手"

    @pytest.mark.asyncio
    async def test_02_topic_input(self, page):
        """输入框正常。"""
        page, errors = page
        await page.goto(f"{BASE_URL}/web/")
        await page.fill("#topic", "基于大语言模型的医学问答可信度评估方法研究")
        await page.screenshot(path=str(SCREENSHOT_DIR / "02_topic_input.png"))
        value = await page.input_value("#topic")
        assert "医学问答" in value

    @pytest.mark.asyncio
    async def test_03_submit_and_progress(self, page):
        """点击开始研究，进度条出现。"""
        page, errors = page
        await page.goto(f"{BASE_URL}/web/")
        await page.fill("#topic", "基于大语言模型的医学问答可信度评估方法研究")
        await page.click("#startBtn")
        # 等待进度条或状态栏出现
        await page.wait_for_selector(".status-bar:not(.hidden)", timeout=10000)
        await page.screenshot(path=str(SCREENSHOT_DIR / "03_submit_progress.png"))
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_04_adapter_results(self, page):
        """适配器结果逐条显示 (arxiv/openalex/crossref/github)。"""
        page, errors = page
        await page.goto(f"{BASE_URL}/web/")
        await page.fill("#topic", "基于大语言模型的医学问答可信度评估方法研究")
        await page.click("#startBtn")
        # 等待搜索阶段出现
        await page.wait_for_selector("#searchSection:not(.hidden)", timeout=30000)
        # 等待至少 1 个 adapter-row 出现
        await page.wait_for_selector(".adapter-row", timeout=30000)
        await page.screenshot(path=str(SCREENSHOT_DIR / "04_adapter_results.png"))
        rows = await page.query_selector_all(".adapter-row")
        assert len(rows) >= 1, "No adapter rows found"

    @pytest.mark.asyncio
    async def test_05_filter_result(self, page):
        """质量过滤结果显示。"""
        page, errors = page
        await page.goto(f"{BASE_URL}/web/")
        await page.fill("#topic", "基于大语言模型的医学问答可信度评估方法研究")
        await page.click("#startBtn")
        await page.wait_for_selector("#filterSection:not(.hidden)", timeout=60000)
        await page.screenshot(path=str(SCREENSHOT_DIR / "05_filter_result.png"))
        text = await page.text_content("#filterResult")
        assert "保留" in text or "丢弃" in text

    @pytest.mark.asyncio
    async def test_06_verify_round1(self, page):
        """第一轮验证: accept/weak_reject/reject。"""
        page, errors = page
        await page.goto(f"{BASE_URL}/web/")
        await page.fill("#topic", "基于大语言模型的医学问答可信度评估方法研究")
        await page.click("#startBtn")
        # 等待验证完成事件
        await page.wait_for_function(
            "() => document.body.textContent.includes('accept')",
            timeout=120000,
        )
        await page.screenshot(path=str(SCREENSHOT_DIR / "06_verify_round1.png"))

    @pytest.mark.asyncio
    async def test_07_expansion_seeds(self, page):
        """种子论文 + score 显示。"""
        page, errors = page
        await page.goto(f"{BASE_URL}/web/")
        await page.fill("#topic", "基于大语言模型的医学问答可信度评估方法研究")
        await page.click("#startBtn")
        await page.wait_for_selector("#expansionSection:not(.hidden)", timeout=120000)
        await page.screenshot(path=str(SCREENSHOT_DIR / "07_expansion_seeds.png"))
        # 检查种子 score 是否渲染
        text = await page.text_content("#expansionResults")
        assert "score" in text.lower() or "种子" in text

    @pytest.mark.asyncio
    async def test_08_expansion_completed(self, page):
        """扩展完成: 篇数/综述/repo。"""
        page, errors = page
        await page.goto(f"{BASE_URL}/web/")
        await page.fill("#topic", "基于大语言模型的医学问答可信度评估方法研究")
        await page.click("#startBtn")
        await page.wait_for_function(
            "() => document.body.textContent.includes('扩展完成')",
            timeout=180000,
        )
        await page.screenshot(path=str(SCREENSHOT_DIR / "08_expansion_completed.png"))

    @pytest.mark.asyncio
    async def test_09_verify_round2(self, page):
        """第二轮验证结果显示。"""
        page, errors = page
        await page.goto(f"{BASE_URL}/web/")
        await page.fill("#topic", "基于大语言模型的医学问答可信度评估方法研究")
        await page.click("#startBtn")
        await page.wait_for_function(
            "() => document.body.textContent.includes('round') || "
            "document.body.textContent.includes('第二轮')",
            timeout=180000,
        )
        await page.screenshot(path=str(SCREENSHOT_DIR / "09_verify_round2.png"))

    @pytest.mark.asyncio
    async def test_10_analysis_nodes(self, page):
        """后续节点逐个完成显示。"""
        page, errors = page
        await page.goto(f"{BASE_URL}/web/")
        await page.fill("#topic", "基于大语言模型的医学问答可信度评估方法研究")
        await page.click("#startBtn")
        await page.wait_for_selector("#analysisSection:not(.hidden)", timeout=180000)
        await page.wait_for_selector(".node-status", timeout=30000)
        await page.screenshot(path=str(SCREENSHOT_DIR / "10_analysis_nodes.png"))
        nodes = await page.query_selector_all(".node-status")
        assert len(nodes) >= 1

    @pytest.mark.asyncio
    async def test_11_complete(self, page):
        """等待完成: "完成! 耗时 Xs"。"""
        page, errors = page
        await page.goto(f"{BASE_URL}/web/")
        await page.fill("#topic", "基于大语言模型的医学问答可信度评估方法研究")
        await page.click("#startBtn")
        await page.wait_for_function(
            "() => document.body.textContent.includes('完成')",
            timeout=300000,  # 5 min timeout
        )
        await page.screenshot(path=str(SCREENSHOT_DIR / "11_complete.png"))

    @pytest.mark.asyncio
    async def test_12_paper_list(self, page):
        """论文列表: accept + weak 卡片, 有 DOI/relation/reason。"""
        page, errors = page
        await page.goto(f"{BASE_URL}/web/")
        await page.fill("#topic", "基于大语言模型的医学问答可信度评估方法研究")
        await page.click("#startBtn")
        await page.wait_for_function(
            "() => document.body.textContent.includes('完成')",
            timeout=300000,
        )
        await page.screenshot(path=str(SCREENSHOT_DIR / "12_paper_list.png"))
        cards = await page.query_selector_all(".paper-card")
        assert len(cards) >= 1, "No paper cards found"

    @pytest.mark.asyncio
    async def test_13_evidence_graph(self, page):
        """证据图谱面板: 分组显示 baseline/parallel/survey/repo。"""
        page, errors = page
        await page.goto(f"{BASE_URL}/web/")
        await page.fill("#topic", "基于大语言模型的医学问答可信度评估方法研究")
        await page.click("#startBtn")
        await page.wait_for_function(
            "() => document.body.textContent.includes('完成')",
            timeout=300000,
        )
        await page.screenshot(path=str(SCREENSHOT_DIR / "13_evidence_graph.png"))
        # 检查 evidence graph 面板存在且非空
        text = await page.text_content("body")
        assert "Baseline" in text or "baseline" in text.lower()

    @pytest.mark.asyncio
    async def test_14_work_packages(self, page):
        """工作包面板: 标题和描述。"""
        page, errors = page
        await page.goto(f"{BASE_URL}/web/")
        await page.fill("#topic", "基于大语言模型的医学问答可信度评估方法研究")
        await page.click("#startBtn")
        await page.wait_for_function(
            "() => document.body.textContent.includes('完成')",
            timeout=300000,
        )
        await page.screenshot(path=str(SCREENSHOT_DIR / "14_work_packages.png"))

    @pytest.mark.asyncio
    async def test_15_final_report(self, page):
        """最终结果面板: final_recommendation 内容。"""
        page, errors = page
        await page.goto(f"{BASE_URL}/web/")
        await page.fill("#topic", "基于大语言模型的医学问答可信度评估方法研究")
        await page.click("#startBtn")
        await page.wait_for_function(
            "() => document.body.textContent.includes('完成')",
            timeout=300000,
        )
        await page.screenshot(path=str(SCREENSHOT_DIR / "15_final_report.png"))

    @pytest.mark.asyncio
    async def test_16_history_dropdown(self, page):
        """历史 Case 下拉显示已有 case 列表。"""
        page, errors = page
        await page.goto(f"{BASE_URL}/web/")
        # 触发历史加载 (可能需要点击下拉)
        await page.wait_for_selector("#historySelect", timeout=10000)
        # 如果有 options 则验证
        options = await page.query_selector_all("#historySelect option")
        await page.screenshot(path=str(SCREENSHOT_DIR / "16_history_dropdown.png"))
        # 可能没有历史 case (首次运行), 不强制 assert
        if len(options) > 0:
            assert len(options) >= 1

    @pytest.mark.asyncio
    async def test_17_history_case_load(self, page):
        """点击历史 case, 全部面板渲染。"""
        page, errors = page
        await page.goto(f"{BASE_URL}/web/")
        await page.wait_for_selector("#historySelect", timeout=10000)
        # 选择历史 case
        await page.select_option("#historySelect", HISTORY_CASE_ID)
        await page.wait_for_selector(".paper-card", timeout=15000)
        await page.screenshot(path=str(SCREENSHOT_DIR / "17_history_case_load.png"))
        # 验证面板渲染
        cards = await page.query_selector_all(".paper-card")
        assert len(cards) >= 1, "No paper cards rendered for history case"
```

#### 截图产物

测试运行后，截图保存在 `tmp_re14_screenshots/` 目录：

```
tmp_re14_screenshots/
├── 01_page_load.png
├── 02_topic_input.png
├── 03_submit_progress.png
├── 04_adapter_results.png
├── 05_filter_result.png
├── 06_verify_round1.png
├── 07_expansion_seeds.png
├── 08_expansion_completed.png
├── 09_verify_round2.png
├── 10_analysis_nodes.png
├── 11_complete.png
├── 12_paper_list.png
├── 13_evidence_graph.png
├── 14_work_packages.png
├── 15_final_report.png
├── 16_history_dropdown.png
└── 17_history_case_load.png
```

#### 通过条件

- 17/17 测试通过 (或带已知 skip 的说明)。
- `tmp_re14_screenshots/` 下有 17 张截图。
- 每张截图非空白（文件大小 > 1KB）。
- 完工报告中必须附关键截图（至少 01, 07, 11, 12, 13, 14, 17）。
- 浏览器 Console errors 列表为空。

#### 截图审核标准

执行 AI 提交完工报告时，SOP AI 检查以下截图：

| 截图 | 检查点 |
|---|---|
| 01_page_load | 页面有标题、输入框、开始按钮 |
| 04_adapter_results | 至少 1 行 adapter-row，显示 adapter 名 + 篇数 |
| 07_expansion_seeds | 种子论文标题 + score 可见 |
| 11_complete | 显示 "完成! 耗时 Xs" |
| 12_paper_list | 论文卡片 ≥ 1，有 verdict 标记 (✓/⚠/✗) |
| 13_evidence_graph | 有 Baseline/Parallel/Survey/Repo 分组 |
| 14_work_packages | 有工作包标题 |
| 17_history_case_load | 历史 case 的论文列表正确渲染 |

### Loop 3：历史 Case 加载（Playwright + 截图）

用 Playwright 自动化验证历史 case 加载（已包含在 Loop 2 test_17 中，此处做数据一致性断言）。

测试脚本：

```python
# apps/web/e2e/test_re1_4_history.py

class TestHistoryCaseLoad:
    """历史 case 加载 — 数据一致性验证。"""

    @pytest.mark.asyncio
    async def test_history_case_papers_match_state(self, page):
        """论文列表与 state.json 中的 verified_papers 一致。"""
        page, errors = page
        await page.goto(f"{BASE_URL}/web/")
        await page.wait_for_selector("#historySelect option", timeout=10000)
        await page.select_option("#historySelect", HISTORY_CASE_ID)
        await page.wait_for_selector(".paper-card", timeout=15000)
        await page.screenshot(path=str(SCREENSHOT_DIR / "loop3_papers.png"))

        # 从 API 拉取 state.json 做对比
        import httpx
        resp = httpx.get(f"{BASE_URL}/api/v1/research/{HISTORY_CASE_ID}/state")
        state = resp.json()
        verified = state.get("verified_papers") or []
        weak = state.get("weak_papers") or []

        # 前端渲染的卡片数应与 state 中 verified + weak 一致
        cards = await page.query_selector_all(".paper-card")
        assert len(cards) >= len(verified), \
            f"cards={len(cards)} < verified_papers={len(verified)}"

    @pytest.mark.asyncio
    async def test_history_case_evidence_graph_matches(self, page):
        """证据图谱与 evidence_graph.json 一致。"""
        page, errors = page
        await page.goto(f"{BASE_URL}/web/")
        await page.wait_for_selector("#historySelect option", timeout=10000)
        await page.select_option("#historySelect", HISTORY_CASE_ID)
        await page.wait_for_selector(".paper-card", timeout=15000)
        await page.screenshot(path=str(SCREENSHOT_DIR / "loop3_evidence_graph.png"))

        import httpx
        resp = httpx.get(f"{BASE_URL}/api/v1/research/{HISTORY_CASE_ID}/evidence-graph")
        eg = resp.json()
        nodes = eg.get("nodes") or []

        text = await page.text_content("body")
        # 至少 1 个 node 的 title 出现在页面中
        matched = sum(1 for n in nodes if n.get("title", "")[:30] in text)
        assert matched >= 1, f"No evidence graph nodes found in page text"

    @pytest.mark.asyncio
    async def test_history_case_work_packages_match(self, page):
        """工作包与 state.json 中的 work_packages 一致。"""
        page, errors = page
        await page.goto(f"{BASE_URL}/web/")
        await page.wait_for_selector("#historySelect option", timeout=10000)
        await page.select_option("#historySelect", HISTORY_CASE_ID)
        await page.wait_for_selector(".paper-card", timeout=15000)
        await page.screenshot(path=str(SCREENSHOT_DIR / "loop3_work_packages.png"))

        import httpx
        resp = httpx.get(f"{BASE_URL}/api/v1/research/{HISTORY_CASE_ID}/state")
        state = resp.json()
        wps = state.get("work_packages") or []

        if wps:
            text = await page.text_content("body")
            # 至少 1 个工作包标题出现在页面中
            matched = sum(1 for wp in wps if wp.get("title", "")[:20] in text)
            assert matched >= 1, f"No work packages found in page text"
```

通过条件：

- 论文列表卡片数 ≥ state.json 中 verified_papers 数。
- 证据图谱至少 1 个 node title 出现在页面。
- 工作包至少 1 个 title 出现在页面（当 state 有 work_packages 时）。
- 3 张截图已保存。

## 8. 禁止事项

- 禁止引入 npm/构建工具/外部 CDN。
- 禁止引入 JS 框架（React/Vue/jQuery 等）。
- 禁止用 code_path_verified 代替 Playwright 截图验证。
- 禁止提交无截图的完工报告——Loop 2 的 17 张截图是硬性交付物。
- 禁止 SSE 阻塞后端 graph 执行。
- 禁止 `fetchPapers()` 覆盖已有卡片。
- 禁止在 Re1.4 做 Re2 的 6 个分析节点。

## 9. 交付物

代码：

- `apps/web/index.html` 🔧 (重写前端)
- `apps/api/app/api/v1/research.py` 🔧 (SSE 事件补全)
- `.env.example` 🔧 (DeepSeek 配置)

测试：

- `apps/api/tests/test_re1_4_sse_events.py` 🆕 (SSE 事件验证)
- `apps/web/e2e/test_re1_4_frontend.py` 🆕 (Playwright 17 项 E2E + 截图)
- `apps/web/e2e/test_re1_4_history.py` 🆕 (Playwright 历史 case 数据一致性)

截图产物：

- `tmp_re14_screenshots/01_page_load.png` ~ `17_history_case_load.png` (17+3=20 张)

报告：

- `Plan/PaperAgent_Re1.4_Loop0_静态审计.md`
- `Plan/PaperAgent_Re1.4_Loop1_SSE事件验证.md`
- `Plan/PaperAgent_Re1.4_Loop2_浏览器E2E.md` (含截图引用)
- `Plan/PaperAgent_Re1.4_Loop3_历史Case加载.md` (含截图引用)
- `Plan/PaperAgent_Re1.4_完工报告.md`

## 10. 最终验收条件

| # | 条件 | 验证方式 |
|---|---|---|
| 1 | SSE 发送 adapter_result 事件 | Loop 1 验证 |
| 2 | SSE verify_completed 含 accepted/weak_reject/rejected | Loop 1 验证 |
| 3 | SSE expansion_started 含 seed_titles + seed_scores | Loop 1 验证 |
| 4 | SSE done 含 n_verified/n_weak/n_expanded/n_work_packages | Loop 1 验证 |
| 5 | 前端进度条显示百分比 | Loop 2 Playwright 截图 03 |
| 6 | 前端论文列表有 tab 筛选 (accept/weak/reject) | Loop 2 Playwright 截图 12 |
| 7 | 前端论文卡片显示 DOI + relation + reason | Loop 2 Playwright 截图 12 |
| 8 | 前端种子论文显示 score | Loop 2 Playwright 截图 07 |
| 9 | 前端 evidence_graph 面板分组展示 | Loop 2 Playwright 截图 13 |
| 10 | 前端 work_packages 面板展示 | Loop 2 Playwright 截图 14 |
| 11 | 前端 final_recommendation 面板展示 | Loop 2 Playwright 截图 15 |
| 12 | 前端历史 case 列表可用 | Loop 2 Playwright 截图 16 |
| 13 | 点击历史 case 可查看全部面板 | Loop 3 Playwright 截图 + 数据一致性断言 |
| 14 | 前端无外部依赖 | 静态检查 |
| 15 | 浏览器 Console 无 JS 报错 | Loop 2 Playwright errors 列表为空 |
| 16 | fetchPapers 不覆盖已有卡片 | 代码检查 |
| 17 | .env.example 含 DeepSeek 配置 | 静态检查 |
| 18 | Playwright 17/17 通过 | pytest 结果 |
| 19 | tmp_re14_screenshots/ 有 ≥17 张截图 | 文件检查 |
| 20 | 截图非空白 (文件 > 1KB) | 文件检查 |
| 21 | 完工报告附关键截图 (01/07/11/12/13/14/17) | 报告检查 |

## 11. 自测与验证 SOP

> **执行者必读**：Playwright 测试通过后，必须检查截图质量。截图是完工报告的硬性交付物。

### 12.1 角色定义

| 角色 | 职责 | 执行时机 |
|---|---|---|
| **执行 AI** | 编写前端代码 + Playwright 测试，运行后检查截图 | 代码完成后 |
| **SOP AI** | 审核截图内容，确认页面渲染正确 | 执行 AI 完成后 |

### 12.2 截图验证清单

执行 AI 提交完工报告前，必须逐项检查截图：

- [ ] `tmp_re14_screenshots/` 目录存在。
- [ ] 至少 17 张截图文件存在（01-17）。
- [ ] 每张截图文件 > 1KB（非空白）。
- [ ] 截图 01: 页面有标题 + 输入框 + 按钮。
- [ ] 截图 04: 至少 1 行 adapter 结果。
- [ ] 截图 07: 种子论文 + score 可见。
- [ ] 截图 11: "完成" 字样可见。
- [ ] 截图 12: 论文卡片 ≥ 1，有 verdict 标记。
- [ ] 截图 13: evidence_graph 面板有分组内容。
- [ ] 截图 14: work_packages 面板有标题。
- [ ] 截图 17: 历史 case 论文列表正确渲染。
- [ ] Playwright 测试输出中 Console errors 为空。
- [ ] 完工报告中附有上述关键截图。

### 12.3 截图审核标准

SOP AI 检查截图时，用 `analyze_multimedia` 工具验证：

```
对截图 01_page_load.png: "这个页面是否有标题 'PaperAgent'、一个输入框、一个按钮？是否有 JS 错误痕迹？"
对截图 07_expansion_seeds.png: "这个页面是否显示了种子论文标题和 score？"
对截图 12_paper_list.png: "这个页面是否有论文卡片，每张卡片有 verdict 标记（accept/weak_reject）？"
对截图 13_evidence_graph.png: "这个页面是否有证据图谱面板，按 baseline/parallel/survey/repo 分组？"
```

### 12.4 自测流程

```
执行 AI 编写前端 + Playwright 测试
    │
    ▼
启动 API 服务 (uvicorn)
    │
    ▼
运行 Playwright 测试 (pytest apps/web/e2e/ -s)
    │
    ├── 测试失败 → 修复代码 → 重跑
    │
    └── 测试通过 → 检查截图质量 (§12.2)
            │
            ├── 截图问题 → 修复前端 → 重跑
            │
            └── 截图 OK → 提交完工报告 + 截图
                    │
                    ▼
SOP AI 用 analyze_multimedia 审核截图
    │
    ├── 审核通过 → Re1.4 验收通过
    │
    └── 审核有问题 → 执行 AI 修复
```

Re1.4 通过后进入 Re2。Re2 做：

- 6 个分析节点 (feasibility_assessor / innovation_extractor / sota_matcher / narrative_builder / optimization_advisor / devils_advocate)
- 前端从论文列表升级为分析报告展示
- 引文扩展结果接入 evidence_graph 可视化
- 档位分层
