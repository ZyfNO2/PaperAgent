﻿# Phase 02：题目拆解与论文结构映射

> 阶段目标：把原始题目拆成研究组件、风险词、工作包雏形和毕业论文目录映射。  
> 方法依据：毕业论文合集强调“大论文不是一个口号，而是 1-2 个可写成章节的工作量”。  
> 技术落点：Pydantic `TopicSpec`、`WorkPackageDraft`，LangGraph `TopicDecompositionNode`。  
> 阶段输入：Phase 01 中 `allow_proceed_to_phase02 == true` 的 `ProjectIntake`，或由其导出的 `00_input.md`。  
> 阶段产物：`01_topic_spec.md`、结构化 `TopicSpec`。

---

## 1. 阶段定位

Phase 02 不是美化题目，而是拆题、降风险、做章节预映射。

进入 Phase 02 的前提是 Phase 01 已经通过入口评级：

```text
ValidationOutcome.OK
intake_rating in ["A", "B"]
allow_proceed_to_phase02 == true
```

如果 Phase 01 的结果是 C 或 D，不能进入本阶段拆题，应先回到 Phase 01 的补问 / 重校验链路。尤其是 `00_input.md` 仍为 TBD 占位骨架时，只能作为阻断样例，不能作为本阶段输入。

它要判断：

- 题目有没有明确研究对象、任务、数据、方法和评价指标？
- 题目中的“智能、实时、高精度、多模态、大模型、通用”等词能否被验证？
- 题目能否自然拆出 1-2 个工作包？
- 第三章、第四章是否有可写内容？
- 是否需要把“航母题目”收缩成可毕业题目？

---

## 2. 毕业方法论转化

| 毕业论文合集经验 | Phase 02 中的产品化规则 |
|---|---|
| 大论文通常由两个工作量组成 | 每个题目必须尝试拆出工作包一、工作包二 |
| 方法章节是论文核心 | 工作包必须能落到第三章 / 第四章 |
| 目录先行 | 题目拆解时同步生成五章式目录映射 |
| 创新必须是问题-方法-证据链 | 每个创新雏形必须绑定待验证证据 |
| 不要只写百科式第二章 | 第二章只放后续方法真正需要的基础 |

---

## 3. 技术设计

### 3.1 Pydantic 对象

```python
class TopicSpec(BaseModel):
    project_id: str
    source_intake_case_id: str
    goal_level: Literal["保毕业", "稳中求新", "冲高水平"]
    first_result_deadline: str | None
    raw_topic: str
    normalized_topic: str
    research_object: str | None
    application_scenario: str | None
    task_type: list[str]
    data_modality: list[str]
    method_family: list[str]
    expected_outputs: list[str]
    evaluation_metrics: list[str]
    engineering_constraints: list[str]
    risk_terms: list[RiskTerm]
    thesis_mapping: ThesisMapping
    work_package_drafts: list[WorkPackageDraft]
    carried_constraints: list[str]
    decomposition_rating: Literal["A", "B", "C", "D"]
```

### 3.2 LangGraph 节点

```text
TopicDecompositionNode
→ RiskTermNormalizationNode
→ ThesisMappingNode
→ WorkPackageDraftNode
→ HumanConfirmNode?
```

若题目拆不出数据、任务、指标或章节位置，进入人工确认或题目收缩节点。

---

## 4. 执行步骤

### Step 0：校验 Phase 01 交接条件

从 API 或数据库读取 `ProjectIntake`，确认：

- `allow_proceed_to_phase02 == true`
- `intake_rating` 为 A 或 B
- `raw_topic` 不是 TBD / TODO / 待定 / 未知等占位符
- `goal_level`、导师方向、时间红线、资源条件已进入结构化字段

若不满足，返回 Phase 01，不生成 `TopicSpec`。

### Step 1：标准化题目

将原题转成更明确的研究题目。

示例：

```text
原题：基于大模型的智能开题助手
标准化：面向中国研究生开题选题场景的多证据链题目风险评估与工作包生成方法研究
```

标准化时不能扩大承诺，只能收缩边界。

### Step 2：拆研究组件

| 字段 | 说明 |
|---|---|
| 研究对象 | 学生题目、文献、数据集、baseline、开题报告等 |
| 应用场景 | 中国研究生开题选题、导师沟通、开题报告准备 |
| 核心任务 | 题目解析、证据检索、风险评分、Pivot、工作包生成 |
| 数据模态 | Markdown、PDF、DOCX、论文元数据、代码仓库元数据 |
| 方法族 | Agent、RAG、混合检索、结构化输出、风险评估 |
| 预期输出 | 风险报告、证据账本、工作包、开题报告草案 |
| 评价指标 | Evidence Precision、Baseline Recall@K、Citation Hallucination Rate 等 |
| 工程约束 | 成本、延迟、证据可追溯、人工确认、可部署 |

### Step 3：识别并改写高风险词

| 高风险词 | 规范化处理 |
|---|---|
| 智能 | 改为“基于证据链的自动分析与人工确认” |
| 高精度 | 改为具体指标，如 Evidence Precision |
| 实时 | 改为 SSE 展示进度，不承诺实时完成检索 |
| 通用 | 改为“面向中国研究生开题选题场景” |
| 大模型 | 明确为 LiteLLM 网关下的 LLM 调用，不做模型训练 |
| 全自动 | 改为 Agent 辅助 + 人工确认 |

### Step 4：五章式论文结构预映射

推荐映射：

| 论文章节 | TopicPilot-CN 可写内容 |
|---|---|
| 第一章 绪论 | 开题选题痛点、证据链不足、AI Agent/RAG 应用价值 |
| 第二章 相关基础 | LangGraph、RAG、混合检索、结构化输出、评估指标 |
| 第三章 工作包一 | 题目解析、文献/数据集/baseline 检索与证据账本构建 |
| 第四章 工作包二 | 选题风险评分、Pivot 规划、工作包生成与开题委员会审查 |
| 第五章 总结与展望 | 系统实现、实验结果、局限与后续扩展 |

### Step 5：生成工作包雏形

每个工作包必须满足：

```text
明确问题 + 方法方案 + 数据来源 + 实验方式 + 论文章节位置
```

建议初始工作包：

| 工作包 | 研究问题 | 方法方案 | 实验方式 | 章节 |
|---|---|---|---|---|
| WP1 证据链构建 | 题目推荐缺少可追溯依据 | 混合检索 + Reranker + Evidence Ledger | Evidence Precision、Baseline Recall@K | 第三章 |
| WP2 风险与工作包生成 | 学生难判断题目能否毕业 | LangGraph 状态机 + 风险评分 + Pivot + 工作包生成 | 风险分类准确率、人工接受率、案例评审 | 第四章 |

---

## 5. 输出模板：`01_topic_spec.md`

```markdown
# 01_topic_spec

## 1. 原始题目

## 2. 标准化题目

## 3. 结构化拆解
| 字段 | 内容 | 风险备注 |
|---|---|---|
| 研究对象 |  |  |
| 应用场景 |  |  |
| 核心任务 |  |  |
| 数据模态 |  |  |
| 方法族 |  |  |
| 预期输出 |  |  |
| 评价指标 |  |  |
| 工程约束 |  |  |

## 4. 高风险词解释
| 高风险词 | 可能风险 | 可验证定义 | 处理方式 |
|---|---|---|---|

## 5. 五章式论文结构预映射
| 论文部分 | 当前题目可写内容 | 是否充分 | 缺口 |
|---|---|---|---|
| 第一章 绪论 |  |  |  |
| 第二章 相关基础 |  |  |  |
| 第三章 工作包一 |  |  |  |
| 第四章 工作包二 |  |  |  |
| 第五章 总结与展望 |  |  |  |

## 6. 工作包雏形
| 工作包 | 研究问题 | 方法方案 | 数据来源 | 实验方式 | 章节 |
|---|---|---|---|---|---|

## 7. Phase 02 结论
- 可保留部分：
- 必须收缩部分：
- 需要证据验证部分：
- 当前最大结构风险：
- 是否允许进入 Phase 03：
```

---

## 6. 验收标准

- [ ] Phase 01 交接状态为 OK，且 `allow_proceed_to_phase02 == true`。
- [ ] 至少拆出研究对象、核心任务、数据模态、方法族、评价指标五项。
- [ ] 每个高风险词都有可验证定义或处理方式。
- [ ] 至少形成 2 个工作包雏形；若不足 2 个，必须说明原因。
- [ ] 第三章和第四章均有候选工作内容。
- [ ] 题目边界比原始题目更清晰，没有扩大承诺。
- [ ] `TopicSpec` 可通过 Pydantic 校验。
- [ ] 若数据、指标、baseline 全部未知，必须标记高风险并在 Phase 03 优先检索。

---

## 7. 阻断条件

出现以下情况不得进入 Phase 03：

1. Phase 01 仍为 C/D，或 `allow_proceed_to_phase02 == false`。
2. 题目无法拆出核心任务。
3. 题目没有任何可评价输出。
4. 第三章、第四章没有可写工作包。
5. 用户坚持保留“通用、全自动、全场景”等无法验证承诺。
6. 所有关键假设都依赖尚未确认的私有数据或未授权资源。
