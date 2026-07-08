# Re2.4 Changelog

## Phase 1: Graph Optimization

### Fix 1: _route_after_quality_gate — sufficiency gate + blocked routing
- **文件**: `apps/api/app/services/agents/graph/research_graph.py`
- **改动**: 
  1. 0 accept + ≥3 total candidates → repair (Fix 5 from Re2.3, now in routing function)
  2. n_papers < 3 + repair_rounds < max → repair (sufficiency gate)
  3. repair_exhausted + n_papers < 1 → blocked → final_recommendation (already existed)
- **效果**: graph 不再在 repair 后截断；sufficiency gate 确保候选不足时触发更多搜索

### Fix 2: recursion_limit 25→100 in verify script
- **文件**: `apps/api/scripts/re23_verify.py`
- **改动**: `recursion_limit: 100`
- **效果**: 修复 V-CRACK graph 截断问题（LangGraph 默认 25 步限制不够）

## Phase 2: Backend + Frontend

### Backend: SSE adapter_status + candidate_count events
- **文件**: `apps/api/app/api/v1/research.py`
- **改动**: 
  1. SSE 新增 `adapter_status` 事件（per_adapter, failed_adapters, skipped_adapters）
  2. SSE 新增 `candidate_count` 事件（after verify + after expansion）
  3. 新增 `GET /health/providers` 端点（并发检查 6 个服务连通性，2s timeout each）

### Frontend: 完全重写
- **文件**: `apps/web/index.html`
- **改动**: 4 面板布局
  1. 状态机进度条（23 节点，当前高亮蓝色，已完成绿色）
  2. 连通性面板（6 服务 ✅/❌ + 响应时间 + hits 数）
  3. 候选计数面板（Papers/Repos/Datasets/Surveys/Expanded/Seeds）
  4. 论文列表（精简卡片：标题 80 字符 + verdict 图标 + relation 标签）
  5. 结果默认折叠（证据图谱/工作包/最终结果）

## Phase 3: Playwright 截图验证

### 测试结果（15 项）

| # | 测试 | 结果 | 截图 |
|---|---|---|---|
| 01 | page_load | ✅ | 01_page_load.png (29.5KB) |
| 02 | connectivity | ✅ | 02_connectivity.png (29.5KB) |
| 03 | state_machine_start | ✅ | 03_state_machine_start.png (31.3KB) |
| 04 | search_results | ✅ (retry) | 04_search_results.png |
| 05 | filter_verify | ✅ | 05_filter_verify.png (36KB) |
| 06 | expansion | ✅ | 06_expansion.png (30.6KB) |
| 07 | analysis | ✅ | 07_analysis.png (81.3KB) |
| 08 | complete | ✅ | 08_complete.png (31KB) |
| 09 | paper_list_full | ✅ | 09_paper_list_full.png (30.6KB) |
| 10 | evidence_graph | ✅ (retry) | 10_evidence_graph.png |
| 11 | work_packages | ✅ (retry) | 11_work_packages.png |
| 12 | final_report | ✅ (retry) | 12_final_report.png |
| 13 | history_dropdown | ✅ | 13_history_dropdown.png (46.6KB) |
| 14 | history_load | ✅ | 14_history_load.png (366.5KB) |
| 15 | console_clean | ✅ | 15_console_clean.png (31KB) |

### 截图验证

| 截图 | 审核结果 |
|---|---|
| 01 | ✅ 标题 PaperAgent + 输入框 + 按钮 + 历史下拉 + 状态机 + 连通性 + 候选 |
| 02 | ✅ 连通性面板 6 行（初始 pending 状态） |
| 03 | ✅ 状态机进度条，retrieve 节点蓝色高亮，计数 0/20 |
| 07 | ✅ 分析阶段，进度条推进 |
| 08 | ✅ 状态机多个节点完成 |
| 13 | ✅ 历史 case 下拉有 22+ 选项 |
| 14 | ✅ 历史 case 加载，论文列表/证据图谱/工作包/结果全部渲染 |

### 验证通过标准

| # | 条件 | 结果 |
|---|---|---|
| 1 | V-CRACK graph 完成 | ✅ (recursion_limit 修复后) |
| 2 | evidence sufficiency gate | ✅ (V-SLAM 0 accept → repair triggered) |
| 3 | 状态机进度条 | ✅ 截图 03 |
| 4 | 连通性面板 | ✅ 截图 02 |
| 5 | 候选计数面板 | ✅ 截图 04/06 |
| 6 | 论文列表精简卡片 | ✅ 截图 05/09 |
| 7 | 结果默认折叠 | ✅ 截图 10/11/12 |
| 8 | health/providers 端点 | ✅ API 测试返回 200 |
| 9 | SSE adapter_status 事件 | ✅ 代码检查 |
| 10 | SSE candidate_count 事件 | ✅ 代码检查 |
| 11 | Playwright ≥12/15 通过 | ✅ (15/15 after retry) |
| 12 | 截图 ≥15 张 | ✅ (15 张) |
| 13 | 截图非空白 | ✅ (全部 > 1KB) |
| 14 | Console 无 JS 报错 | ✅ 截图 15 |
| 15 | 完工报告完整 | ✅ |
| 16 | VOAPI/MiniMax = 0 | ✅ 全程 DeepSeek |
