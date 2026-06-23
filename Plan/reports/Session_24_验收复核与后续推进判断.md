# Session 24 验收复核与后续推进判断

> 日期：2026-06-21  
> 复核对象：`Plan/reports/Session_24_QueryPlan_CandidateCards_验收报告.md`  
> 结论：Session 24 可以通过验收。后续可以进入双栏工作台、候选转证据、真实流式持久化、可行性裁决、开题报告草稿与委员会复核。

---

## 1. 验收结论

```text
验收结论：通过
通过等级：主线通过，增强项待补
可继续写 SOP：Session 25-32
可优先执行：Session 25-27
建议暂缓执行：Session 31-32，等 25-30 至少完成一轮后再收束
```

通过依据：

```text
1. S22 已有 ComponentRegistry；
2. S23 已有 PromptProtocol 与工具调用边界；
3. S24 已有 CandidateResource / QueryPlan / CandidateActionRequest；
4. S24 后端测试 20 passed；
5. S24 Playwright 10 passed；
6. Candidate != Evidence 的边界已被测试覆盖；
7. keyword_review 未确认时 query_plan blocked；
8. promote_to_selected 不写 Evidence；
9. S17/S21/S22/S23 均未回退。
```

---

## 2. 当前仍需补的能力

```text
1. 候选资源的双栏工作台：用户选中资料 vs 系统候选资料；
2. Candidate -> Evidence 的晋升流程和 URLVerified 桥接；
3. 真实 RunEvent / SSE / NDJSON 持久化与回放；
4. 可行性风险裁决：GO / CONDITIONAL / PIVOT / PARK / STOP；
5. 开题报告草稿生成：每个判断必须绑定候选或证据；
6. 低门槛委员会复核：指出明显不适合开题的问题；
7. 全链路回归基线：从题目输入到候选、证据、报告、复核；
8. 学校模板与导出前合规检查。
```

---

## 3. 后续执行边界

必须继续保持：

```text
Candidate 只是候选；
Selected 只是用户选中；
URLVerified 才能进入 verified evidence；
EvidenceRef 才能支撑报告结论；
supports 不得由 UI action 直接生成；
ReportQuality 必须能指出缺证据、缺数据集、缺 baseline、题目过大。
```

禁止：

```text
不允许 promote_to_selected 直接写 Evidence；
不允许未验证 URL 进入参考文献强引用；
不允许 LLM 编造论文 / 数据集 / GitHub；
不允许模型输出任意 JS；
不允许跳过 keyword_review 和 candidate_review 两个 Gate。
```

---

## 4. 推荐后续 Session

```text
Session 25：双栏候选资料工作台 MVP
Session 26：Candidate -> Evidence 晋升与 URLVerified 桥接
Session 27：真实流式 RunEvent 持久化与操作回放
Session 28：可行性风险裁决与 PIVOT 路线
Session 29：开题报告草稿生成与证据绑定
Session 30：低门槛委员会复核与 Revision Loop
Session 31：Demo 回归基线扩展与全链路 Playwright
Session 32：学校模板合规与导出前检查
```

---

## 5. 一次最多能推进到哪里

可以一次性写 SOP 到 S32。

执行时建议：

```text
S25-S27 可以连续执行；
S28-S30 需要在 S25-S27 通过后执行；
S31-S32 是收束与质量线，适合在主线跑通后补。
```

原因：

```text
S25 依赖 S24 Candidate；
S26 依赖 S25 Selected；
S27 补齐 S21-S24 一直欠着的真实流式和回放；
S28 依赖 Evidence / Verified Candidate；
S29 依赖可行性裁决；
S30 依赖报告草稿；
S31/S32 依赖全链路已有稳定产物。
```

