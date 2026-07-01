# PaperAgent Re01 终结审计报告

> 审计对象：`G:\PaperAgent\Plan\PaperAgent_Re01_报告.md`、`G:\PaperAgent\apps\api\app\services\agents\research_agent.py`、`apps/api/app/services/agents/prompts/*.py`
>
> 参考对象：`C:\Users\ZYF\Desktop\Paper\AutoResearchClaw`、`C:\Users\ZYF\Desktop\Paper\academic-research-skills`
>
> 本版说明：本报告不再围绕此前某几张截图中的旧错误逐条打补丁。Re01 审计按“新 agent 是否具备毕业选题证据工作流的最小能力”来判断，重点看检索计划、检索增强、候选池、过滤器分层与低门槛复核是否成立。

---

## 1. 总体判断

Re01 已完成一个新的 agent 骨架：

```text
parse_topic -> plan_tools -> fetch_all -> synthesize -> devils_advocate
```

这个方向是对的：它把旧的一页式固定报告，推进成了“先拆题、再检索、再综合、再复核”的 agent 形态。但 Re01 还不能算毕业选题主线可用，因为它当前更像“把 raw 检索结果塞进几个桶”，还缺少三个现阶段最关键的控制点：

1. **检索增强**：从单轮 query list 升级为宽召回、参考扩展、repo/dataset 补查的多轮检索。
2. **候选池与过滤器分层**：不是少给结果，而是尽可能多召回，再按核心推荐、普通候选、需确认、拒绝/隔离分层。
3. **低门槛审稿/复核**：在最终建议前，用简单规则和 LLM 复核判断“证据是否足够支撑推荐”，但不做复杂委员会系统。

因此，Re02 不应一次性加入完整多 agent 架构、复杂关系图、长期记忆、跨模型验证等重功能。现阶段只补“能广泛检索、能保留候选、能分层排序、能提醒风险、能低门槛复核”的最小闭环。HumanGate 暂缓，只预留字段。

---

## 2. Re01 已有价值

### 2.1 Agent 分层已经成形

`research_agent.py` 已经把职责拆成：

- `parse_topic()`：题目解析。
- `plan_tools()`：检索计划。
- `fetch_all()`：多源检索。
- `synthesize_buckets()`：结果综合。
- `devils_advocate()`：复核。

这比旧版直接生成结论更适合继续演进。

### 2.2 四类来源已经接入

当前接入：

- arXiv
- OpenAlex
- Crossref
- GitHub

这满足了新 agent 的初始基础。Re02 不需要立刻引入一大堆外部工具，只需要把“什么时候用什么工具、结果如何记录、失败如何解释”做清楚。

### 2.3 Circuit breaker 可保留

`AdapterSuspendState` 与 `_PerAdapterCB` 已经能处理 OpenAlex/arXiv/GitHub 的失败与暂停。Re02 可保留，不需要重写。

---

## 3. Re01 当前主要问题

### 3.1 检索增强不足，仍然像单轮关键词搜索

当前流程虽然已经有 parse、plan、fetch、synthesize，但检索仍偏单轮、偏关键词直搜。它没有形成“先宽召回，再从参考文献/摘要/README 中抽取线索继续追查，最后补 repo/dataset/baseline”的科研检索节奏。

这不适合毕业选题，因为题目通常含糊，例如：

- “基于三维成像的智能损伤检测”
- “基于大语言模型的主观题评分”
- “基于多源遥感的作物识别”

这些题目在“对象、任务、数据、方法路线”上都可能需要多种检索路径。只做一次 query 很容易把方向搜窄，或者不同题目返回相似泛化结果。

Re02 最小修法：

- Step 1 输出 `topic_atoms`。
- Step 2 输出三轮 `search_plan`：宽召回、参考扩展、repo/dataset 补查。
- Step 3 建立 `candidate_pool`，保留相关参考中出现的论文、数据集、repo、baseline。
- Step 4 由 LLM 审计分层排序，而不是早期强过滤。

---

### 3.2 检索计划缺少角色意识

当前 `plan_tools()` 只生成各 adapter 的 query 列表：

- `arxiv_queries`
- `openalex_queries`
- `crossref_queries`
- `github_queries`

但它没有明确每个 query 的目的：

- 找 baseline？
- 找 parallel paper？
- 找 dataset？
- 找 repo？
- 找 survey？

结果是后面的 synthesize 只能凭 LLM 自己猜，容易把候选放错桶。

Re02 最小修法：

检索计划必须改为 role-aware：

```json
{
  "calls": [
    {
      "tool": "search_arxiv",
      "query": "unet crack segmentation",
      "target_role": "baseline_or_parallel_paper",
      "why_call": "find reproducible method papers",
      "expected_output": "paper"
    }
  ]
}
```

---

### 3.3 证据验证只解决“是否出现”，没有解决“是否能用”

当前 verifier 主要检查 LLM 输出的 title 是否出现在 raw tool output 中。这能防止一部分幻觉，但不能判断：

- 是否和题目方向相关。
- 是否放进了正确桶。
- 是否是可复现 baseline。
- 是否只是背景文献。
- 是否需要人工确认。

Re02 最小修法：

不引入完整复杂 typed evidence 系统，但必须增加一个轻量 `EvidenceReview` 层：

```text
candidate -> evidence_type -> role_hint -> review_status -> review_reason
```

其中：

- `evidence_type`: `paper | dataset | repo | survey | unknown`
- `role_hint`: `baseline | parallel | module | reference | dataset | repo | needs_manual`
- `review_status`: `core | candidate | needs_manual | rejected`

---

### 3.4 synthesize 责任过重

当前 synthesize 同时负责：

- 从 raw 中选择候选。
- 分类候选。
- 写用途。
- 生成 gap。

这对 LLM 要求过高，也难以验收。

Re02 最小修法：

不要一下拆成十几个 agent。只做三层：

1. `SearchPlanner`：决定搜什么。
2. `EvidenceReviewer`：判断候选能不能用、放哪类。
3. `SynthesisAgent`：只基于 reviewed candidates 写总结和建议。

---

## 4. 参考工作流对照

### 4.1 AutoResearchClaw 可借鉴点

参考文件：

- `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw\researchclaw\literature\search.py`
- `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw\researchclaw\pipeline\stage_impls\_literature.py`
- `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw\researchclaw\mcp\tools.py`

只借鉴三点：

1. **Search strategy 先于检索**：先写清楚搜什么、为什么搜、用什么源。
2. **多源结果要有 ledger**：每次 query 的来源、数量、失败原因要保存。
3. **检索失败要能解释**：OpenAlex 失败不是“无证据”，而是“该源失败，已用其他源补查/仍需人工补查”。

暂不引入：

- 完整 pipeline runner。
- 实验执行 sandbox。
- 大型 benchmark agent。
- 复杂 web crawler。

### 4.2 academic-research-skills 可借鉴点

参考文件：

- `C:\Users\ZYF\Desktop\Paper\academic-research-skills\academic-pipeline\SKILL.md`
- `C:\Users\ZYF\Desktop\Paper\academic-research-skills\agents\synthesis_agent.md`
- `C:\Users\ZYF\Desktop\Paper\academic-research-skills\shared\cross_model_verification.md`

只借鉴三点：

1. **阶段意识**：每个关键阶段要有明确输入、输出、状态和停止点；HumanGate 可后续实现。
2. **证据优先**：综合报告只能基于已收集证据。
3. **低门槛复核**：先做轻量 review，不上复杂委员会。

暂不引入：

- 完整 10-stage academic pipeline。
- cross-model verification。
- PRISMA-trAIce 完整合规。
- 多轮 external review。

---

## 5. Re01 是否通过

结论：部分通过。

通过的部分：

- 新 agent 主流程已经接通。
- 多源检索已经接入。
- 有初步复核函数。
- 有原始结果与 buckets 输出。

不通过的部分：

- 检索仍偏单轮，缺少参考扩展与 repo/dataset 补查。
- 没有 CandidatePool，弱相关但真实存在的线索容易丢失。
- 检索计划缺少 target role。
- 证据 review 过于粗。
- synthesize 责任过重。
- 测试还没有覆盖“科研选题工作流”的真实场景。

所以 Re02 的目标不是推倒重来，而是在新 agent 上补最小闭环。

---

## 6. Re02 推荐方向

Re02 只做四件事：

1. **SearchPlan v2**：每个 tool call 都有 `target_role / why_call / expected_output`。
2. **Multi-round Retrieval v1**：宽召回、参考扩展、repo/dataset 补查三轮自动检索。
3. **CandidatePool + EvidenceReview v1**：候选进入展示前必须经过轻量复核，并分为核心推荐、普通候选、需人工确认、拒绝/隔离。
4. **Synthesis v1 收敛**：基于 reviewed evidence 生成“好毕业方向 + 论文/数据集/Baseline + 工作建议”，同时保留长尾候选和风险提醒，到这里停止。

Re02 不做：

- 不做完整 Agent 大图重构。
- 不做多 subagent 编排。
- 不做复杂 relation graph。
- 不做长期记忆。
- 不做 UI 大改。

---

## 7. Re02 验收重点

Re02 验收不以“只给少量最安全结果”为准，而以“尽可能多召回 + 分层可信展示”为准：

1. 用户能看到系统如何理解题目。
2. 用户能看到系统准备搜什么、为什么搜、用什么 tool 搜。
3. 每个候选能说明“为什么排在前面/为什么只是候选/为什么需人工确认/为什么拒绝”。
4. 推荐的方向能绑定至少 1 个 baseline 候选、1 类数据来源、若干参考论文或明确 gap。
5. 系统在证据不足时不删除长尾线索，而是把它们列为候选/提醒，并说明还需要用户或后续检索确认。
6. 后续可基于论文引用、年份、repo、dataset 形成数据网；Re02 只预留字段和输出形态，不实现图谱。
