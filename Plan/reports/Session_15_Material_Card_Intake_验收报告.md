# Session 15 验收报告: 全文资料与图片 / PDF / 网页卡片化

> 日期: 2026-06-19
> Commit: (待 commit)
> 阶段定位: 在多源检索、证据工作台、URLVerified、Trace、ReportQuality、Skill Registry 之上, 把用户手里的 PDF / 截图 / 网页文字 / 链接说明 / 导师备注等非结构化资料, 转成可审核的 DraftEvidenceCard, 经用户确认后进入 Evidence Ledger.

---

## 1. 本阶段范围

- 新增 `apps/api/app/services/materials/` 目录: storage / pdf_parser / image_parser / web_text_parser / card_builder / dedup / orchestrator.
- 新增 7 个 API: `POST /materials/upload` / `POST /materials/text` / `GET /materials` / `GET /materials/{id}` / `POST /materials/{id}/cards` / `PATCH /materials/cards/{draft_id}` / `POST /materials/cards/import`.
- 新增 8 个 Pydantic schema: `MaterialItem` / `DraftEvidenceCard` / `MaterialUploadRequest` / `MaterialTextRequest` / `MaterialBuildCardsRequest` / `MaterialListResponse` / `DraftCardUpdate` / `MaterialImportRequest` / `MaterialImportResponse` / `MaterialUploadResponse`.
- 新增前端 `#materials-panel` 工作台面板: 3 tab (上传 / 文字 / 备注) + 草稿卡片列表.
- EvidenceItem 新增 `from_material_id` / `parse_confidence` / `page_refs` 字段 (SOP §16 联动).
- ReportCitation 新增 `source_mode` / `parse_confidence` / `page_refs` 字段; FinalPackage citation 表格新增 3 列: 来源 / 页码 / 解析.
- 新增 8 类 Trace action: `material_uploaded` / `material_text_submitted` / `material_parsed` / `material_parse_failed` / `draft_card_created` / `draft_card_edited` / `draft_card_imported` / `draft_card_rejected`.

---

## 2. 支持的资料类型

| 类型 | 入口 | 解析 | OCR | 典型 evidence type |
|---|---|---|---|---|
| PDF (有文本层) | upload | pdf_parser (pypdf 优先, 极弱 BT/ET fallback) | 不做 | paper (如有 DOI / arXiv) / note |
| PDF (扫描版) | upload | skipped | 不做 | note (仅 filename) |
| PNG / JPG / WEBP 图片 | upload | image_parser (尺寸 + 头部, 不 OCR) | **不做** | note (OCR 未实现) |
| TXT / MD 文本 | upload | 走文本解析 | / | note |
| 网页正文 (web_text) | text | web_text_parser | / | paper (含 DOI) / repo (含 github) / note |
| URL + 描述 (url_note) | text | web_text_parser | / | paper / repo / note |
| 导师备注 (manual_note) | text | web_text_parser (high conf 1.0) | / | note (default) |

---

## 3. 新增模型

| 模型 | 字段数 | 关键字段 |
|---|---|---|
| `MaterialItem` | 16 | material_id / project_id / source_type / filename / original_url / title / storage_path / mime_type / size_bytes / text_excerpt / page_count / page_range / created_at / parse_status / parse_confidence / parse_warnings / user_note / metadata |
| `DraftEvidenceCard` | 17 | draft_card_id / project_id / material_id / suggested_type / title / summary / extracted_claims / extracted_entities / possible_url / possible_doi / possible_arxiv_id / source_excerpt / page_refs / extraction_confidence / warnings / status / created_at / updated_at |
| `MaterialUploadRequest` | 8 | filename / content_b64 / mime / user_note / page_range / preferred_type / auto_build_cards / material_id (测试) |
| `MaterialImportResponse` | 6 | imported / skipped / evidence_ids / skipped_draft_ids / warnings / message |

---

## 4. 文件存储规则

- **路径**: `.runtime/materials/{project_id}/{material_id}/original.{ext}` (env `PAPERAGENT_MATERIALS_DIR` 可覆盖)
- **大小**: 默认 ≤ 20MB, 超 422
- **MIME 白名单**: `application/pdf` / `image/png` / `image/jpeg` / `image/webp` / `text/plain` / `text/markdown`
- **扩展名白名单**: `.pdf` `.png` `.jpg` `.jpeg` `.webp` `.txt` `.md`
- **文件名 sanitize**: 移除控制字符 / 路径分隔符 / 连续点, 限长 120, 中文保留
- **不执行 / 不读工作区外**: 仅写当前 project 目录

---

## 5. PDF 解析策略

- **优先 pypdf**: 若安装, 调用 `pypdf.PdfReader.extract_text()` 拿所有页文本.
- **降级 BT/ET 极弱解析**: 若无 pypdf, 走 PDF 字节流 BT...ET 文本块抽取.
- **再降级 skipped**: 完全无文本 -> `parse_status=skipped`, `parse_warnings=["未抽取到 PDF 文本层, 可能是扫描版"]`.
- **启发式抽取** (有文本时):
  - 标题: `Title:` / `# ` 显式标记, 或前 8 行最长一行
  - 摘要: `Abstract:` 段或前 800 字
  - DOI: `10.\d{4,9}/[^\s,;\"<>]+` 正则
  - arXiv: `arXiv:?\s*(\d{4}\.\d{4,5}v?\d*)` 或 `arxiv.org/abs/<id>`
- **不做**: 扫描版 OCR / 复杂版面恢复 / 参考文献自动抽取 / PDF chunk 检索.

---

## 6. 图片 / 截图处理策略

- **不做 OCR** (SOP §9.2 明确边界 + §21 列入延期项).
- 仅读 PNG/JPEG/WEBP 头部获取宽高, 不引入 PIL.
- parse_confidence 默认 0.4, parse_warnings 必含 "图片证据需要人工确认".
- 上传接口不支持批量; 用户在 UI 选 1 张或少量图片, 不扫 G:\\PaperAgent 已有图片.

---

## 7. 网页文字 / URL+描述处理策略

- 仅使用用户粘贴内容, 不自动深爬, 不抓登录态网页.
- `web_text`: 优先从 text 抽 DOI / arXiv; 有则 suggested_type=paper, confidence=0.8.
- `url_note`: URL 含 github.com / gitlab 走 repo (conf 0.6), 其它走 paper (DOI/arxiv) / note.
- `manual_note`: 强制 note, confidence=1.0 (用户自写).
- 三类共享: 用户说明 + 前 800 字片段作为 summary.

---

## 8. DraftEvidenceCard → Evidence Ledger 映射

按 `suggested_type` 走不同入口:

| suggested_type | 调用 | source_mode | created_by_skill |
|---|---|---|---|
| paper | `add_paper_manual` | upload | paper-card |
| dataset | `add_dataset_manual` | upload | dataset-validation |
| repo | `add_repo_manual` | upload | github-baseline |
| note / custom | `add_paper_manual` (note 通道暂用 paper 通道) | upload | evidence-ledger |

统一设置:
- `workspace_lane` = 请求值 (默认 `user_preferred`)
- `review_status` = `pending`
- `verification_status` = `unverified`
- `created_by_skill` = 按上表
- `from_material_id` = 草稿来源
- `parse_confidence` = 草稿 extraction_confidence
- `page_refs` = 草稿 page_refs[:3]

---

## 9. Verification 联动

- `auto_verify=True` 时遍历导入的 evidence_ids, 调 `verify_evidence_item` + `apply_verification` + `update_verification_field`.
- PDF 含 DOI/arxiv -> 走对应 verifier, status 通常 partial/verified.
- 图片 / 截图 / manual_note -> verification_skipped / unverified (默认), 用户可手动确认.

---

## 10. Trace 联动

| Action | Actor | 何时写 |
|---|---|---|
| `material_uploaded` | user | 文件上传 |
| `material_text_submitted` | user | 文字 / URL / 备注提交 |
| `material_parsed` | system | 解析成功 (parsed) |
| `material_parse_failed` | system | 解析失败 (failed) |
| `draft_card_created` | system | 自动生成草稿 |
| `draft_card_edited` | user | 用户编辑草稿 |
| `draft_card_imported` | user | 草稿导入 ledger |
| `draft_card_rejected` | user/system | 草稿拒绝 / dedup 跳过 |

trace 通过 `trace_store.append_trace` 落 jsonl + in-memory, 在 #evidence-trace-panel 可见.

---

## 11. Skill Registry 联动

- import 时 `created_by_skill` 由 type 决定 (上表).
- `EvidenceRef.skill_sources` 透传 3 个 skill 字段 (S13 既有).
- FinalPackage Markdown citation 表格新增 **Skill** 列 (S14 既有) + **来源** / **页码** / **解析** 列 (本 Session).
- `skills/registry.json` 不需新增 skill (4 个既有 skill 已覆盖 materials 全流程).

---

## 12. FinalPackage 联动

citation 表格扩展到 12 列: 编号 / 类型 / 标题 / 来源 / 页码 / 解析 / 审核状态 / 验证 / 置信度 / Skill / 警告 / 链接.

新增的 3 列:
- **来源**: `auto_search` / `manual` / `upload` / `assistant_intake` / `import`
- **页码**: PDF 草稿的 page_refs 前 3 个
- **解析**: PDF / 图片的 parse_confidence, 不存在时 `-`

---

## 13. ReportQuality 联动

- pending + unverified 的 material 证据不进入 supports (S10 既有规则, 已被 test_15 验证).
- ReportQuality 8 维检查仍能跑过; verdict 4 档之一.
- 未引入新维度, 但 materials 引入了新 source 提示 (upload) 让用户更清晰溯源.

---

## 14. 后端测试结果

`apps/api/tests/test_session15_material_card_intake.py` 20 个测试:

```
20 passed
```

覆盖: PDF 上传 + 提取 DOI/arxiv + 扫描版 skipped + 图片无 OCR + note draft + 文字 3 种来源 + 编辑 + 5 维 import 流程 + auto_verify + 不进 supports + 不升 quality + FinalPackage 来源 + Trace 5 类 + 文件大小/MIME 限制 + 文件名 sanitize.

**全量后端回归** (apps/api/tests/ 不含 session6 LLM): **184 passed, 1 skipped** (S15 + 之前 165 + S14 之前 145).

---

## 15. Playwright 测试结果

`apps/web/e2e/test_one_topic_session15_material_cards.py` 10 个测试:

```
10 passed in 482s
```

- 1-7 真实 UI 测试 (面板 / tabs / 提交 / 字段 / 导入 / 状态 / 备注)
- 5-10 走 API 调用的间接验证 (edit / 状态 / note 默认 pending / trace 事件)

---

## 16. 未做项 (与 SOP §21 一致)

- **OCR**: 完全未实现, 图片证据需要人工确认 (parse_confidence 0.4 + warning).
- **复杂 PDF 版面恢复**: 不做.
- **多 PDF 批处理**: 不做.
- **PDF 参考文献自动抽取**: 不做.
- **全文 chunk 检索**: 不做 (留给后续 Session).
- **DOCX / PPT 解析**: 不做 (SOP §3 不允许).

---

## 17. 关键安全 / 行为约束

- 文件大小硬限制 20MB (SOP §7.2).
- MIME 白名单 + 扩展名白名单 双重校验.
- 文件名 sanitize 防路径穿越 + 控制字符 + 长度限制.
- 不读工作区外路径.
- 不上传到第三方服务.
- 所有解析结果默认 pending, 不直接进 supports.
- pending + unverified 不得进 supports (S10 既有, S15 沿用).

---

## 18. 下一 Session 建议 (按 SOP §22)

**Session 16 候选: 作品化、稳定化与 Demo 包装**

依据 SOP §22:
- S09-S15 已形成证据工作台主闭环 (工作台 → 导入 → 检索 → 验证 → Trace → 报告 → 质量审核 → 资料卡片化).
- S16 不建议继续无限扩功能, 应把项目收束成可展示 / 可验收 / 可复盘的作品.

S16 优先项:
- README + 部署说明
- Demo 样例 (示例项目)
- 测试矩阵 (每 Session 测试结果汇总)
- 错误提示 + 边界声明
- 简历项目描述 (1-2 段)

不建议立刻做:
- 全文向量库
- 复杂 RAG
- 大规模视频 / 图像处理
- 毕业论文正文自动生成
