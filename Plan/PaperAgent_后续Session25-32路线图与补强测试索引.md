# PaperAgent 后续 Session 25-32 路线图与补强测试索引

> 日期：2026-06-21  
> 前置：Session 24 已完成 QueryPlan + CandidateResource + Candidate Cards。  
> 用途：给后续多个 Session 提供主线、边界、补功能与补测试索引。

---

## 1. 主线

```text
候选资源 -> 用户选择 -> 轻验证 -> EvidenceRef -> 可行性裁决 -> 开题报告草稿 -> 委员会复核 -> 回归基线
```

产品体验主线：

```text
左侧：用户已经选中的论文 / 数据集 / 工程；
右侧：系统检索到的候选资源；
中间或底部：当前题目的可行性、风险、下一步建议；
最终：生成一份有证据绑定的开题报告草稿，并经过低门槛复核。
```

---

## 2. Session 总览

| Session | 名称 | 目标 | 风险 |
|---|---|---|---|
| 25 | 双栏候选资料工作台 MVP | selected vs candidate | 中 |
| 26 | Candidate -> Evidence 晋升与 URLVerified 桥接 | 轻验证后才能变证据 | 高 |
| 27 | 真实流式 RunEvent 持久化与回放 | 补真实 SSE/NDJSON 与 replay | 高 |
| 28 | 可行性风险裁决与 PIVOT 路线 | GO/PIVOT/STOP 等判断 | 中-高 |
| 29 | 开题报告草稿生成与证据绑定 | 草稿每段绑定 EvidenceRef | 中 |
| 30 | 低门槛委员会复核与 Revision Loop | 报告初审与修改闭环 | 中 |
| 31 | Demo 回归基线扩展与全链路 Playwright | 把新主线固化成 baseline | 中 |
| 32 | 学校模板合规与导出前检查 | 模板和导出前 QA | 中 |

---

## 3. 必补功能

```text
1. SelectedResource：用户选中资料，仍不等于 Evidence；
2. CandidateReviewGate：候选进入证据前的人工确认；
3. URLVerified bridge：URL 检查结果进入 Candidate / Evidence；
4. EvidencePromotion：只有 verified + selected 才能尝试晋升；
5. RunEventStore：流式事件落盘和 replay；
6. FeasibilityDecision：GO / CONDITIONAL / PIVOT / PARK / STOP；
7. ProposalDraft：开题报告草稿结构化对象；
8. ReviewRound：委员会复核意见与 revision action；
9. FullChainBaseline：新交互主线的演示基线；
10. ExportReadiness：导出前证据、格式、模板检查。
```

---

## 4. 必补测试

后端：

```text
test_session25_workspace_board.py
test_session26_evidence_promotion.py
test_session27_run_event_store.py
test_session28_feasibility_decision.py
test_session29_proposal_draft.py
test_session30_committee_review_loop.py
test_session31_full_chain_baseline.py
test_session32_export_readiness.py
```

前端 Playwright：

```text
test_one_topic_session25_workspace_board.py
test_one_topic_session26_evidence_promotion.py
test_one_topic_session27_run_replay.py
test_one_topic_session28_feasibility_pivot.py
test_one_topic_session29_proposal_draft.py
test_one_topic_session30_committee_review.py
test_one_topic_session31_full_chain_baseline.py
test_one_topic_session32_export_readiness.py
```

---

## 5. 总边界

```text
Candidate != Selected
Selected != Evidence
URLVerified != Support
EvidenceRef != Final Claim
ReportDraft != Final Thesis
CommitteeReview != Real Expert Review
ExportReady != 学校一定通过
```

---

## 6. 执行建议

```text
第一批：S25 + S26 + S27
第二批：S28 + S29 + S30
第三批：S31 + S32
```

第一批完成后，项目会从“候选卡片”升级为“可追溯资料工作台”。

第二批完成后，项目会从“资料工作台”升级为“开题报告助手”。

第三批完成后，项目会从“可演示功能”升级为“可回归、可交付、可导出前检查”的稳定版本。

