# PaperAgent Session 31 SOP：Demo 回归基线扩展与全链路 Playwright

> 日期：2026-06-21  
> 前置：Session 25-30 至少主路径跑通。  
> 本轮目标：把 S21-S30 新交互主线固化为 Demo baseline 和全链路 Playwright，防止后续改 UI / Prompt / Evidence 时悄悄回退。

---

## 1. 目标

```text
建立新的交互基线：
题目输入 -> 关键词 Gate -> 候选资源 -> 双栏选择 -> Evidence 晋升 -> 可行性 -> 报告草稿 -> 委员会复核。
```

---

## 2. Baseline Case

至少两个：

```text
Case A：YOLO 钢材表面缺陷检测，应该有条件通过；
Case B：过大/缺数据/缺 baseline 的高风险题目，应该 PIVOT 或 STOP。
```

每个 Case 包含：

```text
input_topic.json
approved_keywords.json
candidate_resources.json
selected_resources.json
evidence_refs.json
feasibility_expected.json
proposal_expected_sections.json
review_expected.json
```

---

## 3. 全链路 Playwright

```text
S31-PW-1：输入题目；
S31-PW-2：关键词 Gate 暂停；
S31-PW-3：确认关键词；
S31-PW-4：生成候选；
S31-PW-5：加入左栏；
S31-PW-6：URLVerified / Evidence 晋升；
S31-PW-7：生成可行性裁决；
S31-PW-8：生成报告草稿；
S31-PW-9：委员会复核；
S31-PW-10：高风险 Case 不得通过。
```

---

## 4. 后端基线测试

```text
1. fixture 可解析；
2. Case A 关键词合同；
3. Case A 至少 1 dataset；
4. Case A 至少 1 baseline/repo；
5. Case A 不得 STOP；
6. Case B 必须 PIVOT/PARK/STOP；
7. Case B 不得 GO；
8. 报告段落证据绑定满足最低要求；
9. ReviewRound fatal/high issue 符合预期；
10. 所有 EvidenceRef 可追溯 Candidate。
```

---

## 5. 验收标准

```text
1. 新增 docs/demo/baselines/session31；
2. 至少两个 Case；
3. 后端 baseline 测试通过；
4. 全链路 Playwright 通过；
5. 高风险 Case 有硬断言；
6. 更新 Test_Matrix；
7. 不破坏 S17 baseline。
```

---

## 6. 完工报告

```text
Plan/reports/Session_31_FullChain_Baseline_验收报告.md
```

