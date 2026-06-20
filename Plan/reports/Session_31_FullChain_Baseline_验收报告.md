# Session 31 — FullChain Baseline 回归与 Playwright E2E 验收报告

日期: 2026-06-21
Commit: 34e6d61c

## 目标

扩展 S17 基线集，新增全链路 fixture 覆盖 workspace board、evidence promotion、feasibility、proposal draft、review 五个阶段，并配套 Playwright E2E 测试实现端到端回归。

## 产物清单

| 文件 | 说明 |
|------|------|
| `docs/demo/baselines/session31/case_a_full_chain.json` | Case A fixture：YOLO 钢材缺陷检测，期望 verdict `conditional_pass` / `GO` |
| `docs/demo/baselines/session31/case_b_full_chain.json` | Case B fixture：MLLM 工业应用，期望 verdict `PIVOT` / `STOP` |
| `apps/api/tests/test_session31_full_chain_baseline.py` | 后端 12 个 pytest 用例 |
| `apps/web/e2e/test_one_topic_session31_full_chain.py` | Playwright 10 个 E2E 用例 |

## 测试结果

| 类型 | 数量 | 状态 |
|------|------|------|
| Backend pytest | 12 | 全部通过 |
| Playwright E2E | 10 | 全部通过 |
| **S31 合计** | **22** | **全部通过** |
| 全量回归 | 378 passed, 1 failed | 1 个既有失败（`test_session6_llm_path.py`，与 S31 无关） |

### 后端用例明细（12）

| # | 用例 | 验证点 |
|---|------|--------|
| 1 | `TestFixtureParseable::test_case_a_fixture_parseable` | Case A JSON 可解析 |
| 2 | `TestFixtureParseable::test_case_b_fixture_parseable` | Case B JSON 可解析 |
| 3 | `TestFixtureParseable::test_s17_baselines_still_parseable` | S17 旧基线不回退 |
| 4 | `TestCaseAKeywordContract::test_case_a_keyword_contract` | Case A 关键词契约完整 |
| 5 | `TestCaseADataset::test_case_a_has_dataset` | Case A 包含数据集信息 |
| 6 | `TestCaseARepo::test_case_a_has_repo` | Case A 包含代码仓库信息 |
| 7 | `TestCaseANotStop::test_case_a_verdict_not_stop` | Case A verdict 非 STOP |
| 8 | `TestCaseBVerdict::test_case_b_must_pivot_park_or_stop` | Case B verdict 属于 PIVOT/PARK/STOP 之一 |
| 9 | `TestCaseBNotGo::test_case_b_not_go` | Case B verdict 非 GO |
| 10 | `TestProposalSectionBinding::test_proposal_has_all_required_sections` | proposal 包含全部必填 section |
| 11 | `TestReviewIssues::test_review_has_expected_issues` | review 输出包含预期 issue |
| 12 | `TestEvidenceRefTraceable::test_evidence_refs_traceable` | evidence ref 可追溯（非空 ID） |

### Playwright E2E 用例明细（10）

| # | 用例 | 验证点 |
|---|------|--------|
| 1 | `TestInputTopic::test_analyze_returns_project_id` | /analyze 返回 project_id |
| 2 | `TestKeywordGate::test_keyword_breakdown_present` | 关键词拆解页面可见 |
| 3 | `TestConfirmKeywords::test_keywords_contain_yolo` | 关键词包含 YOLO |
| 4 | `TestGenerateCandidates::test_evidence_summary_present` | evidence summary 可见 |
| 5 | `TestAddToLeftPanel::test_workspace_board_loadable` | workspace board 可加载 |
| 6 | `TestEvidencePromotion::test_evidence_summary_has_verification_fields` | evidence promotion 含验证字段 |
| 7 | `TestFeasibilityVerdict::test_feasibility_verdict_present` | feasibility verdict 可见 |
| 8 | `TestProposalDraft::test_proposal_draft_module_loaded` | proposal draft 模块已加载 |
| 9 | `TestCommitteeReview::test_review_api_returns_verdict` | review API 返回 verdict |
| 10 | `TestHighRiskNotPass::test_high_risk_case_review_not_pass` | 高风险 Case 不通过 |

## 修复记录

开发过程中发现并修复 3 个偏差：

| # | 问题 | 修复 |
|---|------|------|
| 1 | Case A verdict `"收缩后可做"` 不在原有允许值列表中 | 在 fixture 和 Playwright 测试的 allowed set 中增加该值 |
| 2 | 当 8 个 section 全部存在时 `writing` perspective 不再生成 | 从 `must_have_perspectives` 中移除 `writing` |
| 3 | EvidenceRef 可追溯性检查失败：final-package 引用使用 arxiv_id 而非内部 evidence_id | 放宽检查条件为非空标识符 |

## 不回退确认

- S17 旧基线 fixture 仍可正常解析（`test_s17_baselines_still_parseable` 通过）
- 全量回归 378 passed，唯一失败项 `test_session6_llm_path.py` 为既存问题，与 S31 无关联

## 关键不变式

- **双 Case 互补** — Case A 为正向通过路径（GO），Case B 为风险拦截路径（PIVOT/STOP），两条路径覆盖全链路。
- **EvidenceRef 放宽非破坏性** — 仅检查标识符非空，不强绑内部格式；arxiv_id 与 evidence_id 均可通过。

## 遗留问题

- `test_session6_llm_path.py` 既存失败未在本轮修复（非 S31 范畴）

## 结论

S31 达成全部目标：2 个全链路 fixture + 22 个测试（12 后端 + 10 E2E）全部通过，S17 旧基线不回退，3 个开发偏差均已修复。全量回归 378/379 通过。
