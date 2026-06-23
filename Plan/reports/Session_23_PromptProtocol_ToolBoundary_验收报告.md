# Session 23 验收报告：Streaming Prompt Protocol & Tool Boundary

> 日期：2026-06-20
> SOP：Plan/PaperAgent_Session23_PromptProtocol_ToolBoundary_SOP.md
> 状态：✅ 通过

## 1. 本轮目标

定义 LLM 流式输出的 Prompt 协议骨架（每步输出合同、安全条款、工具调用边界），
并通过 Playwright 测试验证安全拦截、边界放行、与前序 Session 不回退。

## 2. 关键产物

### 2.1 新增文件

- `apps/web/prompt_protocol.js` — Prompt 协议模块
  - `SECURITY_CLAUSE`: LLM 输出安全条款（禁止 script/eval/iframe/事件处理器等）
  - `STEP_CONTRACTS`: 9 步输出合同（每步 requiredFields、optionalFields、cardType、preCondition）
  - `TOOL_PRECONDITIONS`: 工具前置条件映射（search_papers 等需 keyword_review_approved）
  - `FORBIDDEN_TOOLS`: 永禁工具列表（exec_code、run_shell、eval_expression 等）
  - `generatePromptSkeleton(stepKey, ctx)`: 生成 prompt 骨架
  - `validateLLMOutput(stepKey, output)`: 校验 LLM 输出结构 + 安全扫描
  - `isToolAllowed(toolName, runState)`: 检查工具调用权限

- `apps/web/e2e/test_one_topic_session23_prompt_protocol.py` — 8 个 Playwright 测试

### 2.2 修改文件

- `apps/web/step_deck.js` — 新增两个扩展 mock stream 函数
  - `startExtendedMockStream(rs)`: keyword_review approve → query_plan 步骤（含 SearchQueryPlanCard）
  - `startCandidatesMockStream(rs)`: query_plan approve → candidates 步骤（含 3 张 RetrievalCandidateCard）

- `apps/web/index.html` — 新增 `<script src="prompt_protocol.js">` 加载

## 3. Step 输出合同

| 步骤 | cardType | preCondition | gateType |
|------|----------|--------------|----------|
| input | — | — | — |
| topic_understanding | TopicUnderstandingCard | — | — |
| keyword_review | KeywordReviewCard | — | user_confirm |
| query_plan | SearchQueryPlanCard | keyword_review_approved | — |
| candidates | RetrievalCandidateCard | keyword_review_approved | — |
| workspace | EvidenceRefCard | — | — |
| feasibility | — | — | — |
| proposal | — | — | — |
| report_quality | ReportQualityCard | — | — |

## 4. 安全条款

- 15 个 FORBIDDEN_PATTERNS 正则：`<script>`、`javascript:`、`eval()`、`onclick=`、`<iframe>` 等
- validateLLMOutput 对任何命中返回 `{ ok: false, securityViolation: true }`
- 5 个永禁工具：exec_code, run_shell, eval_expression, write_file_system, delete_file_system

## 5. 工具调用边界

| 工具 | 前置条件 | keyword_review 确认前 | 确认后 |
|------|----------|---------------------|--------|
| search_papers | keyword_review_approved | ❌ blocked | ✅ allowed |
| search_datasets | keyword_review_approved | ❌ blocked | ✅ allowed |
| search_repos | keyword_review_approved | ❌ blocked | ✅ allowed |
| fetch_url | keyword_review_approved | ❌ blocked | ✅ allowed |
| generate_report | workspace_approved | ❌ blocked | ❌ blocked |
| export_docx | report_quality_approved | ❌ blocked | ❌ blocked |
| exec_code | 永禁 | ❌ 永禁 | ❌ 永禁 |

## 6. Mock Stream 扩展

keyword_review approve 后的扩展流：
```
step_resumed(keyword_review)
  → step_started(query_plan) → token_delta → card_delta(SearchQueryPlanCard) → step_pause(query_plan)
    → [用户 approve query_plan]
      → step_resumed(query_plan) → step_started(candidates) → token_delta
        → card_delta(RetrievalCandidateCard: paper)
        → card_delta(RetrievalCandidateCard: dataset)
        → card_delta(RetrievalCandidateCard: repo)
        → step_pause(candidates)
```

## 7. 测试结果

```
apps/web/e2e/test_one_topic_session23_prompt_protocol.py — 8 passed

S23-PW-1 ✅ PromptProtocol 在 window 上可用，STEP_CONTRACTS 含 9 步
S23-PW-2 ✅ validateLLMOutput 通过正常 keyword_review 数据
S23-PW-3 ✅ validateLLMOutput 拒绝含 <script> 的输出
S23-PW-4 ✅ validateLLMOutput 拒绝含 eval() 的输出
S23-PW-5 ✅ isToolAllowed 在 keyword_review 未确认时拦截 search_papers
S23-PW-6 ✅ isToolAllowed 在 keyword_review 确认后放行 search_papers
S23-PW-7 ✅ isToolAllowed 永远拒绝 exec_code
S23-PW-8 ✅ S21/S22 主流程不回退（rail 9 步、mock 流暂停、通过后推进）

Total tests collected: 424 (增长自 416)
```

## 8. S21/S22 不回退确认

- S21 rail 9 步 ✅
- S21 mock 流 keyword_review 暂停 ✅
- S21 approve 后推进 ✅
- S22 ComponentRegistry 6 张核心卡 ✅
- S22 未知组件 fallback ✅
- S22 安全降级 invalid 卡 ✅

## 9. 后续建议

Session 24 可直接基于：
- `startExtendedMockStream()` 生成 query_plan 步骤
- `startCandidatesMockStream()` 生成候选资源步骤
- `isToolAllowed()` 在 UI 层拦截未授权操作
- `validateLLMOutput()` 在接收 LLM 输出时安全扫描
