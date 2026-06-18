# PaperAgent Session 09 SOP：双栏证据工作台与 Agent 卡片导入入口

> 日期：2026-06-18  
> 阶段定位：在 Session 08 完成 Markdown 导出后，回到“交互式证据工作台”的产品形态升级。  
> 本轮目标：把证据工作台从“证据列表”升级为“用户材料 vs 系统候选”的双栏工作区，并提供 Agent Card Intake 的最小入口。  
> 重要边界：本阶段只做最小可用入口，不做 PDF 全文 RAG、不做图片 OCR 大模型链路、不做完整网页爬虫、不做 Skill Marketplace。

---

## 1. 当前状态判断

根据 `Plan/reports/Session_08_FinalPackage_Markdown_验收报告.md`：

- Session 08 已完成 13 章节开题报告 Markdown 导出；
- 已支持 EvidenceRef 引用编号 `[E1] / [D1] / [R1]`；
- 前端已有“开题报告导出”区域、预览、下载；
- 后端新增 `final_package.py`，并通过 85 个后端测试；
- Playwright 新增 8 个 Session 08 测试，全部通过；
- Session 08 已明确预留：
  - 双栏证据工作台；
  - Agent Card Intake；
  - `workspace_lane`；
  - `assistant_intake`；
  - `raw_input_type` / `extraction_confidence` / `extraction_warnings`。

因此 Session 09 不再继续做报告导出，而应落实这两个预留点的最小版本。

---

## 2. Session 09 目标

Session 09 名称：

```text
双栏证据工作台与 Agent 卡片导入入口
```

目标：

```text
左侧：用户希望使用的证据
右侧：系统检索到的候选证据
底部/侧边：Agent 助手输入链接或文字，生成待确认 EvidenceCard
```

完成后，用户应能：

```text
1. 看到论文 / 数据集 / 工程三类证据的双栏布局；
2. 把系统候选移动到“用户希望使用”栏；
3. 把某条证据标为核心；
4. 输入 URL / GitHub 链接 / 数据集网页 / 文字描述，生成一张待确认卡片；
5. 确认卡片后进入证据池；
6. 后续 EvidenceRef 和 Markdown 报告优先引用左侧用户选择的证据。
```

---

## 3. 本阶段不做什么

| 不做 | 原因 |
|---|---|
| 不做拖拽排序 | MVP 用按钮移动即可，减少前端复杂度 |
| 不做图片识别/OCR | 先支持 URL 和纯文本，图片留给后续 |
| 不做 PDF 解析 | PDF 全文解析属于 RAG/Docling/GROBID 后续阶段 |
| 不做网页深爬 | 只做 URL 类型识别和轻量元数据抽取 |
| 不做真实 GitHub API 强依赖 | 可先用 URL 规则 + 现有 repo 字段生成卡片 |
| 不做 Skill Marketplace | 只参考已有内部 skill，不引入第三方代码 |
| 不做报告结构重写 | Session 08 已完成报告导出，本阶段只影响证据来源优先级 |

---

## 4. 功能范围

### 4.1 EvidenceItem 字段扩展

建议扩展 `apps/api/app/schemas_evidence.py` 中的 `EvidenceItem`：

```python
workspace_lane: Literal[
    "user_preferred",
    "system_found",
    "selected",
    "rejected"
] = "system_found"

workspace_order: int | None = None
paired_with: list[str] = []

raw_input_type: Literal[
    "url",
    "text",
    "github",
    "dataset_page",
    "paper_page",
    "image",
    "pdf"
] | None = None

raw_input_ref: str | None = None
extraction_confidence: float | None = None
extraction_warnings: list[str] = []
```

字段语义：

| 字段 | 说明 |
|---|---|
| `workspace_lane` | 当前证据在工作台的栏位 |
| `workspace_order` | 后续支持用户排序 |
| `paired_with` | 后续支持用户论文和系统论文配对 |
| `raw_input_type` | Agent 卡片导入的输入类型 |
| `raw_input_ref` | 原始 URL / 文本摘要 / 文件引用 |
| `extraction_confidence` | Agent 抽取置信度 |
| `extraction_warnings` | 抽取风险，例如“缺少许可信息” |

MVP 规则：

```text
manual / upload / import / assistant_intake 默认 user_preferred
auto_search 默认 system_found
review_status=core 默认 selected
review_status=rejected 默认 rejected
```

---

### 4.2 双栏 Board 模型

新增响应结构：

```python
class EvidenceWorkspaceBoard(BaseModel):
    project_id: str
    board_type: Literal["paper", "dataset", "repo"]
    left_lane_title: str = "用户希望使用"
    right_lane_title: str = "系统检索候选"
    left_items: list[EvidenceItem]
    right_items: list[EvidenceItem]
    selected_items: list[EvidenceItem]
    rejected_items: list[EvidenceItem]
```

建议三类 board：

```text
paper board
dataset board
repo board
```

---

### 4.3 Board API

新增：

```text
GET /api/v1/one-topic/{project_id}/workspace/board
```

返回：

```json
{
  "project_id": "ot_xxx",
  "papers": {"left_items": [], "right_items": []},
  "datasets": {"left_items": [], "right_items": []},
  "repos": {"left_items": [], "right_items": []}
}
```

新增：

```text
PATCH /api/v1/one-topic/{project_id}/workspace/item
```

请求：

```json
{
  "evidence_id": "paper_001",
  "workspace_lane": "user_preferred",
  "review_status": "core",
  "reason": "导师指定核心论文"
}
```

要求：

```text
更新 workspace_lane；
可选同步 review_status；
写入 Trace；
触发 refs/coverage 可重新计算；
不删除证据。
```

---

### 4.4 Agent Card Intake 最小入口

新增：

```text
POST /api/v1/one-topic/{project_id}/cards/intake
```

请求：

```json
{
  "input_type": "url",
  "content": "https://github.com/ultralytics/ultralytics",
  "hint": "这是我想用的 YOLO baseline",
  "target_lane": "user_preferred"
}
```

响应：

```json
{
  "ok": true,
  "needs_user_confirmation": true,
  "card_type": "repo",
  "evidence": {
    "evidence_id": "repo_xxx",
    "evidence_type": "repo",
    "source_mode": "assistant_intake",
    "title": "ultralytics/ultralytics",
    "url": "https://github.com/ultralytics/ultralytics",
    "review_status": "pending",
    "workspace_lane": "user_preferred"
  },
  "extraction_confidence": 0.80,
  "warnings": ["未实际验证 train/eval 脚本"]
}
```

MVP 识别规则：

| 输入 | 识别为 |
|---|---|
| `github.com/{owner}/{repo}` | repo |
| URL 中含 `arxiv.org/abs` | paper |
| URL 中含 `huggingface.co/datasets` | dataset |
| URL 中含 `kaggle.com/datasets` | dataset |
| 普通 URL + hint 含“论文” | paper |
| 普通 URL + hint 含“数据集” | dataset |
| 普通 URL + hint 含“代码/工程/repo/baseline” | repo |
| 纯文本描述 | note 或按 hint 生成 paper/dataset/repo |

注意：

```text
MVP 不需要真的抓网页内容；
可以先从 URL 和 hint 生成卡片；
所有 assistant_intake 卡片默认 pending，必须用户确认后才能作为 supports。
```

---

## 5. 前端工作台设计

### 5.1 页面布局

在当前证据工作台区域加入三组 tabs 或分区：

```text
论文工作台
├── 左：用户希望使用
└── 右：系统检索候选

数据集工作台
├── 左：用户希望使用
└── 右：系统检索候选

工程工作台
├── 左：用户希望使用
└── 右：系统检索候选
```

MVP 可以不做独立路由，直接在现有 OneTopic 页面证据区中增强。

---

### 5.2 卡片操作

每张卡片按钮：

```text
加入左侧
标为核心
移到系统候选
拒绝
查看来源
```

行为映射：

| 按钮 | workspace_lane | review_status |
|---|---|---|
| 加入左侧 | user_preferred | accepted |
| 标为核心 | selected | core |
| 移到系统候选 | system_found | pending/background |
| 拒绝 | rejected | rejected |

---

### 5.3 Agent 卡片导入 UI

新增一个小面板：

```text
Agent 助手：把材料变成证据卡片
输入框：URL / 文字描述
hint：这是什么材料？
目标栏：用户希望使用 / 系统候选
按钮：生成卡片
```

生成后展示：

```text
待确认卡片
├── 类型
├── 标题
├── 来源
├── 置信度
├── 风险提示
└── 确认加入 / 放弃
```

MVP 可以直接生成并放入 pending，用户再用现有状态按钮确认。

---

## 6. 与 EvidenceRef / FinalPackage 的联动

Session 09 必须保证：

```text
workspace_lane=user_preferred 或 selected 的证据，在 EvidenceRef 选择中优先级更高；
assistant_intake 且 pending 的证据不能作为 supports；
assistant_intake 且 core/accepted 的证据可以进入报告引用；
rejected lane 的证据不得进入 Markdown 正向引用。
```

建议更新 `evidence_refs._ref_priority()`：

```text
workspace_lane bonus:
selected = +0.15
user_preferred = +0.10
system_found = +0.00
rejected = -1.00
```

---

## 7. 测试要求

### 7.1 后端测试

新增：

```text
apps/api/tests/test_session9_workspace_board.py
```

必须覆盖：

```text
1. workspace board 能按 paper/dataset/repo 分组
2. manual evidence 默认进入 user_preferred
3. auto_search evidence 默认进入 system_found
4. PATCH workspace/item 能移动 evidence
5. 标为核心后 review_status=core
6. rejected lane 不进入 supports
7. user_preferred 在 EvidenceRef priority 中优先
8. cards/intake 能识别 GitHub URL 为 repo
9. cards/intake 能识别 arXiv URL 为 paper
10. cards/intake 能识别 HuggingFace/Kaggle 为 dataset
11. assistant_intake 默认 pending
12. assistant_intake pending 不进入 Markdown supports
```

---

### 7.2 前端 Playwright

新增：

```text
apps/web/e2e/test_one_topic_session9_workspace_board.py
```

必须覆盖：

```text
1. 页面显示双栏证据工作台
2. paper/dataset/repo 三类分区存在
3. 系统候选卡片可以加入左侧
4. 卡片可以标为核心
5. 拒绝卡片后不再作为正向引用
6. Agent 卡片导入面板存在
7. 输入 GitHub URL 后生成 repo 卡片
8. 生成的卡片显示 pending / extraction_confidence / warning
```

---

### 7.3 回归测试

必须继续通过：

```text
Session 05 Evidence Scoring
Session 07 EvidenceRef
Session 08 FinalPackage Markdown
OneTopic happy path
```

如果 Playwright 慢，可保留 smoke + mock fallback，但报告必须写清楚。

---

## 8. 验收标准

Session 09 通过条件：

```text
1. 证据工作台出现双栏布局；
2. 论文 / 数据集 / 工程都能分到用户栏和系统栏；
3. 用户能把系统候选加入左侧；
4. 用户能把卡片标为核心；
5. 用户能拒绝卡片；
6. Agent Card Intake 能从 URL / 文字生成 pending EvidenceItem；
7. GitHub / arXiv / HuggingFace / Kaggle URL 有基础类型识别；
8. assistant_intake 卡片默认不能直接 supports；
9. workspace_lane 会影响 EvidenceRef 优先级；
10. Markdown 报告仍能正常导出；
11. 新增后端测试通过；
12. 新增 Playwright 测试通过。
```

最低可接受 MVP：

```text
双栏 UI
+ workspace_lane 字段
+ 按钮移动卡片
+ URL -> pending EvidenceCard
+ EvidenceRef 优先级接入 workspace_lane
```

---

## 9. 完工报告要求

完成后新增：

```text
Plan/reports/Session_09_WorkspaceBoard_CardIntake_验收报告.md
```

报告必须包含：

```text
1. 本阶段范围
2. 新增字段
3. 新增 API
4. 双栏 UI 变化
5. Agent Card Intake 规则
6. EvidenceRef / Markdown 联动
7. 后端测试结果
8. Playwright 测试结果
9. 未做项
10. 下一 Session 建议
```

---

## 10. 下一 Session 预告

Session 10 建议：

```text
多源检索与 URL 验证增强
```

重点：

```text
OpenAlex / Semantic Scholar / GitHub URL 轻验证
dataset URL 验证
url_verified / extraction_confidence 接入 EvidenceRef
```

仍然围绕“证据工作台”，不要跳到完整论文写作。

