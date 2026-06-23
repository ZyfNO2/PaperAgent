# PaperAgent Session 05 下一步 SOP：证据评分与科研 Skill 化

> 日期：2026-06-18  
> 适用范围：PaperAgent / TopicPilot-CN OneTopic MVP  
> 依据文档：
> - `Plan/Faraway/PaperAgent_交互式证据工作台改造计划书与SOP.md`
> - `Plan/Faraway/PaperAgent_科研Skill下载链接汇总.md`
> - `Plan/reports/Session_01_Evidence_验收报告.md`
> - `Plan/reports/Session_02_Evidence_Workbench_验收报告.md`
> - `Plan/reports/Session_03_Human_Gates_验收报告.md`
> - `Plan/reports/Session_04_Pivot_Routes_验收报告.md`

---

## 1. 当前状态判断

截至 Session 04，OneTopic MVP 已完成以下能力：

| Session | 已完成能力 | 状态 |
|---|---|---|
| Session 01 | EvidenceItem 数据模型、手动添加论文/数据集/工程、审核状态、自动证据入池 | 已验收 |
| Session 02 | 证据工作台 UI、三栏证据池、接受/拒绝/核心/背景/待核查状态 | 已验收 |
| Session 03 | Human Gate 1-2，用户可编辑关键词与检索计划后 regenerate | 已验收 |
| Session 04 | GO/NARROW/PIVOT/PARK/STOP 五档判断，三条退化路线，用户选择 Pivot | 已验收 |

当前系统已经不是单纯“一键生成”，而是具备了：

```text
输入题目
→ 关键词拆解
→ 用户修改关键词
→ 生成检索计划
→ 自动证据入池
→ 手动证据补充
→ 证据审核
→ 可行性判断
→ 三条 Pivot 路线
→ 用户选择路线
```

下一步的主要缺口不是继续扩前端交互，而是让证据池里的证据变得“可比较、可排序、可解释、可复用”。

---

## 2. Session 05 目标

Session 05 的目标是：

> 对论文、数据集、GitHub 工程证据进行去重、分类、评分，并把评分结果接入可行性判断和 Pivot 路线选择。

本阶段不做完整 Skill Marketplace，不批量下载第三方 Skill，不重构 8 Phase。

本阶段只做一个最小闭环：

```text
EvidenceItem
→ 去重
→ 类型分类
→ PaperRelevance / DatasetScore / RepoScore
→ 证据工作台展示分数
→ 可行性判断使用 accepted/core 且高质量证据
→ Playwright 验收
```

---

## 3. 本阶段不做什么

| 暂不做 | 原因 |
|---|---|
| 不批量下载 8 个科研 Skill | 当前还没有 SkillRegistry，直接引入会增加不可控复杂度 |
| 不做 PDF 全文 RAG | 需要 Docling/GROBID，属于后续 Session |
| 不做 SchoolRulePack | 与当前证据评分主线无关 |
| 不做 DOCX 导出 | 当前目标是选题可行性，不是最终材料排版 |
| 不重写 05-08 Phase | OneTopic 主线仍在验证期，先稳定证据质量 |
| 不做多 Agent 委员会升级 | 没有高质量证据前，评审升级意义有限 |

---

## 4. Session 05 功能范围

### 4.1 论文证据评分

为每篇 paper evidence 计算 `PaperRelevance`。

建议公式：

```text
PaperRelevance =
    0.25 × title_match
  + 0.25 × abstract_match
  + 0.15 × task_match
  + 0.15 × object_match
  + 0.10 × method_match
  + 0.10 × recency
```

字段建议：

```python
class PaperScore(BaseModel):
    title_match: float
    abstract_match: float
    task_match: float
    object_match: float
    method_match: float
    recency: float
    total: float
    reason: str
```

论文类型分类：

```text
survey
baseline_method
application
dataset_paper
benchmark
case_study
irrelevant
unknown
```

验收要求：

```text
YOLO steel defect paper → application 或 baseline_method
survey paper → survey
无关论文 → irrelevant，且默认不进入核心证据
```

---

### 4.2 数据集证据评分

为每个 dataset evidence 计算 `DatasetScore`。

建议公式：

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

字段建议：

```python
class DatasetScore(BaseModel):
    existence: float
    accessibility: float
    annotation_match: float
    task_match: float
    license_clarity: float
    baseline_available: float
    scale: float
    total: float
    status: Literal[
        "ready",
        "needs_preprocess",
        "needs_permission",
        "weak_match",
        "unverified",
        "invalid"
    ]
    reason: str
```

验收要求：

```text
有下载链接 + 有标注 + 匹配检测任务 → ready 或 needs_preprocess
无下载链接 → accessibility 低
无标注信息 → annotation_match 低
无法确认来源 → unverified
```

---

### 4.3 GitHub / 工程证据评分

为 repo evidence 计算 `RepoScore`。

建议公式：

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

工程类型分类：

```text
official
reproduction
baseline_framework
demo_only
not_reproducible
unknown
```

验收要求：

```text
ultralytics / YOLO 官方生态 → baseline_framework 或 official
有 README + train/eval 脚本 → reproduction 或 official
只有 notebook / demo → demo_only
无 README 或无代码 → not_reproducible
```

---

### 4.4 证据去重增强

Session 01 已实现：

```text
DOI 相同
arXiv ID 相同
标题 jaccard > 0.92
```

Session 05 增强为：

```text
DOI 完全相同
arXiv ID 完全相同
OpenAlex ID 完全相同
Semantic Scholar ID 完全相同
标题 normalize 后相似度 > 0.92
标题相似且年份相同
GitHub repo owner/name 相同
数据集 canonical name 相同
```

新增字段：

```python
canonical_key: str
duplicate_of: str | None
dedup_reason: str | None
```

验收要求：

```text
重复论文不新增，只返回 existing evidence_id
重复 repo 不新增
重复 dataset 不新增
用户手动添加重复项时前端显示“已存在”
```

---

### 4.5 证据评分接入可行性判断

当前可行性判断主要看数量：

```text
paper_count
dataset_count
baseline_count
```

Session 05 改为同时看数量和质量：

```text
accepted_or_core_papers_score >= 阈值
ready_or_needs_preprocess_datasets >= 1
official_or_reproduction_repos >= 1
```

建议规则：

```text
GO:
  core/accepted paper >= 3
  且 paper_score 平均 >= 0.60
  且 dataset ready/needs_preprocess >= 1
  且 repo official/reproduction/baseline_framework >= 1

NARROW:
  paper 足够
  但 dataset 或 repo 只有 weak_match/unverified

PIVOT:
  paper 足够
  但 dataset 和 repo 都不足

PARK:
  用户手动证据不足，系统证据也不够，需要导师或数据源确认

STOP:
  无可用数据集
  或无评价指标
  或所有 repo 不可复现
```

---

## 5. 科研 Skill 化的最小落点

`PaperAgent_科研Skill下载链接汇总.md` 建议内置 8 个核心科研 Skill，但本阶段只建立最小 Skill 规范，不引入完整第三方仓库。

### 5.1 本阶段只抽象 4 个内部 Skill

```text
paper-card
dataset-validation
github-baseline
evidence-ledger
```

对应关系：

| 内部 Skill | 本阶段用途 | 来源参考 |
|---|---|---|
| paper-card | 论文分类与相关性评分 | Academic Research Skills / Claude Scholar |
| dataset-validation | 数据集可用性评分 | DatasetResearch / Scientific Agent Skills |
| github-baseline | 仓库可复现评分 | Agent Research Skills |
| evidence-ledger | 证据状态、去重、评分汇总 | Claude Scholar |

### 5.2 Skill 不直接执行外部代码

本阶段的 Skill 形态是项目内部规范：

```text
skills/
├── research/
│   └── paper-card/SKILL.md
├── dataset/
│   └── dataset-validation/SKILL.md
├── engineering/
│   └── github-baseline/SKILL.md
└── evidence/
    └── evidence-ledger/SKILL.md
```

每个 `SKILL.md` 只描述：

```text
触发条件
输入结构
输出结构
评分规则
禁止事项
测试样例
```

不要在本阶段加入：

```text
第三方 shell 命令
pip/npm install
外部 repo 原样拷贝
自动上传文件
未知 API 调用
```

---

## 6. 推荐文件改动

### 6.1 后端新增

```text
apps/api/app/services/evidence_scoring.py
apps/api/app/services/evidence_dedup.py
apps/api/app/schemas_evidence_scoring.py
apps/api/tests/test_session5_evidence_scoring.py
```

### 6.2 前端修改

```text
apps/web/app.js
apps/web/styles.css
apps/web/e2e/test_one_topic_session5_scoring.py
```

### 6.3 Skill 文档新增

```text
skills/research/paper-card/SKILL.md
skills/dataset/dataset-validation/SKILL.md
skills/engineering/github-baseline/SKILL.md
skills/evidence/evidence-ledger/SKILL.md
```

---

## 7. 前端改造要求

### 7.1 证据卡片展示评分

论文卡片增加：

```text
相关性：0.72
类型：baseline_method
理由：标题和摘要均命中 YOLO + defect detection
```

数据集卡片增加：

```text
可用性：0.68
状态：needs_preprocess
理由：有公开链接和标注说明，但 license 不明确
```

工程卡片增加：

```text
可复现性：0.75
类型：baseline_framework
理由：README、requirements、train/eval 脚本齐全
```

### 7.2 增加排序

证据工作台支持：

```text
按评分排序
按年份排序
按证据状态排序
只看核心证据
只看待核查证据
只看低分证据
```

### 7.3 增加评分刷新按钮

按钮：

```text
重新评分证据
```

行为：

```text
对当前 project 的 evidence pool 重新计算 score
不改变用户 review_status
被 rejected 的证据仍保留，但不参与可行性判断
```

---

## 8. API 设计建议

### 8.1 重新评分

```text
POST /api/v1/one-topic/{project_id}/evidence/rescore
```

输出：

```json
{
  "project_id": "ot_xxx",
  "paper_count": 5,
  "dataset_count": 2,
  "repo_count": 2,
  "updated_count": 9,
  "summary": {
    "avg_paper_score": 0.68,
    "avg_dataset_score": 0.55,
    "avg_repo_score": 0.72
  }
}
```

### 8.2 获取评分摘要

```text
GET /api/v1/one-topic/{project_id}/evidence/score-summary
```

输出：

```json
{
  "usable_papers": 4,
  "usable_datasets": 1,
  "usable_repos": 1,
  "low_quality_evidence": 3,
  "rejected_evidence": 2,
  "feasibility_inputs": {
    "paper_quality": "中",
    "dataset_quality": "弱",
    "repo_quality": "中"
  }
}
```

### 8.3 去重检查

```text
POST /api/v1/one-topic/{project_id}/evidence/dedup/check
```

用于手动添加前提示：

```json
{
  "is_duplicate": true,
  "existing_evidence_id": "paper_xxx",
  "reason": "same_doi"
}
```

---

## 9. 测试要求

### 9.1 后端单元测试

新增文件：

```text
apps/api/tests/test_session5_evidence_scoring.py
```

必须覆盖：

```text
1. paper relevance score
2. paper type classification
3. dataset score
4. dataset status
5. repo score
6. repo type classification
7. DOI 去重
8. title 相似去重
9. repo owner/name 去重
10. rejected evidence 不参与 score summary
11. core evidence 优先进入 feasibility
12. rescore 不改变 review_status
```

### 9.2 前端 Playwright

新增文件：

```text
apps/web/e2e/test_one_topic_session5_scoring.py
```

必须覆盖：

```text
1. 证据卡片显示分数
2. 点击“重新评分证据”后 score summary 更新
3. 低分证据可以被拒绝
4. 被拒绝证据不参与可行性判断
5. 排序功能能把高分证据排在前面
6. 手动添加重复 DOI 时前端提示已存在
```

### 9.3 回归测试

必须继续通过：

```text
Session 01 evidence API
Session 02 evidence workbench e2e
Session 03 gates
Session 04 pivot routes
OneTopic happy path
```

---

## 10. 验收标准

Session 05 通过条件：

```text
1. 每条 paper / dataset / repo evidence 都有 score 或明确 unscored 原因
2. 证据工作台能展示评分、类型和理由
3. 证据可按评分排序
4. 低分或无关证据可被拒绝
5. rejected 证据不参与可行性判断
6. core 证据优先参与可行性判断
7. 重复 DOI / repo / dataset 不会重复入池
8. 可行性判断不再只看数量，也看证据质量
9. 新增 API 测试通过
10. 新增 Playwright 测试通过
```

---

## 11. Session 05 完工报告要求

完成后必须新增：

```text
Plan/reports/Session_05_Evidence_Scoring_验收报告.md
```

报告必须包含：

```text
1. 范围
2. 文件清单
3. 新增 API
4. 评分公式
5. 去重规则
6. 前端变化
7. 测试结果
8. 修复的 bug
9. 未做项
10. 下一 session 建议
```

---

## 12. Session 06 预告

Session 05 完成后，下一步建议是 Session 06：

> EvidenceRef 强制挂接：让可行性判断、Pivot 路线、工作包和开题建议都能引用具体 evidence_id。

目标：

```text
FeasibilitySummary.evidence_refs
PivotRoute.evidence_refs
WorkPackage.evidence_refs
ProposalRecommendation.evidence_refs
```

这一步完成后，系统才真正从“有证据池”升级为“所有结论都能追溯证据来源”。

---

## 13. 一句话执行指令

下一步只做一件事：

> 给证据池里的论文、数据集和工程仓库建立去重、分类、评分体系，并让可行性判断使用“已审核 + 高质量”的证据，而不是继续按数量粗略判断。

