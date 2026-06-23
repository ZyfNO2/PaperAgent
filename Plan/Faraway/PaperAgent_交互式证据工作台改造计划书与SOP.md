# PaperAgent 交互式证据工作台改造计划书与 SOP

> 项目：ZyfNO2/PaperAgent（TopicPilot-CN / OneTopic MVP）  
> 目标：把当前“一键生成式开题判断”升级为“证据驱动、可人工干预、可回退、可复用”的开题选题助手。  
> 本轮重点：手动添加论文、阶段性用户交互、论文/数据集/工程检索增强。

---

## 0. 当前状态判断

从当前页面和仓库 README 看，项目已经具备一个可演示的 OneTopic MVP：

- 输入一个题目；
- 拆解关键词；
- 检索论文、数据集、工程；
- 输出可行性判断；
- 输出开题建议和工作包；
- 右侧展示 Agent Trace；
- 后端已有 FastAPI、Pydantic、LangGraph 基础；
- 前端已有可运行页面。

当前最大问题不是“功能完全没有”，而是：

> 系统已经能自动跑通，但还没有形成真正适合开题场景的“证据工作台”。

| 问题 | 当前表现 | 对开题助手的影响 |
|---|---|---|
| 没有手动添加论文 | 用户只能依赖系统自动检索 | 导师给的论文、用户已有论文、中文数据库导出的文献无法进入证据链 |
| 缺少中间交互 | 按一下按钮全部跑完 | 用户不能修正关键词、剔除错误论文、选择退化方向 |
| 检索质量不稳定 | 数据集、论文、工程检索容易混杂 | 可行性判断可能被低质量证据误导 |

下一阶段不应继续堆生成能力，而应先补齐：

```text
自动检索
+
手动证据导入
+
人工审核关卡
+
分阶段继续运行
+
可解释检索评分
```

---

# 1. 下一阶段总目标

## 1.1 产品定位

将 PaperAgent 从：

> 输入一个题目 → 自动输出开题建议

升级为：

> 输入一个题目 → 构建证据池 → 用户审核证据 → 系统判断可行性 → 用户选择退化路线 → 系统生成工作包与开题方案。

## 1.2 技术定位

下一阶段重点展示以下实习能力：

- Agent 状态机与人在环；
- RAG 与证据管理；
- 多源检索与检索质量控制；
- 数据集和 GitHub 工程可用性评估；
- 前后端交互设计；
- 可复现的评估与回归测试。

---

# 2. 改造原则

## 2.1 不要一键到底

当前的“一键到底”适合 Demo，但不适合开题场景。

开题选题需要反复确认：

```text
题目是否被正确理解？
关键词是否正确？
检索结果是否相关？
数据集是否真实可用？
Baseline 是否真的能跑？
是否需要收缩题目？
工作包是否符合毕业要求？
```

因此系统必须增加 **Human Gate**。

## 2.2 不要只信自动检索

开题时学生通常已经有：

- 导师给的 3～5 篇核心论文；
- 学长论文；
- 中文数据库导出的 BibTeX / RIS；
- arXiv / DOI / GitHub 链接；
- 课程或课题组已有数据集；
- 已下载 PDF。

这些材料必须能手动进入系统。

## 2.3 不要只看论文数量

判断是否“造航母”，不能只看论文多不多，还要看：

- 有没有公开数据集；
- 数据集是否匹配题目；
- 有没有成熟 Baseline；
- 工程代码是否可运行；
- 指标是否明确；
- 是否能拆成 2～3 个工作包；
- 是否符合当前时间和算力。

## 2.4 不要让 LLM 独自决定证据质量

LLM 可以总结证据，但证据质量评分应尽量规则化：

```text
论文相关性
数据集可获得性
代码完整性
实验可评价性
工作包独立性
```

LLM 负责解释，规则负责兜底。

---

# 3. 参考项目与借鉴点

## 3.1 ResearchAgent

ResearchAgent 的核心价值在于：

```text
核心论文
→ 检索相关论文和知识实体
→ 生成研究问题
→ 多 Reviewer 评价
→ 迭代修改
```

可借鉴：

- 从“用户手动指定核心论文”启动；
- 候选研究问题需要多轮评价；
- Reviewer 不直接写结论，而是给修改建议；
- 研究问题、方法、实验需要互相对应。

对应改造：

```text
用户上传/手动添加核心论文
→ 系统围绕核心论文扩展检索
→ 生成候选题目和工作包
→ 开题委员会 Agent 审核
```

## 3.2 DatasetResearch

DatasetResearch 的启示是：

> 数据集发现本身就是一个困难任务，不能让系统仅凭模型记忆输出数据集名称。

可借鉴：

- 数据集搜索应独立成模块；
- 数据集需要验证来源、下载、许可、标注和任务匹配；
- 对数据集的判断要有结构化字段。

对应改造：

```text
DatasetCandidate
├── 数据集名称
├── 来源链接
├── 下载状态
├── 数据规模
├── 标注类型
├── 许可
├── 关联论文
├── 已有 Baseline
└── 适配风险
```

## 3.3 PaperQA2

PaperQA2 的价值在于面向科研文献的高准确率 RAG，强调：

- 科学文献问答；
- 引用定位；
- 证据排序；
- 总结、问答和矛盾检测；
- PDF、文本、Office 文档和代码文件的处理。

对应改造：

```text
用户手动上传论文 PDF
→ 解析成 PaperCard
→ 切片入库
→ 后续可行性判断必须引用这些片段
```

## 3.4 AI Scientist / AI Researcher 类项目

这些项目强调：

- 想法生成；
- 新颖性检查；
- 实验设计；
- 多轮审查。

可借鉴：

- novelty check；
- idea refinement；
- 实验矩阵生成；
- 多 Agent 审查。

不应照搬：

- 自动生成论文；
- 自动宣称创新；
- 自动执行完整实验；
- 不经过人工确认的开题结论。

---

# 4. 总体改造路线

## 4.1 当前流程

```text
输入题目
→ 自动拆解关键词
→ 自动检索论文/数据集/工程
→ 自动判断可行性
→ 自动生成工作包
```

## 4.2 改造后流程

```text
输入题目
        ↓
题目拆解
        ↓
【Human Gate 1】确认/修改关键词
        ↓
自动检索 + 手动添加证据
        ↓
证据池构建
        ↓
【Human Gate 2】审核论文、数据集、工程证据
        ↓
可行性判断
        ↓
【Human Gate 3】接受判断 / 补充证据 / 重新检索
        ↓
生成退化路线
        ↓
【Human Gate 4】选择保守 / 平衡 / 激进路线
        ↓
生成 2～3 个工作包
        ↓
【Human Gate 5】确认工作包
        ↓
生成开题报告骨架和修改清单
```

---

# 5. 功能改造一：手动添加论文与证据

## 5.1 目标

新增一个“证据工作台”，允许用户手动添加：

- 论文标题；
- DOI；
- arXiv ID；
- Semantic Scholar URL；
- OpenAlex URL；
- PDF 文件；
- BibTeX；
- RIS；
- GitHub 仓库；
- Hugging Face Dataset；
- Kaggle / OpenML / Zenodo 链接；
- 自有数据集说明；
- 导师备注。

## 5.2 前端页面

新增页面：

```text
/projects/[id]/evidence
```

页面分区：

```text
证据池
├── 论文
├── 数据集
├── GitHub 工程
├── Baseline
├── 用户自有资料
└── 待审核证据
```

新增按钮：

```text
+ 添加论文
+ 上传 PDF
+ 导入 BibTeX / RIS
+ 添加 GitHub 仓库
+ 添加数据集链接
+ 添加导师备注
```

## 5.3 手动添加方式

### 方式 A：输入 DOI / arXiv

```text
用户输入 DOI / arXiv
→ 系统调用 Crossref / arXiv / Semantic Scholar
→ 补全标题、作者、年份、摘要
→ 生成 PaperCandidate
→ 用户确认
→ 入 EvidenceLedger
```

### 方式 B：上传 PDF

```text
上传 PDF
→ Docling / PyMuPDF 解析
→ GROBID 提取标题、摘要和参考文献
→ LLM 生成 PaperCard
→ 用户审核
→ 入 EvidenceLedger
```

### 方式 C：导入 BibTeX / RIS

```text
上传 BibTeX / RIS
→ 解析条目
→ 去重
→ 批量补全元数据
→ 批量生成 PaperCandidate
→ 用户勾选入库
```

### 方式 D：手动填写

```text
标题
作者
年份
摘要
链接
备注
与当前题目的关系
```

适合中文数据库导出不完整、导师口头推荐等场景。

## 5.4 后端接口

```text
POST /api/v1/projects/{project_id}/evidence/papers/manual
POST /api/v1/projects/{project_id}/evidence/papers/upload-pdf
POST /api/v1/projects/{project_id}/evidence/papers/import-bibtex
POST /api/v1/projects/{project_id}/evidence/papers/import-ris
POST /api/v1/projects/{project_id}/evidence/datasets/manual
POST /api/v1/projects/{project_id}/evidence/repos/manual
GET  /api/v1/projects/{project_id}/evidence
PATCH /api/v1/evidence/{evidence_id}/review
DELETE /api/v1/evidence/{evidence_id}
```

## 5.5 数据结构

```python
class EvidenceItem(BaseModel):
    evidence_id: str
    project_id: str
    evidence_type: Literal[
        "paper", "dataset", "repo", "baseline", "note", "thesis", "custom"
    ]
    source_mode: Literal["auto_search", "manual", "upload", "import"]
    title: str
    url: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    year: int | None = None
    abstract: str | None = None
    authors: list[str] = []
    tags: list[str] = []
    user_note: str | None = None
    relevance_score: float | None = None
    quality_score: float | None = None
    review_status: Literal[
        "pending", "accepted", "rejected", "needs_check"
    ] = "pending"
```

## 5.6 验收标准

- 用户可以手动添加一篇论文；
- 用户可以上传 PDF 并生成 PaperCard；
- 用户可以导入 BibTeX / RIS；
- 手动证据会出现在可行性判断中；
- 自动证据和手动证据能区分来源；
- 用户可以接受、拒绝、标记待核查；
- 被拒绝证据不参与最终评分。

---

# 6. 功能改造二：加入中间交互与 Human Gate

## 6.1 目标

把“一键跑到底”改为“分阶段确认”。

## 6.2 推荐关卡

### Gate 1：关键词确认

系统输出：

```text
方法词：YOLO、YOLOv8
任务词：检测、目标检测
对象词：钢材表面缺陷
场景词：工业质检
风险词：实时、高精度
```

用户操作：

```text
确认
编辑关键词
增加关键词
删除关键词
要求重新拆解
```

### Gate 2：检索计划确认

系统输出：

```text
论文检索词
数据集检索词
工程检索词
Baseline 检索词
中文检索词
英文检索词
```

用户操作：

```text
确认检索
增加中文关键词
增加英文关键词
删除错误检索词
指定必须检索的论文/数据集/仓库
```

### Gate 3：证据审核

系统展示：

```text
论文候选
数据集候选
GitHub 候选
Baseline 候选
```

用户操作：

```text
接受
拒绝
标记为核心证据
标记为背景证据
标记为无关
补充证据
```

### Gate 4：可行性判断确认

系统输出：

```text
GO / NARROW / PIVOT / PARK / STOP
```

用户操作：

```text
接受判断
要求解释
补充证据后重算
手动调整目标档位
进入退化路线
```

### Gate 5：退化路线选择

系统输出三条路线：

```text
保守路线：优先毕业
平衡路线：保留部分创新
激进路线：保留原始想法
```

用户操作：

```text
选择一条
合并两条
要求重新生成
指定保留某个关键词
```

### Gate 6：工作包确认

系统输出：

```text
WP1
WP2
WP3
实验矩阵
章节映射
```

用户操作：

```text
确认
删除一个工作包
要求增加工程系统工作包
要求降低难度
要求增强创新性
```

## 6.3 LangGraph 改造

新增 `interrupt` / `resume` 语义：

```text
parse_topic
→ keyword_review_gate
→ build_query_plan
→ query_review_gate
→ collect_evidence
→ evidence_review_gate
→ judge_feasibility
→ feasibility_review_gate
→ generate_pivots
→ pivot_selection_gate
→ design_work_packages
→ work_package_review_gate
→ generate_report
```

## 6.4 前端交互

每个 Gate 页面统一结构：

```text
当前阶段
系统结论
证据/候选项
用户可操作按钮
继续运行按钮
回退按钮
```

按钮：

```text
确认并继续
修改后继续
补充证据
重新运行本阶段
返回上一步
停止分析
```

## 6.5 验收标准

- 用户能在关键词阶段暂停；
- 用户修改关键词后，后续检索使用新关键词；
- 用户拒绝错误论文后，该论文不参与评分；
- 用户选择 Pivot 后，系统重新生成工作包；
- Trace 中能看到每个 Gate 的用户操作。

---

# 7. 功能改造三：增强论文 / 数据集 / 工程检索

## 7.1 当前问题

当前检索容易出现：

- 论文不相关；
- 数据集名称幻觉；
- 工程仓库不是 Baseline；
- GitHub 搜到课程作业或无关仓库；
- 同一论文重复出现；
- 中文题目英文检索词不准；
- 检索结果未分层，直接进入总结。

## 7.2 新检索架构

```text
Query Expansion
        ↓
Multi-source Search
        ↓
Candidate Normalization
        ↓
Deduplication
        ↓
Type Classification
        ↓
Relevance Scoring
        ↓
Quality Scoring
        ↓
User Review
        ↓
Evidence Ledger
```

## 7.3 论文检索增强 SOP

### Step 1：生成多层查询

```text
L0：原题精确查询
L1：关键词组合查询
L2：英文术语查询
L3：去掉特殊对象后的泛化查询
L4：底层任务查询
L5：survey / review 查询
```

示例：

```text
原题：基于YOLO的钢材表面缺陷检测

L0: "YOLO 钢材表面缺陷检测"
L1: "YOLO steel surface defect detection"
L2: "steel surface defect detection deep learning"
L3: "industrial defect detection YOLO"
L4: "surface defect detection survey"
```

### Step 2：多源检索

优先：

```text
OpenAlex
Semantic Scholar
arXiv
Crossref
用户本地文献库
```

可选：

```text
Google Scholar 手动导入
知网/万方/维普导出 BibTeX/RIS 后导入
```

不建议：

```text
绕过权限抓取中文付费数据库
```

### Step 3：候选归一化

统一字段：

```text
title
authors
year
venue
abstract
doi
arxiv_id
openalex_id
semantic_scholar_id
citation_count
url
source
```

### Step 4：去重

去重规则：

```text
DOI 完全相同
arXiv ID 完全相同
标题归一化后相似度 > 0.92
标题相似且年份相同
```

### Step 5：相关性评分

```text
PaperRelevance =
    0.25 × title_match
  + 0.25 × abstract_match
  + 0.15 × task_match
  + 0.15 × object_match
  + 0.10 × method_match
  + 0.10 × recency
```

### Step 6：论文类型分类

```text
survey
baseline_method
application
dataset_paper
benchmark
case_study
irrelevant
```

### Step 7：进入人工审核

所有论文默认是：

```text
pending
```

只有 `accepted` 和 `core` 才进入最终风险评分。

---

## 7.4 数据集检索增强 SOP

### Step 1：生成数据集查询

```text
对象 + dataset
任务 + dataset
英文对象 + dataset
论文中出现的数据集名
GitHub README 中出现的数据集名
```

示例：

```text
steel surface defect dataset
NEU-DET
GC10-DET
KolektorSDD
industrial defect detection dataset
```

### Step 2：检索来源

```text
Hugging Face Datasets
Kaggle
OpenML
Papers with Code 历史数据
GitHub
论文项目页
Zenodo
Figshare
用户手动添加
```

### Step 3：验证字段

每个数据集必须验证：

```text
是否真实存在
是否有可访问链接
是否可下载
许可是否清楚
是否有图像/文本/点云等模态
是否有标注
标注是否匹配任务
规模是否足够
是否已有论文使用
是否已有 baseline
是否需要注册或申请
```

### Step 4：数据集评分

```text
DatasetScore =
    0.20 × existence
  + 0.20 × accessibility
  + 0.15 × annotation_match
  + 0.15 × task_match
  + 0.10 × license_clarity
  + 0.10 × baseline_available
  + 0.10 × scale
```

### Step 5：输出状态

```text
ready
可直接使用

needs_preprocess
需要转换格式或清洗

needs_permission
需要申请权限

weak_match
与题目有关系但不完全匹配

unverified
系统无法确认

invalid
无效或不存在
```

---

## 7.5 GitHub / 工程检索增强 SOP

### Step 1：检索来源

```text
GitHub Search API
论文项目页
Papers with Code 历史数据
Hugging Face Models / Spaces
Ultralytics / OpenMMLab 等官方生态
```

### Step 2：仓库初筛

过滤：

```text
无 README
无 License
无代码
纯笔记
课程作业
与任务无关
```

不要简单按 Star 排名，因为小领域仓库 Star 可能少但有用。

### Step 3：Baseline 可运行性评分

```text
RepoScore =
    0.15 × readme_quality
  + 0.15 × license_exists
  + 0.15 × train_script
  + 0.15 × eval_script
  + 0.10 × pretrained_weights
  + 0.10 × requirements_file
  + 0.10 × recent_activity
  + 0.10 × issue_health
```

### Step 4：工程证据标签

```text
official
论文官方仓库

reproduction
第三方复现

baseline_framework
通用框架，如 YOLO / MMDetection

demo_only
仅演示

not_reproducible
不可复现
```

### Step 5：输出建议

```text
推荐作为 baseline
可参考但不建议直接依赖
仅作背景参考
不建议使用
```

---

# 8. 证据工作台设计

## 8.1 页面结构

```text
证据工作台
├── 总览
│   ├── 论文数量
│   ├── 数据集数量
│   ├── 工程数量
│   └── 核心证据数量
│
├── 论文证据
│   ├── 自动检索
│   ├── 手动添加
│   ├── 已接受
│   └── 已拒绝
│
├── 数据集证据
│   ├── 可直接使用
│   ├── 需要预处理
│   ├── 需要申请
│   └── 不匹配
│
├── 工程证据
│   ├── 官方代码
│   ├── 第三方复现
│   ├── 通用框架
│   └── 不可复现
│
└── 证据关系图
```

## 8.2 证据状态

```text
pending
accepted
core
background
rejected
needs_check
```

| 状态 | 含义 |
|---|---|
| pending | 待用户审核 |
| accepted | 可参与评分 |
| core | 核心证据，优先参与报告 |
| background | 只作背景，不支撑关键结论 |
| rejected | 无关或错误，不参与 |
| needs_check | 需要人工进一步确认 |

## 8.3 证据关系

```text
题目
→ 论文
→ 数据集
→ Baseline
→ 指标
→ 工作包
```

每个工作包必须至少关联：

```text
1 个 Baseline
1 个数据集
2～3 篇论文
1 套评价指标
```

---

# 9. 新版可行性判断 SOP

## 9.1 输入

```text
TopicSpec
KeywordBreakdown
Accepted Papers
Accepted Datasets
Accepted Repos
User Constraints
Manual Notes
```

## 9.2 判断顺序

```text
1. 是否有核心论文
2. 是否有可用数据集
3. 是否有可复现 Baseline
4. 是否有明确指标
5. 是否能拆工作包
6. 是否存在硬性阻断
7. 是否需要退化或泛化
```

## 9.3 硬性阻断

```text
没有任何可用数据集，且用户无法自采
没有评价指标，且无法构造 Ground Truth
所有 baseline 都不可运行
题目要求同时做新数据、新模型、新系统、新硬件
工作包完全串行，前一步失败后整篇论文失效
```

## 9.4 判定

```text
GO
证据充分，可以进入工作包设计

NARROW
方向可行，但题目过宽，需要收缩

PIVOT
原题风险高，需要转向相邻成熟方向

PARK
当前材料不足，暂缓，等待数据或导师确认

STOP
当前不适合作为毕业题目
```

## 9.5 输出

```json
{
  "verdict": "NARROW",
  "summary": "方向可行，但当前题目范围偏大，需要先限定到二维检测或公开数据集。",
  "hard_blockers": [],
  "evidence_used": ["paper_001", "dataset_002", "repo_003"],
  "missing_evidence": [
    "缺少目标场景自有数据",
    "缺少三维标注"
  ],
  "required_user_action": [
    "确认是否接受退化为二维检测",
    "确认是否使用公开数据集作为主实验"
  ]
}
```

---

# 10. 退化与泛化 SOP

## 10.1 触发条件

以下任一条件触发退化：

```text
数据集不足
Baseline 不可复现
题目范围过大
三维/多模态/大模型等高风险词过多
工作包无法拆分
```

## 10.2 退化维度

```text
对象退化：特殊对象 → 通用对象 → 公开数据集对象
任务退化：精确测量 → 估计 → 定位 → 分割 → 检测 → 分类
模态退化：多模态 → RGB-D → 双目 → 单目图像
方法退化：自研模型 → 成熟 baseline + 模块改进
数据退化：自采大数据 → 公开数据 + 少量自采验证
结论退化：measured → estimated → visual_only
```

## 10.3 三条路线

### 保守路线

目标：优先保证毕业。

```text
公开数据集
成熟 baseline
指标明确
工作包少
创新轻量
```

### 平衡路线

目标：保留一定创新和工程特色。

```text
公开数据集 + 少量目标域验证
成熟 baseline + 轻量模块
有跨域或消融分析
```

### 激进路线

目标：尽量保留原始题目特色。

```text
保留特定场景
增加自有数据
保留多模态或三维
但必须设置降级出口
```

## 10.4 输出结构

```json
{
  "pivot_routes": [
    {
      "level": "conservative",
      "new_topic": "基于YOLOv8的钢材表面缺陷检测方法研究",
      "risk_before": 78,
      "risk_after": 32,
      "preserved_keywords": ["YOLO", "缺陷检测"],
      "removed_keywords": ["高精度", "实时", "多模态"],
      "required_evidence": ["dataset_001", "repo_002", "paper_003"],
      "tradeoff": "降低了场景复杂度，但可以保证实验闭环。"
    }
  ]
}
```

---

# 11. 工作包生成 SOP

## 11.1 输入

```text
Selected Pivot
Core Papers
Datasets
Baselines
User Goal Level
```

## 11.2 工作包规则

每个工作包必须满足：

```text
有研究问题
有数据集
有 Baseline
有评价指标
有对照组
有可交付物
可映射到章节
```

## 11.3 推荐模板

### 两工作包模板

```text
WP1：基线复现与目标数据验证
WP2：轻量改进与消融实验
```

### 三工作包模板

```text
WP1：数据集整理与 Baseline 复现
WP2：问题驱动的模型改进
WP3：跨域验证 / 工程系统 / 可视化展示
```

## 11.4 输出结构

```json
{
  "work_packages": [
    {
      "wp_id": "WP1",
      "title": "公开数据集上的YOLOv8钢材表面缺陷检测基线复现",
      "research_question": "YOLOv8 在钢材表面缺陷数据上的基础性能如何？",
      "dataset": ["NEU-DET"],
      "baseline": ["YOLOv8"],
      "metrics": ["mAP", "Recall", "FPS"],
      "deliverables": [
        "baseline 训练结果",
        "第一张对比表",
        "失败案例可视化"
      ],
      "chapter_mapping": "第3章"
    }
  ]
}
```

---

# 12. 前端改造 SOP

## 12.1 页面路由

```text
/
一题输入首页

/projects/[id]/analysis
分阶段分析页

/projects/[id]/evidence
证据工作台

/projects/[id]/pivot
退化路线选择

/projects/[id]/work-packages
工作包设计

/projects/[id]/report
开题报告输出
```

## 12.2 结果页面改造

不要把所有结果一次性展开。

改成步骤式：

```text
Step 1 题目理解
Step 2 关键词确认
Step 3 检索计划
Step 4 证据审核
Step 5 可行性判断
Step 6 退化路线
Step 7 工作包
Step 8 开题输出
```

## 12.3 右侧 Trace 改造

当前 Trace 主要显示技术执行过程。

新增用户操作节点：

```text
系统：拆解关键词完成
用户：删除关键词“xxx”
用户：新增关键词“xxx”
系统：重新生成检索计划
用户：拒绝论文 paper_003
用户：标记 dataset_002 为核心数据集
系统：重新计算可行性
用户：选择平衡路线
```

## 12.4 按钮设计

每个阶段统一提供：

```text
确认并继续
修改后继续
补充证据
重新运行本阶段
返回上一步
导出当前结果
```

---

# 13. 后端改造 SOP

## 13.1 新增模块

```text
packages/
├── evidence/
│   ├── models.py
│   ├── service.py
│   ├── dedup.py
│   ├── scoring.py
│   └── validators.py
│
├── retrieval/
│   ├── query_expansion.py
│   ├── paper_search.py
│   ├── dataset_search.py
│   ├── repo_search.py
│   ├── normalize.py
│   └── rerank.py
│
├── gates/
│   ├── keyword_gate.py
│   ├── query_gate.py
│   ├── evidence_gate.py
│   ├── pivot_gate.py
│   └── work_package_gate.py
```

## 13.2 新增 Graph

```text
build_one_topic_interactive_graph()
```

图结构：

```text
parse_topic
→ keyword_gate
→ build_query_plan
→ query_gate
→ search_papers
→ search_datasets
→ search_repos
→ normalize_evidence
→ evidence_gate
→ judge_feasibility
→ feasibility_gate
→ generate_pivots
→ pivot_gate
→ design_work_packages
→ work_package_gate
→ generate_report
```

## 13.3 状态模型

```python
class InteractiveTopicState(BaseModel):
    project_id: str
    raw_topic: str
    user_goal: str

    keyword_breakdown: KeywordBreakdown | None = None
    keyword_review: HumanReview | None = None

    query_plan: SearchQueryPlan | None = None
    query_review: HumanReview | None = None

    paper_candidates: list[EvidenceItem] = []
    dataset_candidates: list[EvidenceItem] = []
    repo_candidates: list[EvidenceItem] = []

    evidence_review: HumanReview | None = None

    feasibility: FeasibilitySummary | None = None
    feasibility_review: HumanReview | None = None

    pivot_candidates: list[PivotRoute] = []
    selected_pivot: PivotRoute | None = None

    work_packages: list[WorkPackage] = []
    work_package_review: HumanReview | None = None

    final_report: str | None = None
```

---

# 14. 测试与验收 SOP

## 14.1 单元测试

### 关键词拆解

```text
输入：基于YOLO的钢材表面缺陷检测
期望：
method 包含 YOLO
task 包含 缺陷检测
object 包含 钢材表面
```

### 证据去重

```text
同 DOI 去重
同 arXiv 去重
标题相似去重
```

### 数据集评分

```text
无下载链接 → accessibility 低
无标注 → annotation_match 低
有 baseline → baseline_available 高
```

### Repo 评分

```text
无 README → 降分
无训练脚本 → 降分
有官方仓库 → 加分
```

## 14.2 Playwright E2E

### E2E 1：手动添加论文

```text
进入 evidence 页面
点击添加论文
输入 DOI / 标题
保存
证据池出现该论文
标记为核心证据
该论文进入可行性判断
```

### E2E 2：关键词人工修改

```text
输入题目
系统拆解关键词
用户删除错误关键词
用户增加新关键词
继续检索
检索计划使用修改后的关键词
```

### E2E 3：拒绝错误证据

```text
系统检索到无关论文
用户点击拒绝
重新计算
最终报告不引用该论文
```

### E2E 4：Pivot 选择

```text
系统给出三条路线
用户选择平衡路线
系统生成对应工作包
报告中保留该选择记录
```

---

# 15. 里程碑计划

## 第 1 周：证据工作台

目标：

- 手动添加论文；
- 上传 PDF；
- BibTeX / RIS 导入；
- 证据状态管理。

交付：

```text
EvidenceItem 模型
证据 API
证据页面
证据审核状态
```

## 第 2 周：Human Gate

目标：

- 关键词确认；
- 检索计划确认；
- 证据审核；
- Pivot 选择。

交付：

```text
InteractiveTopicGraph
resume API
Gate UI
Trace 中记录用户操作
```

## 第 3 周：检索增强

目标：

- 多层查询；
- 多源论文检索；
- 数据集检索；
- GitHub 工程检索；
- 去重与评分。

交付：

```text
paper_search_v2
dataset_search_v2
repo_search_v2
evidence scoring
```

## 第 4 周：可行性与退化路线

目标：

- 证据驱动评分；
- GO / NARROW / PIVOT / PARK / STOP；
- 三条退化路线；
- 风险前后对比。

交付：

```text
FeasibilitySummary v2
PivotRoute v2
风险雷达图
Pivot 页面
```

## 第 5 周：工作包与报告

目标：

- 工作包生成；
- 问题—方法—实验矩阵；
- 开题报告骨架；
- 修改清单。

交付：

```text
WorkPackage Designer
Opening Report Markdown
导出功能
```

## 第 6 周：测试与作品化

目标：

- E2E 测试；
- README；
- Demo 视频；
- 技术文档；
- 样例题目库。

交付：

```text
Playwright 测试
pytest
演示案例
部署说明
简历项目描述
```

---

# 16. 最高优先级任务清单

## P0：必须先做

```text
1. 证据工作台
2. 手动添加论文
3. 关键词确认 Gate
4. 证据审核 Gate
5. 用户选择 Pivot
```

这五个功能能直接解决当前最大问题。

## P1：第二优先级

```text
1. 数据集检索增强
2. GitHub baseline 检索增强
3. 证据评分
4. 退化路线风险对比
5. 工作包矩阵
```

## P2：后续增强

```text
1. PDF 全文 RAG
2. 开题委员会多 Agent 审查
3. DOCX 导出
4. 学校开题模板适配
5. 历史题目评估数据集
```

---

# 17. 推荐最终效果

改造完成后，用户体验应变成：

```text
用户：输入“基于XXX的YYY检测”

系统：
我先拆出关键词，请你确认。

用户：
删除“高精度”，增加“YOLOv8”。

系统：
我将按论文、数据集、工程三条线检索。以下检索词是否可用？

用户：
补充一个导师给的论文 DOI。

系统：
已加入核心证据。现在发现论文较多，但数据集不足，建议收缩到公开数据集场景。给你三条路线。

用户：
选择平衡路线。

系统：
基于该路线，我生成两个工作包：
WP1：Baseline 复现与数据集验证
WP2：轻量模块改进与消融实验

系统：
以下是开题委员会可能追问的问题和修改清单。
```

这才像一个真正的开题助手，而不是一次性文本生成器。

---

# 18. 简历描述

推荐写法：

> 设计并实现面向中国硕士研究生开题场景的选题可行性 Agent。针对初版“一键生成”缺少人工干预与证据管理的问题，重构为基于 LangGraph 的交互式 Human-in-the-loop 工作流，支持手动添加论文、PDF/BibTeX/RIS 导入、论文/数据集/GitHub 工程三线证据审核、可行性评分、选题退化路线选择和 2～3 个论文工作包生成。构建 Evidence Ledger，对每个选题判断关联论文、数据集、Baseline 和指标证据，降低检索幻觉和不可复现风险。

---

# 19. 本轮改造的验收定义

当以下流程能稳定跑通，即可认为下一阶段完成：

```text
输入题目
→ 系统拆解关键词
→ 用户修改关键词
→ 系统生成检索计划
→ 用户手动添加一篇论文
→ 系统自动检索论文/数据集/GitHub
→ 用户审核证据
→ 系统判断可行性
→ 系统给出三条退化路线
→ 用户选择一条
→ 系统生成 2 个工作包
→ 系统导出 Markdown 开题建议
```

最低验收标准：

```text
手动证据能进入评分
被拒绝证据不进入评分
用户修改关键词能影响检索
Pivot 选择能影响工作包
报告中能看到证据来源
```
