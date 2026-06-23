# PaperAgent Session 15 SOP：全文资料与图片 / PDF / 网页卡片化

> 日期：2026-06-19  
> 阶段定位：在多源检索、证据工作台、URLVerified、Trace、ReportQuality、Skill Registry 已完成后，把用户手里的“非结构化资料”转成可审核的 EvidenceCard。  
> 本轮目标：支持用户选择性导入 PDF 片段、网页文字、截图 / 图片说明和手动描述，由系统生成 pending 卡片进入工作台；不做大规模全文 RAG，不批处理已有大量视频和图片。

---

## 1. Session 14 验收判断

已审阅：

```text
Plan/reports/Session_14_MultiSource_Retrieval_验收报告.md
```

判断：

```text
Session 14 可过验收；
可以进入 Session 15。
```

依据：

```text
1. 多源候选已能稳定进入 Evidence Ledger；
2. 导入候选默认 system_found / pending / unverified，不直接污染 supports；
3. Trace 已记录 retrieval_run_started / completed / imported / skipped_duplicate；
4. ReportQuality 已验证 pending + unverified 候选不会提升关键维度；
5. 后端 S14 新增 20 tests passed，全量 API 回归 165 passed；
6. Playwright S14 + S7-S13 总计 59 passed；
7. 真实 OpenAlex smoke 已跑通，S2 / Kaggle 占位降级，不阻塞当前主线。
```

需要带入 Session 15 的风险：

```text
1. 外部资料解析结果不能直接作为 supports；
2. PDF / 图片 / 网页解析结果必须 pending，由用户确认后才进入证据链；
3. 不做大批量视频 / 图片处理，本轮只处理用户显式上传或粘贴的单项资料；
4. 不做全文向量库，不做复杂 RAG，不做 DOCX / PPT 生成；
5. 任何 OCR / 摘要 / LLM 生成内容都必须保留来源片段和置信度。
```

---

## 2. Session 15 名称

```text
全文资料与图片 / PDF / 网页卡片化
```

一句话目标：

```text
把用户手动给出的 PDF、截图、网页文字、链接说明、导师备注等非结构化资料，转成可审核、可追溯、可验证的 EvidenceCard，并放入交互式证据工作台。
```

---

## 3. 本阶段不做什么

| 不做 | 原因 |
|---|---|
| 不批处理已有大量视频和图片 | 用户已说明这些资料已总结好，本轮只做选中资料入口 |
| 不做视频解析 | 视频成本高，且不在开题证据链 P0 |
| 不做全文向量库 | 当前目标是卡片化，不是 RAG 问答系统 |
| 不做全文自动阅读后直接写报告 | 必须先经过卡片、审核、验证、EvidenceRef |
| 不绕过 PDF / 数据库权限 | 保持合规 |
| 不上传用户文件到第三方服务 | 除非后续明确设计隐私开关 |
| 不把 OCR / LLM 摘要直接视为事实 | 解析结果只是候选，必须 pending |

---

## 4. 当前流程位置

Session 15 接在当前主线：

```text
用户输入题目
→ 关键词拆解
→ 多源检索
→ 证据工作台
→ 用户补充 PDF / 截图 / 网页文字 / 导师备注
→ 资料解析为 DraftCard
→ 用户确认 / 修改 / 拒绝
→ Evidence Ledger
→ URLVerified / Manual Verification
→ EvidenceRef
→ FinalPackage
→ ReportQuality
```

核心原则：

```text
资料解析只负责“生成草稿卡片”，不负责“直接支撑结论”。
```

---

## 5. 核心交付

### 5.1 后端能力

新增资料摄入服务：

```text
apps/api/app/services/materials/
├── __init__.py
├── models.py
├── storage.py
├── pdf_parser.py
├── image_parser.py
├── web_text_parser.py
├── card_builder.py
├── dedup.py
└── orchestrator.py
```

如果不想立即拆目录，可先做：

```text
apps/api/app/services/material_intake.py
```

但建议拆目录，因为 PDF / 图片 / 网页后续会继续扩展。

### 5.2 API 能力

新增：

```text
POST /api/v1/one-topic/{project_id}/materials/upload
POST /api/v1/one-topic/{project_id}/materials/text
GET  /api/v1/one-topic/{project_id}/materials
GET  /api/v1/one-topic/{project_id}/materials/{material_id}
POST /api/v1/one-topic/{project_id}/materials/{material_id}/cards
POST /api/v1/one-topic/{project_id}/materials/cards/import
PATCH /api/v1/one-topic/{project_id}/materials/cards/{draft_card_id}
```

### 5.3 前端能力

工作台新增资料卡片化面板：

```text
资料导入
├── 上传 PDF
├── 上传截图 / 图片
├── 粘贴网页文字
├── 粘贴 URL + 文字说明
├── 粘贴导师备注
├── 生成草稿卡片
├── 用户编辑草稿
└── 导入工作区
```

---

## 6. 数据模型

### 6.1 MaterialSourceType

```python
MaterialSourceType = Literal[
    "pdf",
    "image",
    "screenshot",
    "web_text",
    "url_note",
    "manual_note",
]
```

### 6.2 MaterialItem

```python
class MaterialItem(BaseModel):
    material_id: str
    project_id: str
    source_type: MaterialSourceType
    filename: str | None = None
    original_url: str | None = None
    title: str | None = None
    storage_path: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    text_excerpt: str | None = None
    page_count: int | None = None
    page_range: str | None = None
    created_at: str
    parse_status: Literal["pending", "parsed", "failed", "skipped"] = "pending"
    parse_confidence: float | None = None
    parse_warnings: list[str] = []
    metadata: dict = Field(default_factory=dict)
```

### 6.3 DraftEvidenceCard

```python
class DraftEvidenceCard(BaseModel):
    draft_card_id: str
    project_id: str
    material_id: str
    suggested_type: Literal["paper", "dataset", "repo", "note", "custom"]
    title: str
    summary: str
    extracted_claims: list[str] = []
    extracted_entities: list[str] = []
    possible_url: str | None = None
    possible_doi: str | None = None
    possible_arxiv_id: str | None = None
    source_excerpt: str | None = None
    page_refs: list[str] = []
    extraction_confidence: float = 0.0
    warnings: list[str] = []
    status: Literal["draft", "edited", "imported", "rejected"] = "draft"
```

### 6.4 MaterialImportResponse

```python
class MaterialImportResponse(BaseModel):
    imported: int
    evidence_ids: list[str]
    skipped: int
    warnings: list[str] = []
```

---

## 7. 资料存储规则

MVP 建议本地存储：

```text
.runtime/materials/{project_id}/{material_id}/original
.runtime/materials/{project_id}/{material_id}/parsed.json
.runtime/materials/{project_id}/{material_id}/thumb.png
```

安全规则：

```text
1. 文件名必须 sanitize；
2. 单文件大小默认 <= 20MB；
3. 只允许 pdf / png / jpg / jpeg / webp / txt / md；
4. 不执行上传文件中的任何脚本；
5. 不读取工作区外路径；
6. 删除项目时后续可清理 material 文件，本轮可暂不做删除。
```

---

## 8. PDF 卡片化

### 8.1 MVP 目标

PDF 支持：

```text
上传；
提取基本文本；
提取标题候选；
提取摘要候选；
提取 DOI / arXiv / URL；
按用户选择页码或前 N 页生成 DraftEvidenceCard；
```

### 8.2 推荐解析策略

优先：

```text
PyMuPDF / pypdf / pdfplumber 中项目已有可用库；
只解析文本层；
不做复杂版面恢复；
```

降级：

```text
扫描版 PDF 无文本层 → parse_status=skipped 或 failed；
提示用户改用截图 / 手动文字说明；
不在本轮强做 OCR。
```

### 8.3 PDF 生成卡片

论文 PDF：

```text
suggested_type = "paper"
title = 提取标题候选
summary = 摘要或前 800 字摘要
source_excerpt = 摘要片段 / 引言片段
page_refs = ["p1", "p2"]
extraction_confidence = 基于标题、摘要、DOI 是否提取到
```

若无法确认是论文：

```text
suggested_type = "note"
warnings += ["未能确认该 PDF 是否为论文"]
```

---

## 9. 图片 / 截图卡片化

### 9.1 MVP 目标

图片支持：

```text
上传截图 / 图片；
用户填写一句说明；
系统生成 NoteCard 草稿；
可选 OCR 只作为增强，不作为强依赖；
```

### 9.2 不做批量图片解析

明确边界：

```text
不扫描 G:\PaperAgent 下已有图片；
不批量处理视频帧；
不批量 OCR；
只处理用户从 UI 选择上传的单张或少量图片。
```

### 9.3 图片卡片字段

```text
suggested_type = "note"
title = 用户说明或文件名派生
summary = 用户说明 + 可选 OCR 摘要
source_excerpt = OCR 前 500 字或空
warnings = ["图片证据需要人工确认"]
extraction_confidence <= 0.6
```

### 9.4 截图证据使用规则

截图类资料默认：

```text
review_status = "pending"
verification_status = "skipped" 或 "unverified"
role 倾向 background / warns
不得直接 supports 关键结论
```

如果截图包含 URL 或 DOI，用户确认后可触发 URLVerified。

---

## 10. 网页文字 / URL + 描述卡片化

### 10.1 输入方式

支持：

```text
粘贴 URL；
粘贴网页正文；
粘贴 URL + 用户说明；
粘贴导师备注；
```

### 10.2 处理规则

URL：

```text
先走已有 Card Intake / URLVerified；
再生成 DraftEvidenceCard；
```

网页正文：

```text
只使用用户粘贴内容；
不自动深爬；
不自动抓取登录态网页；
```

导师备注：

```text
suggested_type = "note"
source_mode = "manual"
workspace_lane = "user_preferred"
review_status = "pending"
verification_status = "skipped"
```

---

## 11. Agent 卡片生成入口升级

延续用户之前的工作台设想：

```text
用户给 Agent：
1. 相关网页链接；
2. 图片；
3. PDF；
4. 文字描述；
5. 导师备注；

Agent 生成：
DraftEvidenceCard
→ 用户确认
→ EvidenceCard
→ 放入工作区。
```

本轮实现重点：

```text
Agent 只生成草稿；
草稿必须可编辑；
草稿必须显示来源片段；
导入后必须 pending；
导入后必须写 Trace；
```

---

## 12. 导入 Evidence Ledger

DraftEvidenceCard 导入时映射：

```text
paper → add_paper_manual
dataset → add_dataset_manual
repo → add_repo_manual
note/custom → add_manual_note 或等价新增接口
```

统一字段：

```text
source_mode = "upload" / "manual" / "import"
workspace_lane = "user_preferred" 或 "system_found"
review_status = "pending"
verification_status = "unverified" / "skipped"
created_by_skill = 按类型映射
raw_input_ref = material_id
```

建议 skill 映射：

```text
paper PDF → paper-card
dataset 文档 → dataset-validation
repo 说明 → github-baseline
note / screenshot / manual_note → evidence-ledger
```

---

## 13. Trace 联动

新增 Trace actions：

```text
material_uploaded
material_text_submitted
material_parsed
material_parse_failed
draft_card_created
draft_card_edited
draft_card_imported
draft_card_rejected
```

每条 trace 至少记录：

```text
material_id；
draft_card_id；
evidence_id；
source_type；
reason / user_note；
parse_confidence；
```

报告中的“关键决策记录”可显示：

```text
用户上传 PDF；
系统生成 PaperCard 草稿；
用户修改标题并导入；
用户拒绝某截图草稿；
```

---

## 14. Verification / EvidenceRef 联动

### 14.1 Verification

```text
PDF 若提取 DOI / arXiv / URL → 可触发 verify；
URL + 描述 → 走 URLVerified；
图片 / 截图 / 导师备注 → 默认 skipped 或 unverified；
用户可手动确认 verification；
```

### 14.2 EvidenceRef

必须保持：

```text
rejected 不得正向引用；
pending 不得直接 supports；
failed 不得 supports；
图片 / note / OCR-only 证据默认不 supports 关键技术结论；
```

建议角色：

```text
accepted paper PDF + verified DOI → 可 supports；
accepted manual note → background；
accepted screenshot → background / warns；
core 导师备注 → 可影响题目约束，但不支撑文献事实；
```

---

## 15. ReportQuality 联动

Session 15 后，ReportQuality 应新增或加强检查：

```text
1. PDF / 图片 / note 类证据是否过度支撑关键结论；
2. OCR / parse_confidence 低的资料是否进入 supports；
3. 开题报告引用的 PDF 是否有页码 / 片段；
4. 导师备注是否只作为约束，不作为论文事实；
5. 用户上传资料是否补齐缺失 dataset / baseline / related work。
```

建议新增维度内规则：

```text
若关键维度只由 note/screenshot 支撑 → 降级；
若 paper PDF 无标题 / DOI / URL 且未人工确认 → 降级；
若所有新材料都 pending → 不提升评分；
```

---

## 16. FinalPackage 联动

FinalPackage citation 表建议显示：

```text
来源类型；
页码 / 片段；
解析置信度；
Skill；
验证状态；
```

示例：

```markdown
| 编号 | 类型 | 标题 | 来源 | 页码/片段 | 验证 | 解析置信度 | Skill |
|---|---|---|---|---|---|---:|---|
| E1 | paper | ... | PDF 上传 | p1-p2 | partial | 0.78 | paper-card |
| N1 | note | 导师建议 | 手动备注 | - | skipped | 1.00 | evidence-ledger |
```

注意：

```text
开题报告不应大段引用 PDF 原文；
只保留短片段、页码和结构化摘要。
```

---

## 17. 前端设计

### 17.1 新增面板

```text
资料卡片化
├── Tab: PDF
├── Tab: 图片 / 截图
├── Tab: 网页文字
├── Tab: URL + 描述
└── Tab: 导师备注
```

### 17.2 草稿卡片列表

每张草稿显示：

```text
类型；
标题；
摘要；
来源；
页码 / 片段；
解析置信度；
warnings；
编辑按钮；
导入工作台按钮；
拒绝按钮；
```

### 17.3 用户操作

必须支持：

```text
编辑标题；
编辑摘要；
修改 suggested_type；
选择 workspace_lane；
导入后立即验证；
拒绝草稿；
查看来源片段；
```

---

## 18. API 设计

### 18.1 上传资料

```text
POST /api/v1/one-topic/{project_id}/materials/upload
```

`multipart/form-data`：

```text
file；
source_type；
user_note；
page_range；
```

响应：

```json
{
  "material_id": "mat_...",
  "parse_status": "parsed",
  "draft_cards": []
}
```

### 18.2 提交文本资料

```text
POST /api/v1/one-topic/{project_id}/materials/text
```

请求：

```json
{
  "source_type": "web_text",
  "title": "某网页资料",
  "text": "...",
  "url": "https://example.com",
  "user_note": "导师建议关注的数据集"
}
```

### 18.3 从资料生成草稿卡片

```text
POST /api/v1/one-topic/{project_id}/materials/{material_id}/cards
```

请求：

```json
{
  "max_cards": 3,
  "preferred_type": "paper"
}
```

### 18.4 编辑草稿卡片

```text
PATCH /api/v1/one-topic/{project_id}/materials/cards/{draft_card_id}
```

### 18.5 导入草稿卡片

```text
POST /api/v1/one-topic/{project_id}/materials/cards/import
```

请求：

```json
{
  "draft_card_ids": ["draft_001"],
  "workspace_lane": "user_preferred",
  "auto_verify": true
}
```

---

## 19. 测试要求

### 19.1 后端测试

新增：

```text
apps/api/tests/test_session15_material_card_intake.py
```

至少覆盖：

```text
1. 上传 PDF 后生成 MaterialItem；
2. 文本层 PDF 可提取标题 / 摘要候选；
3. 扫描版或无文本 PDF 降级为 skipped / failed；
4. 图片上传不会触发批量扫描；
5. 图片 + 用户说明生成 note draft；
6. 网页文字生成 draft card；
7. URL + 描述复用 URLVerified；
8. 导师备注生成 manual note draft；
9. draft card 可编辑；
10. draft card 导入后写入 Evidence Ledger；
11. 导入后 review_status=pending；
12. 导入后 workspace_lane 正确；
13. 导入后 created_by_skill 正确；
14. PDF DOI / arXiv 提取后可 auto_verify；
15. 截图 / note 默认不进入 supports；
16. pending material evidence 不提升 ReportQuality；
17. FinalPackage citation 显示 material source / page refs；
18. Trace 写入 material_uploaded / parsed / draft_card_imported；
19. 文件大小 / MIME 类型限制有效；
20. 非法文件名被 sanitize。
```

测试要求：

```text
PDF 使用小型 fixture；
图片使用小型 PNG fixture；
OCR 若未实现，不应导致测试失败；
不依赖真实外部网络。
```

### 19.2 Playwright 测试

新增：

```text
apps/web/e2e/test_one_topic_session15_material_cards.py
```

至少覆盖：

```text
1. 资料卡片化面板可见；
2. 用户能上传 PDF；
3. PDF 上传后出现草稿卡片；
4. 用户能编辑草稿标题 / 摘要；
5. 用户能导入草稿到工作台；
6. 导入后卡片出现在 user_preferred 或 system_found；
7. 图片 + 说明能生成 note 草稿；
8. 网页文字能生成 draft；
9. 截图 / note 卡片显示 pending / skipped；
10. Trace 面板能看到 material 相关事件。
```

### 19.3 回归测试

必须跑：

```text
apps/api/tests/test_session10_verification.py
apps/api/tests/test_session11_trace_persistence.py
apps/api/tests/test_session12_report_quality.py
apps/api/tests/test_session13_skill_registry.py
apps/api/tests/test_session14_multi_source_retrieval.py
apps/web/e2e/test_one_topic_session10_verification.py
apps/web/e2e/test_one_topic_session11_trace_persistence.py
apps/web/e2e/test_one_topic_session12_report_quality.py
apps/web/e2e/test_one_topic_session13_skill_registry.py
apps/web/e2e/test_one_topic_session14_retrieval.py
```

---

## 20. 验收标准

通过条件：

```text
1. PDF / 图片 / 网页文字 / URL+描述 / 导师备注至少 4 类入口可用；
2. 资料能生成 DraftEvidenceCard；
3. 草稿卡片可编辑、可拒绝、可导入；
4. 导入后进入 Evidence Ledger；
5. 导入后默认 pending，不直接 supports；
6. PDF 提取 DOI / arXiv / URL 后可触发 URLVerified；
7. 图片 / 截图 / manual note 默认不支撑关键事实；
8. Trace 能记录资料上传、解析、草稿生成、导入；
9. Skill 来源能写入；
10. FinalPackage 能显示 material source / page refs；
11. ReportQuality 能识别低置信解析资料不应提升评分；
12. 后端新增测试通过；
13. Playwright 新增测试通过；
14. Session 10-14 回归通过。
```

最低可接受 MVP：

```text
PDF 文本提取；
网页文字 / 导师备注；
图片 + 用户说明；
DraftEvidenceCard；
导入 Evidence Ledger；
Trace；
Playwright 主路径。
```

可延期项：

```text
OCR；
复杂 PDF 版面；
多 PDF 批处理；
PDF 参考文献自动抽取；
全文 chunk 检索；
```

---

## 21. 完工报告要求

完成后新增：

```text
Plan/reports/Session_15_Material_Card_Intake_验收报告.md
```

报告必须包含：

```text
1. 本阶段范围；
2. 支持的资料类型；
3. 新增模型；
4. 文件存储规则；
5. PDF 解析策略；
6. 图片 / 截图处理策略；
7. 网页文字 / URL + 描述处理策略；
8. DraftEvidenceCard 到 Evidence Ledger 的映射；
9. Verification 联动；
10. Trace 联动；
11. Skill Registry 联动；
12. FinalPackage 联动；
13. ReportQuality 联动；
14. 后端测试结果；
15. Playwright 测试结果；
16. 未做项；
17. 下一 Session 建议。
```

报告中必须明确写：

```text
是否实现 OCR；
PDF 是否只解析文本层；
是否有文件大小限制；
是否做了批量图片 / 视频处理；
低置信解析结果是否能进入 supports。
```

---

## 22. 下一 Session 预告

Session 16 建议：

```text
作品化、稳定化与 Demo 包装
```

理由：

```text
Session 09-15 已形成证据工作台主闭环：
工作台 → 导入 → 检索 → 验证 → Trace → 报告 → 质量审核 → 资料卡片化。
```

Session 16 应优先：

```text
README；
Demo 样例；
测试矩阵；
错误提示；
开发文档；
部署说明；
项目边界声明；
简历项目描述。
```

不建议继续无限扩功能。Session 16 开始应把项目收束成可展示、可验收、可复盘的作品。

