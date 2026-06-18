# PaperAgent Session 08 SOP：基于 EvidenceRef 的开题报告 Markdown 导出

> 日期：2026-06-18  
> 阶段定位：交互式证据工作台短期闭环的最后一步。  
> 本轮目标：把 Session 07 已经挂接好的 `EvidenceRef` 转化为可导出的开题报告 Markdown 初稿。  
> 重要约束：本阶段不做完整毕业论文写作系统，不做 DOCX/PPT，不做全文 RAG，不做多 Agent 委员会升级。

---

## 1. 当前状态判断

截至 Session 07，PaperAgent / TopicPilot-CN OneTopic MVP 已完成：

| Session | 已完成能力 | 状态 |
|---|---|---|
| Session 01 | EvidenceItem、手动添加论文/数据集/工程、证据审核状态 | 已完成 |
| Session 02 | 证据工作台 UI、证据状态按钮、三类证据展示 | 已完成 |
| Session 03 | Human Gate：关键词与检索计划可修改 | 已完成 |
| Session 04 | GO/NARROW/PIVOT/PARK/STOP 五档判断与三条 Pivot 路线 | 已完成 |
| Session 05 | 证据评分、去重、分类、score summary | 已完成 |
| Session 06 | LLM 路径激活：关键词参考论文、rerank、推荐与轻审核 | 已完成，LLM e2e 记录有历史不一致 |
| Session 07 | EvidenceRef 强制挂接，可行性/Pivot/工作包/轻审核可复核 | 已完成 |

现在还差短期闭环中的最后一步：

```text
证据工作台
→ EvidenceRef 复核
→ 工作包确认
→ 导出一份能拿去改 Word 的开题报告 Markdown 初稿
```

这正好对应 `PaperAgent_交互式证据工作台改造计划书与SOP.md` 中的最低验收标准：

```text
报告中能看到证据来源
```

---

## 2. Session 08 目标

Session 08 名称：

```text
EvidenceRef-Based Opening Report Markdown Export
```

目标：

> 基于当前 OneTopicResponse snapshot、EvidenceRef、coverage_score 和用户复核结果，生成一份结构化开题报告 Markdown，并支持前端预览与下载。

本阶段交付的不是“最终可提交论文”，而是：

```text
开题报告初稿
+ 证据引用清单
+ 待补证据标记
+ 修改清单
+ 答辩追问
+ 风险预案
```

---

## 3. 本阶段不做什么

| 不做 | 原因 |
|---|---|
| 不做 DOCX 导出 | 先把 Markdown 结构和证据引用跑稳，DOCX 属后续排版层 |
| 不做完整毕业论文正文 | 当前目标是开题/选题，不是完整论文写作 |
| 不做 PDF 全文 RAG | 会引入解析、切片、向量库，超出短期闭环 |
| 不做多 Agent 委员会 | Session 07 的证据追溯优先级高于评审复杂度 |
| 不做 Skill Marketplace | 当前不需要引入第三方 Skill 批量安装 |
| 不做左/右双栏工作台完整实现 | 本轮只预留数据结构和 UI 入口，后续 Session 再做 |
| 不做 Agent 助手自动网页/图片卡片化完整实现 | 本轮只预留 Card Intake 设计，不进入实现范围 |

---

## 4. Session 08 必须实现的功能

### 4.1 FinalPackage 数据结构

建议新增：

```python
class FinalPackage(BaseModel):
    project_id: str
    final_topic: str
    ready_for_proposal: bool
    coverage_score: float
    low_coverage_warning: bool
    backend_verification: Literal["PASS", "WARN", "FAIL"]
    ui_verification: Literal["PASS", "WARN", "FAIL", "NOT_RUN"]
    playwright_verification: Literal["PASS", "WARN", "FAIL", "NOT_RUN"]
    proposal_markdown: str
    proposal_markdown_chars: int
    sections: list[ReportSection]
    citation_list: list[ReportCitation]
    unsupported_claims: list[str]
    revision_checklist: list[str]
    generated_at: str
```

配套结构：

```python
class ReportSection(BaseModel):
    key: str
    title: str
    content: str
    evidence_refs: list[EvidenceRef]
    unsupported_claims: list[str] = []


class ReportCitation(BaseModel):
    ref_no: str
    evidence_id: str
    evidence_type: str
    title: str
    url: str | None = None
    review_status: str
    role: str
    used_in_sections: list[str]
```

---

### 4.2 Markdown 报告结构

必须输出以下结构：

```markdown
# 开题报告：{final_topic}

> 生成时间：{generated_at}
> 证据覆盖率：{coverage_score}
> 状态：{ready_for_proposal}

## 证据覆盖提示

## 一、研究背景与意义

## 二、国内外研究现状

## 三、研究问题与目标

## 四、研究内容与技术路线

## 五、数据集、Baseline 与评价指标

## 六、工作包设计

## 七、预期创新点

## 八、可行性分析

## 九、风险预案

## 十、进度计划

## 十一、开题答辩可能追问

## 十二、证据引用清单

## 十三、待补证据与修改清单
```

每一节都必须有以下之一：

```text
1. EvidenceRef 引用；
2. 明确标记：[待补证据]；
3. 明确说明该节来自用户输入或系统结构化推理。
```

---

### 4.3 证据引用格式

正文中引用统一采用：

```text
[E1]
[E2]
[D1]
[R1]
```

建议映射：

| 前缀 | 类型 |
---|---|
| `E` | paper / literature evidence |
| `D` | dataset evidence |
| `R` | repo / baseline evidence |
| `N` | note / user note |

示例：

```markdown
YOLO 系列方法在目标检测任务中已有成熟工程生态，适合作为毕业设计的可复现基线 [R1]。
当前方向已有相关应用论文支撑，但特定研究对象的数据集仍需进一步确认 [E1][D1]。
```

证据清单：

```markdown
## 十二、证据引用清单

| 编号 | 类型 | 标题 | 状态 | 分数 | 链接 |
|---|---|---|---|---:|---|
| E1 | paper | xxx | core | 0.82 | https://... |
| D1 | dataset | NEU-DET | accepted | 0.76 | https://... |
| R1 | repo | Ultralytics YOLO | accepted | 0.88 | https://... |
```

---

### 4.4 低覆盖率提示

如果 `coverage_score < 0.70`，Markdown 顶部必须加：

```markdown
> 警告：当前证据覆盖率不足。本文档可作为讨论草稿，但不建议直接用于正式开题提交。
```

同时在 `待补证据与修改清单` 中列出：

```text
缺少 dataset ref 的工作包；
缺少 baseline ref 的工作包；
只有 needs_check 支撑的结论；
LLM 生成但无 evidence_ref 的推荐理由。
```

---

### 4.5 rejected / needs_check 处理规则

报告生成时必须遵守：

```text
rejected 证据不得出现在正向支撑引用中；
needs_check 不得作为 supports，只能作为风险或待确认；
background 可以进入研究现状，但不能支撑“可做”结论；
core 优先出现在研究现状、可行性分析和工作包设计中。
```

如果用户曾经移除某条 EvidenceRef：

```text
报告不得再把它作为默认引用放回去。
```

---

## 5. API 设计

### 5.1 构建最终 Markdown

```text
POST /api/v1/one-topic/{project_id}/final-package/build
```

输入：

```json
{
  "include_low_confidence_refs": false,
  "include_rejected_as_appendix": false,
  "style": "proposal_mvp",
  "language": "zh"
}
```

输出：

```json
{
  "project_id": "ot_xxx",
  "ready_for_proposal": true,
  "coverage_score": 0.86,
  "low_coverage_warning": false,
  "proposal_markdown_chars": 12800,
  "proposal_markdown": "# 开题报告：...",
  "unsupported_claims": [],
  "revision_checklist": []
}
```

---

### 5.2 下载 Markdown

```text
GET /api/v1/one-topic/{project_id}/final-package/markdown
```

要求：

```text
Content-Type: text/markdown; charset=utf-8
Content-Disposition: attachment; filename="proposal_{project_id}.md"
```

如果还没有 build 过：

```text
可以自动 build 一次；
或返回 409，提示先调用 build。
```

推荐 MVP 行为：

```text
若 snapshot 存在，则自动 build，降低用户操作成本。
```

---

### 5.3 获取 FinalPackage 摘要

```text
GET /api/v1/one-topic/{project_id}/final-package
```

用途：

```text
前端预览页加载最终报告摘要、coverage、字符数、ready 状态。
```

---

## 6. 后端实现建议

### 6.1 新增服务

```text
apps/api/app/services/final_package.py
```

核心函数：

```python
def build_final_package(project_id: str, options: FinalPackageBuildOptions) -> FinalPackage:
    snapshot = evidence.get_snapshot(project_id)
    coverage = refs_api_or_service.coverage(project_id)
    citation_map = build_citation_map(snapshot)
    sections = build_sections(snapshot, citation_map, coverage)
    markdown = render_markdown(sections, citation_map, coverage)
    return FinalPackage(...)
```

---

### 6.2 Markdown 渲染原则

不要让 LLM 一次性自由写完整 Markdown。

推荐流程：

```text
结构化数据
→ 每节生成短段落
→ 插入 EvidenceRef 编号
→ 统一渲染 Markdown
→ 校验 rejected/needs_check 规则
→ 输出
```

如果使用 LLM 润色：

```text
只允许改写段落语言；
不允许新增引用；
不允许新增论文名、数据集名、repo 名；
不允许删除 [E1]/[D1]/[R1] 引用标记。
```

---

### 6.3 Citation Map

建议生成稳定编号：

```text
paper refs 按出现顺序编号：E1, E2, E3
dataset refs 按出现顺序编号：D1, D2
repo refs 按出现顺序编号：R1, R2
note refs 按出现顺序编号：N1, N2
```

同一 evidence_id 在全文中编号必须一致。

---

### 6.4 FinalPackage 缓存

建议在 evidence store 中增加：

```python
latest_final_package: FinalPackage | None
```

触发重建：

```text
用户点击“重新生成报告”
EvidenceRef 被修改
coverage_score 改变
snapshot 更新
```

MVP 可先用内存缓存，后续再持久化。

---

## 7. 前端实现建议

### 7.1 新增报告区域

当前可以不做独立路由，先在 OneTopic 页面底部增加：

```text
开题报告导出
├── ready_for_proposal 状态
├── coverage_score
├── proposal_markdown_chars
├── 预览按钮
├── 重新生成按钮
└── 下载 Markdown 按钮
```

后续再扩展为：

```text
/projects/[id]/report
```

---

### 7.2 Markdown 预览

MVP 预览可以使用：

```text
<pre> 显示 Markdown 原文
```

暂不要求完整 Markdown renderer。

但必须能看见：

```text
[E1] / [D1] / [R1]
证据引用清单
待补证据
coverage warning
```

---

### 7.3 下载按钮

按钮：

```text
下载 Markdown
```

行为：

```text
调用 GET /final-package/markdown
浏览器下载 proposal_{project_id}.md
```

---

## 8. 本轮新增灵感：工作台双栏证据布局

这部分不要求 Session 08 实现，但必须预留实现空间。

### 8.1 灵感描述

后续证据工作台可以改造成双栏/多栏对比：

```text
左侧：用户希望使用的证据
右侧：系统检索到的候选证据
```

论文、数据集、项目工程都采用同一套模式。

示例：

```text
论文工作台
├── 左侧：用户指定/导师给定/已标核心论文
└── 右侧：系统从 arXiv / OpenAlex / Semantic Scholar 搜到的论文

数据集工作台
├── 左侧：用户已有数据集 / 导师指定数据集
└── 右侧：系统搜到的公开数据集

工程工作台
├── 左侧：用户希望复现的 repo / 已有代码
└── 右侧：系统搜到的 baseline / framework / demo
```

### 8.2 产品价值

这个设计能解决一个关键问题：

```text
开题不是只让系统推荐，而是让用户把“自己想用的材料”和“系统找到的材料”放在同一个桌面上比较。
```

它支持：

```text
拖拽或按钮加入核心证据；
把系统候选移动到用户证据区；
把用户证据和系统证据配对；
发现冲突、重复和缺口；
让报告优先引用左侧核心证据。
```

### 8.3 预留数据结构

后续可给 `EvidenceItem` 增加：

```python
workspace_lane: Literal["user_preferred", "system_found", "selected", "rejected"] = "system_found"
workspace_order: int | None = None
paired_with: list[str] = []
```

或新增：

```python
class EvidenceWorkspaceBoard(BaseModel):
    project_id: str
    board_type: Literal["paper", "dataset", "repo"]
    left_lane_title: str
    right_lane_title: str
    left_items: list[str]
    right_items: list[str]
    selected_items: list[str]
```

### 8.4 与 Session 08 的关系

Session 08 不实现双栏 UI，但 Markdown 生成时应预留逻辑：

```text
如果 evidence 有 workspace_lane=user_preferred 或 core，则报告优先引用；
如果只有 system_found，则可以引用，但在证据清单中标注“系统检索”；
如果 selected_items 存在，则按 selected_items 排序生成引用。
```

MVP 当前可以先用已有字段近似：

```text
core / accepted / background / pending
```

---

## 9. 本轮新增灵感：Agent 助手自动生成证据卡片

这部分不要求 Session 08 实现，但必须留好入口。

### 9.1 灵感描述

用户可以给 Agent 助手输入：

```text
网页链接
图片
截图
PDF 片段
文字描述
GitHub 链接
数据集页面链接
论文主页链接
导师给的备注
```

Agent 自动识别材料类型，生成证据卡片并放进工作区。

示例：

```text
用户：这是导师发我的数据集网页 https://...
Agent：
我识别到这是 dataset 证据，已生成 DatasetCard：
- 名称
- 来源
- 下载方式
- 许可状态
- 标注类型
- 适合任务
- 风险
是否加入左侧“用户希望使用的数据集”？
```

### 9.2 产品价值

这会让系统从“填表工具”升级为真正的资料整理助手：

```text
用户不需要理解 EvidenceItem schema；
用户只需要把材料丢进来；
Agent 负责转成卡片；
用户负责审核。
```

### 9.3 预留 API

后续可设计：

```text
POST /api/v1/one-topic/{project_id}/cards/intake
```

输入：

```json
{
  "input_type": "url",
  "content": "https://github.com/ultralytics/ultralytics",
  "hint": "这是我想用的 YOLO baseline",
  "target_lane": "user_preferred"
}
```

输出：

```json
{
  "card_type": "repo",
  "evidence_item": {
    "title": "ultralytics/ultralytics",
    "evidence_type": "repo",
    "source_mode": "assistant_intake",
    "review_status": "pending",
    "workspace_lane": "user_preferred"
  },
  "extraction_confidence": 0.84,
  "needs_user_confirmation": true,
  "warnings": []
}
```

### 9.4 预留数据字段

后续可给 `EvidenceItem` 增加：

```python
source_mode: Literal[
    "auto_search",
    "manual",
    "upload",
    "import",
    "assistant_intake"
]

raw_input_type: Literal["url", "image", "text", "pdf", "github", "dataset_page"] | None
raw_input_ref: str | None
extraction_confidence: float | None
extraction_warnings: list[str] = []
```

### 9.5 Session 08 的预留方式

Session 08 不实现卡片自动生成，但 Markdown 证据清单要兼容：

```text
source_mode=assistant_intake
```

如果未来有 Agent 生成卡片，报告引用清单可以显示：

```text
来源：Agent 助手整理，用户已确认
```

未确认的 assistant card 不得直接支撑核心结论。

---

## 10. 测试要求

### 10.1 后端测试

新增：

```text
apps/api/tests/test_session8_final_package.py
```

必须覆盖：

```text
1. build_final_package 能从 latest_snapshot 生成 Markdown
2. Markdown 包含 13 个章节标题
3. Markdown 包含 [E1] / [D1] / [R1] 引用
4. citation_list 中同一 evidence_id 编号稳定
5. rejected evidence 不进入正向引用
6. needs_check evidence 只进入风险或待确认
7. coverage_score < 0.70 时输出 warning
8. unsupported_claims 进入“待补证据与修改清单”
9. GET /final-package/markdown 返回 text/markdown
10. build 不改变 review_status
11. EvidenceRef 被用户移除后不再进入报告
12. 没有 snapshot 时返回清晰错误或自动提示先分析
```

---

### 10.2 前端 Playwright

新增：

```text
apps/web/e2e/test_one_topic_session8_final_package.py
```

必须覆盖：

```text
1. 页面出现“开题报告导出”区域
2. 点击“生成报告”后显示 Markdown 字符数
3. Markdown 预览包含“开题报告”
4. Markdown 预览包含证据引用编号
5. Markdown 预览包含证据引用清单
6. low coverage 时显示 warning
7. 点击“下载 Markdown”触发下载
8. rejected evidence 不出现在引用清单的 supports 中
```

---

### 10.3 回归测试

必须继续通过：

```text
Session 01 Evidence API
Session 02 Evidence Workbench
Session 03 Human Gates
Session 04 Pivot Routes
Session 05 Evidence Scoring
Session 06 LLM Path 核心后端测试
Session 07 EvidenceRef
OneTopic happy path
```

LLM 真实 e2e 允许作为 smoke，不应成为每次 CI 的硬阻断。

---

## 11. 验收标准

Session 08 通过条件：

```text
1. 可以从已有 OneTopic snapshot 构建 FinalPackage
2. 可以生成完整 Markdown 开题报告初稿
3. Markdown 至少包含 13 个固定章节
4. 正文中能看到 [E1]/[D1]/[R1] 等证据引用
5. 末尾有证据引用清单
6. rejected 证据不会作为正向引用
7. needs_check 证据只进入风险或待确认
8. coverage_score < 0.70 时有明显提示
9. 前端能预览 Markdown
10. 前端能下载 Markdown
11. 新增后端测试通过
12. 新增 Playwright 测试通过
```

最低可接受 MVP：

```text
生成 Markdown
+ 显示 EvidenceRef 引用编号
+ 证据引用清单
+ 前端预览
+ 下载 .md
```

---

## 12. 完工报告要求

完成后新增：

```text
Plan/reports/Session_08_FinalPackage_Markdown_验收报告.md
```

报告必须包含：

```text
1. 本阶段范围
2. 新增 / 修改的数据结构
3. 新增 API
4. Markdown 章节结构
5. EvidenceRef 引用规则
6. rejected / needs_check 处理规则
7. 前端预览与下载变化
8. 后端测试结果
9. Playwright 测试结果
10. 未做项
11. 双栏证据工作台灵感的预留情况
12. Agent 助手卡片化灵感的预留情况
13. 下一 Session 建议
```

---

## 13. Session 09 预告

Session 08 完成后，建议进入：

```text
Session 09：证据工作台双栏化 + Agent Card Intake 入口
```

优先级建议：

```text
P0：双栏工作台最小 UI
P0：用户证据 / 系统证据 lane 字段
P1：URL → EvidenceCard
P1：GitHub repo → RepoCard
P1：数据集网页 → DatasetCard
P2：图片 / 截图 → EvidenceCard
P2：PDF 片段 → PaperCard
```

Session 09 仍然应围绕“证据工作台”，不要跳到完整论文写作。

---

## 14. 一句话执行指令

Session 08 只做一个闭环：

> 把已经复核过的 EvidenceRef 变成一份可预览、可下载、能看见证据来源的开题报告 Markdown 初稿，同时为后续“双栏证据工作台”和“Agent 助手自动生成证据卡片”预留字段与接口空间。

