﻿# Phase 03：方向成熟度与检索计划

> 阶段目标：把题目拆解结果转换为可执行的多路检索计划，判断方向是否属于“论文多、数据多、代码多、模板多”的成熟区域。  
> 方法依据：毕业论文合集强调“保毕业优先选择人多方向，先找 baseline，再谈创新”。  
> 技术落点：`SearchQueryPlan`、`LiteratureSearchGraph`、`DatasetSearchGraph`、`BaselineSearchGraph`。  
> 阶段输入：Phase 02 验收通过的 `01_topic_spec.md` / `TopicSpec`。  
> 阶段产物：`02_query_plan.md`、结构化 `SearchQueryPlan`。

---

## 1. 阶段定位

Phase 03 不直接采集证据，而是设计检索路线。

进入 Phase 03 的前提是 Phase 02 已生成可用 `TopicSpec`：

```text
decomposition_rating in ["A", "B"]
work_package_drafts 至少 1 个，理想为 2 个
raw_topic / normalized_topic / task_type / evaluation_metrics 非空
```

它要回答：

- 这个方向应该用哪些中英文关键词检索？
- 哪些关键词用于论文，哪些用于数据集，哪些用于 baseline？
- 哪些检索用于判断方向成熟度？
- 每个工作包雏形分别需要哪些证据？
- 是否需要从精确题目退化到更成熟的通用任务？

毕业论文合集中的“人多方向”可以被产品化为方向成熟度信号：

- 近 3-5 年论文数量足够。
- 有综述或 survey。
- 有公开数据集。
- 有 GitHub / Hugging Face / Papers with Code 代码。
- 有公认指标和 benchmark。
- 有同领域学位论文目录模板。

---

## 2. 技术设计

### 2.1 Pydantic 对象

```python
class SearchQueryPlan(BaseModel):
    project_id: str
    topic_spec_id: str
    goal_level: Literal["保毕业", "稳中求新", "冲高水平"]
    carried_constraints: list[str]
    query_layers: list[QueryLayer]
    source_targets: list[SourceTarget]
    work_package_queries: list[WorkPackageQuery]
    maturity_probe: MaturityProbe
    baseline_probe: BaselineProbe
    thesis_template_probe: ThesisTemplateProbe
    risk_flags: list[str]
```

### 2.2 LangGraph 子图

```text
QueryExpansionNode
→ SourceRoutingNode
→ MaturityProbePlanNode
→ WorkPackageQueryPlanNode
→ QueryPlanReviewNode
```

Phase 03 输出的是计划，不是证据。真正检索和入库在 Phase 04 执行。

### 2.3 检索源路由

| 证据类型 | 优先来源 |
|---|---|
| 英文论文 | OpenAlex、Semantic Scholar、Crossref、arXiv |
| 代码 / baseline | GitHub、Papers with Code、Hugging Face |
| 数据集 | Hugging Face Datasets、Kaggle、论文附录、项目主页 |
| 中文学位论文 | 学校仓储、知网摘要页、万方摘要页、公开论文库 |
| 技术模板 | 同方向硕博论文、综述论文、经典 benchmark 论文 |

---

## 3. 检索层级

```text
L0 原始题目精确检索
L1 中英文术语对齐
L2 去掉特殊场景后的通用任务
L3 底层方法族 / 技术路线
L4 数据集 / Baseline / Benchmark 专项检索
L5 学位论文 / 章节结构 / 实验模板检索
L6 Pivot 备选方向检索
```

### L0：原始题目精确检索

目的：确认是否已有高度相似题目或成熟论文。

### L1：术语对齐

目的：解决中文题目与英文检索词不一致的问题。

### L2：通用任务退化

目的：如果精确场景资料少，退到更成熟任务。

示例：

```text
中国研究生开题选题助手
→ academic topic recommendation
→ research idea generation
→ literature-based recommendation
→ evidence-grounded academic writing assistant
```

### L3：方法族检索

目的：为第二章相关基础和第三/四章技术路线准备材料。

### L4：数据集 / Baseline / Benchmark

目的：为 Phase 04 找实验入口。

### L5：学位论文与实验模板

目的：为开题报告和毕业论文目录提供结构证据。

### L6：Pivot 备选方向

目的：如果原题过大或证据不足，提前准备可收缩方向。

---

## 4. 检索策略

### 4.1 方向成熟度检索

```text
{task_en} survey
{task_en} review
{task_en} benchmark
{task_en} dataset
{task_en} github
{task_en} baseline
{task_en} evaluation metrics
{task_en} ablation study
```

### 4.2 Baseline 优先检索

```text
{task_en} code
{task_en} implementation
{paper_title} github
{method_name} github
{dataset_name} baseline
{task_en} papers with code
{task_en} huggingface
```

### 4.3 TopicPilot-CN 专项检索

```text
academic topic recommendation
research topic recommendation
research idea generation
literature based recommendation system
evidence grounded generation
retrieval augmented generation academic writing
LLM agent workflow evaluation
human in the loop topic selection
```

### 4.4 中文开题与学位论文模板检索

```text
开题报告 选题 辅助 系统
研究生 开题 选题 推荐
学位论文 选题 方法 研究现状
人工智能 开题报告 研究现状
RAG 学位论文
智能推荐系统 硕士论文
```

---

## 5. 输出模板：`02_query_plan.md`

```markdown
# 02_query_plan

## 1. 原题检索 L0
- 中文：
- 英文：

## 2. 术语对齐 L1
| 中文术语 | 英文术语 | 同义表达 | 用途 |
|---|---|---|---|

## 3. 通用任务检索 L2
| 通用任务 | 检索词 | 为什么退到这一层 |
|---|---|---|

## 4. 方法族检索 L3
| 方法族 | 检索词 | 对应论文章节 |
|---|---|---|

## 5. 数据集 / Baseline / Benchmark 检索 L4
### 数据集
-

### Baseline / 代码
-

### Benchmark / 指标
-

## 6. 学位论文与实验模板检索 L5
### 学位论文目录
-

### 对比实验模板
-

### 消融实验模板
-

## 7. Pivot 备选方向 L6
| 原方向风险 | 备选方向 | 检索词 | 收缩理由 |
|---|---|---|---|

## 8. 工作包检索映射
| 工作包 | 必要证据 | 检索词 | 优先来源 |
|---|---|---|---|

## 9. 方向成熟度预判
| 指标 | 检索方式 | 预判 | 风险 |
|---|---|---|---|
| 近年论文密度 |  |  |  |
| 综述数量 |  |  |  |
| 数据集数量 |  |  |  |
| 代码数量 |  |  |  |
| 同领域论文模板 |  |  |  |
```

---

## 6. 验收标准

- [ ] Phase 02 交接状态为 A/B，且 `TopicSpec` 可通过 Pydantic 校验。
- [ ] 至少 10 个英文检索词组合。
- [ ] 至少 5 个中文检索词组合。
- [ ] 检索计划覆盖论文、综述、数据集、baseline、benchmark、学位论文模板。
- [ ] 每个工作包雏形至少绑定 2 组检索词。
- [ ] 至少准备 1 个 Pivot 备选方向。
- [ ] 明确哪些检索由 API 执行，哪些需要人工或后续扩展。
- [ ] `SearchQueryPlan` 可通过 Pydantic 校验。

---

## 7. 阻断条件

出现以下情况必须回到 Phase 02：

1. `TopicSpec` 缺少核心任务、评价指标或工作包雏形。
2. 无法生成英文核心任务词。
3. 无法生成 baseline 检索词。
4. 工作包无法绑定任何检索证据。
5. 题目精确层和通用层都找不到可检索入口。
6. 所有检索都依赖封闭数据库，无法形成可复核证据链。
