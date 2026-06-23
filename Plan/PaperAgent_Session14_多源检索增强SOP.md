# PaperAgent Session 14 SOP：多源检索增强

> 日期：2026-06-19  
> 阶段定位：在证据工作台、URL 轻验证、Trace 持久化、报告质量检查、内部 Skill Registry 均完成后，扩展主动检索来源。  
> 本轮目标：让系统从“用户手动导入 + 少量启发式候选”升级为“论文 / 数据集 / 工程三线多源候选检索”，但所有结果仍先进入候选证据池，由用户审核与轻验证后再支撑结论。

---

## 1. 报告审阅结论

已审阅：

```text
Plan/reports/Session_10_Verification_URLVerified_验收报告.md
Plan/reports/Session_11_Trace_Persistence_验收报告.md
Plan/reports/Session_12_ReportQuality_Review_验收报告.md
Plan/reports/Session_13_SkillRegistry_验收报告.md
```

判断：

```text
Session 11 可过验收；
Session 12 可过验收；
Session 13 可过验收；
可以进入 Session 14。
```

理由：

```text
1. Session 11 已把关键操作写入 jsonl trace，并能进入 FinalPackage 的关键决策记录；
2. Session 12 已能基于 FinalPackage / EvidenceRef / Verification / Trace 做 8 维低门槛审核；
3. Session 13 已注册 paper-card / dataset-validation / github-baseline / evidence-ledger 四个内部 Skill；
4. Session 10 的 URLVerified 规则已经能防止 failed 与 assistant_intake + unverified 证据进入 supports；
5. 多源检索新增的候选证据已有承接路径：Candidate → EvidenceCard → Verification → EvidenceRef → ReportQuality → FinalPackage。
```

需要注意的风险：

```text
1. Session 11 Playwright 报告写的是“后台 subagent 跑”，建议完工报告中补充明确 pass 数；
2. Session 12 的 use_llm=true 仍是预留接口，Session 14 不应依赖 LLM 判断链接真伪；
3. Session 13 的 citation 表暂未展示 skill_sources，Session 14 可顺手补上；
4. 外部检索必须有 fallback / mock，测试不能依赖真实网络稳定性。
```

---

## 2. Session 14 名称

```text
多源检索增强
```

一句话目标：

```text
围绕用户题目和关键词，主动从 OpenAlex / Semantic Scholar / arXiv / GitHub / HuggingFace / Kaggle 等来源检索候选论文、数据集和工程项目，统一归一化、去重、评分，并进入证据工作台等待用户审核。
```

---

## 3. 本阶段不做什么

| 不做 | 原因 |
|---|---|
| 不做 PDF 全文下载和全文 RAG | 留给 Session 15 |
| 不绕过 CNKI / 万方 / 维普 / IEEE / ACM 等权限 | 保持合规 |
| 不依赖 Google Scholar 自动爬取 | 易触发风控且不可测 |
| 不把检索结果直接写入 supports | 必须经过审核与验证 |
| 不让 LLM 判定 URL 真伪 | URL 真伪继续走 Session 10 verification |
| 不追求极限召回率 | 本阶段优先稳定、可解释、可测试 |
| 不执行 GitHub 仓库代码 | 只读元数据，不 clone，不安装依赖 |

---

## 4. 当前流程位置

Session 14 接在当前主线：

```text
输入题目
→ 关键词拆解
→ 检索计划
→ 多源候选检索
→ 候选归一化
→ 去重
→ 轻量评分
→ 进入证据工作台 system_found 栏
→ 用户审核
→ URLVerified
→ EvidenceRef
→ FinalPackage
→ ReportQuality
```

关键原则：

```text
多源检索只负责“找候选”，不负责“替用户决定采用”。
```

---

## 5. 核心交付

### 5.1 后端能力

新增多源检索服务：

```text
apps/api/app/services/retrieval/
├── __init__.py
├── models.py
├── query_plan.py
├── openalex_search.py
├── semantic_scholar_search.py
├── arxiv_search.py
├── github_search.py
├── huggingface_search.py
├── kaggle_search.py
├── normalizer.py
├── dedup.py
├── ranker.py
└── orchestrator.py
```

如果当前项目不适合新建目录，也可以先放为单文件：

```text
apps/api/app/services/multi_source_retrieval.py
```

但建议优先使用目录拆分，避免后续 Session 15 继续堆到一个文件。

### 5.2 API 能力

新增：

```text
POST /api/v1/one-topic/{project_id}/retrieval/search
GET  /api/v1/one-topic/{project_id}/retrieval/summary
POST /api/v1/one-topic/{project_id}/retrieval/import
```

其中：

```text
search：按 topic / keywords / source scope 检索候选；
summary：查看本项目最近一次检索来源、数量、错误和候选分布；
import：把选中的候选导入 Evidence Ledger / Workspace Board。
```

### 5.3 前端能力

工作台新增轻量检索面板：

```text
多源检索
├── 检索关键词预览
├── 来源选择：论文 / 数据集 / 工程
├── 检索按钮
├── 候选结果列表
├── 一键加入工作台
└── 检索日志 / 错误提示
```

候选结果必须显示：

```text
来源；
类型；
标题；
年份 / 更新时间；
URL；
检索得分；
重复状态；
是否已在证据池；
导入按钮。
```

---

## 6. 数据模型

### 6.1 SearchSource

```python
SearchSource = Literal[
    "openalex",
    "semantic_scholar",
    "arxiv",
    "github",
    "huggingface",
    "kaggle",
    "manual_fallback",
]
```

### 6.2 CandidateType

```python
CandidateType = Literal[
    "paper",
    "dataset",
    "repo",
    "project_page",
    "note",
]
```

### 6.3 RetrievalCandidate

建议新增：

```python
class RetrievalCandidate(BaseModel):
    candidate_id: str
    project_id: str
    candidate_type: CandidateType
    source: SearchSource
    title: str
    url: str | None = None
    year: int | None = None
    authors: list[str] = []
    abstract: str | None = None
    venue: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    openalex_id: str | None = None
    semantic_scholar_id: str | None = None
    repo_full_name: str | None = None
    dataset_slug: str | None = None
    license: str | None = None
    stars: int | None = None
    citation_count: int | None = None
    updated_at: str | None = None
    matched_keywords: list[str] = []
    retrieval_score: float = 0.0
    quality_hints: list[str] = []
    warnings: list[str] = []
    raw: dict = Field(default_factory=dict)
```

### 6.4 RetrievalRun

```python
class RetrievalRun(BaseModel):
    run_id: str
    project_id: str
    query_plan: dict
    sources: list[SearchSource]
    started_at: str
    finished_at: str | None = None
    status: Literal["running", "completed", "partial", "failed"]
    total_candidates: int = 0
    imported_count: int = 0
    errors: list[str] = []
    candidates: list[RetrievalCandidate] = []
```

---

## 7. 查询计划

### 7.1 输入

来自现有能力：

```text
raw_topic；
KeywordBreakdown；
用户修改后的关键词；
用户工作台已有核心证据；
Session 12 审核提出的 missing_evidence；
```

### 7.2 查询层级

对“基于 YOLO 的钢材表面缺陷检测”这类题目，生成：

```text
L0 原题精确查询：
基于YOLO的钢材表面缺陷检测

L1 中英关键词组合：
YOLO steel surface defect detection

L2 去方法词的任务查询：
steel surface defect detection dataset

L3 方法 + 任务泛化：
YOLO defect detection industrial inspection

L4 baseline 查询：
YOLOv8 defect detection GitHub

L5 survey / benchmark 查询：
surface defect detection survey benchmark
```

### 7.3 查询数量限制

MVP 建议：

```text
paper_queries <= 6
dataset_queries <= 5
repo_queries <= 5
每个 source 单 query top_k <= 8
总候选数默认 <= 80
```

这样前端不会被淹没，测试也更稳定。

---

## 8. 检索源设计

### 8.1 OpenAlex Paper Search

用途：

```text
论文候选；
综述；
benchmark；
高引用背景论文。
```

优先字段：

```text
id；
doi；
title；
publication_year；
authorships；
abstract_inverted_index；
cited_by_count；
primary_location；
concepts；
open_access；
```

降级策略：

```text
OpenAlex 请求失败 → source error 记录到 RetrievalRun.errors；
不阻塞其他 source；
候选列表标记 partial。
```

### 8.2 Semantic Scholar Paper Search

用途：

```text
补充论文元数据；
论文摘要；
citationCount；
externalIds。
```

注意：

```text
无 API key 时限流较严格；
必须捕获 429；
测试必须 mock；
不能让它成为唯一检索源。
```

### 8.3 arXiv Search

用途：

```text
CV / ML / NLP 等方向的新论文；
无 DOI 的预印本候选。
```

注意：

```text
只解析 Atom feed 元数据；
不下载 PDF；
不把 arXiv 新论文直接视为高质量证据。
```

### 8.4 GitHub Repo Search

用途：

```text
baseline；
复现工程；
官方实现；
工具框架。
```

候选字段：

```text
full_name；
html_url；
description；
stars；
forks；
language；
license；
updated_at；
topics；
```

质量提示：

```text
有 license；
近期更新；
stars / forks 不是唯一标准；
description / topics 命中任务词；
```

不做：

```text
不 clone；
不运行；
不安装；
不下载 release。
```

### 8.5 HuggingFace Dataset Search

用途：

```text
公开数据集候选；
模型 / Space 可作为辅助工程候选。
```

字段：

```text
id；
likes；
downloads；
tags；
license；
lastModified；
cardData；
```

注意：

```text
有些数据集 gated；
有些 license 缺失；
不能仅凭存在就判断可用。
```

### 8.6 Kaggle Dataset Search

MVP 可先做两种模式：

```text
1. 识别用户给的 Kaggle URL 并转为候选；
2. 若环境已有 Kaggle API 配置，再启用搜索。
```

默认不强依赖 Kaggle API。

---

## 9. 候选归一化

不同来源进入统一 `RetrievalCandidate`。

归一化规则：

```text
论文：优先 doi / arxiv_id / openalex_id / semantic_scholar_id；
数据集：优先 dataset_slug / url / title；
工程：优先 repo_full_name / url；
普通网页：优先 url；
```

标题标准化：

```text
小写；
去标点；
压缩空白；
去掉 arXiv / GitHub / dataset 等来源噪声词；
```

抽象字段：

```text
OpenAlex abstract_inverted_index → abstract text；
GitHub description → abstract；
HuggingFace card summary → abstract；
```

---

## 10. 去重规则

### 10.1 论文去重

```text
DOI 完全一致 → duplicate；
arXiv ID 完全一致 → duplicate；
OpenAlex ID 完全一致 → duplicate；
Semantic Scholar ID 完全一致 → duplicate；
标题标准化相似度 > 0.92 且年份相同 → duplicate；
```

### 10.2 数据集去重

```text
相同 URL → duplicate；
相同 HuggingFace dataset slug → duplicate；
相同 Kaggle slug → duplicate；
标题标准化相似度 > 0.90 → possible_duplicate；
```

### 10.3 Repo 去重

```text
相同 github owner/repo → duplicate；
相同 URL → duplicate；
```

### 10.4 与现有 Evidence Ledger 去重

导入前必须检查：

```text
candidate 是否已经存在于 evidence pool；
candidate 是否已被用户 rejected；
candidate 是否与 user_preferred 栏核心证据重复。
```

处理建议：

```text
已存在 accepted/core → 不重复导入，只显示“已在证据池”；
已存在 rejected → 默认不导入，除非用户手动强制；
疑似重复 → 显示 warning，允许用户确认。
```

---

## 11. 检索评分

### 11.1 Paper Retrieval Score

```text
PaperRetrievalScore =
  0.25 × title_match
+ 0.20 × abstract_match
+ 0.15 × task_match
+ 0.15 × object_match
+ 0.10 × method_match
+ 0.10 × recency
+ 0.05 × citation_signal
```

### 11.2 Dataset Retrieval Score

```text
DatasetRetrievalScore =
  0.25 × object_match
+ 0.20 × task_match
+ 0.15 × accessibility_hint
+ 0.15 × license_hint
+ 0.10 × usage_signal
+ 0.10 × recency
+ 0.05 × source_reliability
```

### 11.3 Repo Retrieval Score

```text
RepoRetrievalScore =
  0.20 × task_match
+ 0.15 × method_match
+ 0.15 × readme_hint
+ 0.10 × license_hint
+ 0.10 × stars_normalized
+ 0.10 × recent_activity
+ 0.10 × language_match
+ 0.10 × framework_hint
```

注意：

```text
retrieval_score 只是排序用；
EvidenceRef priority 仍由 Session 10 / 13 的 verification、review、score、lane、skill_sources 等共同决定。
```

---

## 12. 导入 Evidence Ledger

候选导入时，统一变成 `EvidenceItem`：

```text
source_mode = "auto_search"
workspace_lane = "system_found"
review_status = "pending"
verification_status = "unverified"
created_by_skill = paper-card / dataset-validation / github-baseline
```

导入后：

```text
1. 写入 Evidence Ledger；
2. 写入 Trace action = retrieval_candidate_imported；
3. 可选触发 verification；
4. 前端刷新工作台；
5. ReportQuality 不应因为 pending 候选直接升分。
```

建议新增 Trace actions：

```text
retrieval_run_started
retrieval_run_completed
retrieval_source_failed
retrieval_candidate_imported
retrieval_candidate_skipped_duplicate
```

---

## 13. API 设计

### 13.1 启动检索

```text
POST /api/v1/one-topic/{project_id}/retrieval/search
```

请求：

```json
{
  "scope": ["paper", "dataset", "repo"],
  "sources": ["openalex", "semantic_scholar", "arxiv", "github", "huggingface"],
  "top_k_per_source": 8,
  "include_existing": false,
  "auto_import": false,
  "auto_verify": false
}
```

响应：

```json
{
  "run_id": "ret_...",
  "status": "completed",
  "total_candidates": 42,
  "candidates": []
}
```

### 13.2 检索摘要

```text
GET /api/v1/one-topic/{project_id}/retrieval/summary
```

返回：

```text
最近一次检索时间；
来源成功 / 失败数量；
paper / dataset / repo 候选数量；
重复候选数量；
已导入数量；
错误列表；
```

### 13.3 导入候选

```text
POST /api/v1/one-topic/{project_id}/retrieval/import
```

请求：

```json
{
  "run_id": "ret_...",
  "candidate_ids": ["cand_001", "cand_002"],
  "auto_verify": true
}
```

响应：

```json
{
  "imported": 2,
  "skipped_duplicates": 0,
  "evidence_ids": ["paper_...", "repo_..."]
}
```

---

## 14. 前端设计

新增工作台面板：

```text
🔎 多源检索
```

区域：

```text
1. 检索范围：论文 / 数据集 / 工程；
2. 来源开关：OpenAlex / Semantic Scholar / arXiv / GitHub / HuggingFace / Kaggle；
3. 查询预览：展示系统生成的 3-6 条 query；
4. 运行检索；
5. 候选结果；
6. 导入选中；
7. 导入后立即验证；
```

候选卡片按钮：

```text
加入系统候选栏；
加入用户偏好栏；
标记不相关；
查看原始链接；
```

注意：

```text
默认导入到 system_found；
只有用户显式选择“加入用户偏好栏”才进入 user_preferred；
即使加入 user_preferred，也仍然需要 review_status / verification_status 约束。
```

---

## 15. 与 Skill Registry 联动

Session 14 应补齐：

```text
paper 检索候选 → created_by_skill = "paper-card"
dataset 检索候选 → created_by_skill = "dataset-validation"
repo 检索候选 → created_by_skill = "github-baseline"
retrieval / dedup / ledger 操作 → 可记录 "evidence-ledger"
```

FinalPackage citation 表建议新增一列：

```text
Skill
```

示例：

```markdown
| 编号 | 类型 | 标题 | 审核状态 | 验证 | 置信度 | Skill | 链接 |
|---|---|---|---|---|---:|---|---|
| E1 | paper | ... | core | verified | 0.85 | paper-card | https://... |
```

这项是 Session 13 报告里提到的遗留小口，可以在本轮顺手补掉。

---

## 16. 与 Verification 联动

检索候选导入后：

```text
默认 verification_status = "unverified"；
若用户勾选 auto_verify，则调用 Session 10 的 verify endpoint；
failed 不得进入 supports；
assistant_intake + unverified 不得进入 supports 的规则保持不变；
auto_search + unverified 也不应高优先级支撑关键结论；
```

建议加强 EvidenceRef 规则：

```text
auto_search + unverified + pending → warns；
auto_search + partial + accepted → background 或 supports 由 priority 决定；
auto_search + verified + accepted/core → 可进入 supports；
```

---

## 17. 与 ReportQuality 联动

Session 14 完成后，ReportQuality 应能体现：

```text
1. 数据集维度因新增候选而更容易发现缺口；
2. Baseline 维度能读取新增 repo 候选；
3. failed / unverified 候选不应提升报告评分；
4. missing_evidence 可作为下一轮检索 query seed。
```

建议新增规则：

```text
如果 ReportQuality 指出缺少 dataset，则检索面板默认勾选 dataset scope；
如果 ReportQuality 指出缺少 baseline，则默认勾选 repo scope；
```

---

## 18. 测试要求

### 18.1 后端测试

新增：

```text
apps/api/tests/test_session14_multi_source_retrieval.py
```

至少覆盖：

```text
1. query_plan 能从题目生成 paper / dataset / repo 查询；
2. OpenAlex response 能归一化为 paper candidate；
3. Semantic Scholar response 能归一化为 paper candidate；
4. arXiv Atom response 能归一化为 paper candidate；
5. GitHub response 能归一化为 repo candidate；
6. HuggingFace response 能归一化为 dataset candidate；
7. DOI / arXiv / title 相似去重有效；
8. repo owner/name 去重有效；
9. dataset slug / URL 去重有效；
10. retrieval_score 排序稳定；
11. source 失败不影响其他 source；
12. import candidate 后写入 Evidence Ledger；
13. import 后 review_status=pending；
14. import 后 workspace_lane=system_found；
15. import 后 created_by_skill 正确；
16. import + auto_verify 会调用 verification 并写入状态；
17. duplicate candidate 不重复导入；
18. Trace 写入 retrieval_run_started / completed / imported；
19. Retrieval summary 返回来源统计与错误；
20. pending/unverified 检索候选不提升 ReportQuality 关键维度。
```

测试必须 mock 外部 API：

```text
不依赖真实 OpenAlex / Semantic Scholar / GitHub / HuggingFace 网络；
真实网络只允许在 smoke 报告里作为可选项。
```

### 18.2 Playwright 测试

新增：

```text
apps/web/e2e/test_one_topic_session14_retrieval.py
```

至少覆盖：

```text
1. 多源检索面板可见；
2. 用户能选择论文 / 数据集 / 工程 scope；
3. 点击检索后出现候选结果；
4. 候选卡片展示 source / type / score / url；
5. 用户能导入选中候选；
6. 导入后候选出现在 system_found 栏；
7. 导入后卡片显示 unverified 或验证状态；
8. 勾选 auto_verify 后能看到 verification pill；
9. duplicate 候选不会重复出现两张证据卡；
10. Trace 面板能看到 retrieval 相关事件。
```

### 18.3 回归测试

必须跑：

```text
apps/api/tests/test_session10_verification.py
apps/api/tests/test_session11_trace_persistence.py
apps/api/tests/test_session12_report_quality.py
apps/api/tests/test_session13_skill_registry.py
apps/web/e2e/test_one_topic_session10_verification.py
apps/web/e2e/test_one_topic_session11_trace_persistence.py
apps/web/e2e/test_one_topic_session12_report_quality.py
apps/web/e2e/test_one_topic_session13_skill_registry.py
```

理由：

```text
Session 14 会碰 EvidenceItem / EvidenceRef / Trace / Skill / ReportQuality 的交界面，必须防止上游候选污染下游报告。
```

---

## 19. 验收标准

通过条件：

```text
1. 能基于题目和关键词生成 paper / dataset / repo 查询计划；
2. 至少接入 3 类来源：论文源、数据集源、工程源；
3. 检索结果统一为 RetrievalCandidate；
4. 候选能按类型归一化、去重、排序；
5. 候选默认不直接支撑结论；
6. 用户可选择候选导入 Evidence Ledger；
7. 导入后默认进入 system_found / pending / unverified；
8. 导入候选能触发 URLVerified；
9. 导入候选能记录 Trace；
10. created_by_skill / skill_sources 能正确写入；
11. FinalPackage 不引用 rejected / failed / pending-unverified 候选作为 supports；
12. ReportQuality 不因未审核候选虚假升分；
13. 后端新增测试通过；
14. Playwright 新增测试通过；
15. Session 10-13 回归测试通过。
```

最低可接受 MVP：

```text
OpenAlex paper search；
GitHub repo search；
HuggingFace dataset search；
统一 candidate；
导入工作台；
去重；
Trace；
Playwright 主路径。
```

若 Semantic Scholar / Kaggle 因 API key 或限流暂不可用，可以：

```text
保留 adapter；
测试用 mock；
UI 显示“未配置 / 可选来源”；
不阻塞验收。
```

---

## 20. 完工报告要求

完成后新增：

```text
Plan/reports/Session_14_MultiSource_Retrieval_验收报告.md
```

报告必须包含：

```text
1. 本阶段范围；
2. 新增 retrieval 模型；
3. 已接入 source；
4. source fallback 策略；
5. candidate normalization；
6. dedup 规则；
7. scoring 规则；
8. API 列表；
9. Evidence Ledger / Workspace Board 联动；
10. Verification 联动；
11. Trace 联动；
12. Skill Registry 联动；
13. ReportQuality 联动；
14. 后端测试结果；
15. Playwright 测试结果；
16. 未做项；
17. 下一 Session 建议。
```

报告中必须明确写：

```text
外部 API 测试是否 mock；
是否跑过真实网络 smoke；
哪些 source 因 key / 限流 / 网络被降级；
```

---

## 21. 下一 Session 预告

Session 15 建议：

```text
全文资料与图片 / PDF / 网页资料卡片化
```

进入条件：

```text
Session 14 的多源检索候选可以稳定进入工作台；
候选导入不会污染 supports；
Trace 能记录检索来源；
ReportQuality 能识别未审核候选不算有效证据。
```

Session 15 才考虑：

```text
PDF 片段；
截图；
网页文字；
用户描述；
OCR / 解析结果 pending 化；
Agent 生成卡片放入工作区。
```

仍然不建议立刻做：

```text
全文向量库；
大规模 PDF RAG；
DOCX / PPT 高级排版；
完整毕业论文正文生成。
```

