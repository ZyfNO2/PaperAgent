# PaperAgent Re2.4 前端重做 + Graph 优化 + 截图验证 SOP

> 承接：Re2.3 完工（搜索查询词 + reflexion 修复）
> **本 SOP 设计为全程无人值守执行。**
> 预计总时长：4-5 小时。
> 模型：DeepSeek (主)。

## 0. Re2.3 审核结论

Re2.3 通过。核心成果：
- Fix 6（适配器跳过）验证通过：V-CRACK repair 轮次正确跳过 4 个失败适配器
- V-MED 首次获得 feasibility=feasible(75) + review=MINOR_REVISION
- 多查询 + top_k=12 在 Run 1 验证通过

遗留问题：
- V-CRACK graph 截断：repair 后只有 GitHub 返回 1 个不相关 repo，graph 未完成
- citation_expander no-op：verified_papers 中没有 paper_id/DOI 的论文
- Fix 5 未验证：没有 case 触发到"0 accept + ≥3 候选"

## 1. 本轮目标

三件事：**前端重做 + graph 优化 + 强制截图验证**。

必须完成：

1. **前端重做**：简洁界面 + 状态机进度条 + 连通性面板 + 候选计数 + 论文列表。
2. **Graph 优化**：
   - 修复 V-CRACK graph 截断（repair 后仍 0 候选时 → blocked → final_recommendation）
   - 参考项目模式：evidence sufficiency gate（候选 < 3 → repair，repair 后仍 < 3 → blocked）
   - citation_expander：verify 后的论文需要携带 DOI/paper_id（Re2.2-fix 已修，验证）
3. **强制截图验证**：Playwright 截图覆盖全部流程，每步有截图。

不做：

- Docker / 部署。
- 新增分析节点。
- 条件边新增（只修现有边的路由）。

## 2. 模型策略

```text
FAST_JSON_PRIMARY=deepseek
LLM_PROFILE=deepseek
```

## 3. Phase 设计

### Phase 1：Graph 优化 (45min)

#### 3.1.1 修复 V-CRACK graph 截断

**问题**：repair loop 后 retrieve#2 只有 GitHub 返回 1 个不相关 repo，verify 拒绝，quality_gate 第二次判断时 n_papers=0 → 应该继续 repair 或 blocked → 但 graph 截断了。

**根因**：repair 轮次达到 MAX_REPAIR_ROUNDS=2 后，如果仍然 0 verified，quality_gate 应该路由到 `blocked`（→ final_recommendation），但当前逻辑可能没有正确处理这个分支。

**文件**：`apps/api/app/services/agents/graph/nodes/quality_gate.py`

**修改**：确保 repair_exhausted 时路由到 blocked：

```python
# 在现有 repair 判断之后
if repair_rounds >= max_repair and n_papers < 1:
    route = "blocked"  # → final_recommendation (不是 END, 是 final_recommendation)
```

确认 `_route_after_quality_gate` 和 `_route_after_review` 的 blocked 路由到 `final_recommendation` 节点（不是 END）。

#### 3.1.2 Evidence sufficiency gate

**问题**：当前 quality_gate 在 `n_papers >= 1` 时直接走 citation_expander，不检查证据是否充分。参考项目 ARS 在 `< 5 sources` 时触发 re-search。

**修改**：在 quality_gate 中增加 evidence sufficiency 检查：

```python
# 在 n_papers >= 1 的分支中，增加 sufficiency 检查
if n_papers >= 1 and not citation_done:
    # 如果候选论文 < 3 且 repair 没用完 → 再搜一轮
    if n_papers < 3 and repair_rounds < max_repair:
        route = "repair"
    else:
        route = "citation_expander"
```

**注意**：这个修改要和 Fix 5（0 accept repair）协调。Fix 5 检查的是 accept 数，这里检查的是总候选数。

#### 3.1.3 验证

重跑 V-CRACK / V-SLAM / V-MED：

| 检查项 | 通过标准 |
|---|---|
| V-CRACK graph 完成 | has_final=True（不再截断） |
| V-CRACK final_recommendation 有内容 | 有降级建议 |
| V-MED 不退化 | feasibility=feasible, review=MINOR_REVISION |
| V-SLAM graph 完成 | has_final=True |
| graph 完成 | ≥2/3 |

### Phase 2：前端重做 (90min)

#### 3.2.1 页面布局

```
┌─────────────────────────────────────────────────────────────────┐
│  PaperAgent — 题目研究助手            [历史 Case ▼]            │
│  题目: [____________________________________]  [开始研究]       │
├─────────────────────────────────────────────────────────────────┤
│  ┌─ 状态机 ─────────────────────────────────────────────────┐  │
│  │  intake▸parser▸planner▸retrieve▸filter▸verify▸gate▸     │  │
│  │  expand▸verify▸gate▸dataset▸graph▸classify▸feas▸        │  │
│  │  workpkg▸innov▸sota▸narrative▸review▸optimize▸           │  │
│  │  devils▸human▸final                                      │  │
│  │  ████████████████░░░░░░░░  15/20  当前: verify (R2)     │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌─ 连通性 ──────────────┐  ┌─ 候选 ───────────────────────┐  │
│  │ DeepSeek  ✅ 2.1s     │  │ Papers  15  (3✓ 8⚠ 4✗)     │  │
│  │ OpenAlex   ❌ 429     │  │ Repos    2  (openvslam,...)  │  │
│  │ Crossref   ✅ 1.2s    │  │ Datasets 0                  │  │
│  │ arXiv     ✅ 0.8s    │  │ Surveys  1                  │  │
│  │ GitHub    ✅ 0.5s    │  │ Expanded 45                  │  │
│  │ S2 API    ❌ N/A     │  │ Seeds    2                   │  │
│  └──────────────────────┘  └──────────────────────────────┘  │
│  ┌─ 论文列表 (实时流入) ─────────────────────────────────────┐  │
│  │ ✓ DS-SLAM: A Semantic Visual SLAM...    baseline          │  │
│  │ ⚠ Dense visual SLAM for RGB-D cameras   parallel          │  │
│  │ ✗ Deep learning observables in CFD      none             │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌─ 结果 (折叠) ────────────────────────────────────────────┐  │
│  │ [展开查看 evidence_graph / work_packages / final]         │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

#### 3.2.2 后端改动

**文件**：`apps/api/app/api/v1/research.py`

1. SSE 新增 `adapter_status` 事件（从 retrieve trace 的 per_adapter 解析）
2. SSE 新增 `candidate_count` 事件（关键节点完成后推送候选计数）
3. 新增 `GET /health/providers` 端点（检查 6 个服务连通性）

#### 3.2.3 前端重写

**文件**：`apps/web/index.html`（完全重写）

4 个面板：
1. **状态机进度条**：20 节点横向，当前高亮，已完成 ✓，进度百分比
2. **连通性面板**：6 服务 ✅/❌ + 响应时间
3. **候选计数面板**：Papers/Repos/Datasets/Surveys/Expanded/Seeds 计数
4. **论文列表**：精简卡片（标题 80 字符截断 + verdict 图标 + relation 标签），不显示 DOI/reason

结果面板默认折叠，点击展开 evidence_graph / work_packages / final。

### Phase 3：Playwright 截图验证 (60min)

**强制要求：通过多张截图验证每个流程阶段。**

#### 3.3.1 截图清单

| # | 截图文件 | 时机 | 验证内容 |
|---|---|---|---|
| 01 | `01_page_load.png` | 页面加载 | 标题 + 输入框 + 按钮 + 历史下拉 |
| 02 | `02_connectivity.png` | 点击开始前/后 | 连通性面板有 6 个服务名 |
| 03 | `03_state_machine_start.png` | 提交后 | 状态机进度条开始移动，第 1 个节点高亮 |
| 04 | `04_search_results.png` | retrieve 完成 | 连通性面板更新（adapter_status），候选面板有数据 |
| 05 | `05_filter_verify.png` | filter + verify 完成 | 候选面板 Papers 计数 > 0，论文列表有卡片 |
| 06 | `06_expansion.png` | citation_expander 完成 | 候选面板 Expanded/Seeds 有值 |
| 07 | `07_analysis.png` | 分析节点完成 | 状态机进度条到 50%+ |
| 08 | `08_complete.png` | done 事件 | 进度条 100%，"完成! 耗时 Xs" |
| 09 | `09_paper_list_full.png` | 完成后 | 论文列表完整，有 ✓/⚠/✗ 标记 |
| 10 | `10_evidence_graph.png` | 展开结果 | 证据图谱分组显示 |
| 11 | `11_work_packages.png` | 展开结果 | 工作包列表 |
| 12 | `12_final_report.png` | 展开结果 | 最终结果内容 |
| 13 | `13_history_dropdown.png` | 点击历史下拉 | 历史 case 列表 |
| 14 | `14_history_load.png` | 选择历史 case | 全部面板渲染历史数据 |
| 15 | `15_console_clean.png` | 全程 | Console 无 JS 报错（F12 截图或 Playwright errors 列表） |

#### 3.3.2 Playwright 测试脚本

**文件**：`apps/web/e2e/test_re2_4_frontend.py`

```python
class TestRe24Frontend:
    """15 项 Playwright E2E 测试，每步截图。"""

    @pytest.mark.asyncio
    async def test_01_page_load(self, page):
        """页面正常加载，无 JS 报错。"""
        page, errors = page
        await page.goto(f"{BASE_URL}/web/")
        await page.wait_for_selector("#topic", timeout=10000)
        await page.screenshot(path=str(SCREENSHOT_DIR / "01_page_load.png"))
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_02_connectivity(self, page):
        """连通性面板显示 6 个服务。"""
        page, errors = page
        await page.goto(f"{BASE_URL}/web/")
        await page.click("#startBtn")  # 触发连通性加载
        await page.wait_for_selector(".conn-item", timeout=10000)
        await page.screenshot(path=str(SCREENSHOT_DIR / "02_connectivity.png"))
        items = await page.query_selector_all(".conn-item")
        assert len(items) >= 5, f"Only {len(items)} connectivity items"

    @pytest.mark.asyncio
    async def test_03_state_machine_start(self, page):
        """提交后状态机进度条开始移动。"""
        page, errors = page
        await page.goto(f"{BASE_URL}/web/")
        await page.fill("#topic", "基于大语言模型的医学问答可信度评估方法研究")
        await page.click("#startBtn")
        await page.wait_for_selector(".state-node.current", timeout=30000)
        await page.screenshot(path=str(SCREENSHOT_DIR / "03_state_machine_start.png"))

    @pytest.mark.asyncio
    async def test_04_search_results(self, page):
        """retrieve 完成后连通性 + 候选更新。"""
        page, errors = page
        await page.goto(f"{BASE_URL}/web/")
        await page.fill("#topic", "基于大语言模型的医学问答可信度评估方法研究")
        await page.click("#startBtn")
        # 等待 adapter_status 或 search_completed 事件
        await page.wait_for_function(
            "() => document.querySelectorAll('.conn-item').length >= 5 && "
            "document.querySelector('.count-num') !== null",
            timeout=60000,
        )
        await page.screenshot(path=str(SCREENSHOT_DIR / "04_search_results.png"))

    @pytest.mark.asyncio
    async def test_05_filter_verify(self, page):
        """filter + verify 完成后论文列表有卡片。"""
        page, errors = page
        await page.goto(f"{BASE_URL}/web/")
        await page.fill("#topic", "基于大语言模型的医学问答可信度评估方法研究")
        await page.click("#startBtn")
        await page.wait_for_selector(".paper", timeout=120000)
        await page.screenshot(path=str(SCREENSHOT_DIR / "05_filter_verify.png"))

    @pytest.mark.asyncio
    async def test_06_expansion(self, page):
        """citation_expander 完成后候选有 Expanded/Seeds。"""
        page, errors = page
        await page.goto(f"{BASE_URL}/web/")
        await page.fill("#topic", "基于大语言模型的医学问答可信度评估方法研究")
        await page.click("#startBtn")
        await page.wait_for_function(
            "() => document.body.textContent.includes('Expanded') || "
            "document.body.textContent.includes('Seeds')",
            timeout=180000,
        )
        await page.screenshot(path=str(SCREENSHOT_DIR / "06_expansion.png"))

    @pytest.mark.asyncio
    async def test_07_analysis(self, page):
        """分析节点进行中。"""
        page, errors = page
        await page.goto(f"{BASE_URL}/web/")
        await page.fill("#topic", "基于大语言模型的医学问答可信度评估方法研究")
        await page.click("#startBtn")
        await page.wait_for_function(
            "() => document.querySelectorAll('.state-node.done').length >= 10",
            timeout=180000,
        )
        await page.screenshot(path=str(SCREENSHOT_DIR / "07_analysis.png"))

    @pytest.mark.asyncio
    async def test_08_complete(self, page):
        """完成事件。"""
        page, errors = page
        await page.goto(f"{BASE_URL}/web/")
        await page.fill("#topic", "基于大语言模型的医学问答可信度评估方法研究")
        await page.click("#startBtn")
        await page.wait_for_function(
            "() => document.body.textContent.includes('完成')",
            timeout=300000,
        )
        await page.screenshot(path=str(SCREENSHOT_DIR / "08_complete.png"))

    @pytest.mark.asyncio
    async def test_09_paper_list_full(self, page):
        """完成后论文列表完整。"""
        page, errors = page
        await page.goto(f"{BASE_URL}/web/")
        await page.fill("#topic", "基于大语言模型的医学问答可信度评估方法研究")
        await page.click("#startBtn")
        await page.wait_for_function(
            "() => document.body.textContent.includes('完成')",
            timeout=300000,
        )
        await page.screenshot(path=str(SCREENSHOT_DIR / "09_paper_list_full.png"))
        papers = await page.query_selector_all(".paper")
        assert len(papers) >= 1

    @pytest.mark.asyncio
    async def test_10_evidence_graph(self, page):
        """展开结果面板，证据图谱。"""
        page, errors = page
        await page.goto(f"{BASE_URL}/web/")
        await page.fill("#topic", "基于大语言模型的医学问答可信度评估方法研究")
        await page.click("#startBtn")
        await page.wait_for_function(
            "() => document.body.textContent.includes('完成')",
            timeout=300000,
        )
        # 展开结果
        await page.click("details summary")
        await page.wait_for_selector(".results-content", timeout=10000)
        await page.screenshot(path=str(SCREENSHOT_DIR / "10_evidence_graph.png"))

    @pytest.mark.asyncio
    async def test_11_work_packages(self, page):
        """工作包面板。"""
        # 复用 test_10 的流程，滚动到工作包
        # 或单独跑
        await page.screenshot(path=str(SCREENSHOT_DIR / "11_work_packages.png"))

    @pytest.mark.asyncio
    async def test_12_final_report(self, page):
        """最终结果面板。"""
        await page.screenshot(path=str(SCREENSHOT_DIR / "12_final_report.png"))

    @pytest.mark.asyncio
    async def test_13_history_dropdown(self, page):
        """历史 case 下拉。"""
        page, errors = page
        await page.goto(f"{BASE_URL}/web/")
        await page.click("#historySelect")
        await page.screenshot(path=str(SCREENSHOT_DIR / "13_history_dropdown.png"))

    @pytest.mark.asyncio
    async def test_14_history_load(self, page):
        """点击历史 case 后全部面板渲染。"""
        page, errors = page
        await page.goto(f"{BASE_URL}/web/")
        # 选择第一个历史 case
        options = await page.query_selector_all("#historySelect option")
        if len(options) > 1:
            await page.select_option("#historySelect", index=1)
            await page.wait_for_selector(".paper", timeout=15000)
            await page.screenshot(path=str(SCREENSHOT_DIR / "14_history_load.png"))
            papers = await page.query_selector_all(".paper")
            assert len(papers) >= 1

    @pytest.mark.asyncio
    async def test_15_console_clean(self, page):
        """全程 Console 无 JS 报错。"""
        page, errors = page
        await page.goto(f"{BASE_URL}/web/")
        await page.fill("#topic", "基于大语言模型的医学问答可信度评估方法研究")
        await page.click("#startBtn")
        await page.wait_for_function(
            "() => document.body.textContent.includes('完成') || "
            "document.body.textContent.includes('错误')",
            timeout=300000,
        )
        await page.screenshot(path=str(SCREENSHOT_DIR / "15_console_clean.png"))
        assert len(errors) == 0, f"Console errors: {errors}"
```

#### 3.3.3 截图审核标准

| 截图 | 必须可见的内容 |
|---|---|
| 01 | 标题 "PaperAgent" + 输入框 + 按钮 + 历史下拉 |
| 02 | 连通性面板 ≥5 行（DeepSeek/OpenAlex/Crossref/arXiv/GitHub/S2） |
| 03 | 状态机进度条，至少 1 个节点高亮（蓝色） |
| 04 | 连通性面板有 ✅/❌ 标记 + 候选面板 Papers > 0 |
| 05 | 论文列表有 ≥1 张卡片，有 ✓/⚠/✗ 标记 |
| 06 | 候选面板有 Expanded 或 Seeds > 0（或明确显示 0） |
| 07 | 状态机进度条 ≥50%，≥10 个节点完成（绿色） |
| 08 | "完成! 耗时 Xs" 可见 |
| 09 | 论文列表完整，≥3 张卡片 |
| 10 | 证据图谱分组（Baseline/Parallel/Survey/Repo） |
| 11 | 工作包列表 ≥1 个 |
| 12 | 最终结果内容（status/feasibility/review） |
| 13 | 历史 case 下拉有 ≥1 个选项 |
| 14 | 历史 case 加载后论文列表有卡片 |
| 15 | 无 JS 报错 |

### Phase 4：汇总报告 (30min)

输出 `Plan/PaperAgent_Re2.4_完工报告.md`：
1. Graph 优化改动 + 验证结果
2. 前端改动清单
3. 15 张截图索引 + 审核结果
4. 已知限制

## 4. 执行者规则

### 4.1 改动隔离

每次改代码前 `git stash create`。验证通过记录 changelog。验证失败 `git checkout` 回滚。

### 4.2 失败处理

- Phase 1 失败 → 用旧 graph 继续跑 Phase 2/3（前端不依赖 graph 修复）
- Phase 2 失败 → 用旧前端继续跑 Phase 3（用历史 case 截图）
- Phase 3 如果 graph 运行超时 → 改用历史 case 做截图 10-14
- **截图 01-03 + 13-15 不依赖 graph 运行，必须完成**

### 4.3 截图替代策略

如果实时 graph 运行太慢（>5min），部分截图可以用历史 case 模式：
- 04-09：实时运行截图（需要 graph 运行）
- 10-12：历史 case 加载后截图
- 01-03 + 13-15：不依赖 graph

## 5. 禁止事项

- 禁止跳过截图验证（15 张是硬性交付物）。
- 禁止用 code_path_verified 代替 Playwright 截图。
- 禁止引入外部依赖。
- 禁止用 VOAPI / MiniMax。
- 禁止同时改多个文件。

## 6. 交付物

代码：

- `apps/api/app/services/agents/graph/nodes/quality_gate.py` 🔧 (Phase 1: blocked 路由 + sufficiency gate)
- `apps/api/app/api/v1/research.py` 🔧 (Phase 2: SSE 事件 + health/providers)
- `apps/web/index.html` 🔧 (Phase 2: 完全重写)
- `apps/web/e2e/test_re2_4_frontend.py` 🆕 (Phase 3: 15 项 Playwright 测试)

数据：

- `tmp_re24_eval/verify/` (3-case 验证结果)
- `tmp_re24_eval/changelog.md`
- `tmp_re24_screenshots/` (≥15 张截图)

报告：

- `Plan/PaperAgent_Re2.4_完工报告.md`

## 7. 最终验收条件

| # | 条件 | 验证方式 |
|---|---|---|
| 1 | V-CRACK graph 完成 | Phase 1: has_final=True |
| 2 | evidence sufficiency gate 生效 | 候选 < 3 时触发 repair |
| 3 | 状态机进度条 | 截图 03 |
| 4 | 连通性面板 | 截图 02/04 |
| 5 | 候选计数面板 | 截图 04/06 |
| 6 | 论文列表精简卡片 | 截图 05/09 |
| 7 | 结果默认折叠 | 截图 10 |
| 8 | health/providers 端点 | API 测试 |
| 9 | SSE adapter_status 事件 | 代码检查 |
| 10 | SSE candidate_count 事件 | 代码检查 |
| 11 | Playwright ≥12/15 通过 | 测试 |
| 12 | 截图 ≥15 张 | 文件检查 |
| 13 | 截图非空白 | 文件 > 1KB |
| 14 | Console 无 JS 报错 | 截图 15 |
| 15 | 完工报告完整 | Phase 4 |
| 16 | VOAPI/MiniMax = 0 | 全程 |
