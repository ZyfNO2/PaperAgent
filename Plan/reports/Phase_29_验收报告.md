# Session 29 验收报告：开题报告草稿生成与证据绑定

## 产出
- `apps/api/app/schemas_proposal_draft.py`: 12节 ProposalDraft + validate_proposal + 工作量 + 创新点
- `apps/api/app/services/proposal_draft.py`: generate_proposal_draft 服务
- `apps/api/app/api/v1/one_topic.py`: POST /proposal-draft 端点
- `apps/web/proposal_draft.js`: 前端 12节可折叠渲染 + 证据绑定 + 置信度指示器 + 创新点卡 + 工作量卡

## 测试
- 后端: 15/15 通过 (test_session29_proposal_draft.py)
- Playwright: 8/8 通过 (S29-PW-1~8)
- 全量回归:
  - 后端 359 passed, 1 skipped (全部绿色)
  - E2E: S29 的 8 个全部 PASS；另有 9 个 test_one_topic_evidence_workbench 旧测试 timeout（与本次无关，历史问题）

## 证据绑定硬规则
- 没有 evidence_refs 的段落不标 high ✓
- 只有 candidate_refs 的段落标 low 或 medium ✓
- missing_evidence 显示给用户 ✓
- 不编造参考文献 ✓

## Commit
`e6964c02` Session 29: 开题报告草稿 schema + service + frontend + 23 tests

## 备注
e2e test_one_topic_evidence_workbench（9 个旧测试）全部 timeout 在 `#result-grid:not([hidden])` 选择器上，属于 Session 7 时期遗留的前端 selector 问题，与 Session 29 无关。
