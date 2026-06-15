# ThesisFlow：基于“水导式科研 SOP”的证据驱动科研 Agent 项目方案

## 1. 项目结论

GitHub 上已经存在不少科研 Agent，但目前没有一个项目完整覆盖以下流程：

> 选方向 → 找基准 → 阅读拆解 → 方法组合 → 实验组织 → 章节写作 → 校验修改 → 投稿答辩

现有项目通常只覆盖其中一部分，例如：

- 文献调研与综述生成
- PDF 科研问答
- 实验执行
- 论文写作
- 自动审稿
- 引用校验

因此，更合理的项目定位不是“自动生成一篇论文”，而是：

# ThesisFlow：证据驱动的科研工作流 Agent

一句话描述：

> 将研究生论文 SOP 编排为可暂停、可回放、有人类审核、带引用证据的 LangGraph 科研工作台。

这个项目的核心价值不在于让模型完全自主写论文，而在于将经验型科研流程转换成结构化、可执行、可追踪的 Agent 工作流。

---

## 2. 可参考的 GitHub 项目

| 项目 | 相似度 | 可借鉴部分 | 不建议直接照搬的部分 |
|---|---:|---|---|
| [Agent Laboratory](https://github.com/SamuelSchmidgall/AgentLaboratory) | ★★★★★ | 文献综述、实验、报告写作三阶段流程；不同角色 Agent 分工；人在环审核 | 偏自动科研，工程接口和项目管理能力较弱 |
| [PaperOrchestra](https://github.com/google-research/paper-orchestra) | ★★★★★ | 从研究想法和实验日志生成论文；Outline、Literature、Writer、Refiner、Plotter 多 Agent；LaTeX 模板 | 项目较新，适合作为架构参考，不宜直接作为唯一底座 |
| [STORM](https://github.com/stanford-oval/storm) | ★★★★☆ | 多角色调研、生成提纲、基于来源写长报告、引用组织 | 更偏向综述和百科式报告，不处理实验和论文项目状态 |
| [PaperQA2](https://github.com/future-house/paper-qa) | ★★★★☆ | PDF 科研 RAG、引用定位、文档问答、矛盾检测、索引复用 | 不负责完整论文工作流 |
| [data-to-paper](https://github.com/Technion-Kishony-lab/data-to-paper) | ★★★★☆ | 数据—代码—数值—结论的反向追溯；回放、回退、人工干预 | 对结构化数据研究更友好，计算机视觉实验需要改造 |
| [GPT Researcher](https://github.com/assafelovic/gpt-researcher) | ★★★☆☆ | Deep Research、并行搜索、流式进度、前端、LangGraph、可观测性 | 输出主要是调研报告，不是完整学术项目管理系统 |
| [AI Scientist v2](https://github.com/SakanaAI/AI-Scientist-v2) | ★★★☆☆ | 研究想法搜索、实验管理、自动执行、论文审稿 | 复杂、资源消耗高、成功率不稳定，不适合作为第一版 |
| AutoSurvey | ★★★☆☆ | 大规模论文检索、长综述生成、引用质量评估 | 主要覆盖综述环节 |

---

## 3. 各项目的具体参考价值

### 3.1 Agent Laboratory

Agent Laboratory 将科研流程划分为：

1. Literature Review
2. Experimentation
3. Report Writing

这个结构与“读论文—找方法—做实验—写论文”的主线最接近。

建议借鉴：

- 阶段化 Agent
- 每阶段设置明确输入与交付物
- 阶段之间结构化传递
- 关键节点允许用户修改并重新执行
- 不同角色负责不同职责

不建议第一版直接复刻其完整自动实验能力。第一版应优先解决：

- 文献管理
- Baseline 选择
- 方法组合
- 实验规划
- 章节组织
- 引用与证据校验

---

### 3.2 PaperOrchestra

PaperOrchestra 的核心角色包括：

- Outline Agent
- Literature Review Agent
- Section Writing Agent
- Refinement Agent
- Plotting Agent

这套结构可以直接映射到：

- 论文目录生成
- 相关工作生成
- 方法章节写作
- 实验章节写作
- 图表生成
- LaTeX 导出

建议将其作为“论文写作子系统”的参考，而不是整个系统的主框架。

---

### 3.3 STORM

STORM 适合参考：

- 多视角调研
- 研究问题分解
- 长报告提纲生成
- 基于来源的段落写作
- 引用组织

可以将“三层圈法读论文”转换为结构化 `PaperCard`：

```text
论文基本信息
├── 研究任务
├── Baseline
├── 核心问题
├── 方法模块
├── 数据集
├── 指标
├── 实验结论
├── 局限性
└── 可复用位置
```

STORM 负责广度搜索，PaperCard 负责工程化拆解。

---

### 3.4 PaperQA2

PaperQA2 可以作为科研 RAG 层的参考，重点支持：

```python
search_local_papers(query)
answer_from_papers(question)
find_supporting_evidence(claim)
compare_papers(paper_ids)
detect_contradiction(claim_a, claim_b)
```

推荐写作链路：

```text
提出论点
→ 检索证据
→ 定位原文
→ 生成带来源草稿
→ Citation Verifier 检查
```

Agent 不应直接凭模型记忆写相关工作。

---

### 3.5 data-to-paper

data-to-paper 最值得借鉴的是科研可追溯性。

例如论文中出现：

> CVCL-GT+proxy 的 EPE@Top50 降低了 49.7%。

系统应保存类似记录：

```json
{
  "claim": "EPE@Top50降低49.7%",
  "source_type": "experiment",
  "experiment_id": "cvcl_middlebury_ablation_v3",
  "source_file": "metrics.json",
  "formula": "(baseline - proposed) / baseline",
  "status": "verified"
}
```

这样项目就不只是一个聊天机器人，而是一个科研证据管理系统。

---

### 3.6 AI Scientist

AI Scientist 适合后期参考：

- 自动研究假设生成
- 自动实验执行
- 结果分析
- 自动论文写作
- 自动审稿

但第一版不建议采用完全自主式科研 Agent。

更适合你的设计是：

> 固定 SOP 主干 + 局部 Agent 决策

而不是：

> 让 Agent 自由决定全部研究过程

---

## 4. 项目核心设计原则

建议采用：

```text
Workflow 负责确定性流程
Agent 负责不确定性判断
Tool 负责实际执行
Human Gate 负责高风险决策
```

示例：

| 环节 | 推荐实现方式 |
|---|---|
| 上传资料、解析 PDF | 固定 Workflow |
| 判断当前科研阶段 | Agent |
| 文献检索 | Tool |
| 判断哪篇适合作为 Baseline | Agent + 评分规则 |
| 计算实验指标 | Python Tool |
| 是否接受候选创新点 | Human Gate |
| 生成章节草稿 | Writer Agent |
| 检查引用是否真实支持论点 | Citation Verifier |
| 导出 Word 或 LaTeX | 固定 Workflow |

---

## 5. 推荐总体架构

```text
用户输入
   │
   ▼
项目初始化 Agent
   │
   ├── 研究方向与毕业要求
   ├── 已有论文、代码和实验
   ├── 学校模板
   └── 时间与硬件约束
   │
   ▼
LangGraph Supervisor
   │
   ├── 文献研究子图
   ├── Baseline 分析子图
   ├── 方法组合子图
   ├── 实验规划子图
   ├── 章节写作子图
   └── 质量审查子图
   │
   ▼
证据与项目状态数据库
   │
   ▼
Markdown / DOCX / LaTeX / PPT
```

---

## 6. 将科研 SOP 转换为 Agent 节点

### 6.1 阶段一：项目建档

输入：

- 专业与研究方向
- 学校论文要求
- 开题报告
- 中期报告
- 已发表小论文
- 当前代码仓库
- 已有实验结果
- 学长论文
- 目标期刊或毕业要求

输出：

```python
class ProjectBrief:
    research_domain: str
    research_task: str
    graduation_constraints: list[str]
    available_assets: list[str]
    datasets: list[str]
    code_repositories: list[str]
    current_stage: str
    target_deadline: str
```

这一步对应“前期资料整理”。

---

### 6.2 阶段二：方向与 Baseline Agent

主要任务：

1. 搜索相关研究
2. 构建领域方法树
3. 识别常见数据集和评价指标
4. 提取候选 Baseline
5. 对候选 Baseline 排序
6. 给出实现风险和复现成本

建议评分公式：

```text
BaselineScore =
    0.25 × 代码可用性
  + 0.20 × 数据兼容性
  + 0.20 × 复现成本
  + 0.15 × 发布时间
  + 0.10 × 社区活跃度
  + 0.10 × 可扩展模块数
```

输出表格：

| Baseline | 代码状态 | 数据适配 | 算力成本 | 可修改位置 | 风险 |
|---|---|---|---|---|---|

---

### 6.3 阶段三：论文阅读与知识库

每篇论文生成标准化 PaperCard：

```python
class PaperCard:
    title: str
    task: str
    problem: list[str]
    baseline: str
    modules: list[str]
    datasets: list[str]
    metrics: list[str]
    key_results: dict
    limitations: list[str]
    reusable_parts: list[str]
    evidence_spans: list[str]
```

同时建立以下关系：

```text
论文 → 使用了什么 Baseline
论文 → 增加了什么模块
论文 → 解决了什么问题
论文 → 使用了什么数据集
论文 → 使用了什么指标
```

最终形成方法谱系图，而不只是向量数据库。

---

### 6.4 阶段四：方法组合与创新审计

将 A+B+C 思路改造成合规、可验证的形式：

```text
Baseline A
+ 能解决明确问题 P1 的模块 B
+ 能解决明确问题 P2 的模块 C
= 候选方法 M
```

每个候选组合必须回答：

1. A 当前存在什么有证据的问题？
2. B 为什么可能解决该问题？
3. B 与 A 的输入输出是否兼容？
4. C 是否重复解决同一个问题？
5. 增加模块后如何设计消融实验？
6. 失败时有什么降级方案？
7. 是否已有论文做过相同组合？

输出：

```json
{
  "baseline": "A",
  "module_b": "B",
  "module_c": "C",
  "target_problem": ["P1", "P2"],
  "supporting_papers": ["paper_12", "paper_25"],
  "novelty_risk": "medium",
  "implementation_cost": "low",
  "required_experiments": [
    "A",
    "A+B",
    "A+C",
    "A+B+C"
  ]
}
```

---

### 6.5 阶段五：实验规划 Agent

实验规划应包含：

- 主实验
- 对比实验
- 消融实验
- 参数实验
- 泛化实验
- 失败案例
- 资源估算
- 预期表格结构

推荐流程：

```text
实验问题
→ 所需对照组
→ 指标
→ 数据集
→ 运行命令
→ 结果文件
→ 可支持的论文结论
```

必须遵守：

- 没有实验日志时不得生成结果
- 没有指标文件时不得生成数字
- 未完成实验统一标记为 `RESULT_PENDING`
- 结论只能基于实际结果生成

---

### 6.6 阶段六：论文结构 Agent

将五章式模板实现为可配置 Schema：

```text
第1章 绪论
├── 研究背景
├── 国内外研究现状
├── 存在问题
├── 研究内容
└── 章节安排

第2章 理论与技术基础

第3章 方法一
├── 问题1
├── 问题2
├── 问题3
├── 总体模型
├── 关键模块
└── 实验验证

第4章 方法二
├── 研究问题
├── 方法设计
├── 工程实现
└── 实验验证

第5章 总结与展望
```

可支持模板切换：

- 硕士五章式
- SCI 六模块
- 会议论文模板
- 学校自定义模板

---

### 6.7 阶段七：证据约束写作

Writer Agent 生成段落时，应同时生成证据记录：

```json
{
  "paragraph": "……",
  "claims": [
    {
      "text": "……",
      "evidence_id": "paper_003_chunk_18",
      "status": "supported"
    }
  ]
}
```

证据状态：

| 状态 | 含义 |
|---|---|
| `supported` | 有明确文献或实验支持 |
| `author_claim` | 属于本文观点，需要作者确认 |
| `needs_source` | 当前缺少来源，不应进入正式稿 |
| `conflict` | 不同来源之间存在矛盾 |
| `verified_experiment` | 可追溯到实验结果文件 |

---

### 6.8 阶段八：多 Agent 审查

第一版不需要堆叠过多 Agent，保留三个审查角色即可。

#### Reviewer A：学术逻辑

检查：

- 研究问题是否闭环
- 方法是否对应问题
- 实验是否支撑结论
- 创新点是否被夸大
- 章节之间是否存在逻辑断裂

#### Reviewer B：证据与引用

检查：

- 引用是否真实存在
- 原文是否支持当前论点
- 数据是否与实验文件一致
- 是否存在孤立数字
- 是否存在伪造参考文献

#### Reviewer C：论文结构

检查：

- 章节重复
- 前后术语不一致
- 图表是否被正文引用
- 摘要、结论与创新点是否对应
- 图表编号、公式编号是否连续

最后由 Supervisor 合并审查意见。

---

## 7. 推荐技术栈

| 层级 | 技术选择 |
|---|---|
| Agent 编排 | LangGraph |
| 后端 | FastAPI + Pydantic |
| 异步任务 | Celery 或 Dramatiq + Redis |
| 数据库 | PostgreSQL |
| 向量检索 | pgvector 或 Qdrant |
| 文件存储 | MinIO |
| PDF 解析 | Docling / GROBID / PyMuPDF |
| 文献元数据 | OpenAlex / Semantic Scholar / Crossref |
| 关键词检索 | BM25 |
| 语义检索 | Embedding + Reranker |
| 前端 | Next.js 或 Vue |
| 实时状态 | SSE 或 WebSocket |
| Agent 追踪 | LangSmith 或 OpenTelemetry |
| 输出 | Markdown / DOCX / LaTeX |
| 部署 | Docker Compose |

---

## 8. 第一版 MVP 范围

第一版不应覆盖完整科研生命周期，而应先实现最有展示价值的闭环。

### 8.1 MVP 输入

- 一个研究题目
- 10～30 篇本地 PDF
- 一份开题报告
- 一个代码仓库说明
- 若干实验 CSV 或 JSON
- 一个学校论文模板

### 8.2 MVP 输出

1. 论文 PaperCard
2. 领域方法分类
3. Baseline 候选表
4. 问题—方法—实验矩阵
5. 五章式论文目录
6. 相关工作草稿
7. 方法章节骨架
8. 带来源的实验分析草稿
9. 引用与数字审查报告
10. Markdown / DOCX / LaTeX 导出

### 8.3 MVP 状态图

```text
START
  ↓
项目建档
  ↓
资料解析
  ↓
论文卡片生成
  ↓
Baseline 检索与评分
  ↓
方法组合候选
  ↓
[人工选择候选方案]
  ↓
实验矩阵生成
  ↓
章节目录生成
  ↓
分章节写作
  ↓
引用验证
  ↓
Reviewer 审查
  ↓
[人工确认]
  ↓
导出
```

---

## 9. 六周开发计划

### 第 1 周：工作流形式化

完成：

- 整理科研 SOP
- 定义 LangGraph 节点
- 定义 Pydantic 数据模型
- 绘制状态图
- 实现项目创建和检查点

核心数据模型：

```text
ProjectBrief
PaperCard
ContributionCandidate
ExperimentPlan
DraftSection
EvidenceClaim
ReviewReport
```

---

### 第 2 周：文献解析与 RAG

完成：

- PDF 上传与解析
- 标题、摘要、章节、参考文献提取
- BM25 + 向量混合检索
- PaperCard 自动生成
- 原文证据片段定位

评价指标：

- 文献元数据解析成功率
- Recall@5
- 引用定位准确率
- PDF 处理耗时

---

### 第 3 周：Baseline 与方法组合

完成：

- Baseline 候选检索
- 方法模块抽取
- 问题—模块关系图
- A+B+C 候选组合
- 相似工作检索
- 人工审批节点

核心演示：

> 输入研究方向，输出 3 个有证据的候选方法，并给出实现成本、创新风险和实验需求。

---

### 第 4 周：实验与写作

完成：

- 实验计划生成
- CSV / JSON 指标读取
- 自动表格分析
- 论文目录生成
- 相关工作草稿
- 方法章节草稿
- Markdown / LaTeX 导出

必须保证：

- 没有结果时不生成虚假数字
- 每个数字能回溯到文件
- 每个文献观点能回溯到原文

---

### 第 5 周：审查与评估

完成：

- Citation Verifier
- Experiment Verifier
- Logic Reviewer
- 多 Agent 冲突合并
- 运行轨迹记录
- 成本与时延统计

评价指标：

| 指标 | 含义 |
|---|---|
| Citation Precision | 引用是否真正支持句子 |
| Unsupported Claim Rate | 无来源论断比例 |
| Numerical Consistency | 正文数字与结果文件一致率 |
| Human Acceptance Rate | 用户直接接受段落的比例 |
| Workflow Success Rate | 完整流程完成率 |
| Average Cost | 单项目 API 成本 |
| Replay Success Rate | 中断后恢复成功率 |

---

### 第 6 周：产品化与作品集

完成：

- Web 项目主页
- 项目进度时间线
- Agent 状态图可视化
- 文献卡片页面
- 实验证据页面
- 在线流式运行
- Docker 一键部署
- 演示视频
- 架构文档
- 测试报告

---

## 10. 可写入论文或项目介绍的创新点

### 10.1 SOP-to-Graph

将经验型科研 SOP 转换为可执行状态图：

```text
自然语言经验
→ 节点
→ 条件边
→ 输入输出契约
→ 人工审批
```

这比普通“论文聊天机器人”更有系统性。

---

### 10.2 双层知识表示

系统同时维护：

```text
文本向量索引
+
论文方法关系图
```

关系图包括：

```text
Problem → Method
Method → Baseline
Method → Dataset
Method → Metric
Claim → Evidence
```

可命名为：

> Evidence-aware Research Graph

---

### 10.3 科研证据账本

所有输出均记录来源：

```text
段落 → 论断 → 文献片段
数字 → 指标文件 → 实验命令
图表 → 生成脚本 → 原始数据
```

这可以显著提升：

- 可追溯性
- 可复现性
- 引用可靠性
- 实验一致性
- 项目展示价值

---

### 10.4 阶段感知路由

系统根据项目状态自动选择工具：

```text
刚选题
→ 文献和 Baseline Agent

已有代码但没有实验
→ Experiment Planner

已有实验但没有论文
→ Writer Agent

已有论文初稿
→ Reviewer + Citation Verifier
```

这比固定 Agent 链更符合真实科研过程。

---

## 11. 作为实习项目的价值

这个项目可以展示五类能力：

1. **Agent 编排**
   - LangGraph
   - 条件边
   - 检查点
   - 人在环

2. **RAG**
   - PDF 解析
   - 混合检索
   - Reranker
   - 引用定位

3. **后端工程**
   - FastAPI
   - 异步任务
   - 流式输出
   - 数据库设计

4. **Agent Evaluation**
   - 幻觉率
   - 引用准确率
   - 轨迹评估
   - 数值一致性

5. **产品实现**
   - 项目管理
   - 进度展示
   - 文档导出
   - Docker 部署

简历描述示例：

> 设计并实现证据驱动的科研工作流 Agent，将选题、文献分析、Baseline 选择、实验规划、章节写作和多 Agent 审查编排为可回放的 LangGraph 状态图；构建混合检索与句级引用追踪系统，实现论文论断、实验结果和原始证据之间的可追溯关联。

---

## 12. 必须进行的合规调整

可以工程化的部分：

- 资料准备
- 论文拆解
- Baseline 寻找
- 方法模块分析
- 实验组织
- 章节模板
- 格式审查
- 答辩材料准备

不应实现为产品功能的部分：

- 洗稿和规避查重
- 伪造创新性
- 编造实验结果
- 生成不存在的引用
- 一稿多投规避检测
- 将他人方法简单替换名称后宣称原创

可以将“降重 Agent”改为：

> Academic Revision Agent：检查重复表达、引用缺失、术语一致性和原创贡献边界。

---

## 13. 最终推荐组合

```text
LangGraph
→ 主状态图与人在环控制

Agent Laboratory
→ 科研阶段划分

STORM
→ 文献调研与提纲

PaperQA2
→ PDF RAG 与引用定位

PaperOrchestra
→ 分章节写作与 LaTeX 输出

data-to-paper
→ 证据追溯与流程回放

GPT Researcher
→ 前端、流式进度和可观测性
```

---

## 14. 推荐实施顺序

第一步不是直接编写 Agent，而是先完成以下四项设计：

1. 需求规格
2. 状态图
3. 核心数据模型
4. MVP 验收指标

推荐实施顺序：

```text
科研 SOP 形式化
→ 数据模型
→ LangGraph 状态图
→ PDF RAG
→ Baseline Agent
→ 实验规划 Agent
→ 写作 Agent
→ 引用与数字校验
→ Web 产品化
```

项目第一阶段只需要跑通：

> 上传论文 → 生成 PaperCard → 推荐 Baseline → 生成实验矩阵 → 输出章节骨架 → 校验证据

完成这一闭环后，再增加自动实验、图表生成、DOCX 导出和多 Agent 审稿能力。
