﻿# Phase 04：证据采集与 Baseline 账本

> 阶段目标：执行多路检索，建立论文、数据集、baseline、指标、实验模板和学位论文结构的证据账本。  
> 方法依据：毕业论文合集强调“先找基准，再谈方法；先确认实验入口，再谈创新点”。  
> 技术落点：PostgreSQL + pgvector 证据表、Docling/GROBID 文档解析、BGE-M3 embedding、BGE-Reranker 重排、Celery 异步任务。  
> 阶段输入：Phase 03 验收通过的 `02_query_plan.md` / `SearchQueryPlan`。  
> 阶段产物：`03_evidence_ledger.md`、结构化 evidence records、baseline 账本。

---

## 1. 阶段定位

Phase 04 是从“计划”进入“证据”的阶段。

进入 Phase 04 的前提是检索计划已经明确：

```text
SearchQueryPlan 可通过 Pydantic 校验
论文 / 综述 / 数据集 / baseline / benchmark / 学位论文模板均有检索入口
每个工作包至少绑定 2 组检索词
```

它不负责最终创新点设计，而是回答：

- 这个题目有没有足够论文支撑？
- 有没有公开数据或可获得数据？
- 有没有可运行 baseline？
- 有没有公认评价指标？
- 有没有对比实验、消融实验、参数实验模板？
- 有没有学位论文目录可参考？
- 证据是否能支撑后续开题报告和毕业论文目录？

若数据、baseline、指标任一项缺失，题目必须进入高风险状态，不能直接进入创新点规划。

---

## 2. 毕业方法论转化

| 毕业论文合集经验 | Phase 04 中的产品化规则 |
|---|---|
| 先找 baseline，再谈方法 | baseline 账本是必交付物 |
| 实验是客观陈述 | 每个创新雏形必须找到可评价指标 |
| 消融支撑创新点 | 采集对比实验、消融实验和参数实验模板 |
| 同领域论文模板有价值 | 采集学位论文目录和方法章节结构 |
| 继承优于从零复现 | 记录开源代码、同门代码、课题组数据的可用性和授权风险 |

---

## 3. 技术设计

### 3.1 数据对象

```python
class PaperEvidence(BaseModel):
    project_id: str
    query_plan_id: str
    title: str
    year: int | None
    source: str
    url: str | None
    abstract: str | None
    task: list[str]
    method: list[str]
    datasets: list[str]
    metrics: list[str]
    baseline_mentions: list[str]
    reusable_value: str
    evidence_score: float

class BaselineCandidate(BaseModel):
    project_id: str
    query_plan_id: str
    name: str
    paper_title: str | None
    repository_url: str | None
    has_readme: bool
    has_env_file: bool
    has_training_script: bool
    has_eval_script: bool
    has_pretrained_weight: bool
    license: str | None
    reproduce_difficulty: Literal["低", "中", "高", "未知"]
    fit_to_student_resources: Literal["适合", "勉强", "不适合", "未知"]
```

### 3.2 数据库存储

PostgreSQL 保存：

```text
papers
datasets
baselines
metrics
experiment_templates
thesis_templates
evidence_relations
embeddings
retrieval_runs
```

pgvector 保存论文摘要、章节片段、baseline 描述和模板片段的 embedding。

### 3.3 检索与重排流程

```text
API / Web / 本地文档召回
→ 元数据清洗
→ Docling / GROBID 解析
→ PostgreSQL 全文检索字段入库
→ BGE-M3 embedding
→ lexical full-text retrieval + dense vector retrieval
→ Reciprocal Rank Fusion
→ BGE-Reranker-v2-M3
→ Top Evidence 入账
→ LLM 结构化摘要
```

注意：文档中使用“lexical full-text retrieval + dense vector retrieval”，不要把 PostgreSQL 全文检索直接写成 BM25。

### 3.4 异步任务边界

Celery 负责耗时任务：

- 批量 API 检索
- PDF / DOCX 解析
- embedding 计算
- reranking
- GitHub 仓库元数据检查
- 证据摘要生成

LangGraph 只负责任务编排和状态转移。

---

## 4. 必采证据类型

| 类型 | 最小要求 | 用途 |
|---|---|---|
| 论文证据 | 10 篇相关论文或明确证明不足 | 判断方向成熟度、研究问题和已有方法 |
| 综述证据 | 1 篇综述或自建分类依据 | 支撑研究现状层次 |
| 数据集证据 | 2 个候选或明确证明不足 | 判断实验入口 |
| Baseline/代码证据 | 2 个候选或明确证明不足 | 判断复现与工作量可行性 |
| 指标证据 | 1 套可复现指标 | 支撑实验评价 |
| 实验模板证据 | 1 个对比 / 消融模板 | 支撑创新点验证 |
| 学位论文模板证据 | 1 篇同领域目录或明确暂无 | 支撑五章式目录 |
| 继承资源证据 | 所有课题组资源都要记录 | 判断合法复用与落地性 |

---

## 5. Baseline 账本字段

每个 baseline 候选必须记录：

- 对应论文
- 代码仓库
- License
- README 是否完整
- 环境配置是否存在
- 数据预处理脚本是否存在
- 训练脚本是否存在
- 评价脚本是否存在
- 预训练权重是否存在
- 最近更新时间
- Issue 活跃度
- 是否有人复现
- 预计复现难度
- 是否适合学生当前算力和时间
- 可作为 WP1 / WP2 的哪一部分

---

## 6. 执行步骤

### Step 1：执行论文与综述检索

输出：

- 论文候选列表
- 综述候选列表
- 近 3-5 年发表趋势
- 方法类别初步分类

### Step 2：执行数据集检索

输出：

- 数据集名称
- 任务类型
- 模态
- 规模
- 标注类型
- 下载方式
- License
- 与题目匹配度

### Step 3：执行 baseline 与代码检索

输出：

- 代码仓库
- 复现条件
- 维护状态
- 运行风险
- 与学生资源匹配度

### Step 4：采集指标与实验模板

输出：

- 主指标
- 辅助指标
- 对比实验模板
- 消融实验模板
- 参数实验模板
- 案例分析模板

### Step 5：采集学位论文结构证据

输出：

- 五章式目录参考
- 方法章节结构
- 实验章节结构
- 开题报告可复用材料

### Step 6：生成证据成熟度结论

对方向给出结论：

```text
A：证据充分，可进入风险评分与工作包设计
B：证据基本充分，但存在明确风险
C：证据不足，需要 Pivot 或补充检索
D：关键证据缺失，不建议继续当前题目
```

---

## 7. 输出模板：`03_evidence_ledger.md`

```markdown
# 03_evidence_ledger

## 1. 方向成熟度证据
| ID | 证据 | 年份 | 来源 | 说明 | 可信度 |
|---|---|---|---|---|---|

## 2. 论文证据
| ID | 标题 | 年份 | 来源 | 关联任务 | 方法 / 数据 / 结论 | 可复用价值 |
|---|---|---|---|---|---|---|

## 3. 综述证据
| ID | 标题 | 年份 | 可用于哪一层研究现状 | 备注 |
|---|---|---|---|---|

## 4. 数据集证据
| ID | 名称 | 任务 | 模态 | 规模 | 标注 | 下载 | 许可 | 风险 |
|---|---|---|---|---|---|---|---|---|

## 5. Baseline / 代码证据
| ID | 名称 | 论文 | 仓库 | License | 环境 | 训练 | 评价 | 权重 | 复现难度 | 风险 |
|---|---|---|---|---|---|---|---|---|---|---|

## 6. 指标证据
| 指标 | 适用任务 | 来源 | 是否可复现 | 备注 |
|---|---|---|---|---|

## 7. 实验模板证据
| ID | 来源论文 | 对比实验 | 消融实验 | 参数实验 | 可借鉴写法 |
|---|---|---|---|---|---|

## 8. 学位论文结构证据
| ID | 来源 | 目录结构 | 方法章节结构 | 可借鉴内容 |
|---|---|---|---|---|

## 9. 课题组可继承资源
| 资源 | 是否可用 | 授权 / 署名风险 | 对本题帮助 |
|---|---|---|---|

## 10. 证据关系
| 工作包 | 支撑论文 | 支撑数据 | 支撑 baseline | 支撑指标 | 缺口 |
|---|---|---|---|---|---|

## 11. Phase 04 结论
- 方向成熟度：
- 数据可用性：
- Baseline 可用性：
- 指标可用性：
- 章节模板可用性：
- 证据评级：A / B / C / D
- 是否允许进入后续风险评分与工作包设计：
```

---

## 8. 验收标准

- [ ] Phase 03 交接状态为 A/B，且 `SearchQueryPlan` 可通过 Pydantic 校验。
- [ ] 至少 10 篇相关论文，或明确证明精确方向论文不足。
- [ ] 至少 1 篇综述或研究现状类材料，或明确说明需自建分类。
- [ ] 至少 2 个数据集候选，或明确证明数据不足。
- [ ] 至少 2 个 baseline / 代码候选，或明确证明代码不足。
- [ ] 至少 1 套评价指标。
- [ ] 至少 1 个对比实验或消融实验模板。
- [ ] 至少 1 篇同领域学位论文 / 目录模板，或明确说明暂无。
- [ ] 所有关键证据都有来源、年份、链接或可追溯说明。
- [ ] Baseline 候选有复现难度判断。
- [ ] 证据记录可入库，并能绑定到工作包。

---

## 9. 阻断条件

出现以下情况不得进入后续工作包设计：

1. Phase 03 没有通过验收，或检索计划缺少 baseline / 数据集 / 指标入口。
2. 没有可用数据，也没有可获得替代数据。
3. 没有 baseline，也没有可比较的规则方法或系统方法。
4. 没有评价指标。
5. 论文证据无法支撑研究现状。
6. 关键证据来源不可追溯。
7. baseline 复现周期超过 Phase 01 中的时间红线。

---

## 10. 与后续 Phase 的交接

Phase 04 之后，后续阶段应基于证据账本继续执行：

- 风险评分：根据论文、数据、baseline、指标、时间红线计算选题风险。
- Pivot：若证据不足，生成收缩方向和替代题目。
- 工作包设计：将证据链映射到 2 个左右可写入第三章、第四章的工作包。
- 开题报告生成：把证据账本转为研究现状、技术路线、实验方案和风险预案。
