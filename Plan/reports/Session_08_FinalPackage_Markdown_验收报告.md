# Session 08 验收报告: EvidenceRef-Based Opening Report Markdown Export

> 验收时间: 2026-06-18
> 阶段: Session 8 (按 `Plan/PaperAgent_Session08_EvidenceRef_开题报告Markdown导出SOP.md`)
> Commit: <待 commit>

---

## 1. 本阶段范围

按 SOP §1-§2, Session 08 不扩张 Agent 能力, 只做一件事:

> 把 Session 07 已挂接好的 EvidenceRef 转化为可导出的开题报告 Markdown 初稿, 支持前端预览与下载.

本阶段交付:
- 13 章节开题报告初稿
- 证据引用清单 (Markdown 表格)
- 待补证据与修改清单
- coverage < 0.70 警告
- rejected / needs_check 规则
- 前端预览 + 下载按钮

不做 (SOP §3 黑名单):
- DOCX 导出
- 完整毕业论文正文
- PDF 全文 RAG
- 多 Agent 委员会
- Skill Marketplace
- 双栏工作台完整实现 (本阶段预留字段空间, 见 §11)
- Agent Card Intake 完整实现 (本阶段预留字段空间, 见 §12)

---

## 2. 新增 / 修改的数据结构

### 2.1 Pydantic 模型 (`apps/api/app/schemas.py`)

| 模型 | 字段 | 用途 |
|---|---|---|
| `FinalPackageBuildOptions` | include_low_confidence_refs / include_rejected_as_appendix / style / language | POST /build 请求体 |
| `ReportSection` | key / title / content / evidence_refs / unsupported_claims | 13 章节数据结构 |
| `ReportCitation` | ref_no / evidence_id / evidence_type / title / url / review_status / role / score / used_in_sections | 引用清单条目 |
| `FinalPackageSummary` | 不含 markdown 全文 | GET / 摘要 |
| `FinalPackage` | 完整 (含 sections + citation_list + markdown) | POST /build 完整响应 |

### 2.2 FinalPackage 缓存 (`apps/api/app/services/evidence.py`)

- `_ProjectEvidence.latest_final_package: Any | None` 字段
- `save_final_package(project_id, pkg)` / `get_final_package(project_id)` helper

### 2.3 final_package 服务 (`apps/api/app/services/final_package.py`, ~400 行)

- `build_citation_map()` — 稳定编号 (E1, E2, D1, R1)
- `_build_sections()` — 13 章节内容拼装
- `_render_markdown()` — Markdown 渲染 (含 warning + 引用表)
- `build_final_package()` — 顶层 API, 自动缓存
- `build_final_package_summary()` — GET 摘要

---

## 3. 新增 API (`apps/api/app/api/v1/one_topic.py`)

| 方法 | 路径 | 用途 | SOP |
|---|---|---|---|
| POST | `/{project_id}/final-package/build` | 构建 FinalPackage (含 Markdown + sections + citations) | §5.1 |
| GET | `/{project_id}/final-package` | 返回摘要 (无 markdown 全文) | §5.3 |
| GET | `/{project_id}/final-package/markdown` | 下载 Markdown (Content-Type: text/markdown; charset=utf-8 + attachment) | §5.2 |

Pydantic 模型 (3 个): `FinalPackage`, `FinalPackageBuildOptions`, `FinalPackageSummary`.

---

## 4. Markdown 章节结构 (SOP §4.2)

13 个二级标题:

1. 一、研究背景与意义
2. 二、国内外研究现状
3. 三、研究问题与目标
4. 四、研究内容与技术路线
5. 五、数据集、Baseline 与评价指标
6. 六、工作包设计
7. 七、预期创新点
8. 八、可行性分析
9. 九、风险预案
10. 十、进度计划
11. 十一、开题答辩可能追问
12. 十二、证据引用清单
13. 十三、待补证据与修改清单

顶部 metadata:
```
> 生成时间: ...
> 证据覆盖率: ...
> 状态: 可提交草稿 / 需补证据
```

低 coverage 时额外加:
```
> ⚠️ 警告: 当前证据覆盖率不足 0.70. 本文档可作为讨论草稿, 但不建议直接用于正式开题提交.
```

---

## 5. EvidenceRef 引用规则 (SOP §4.3 + §4.5)

### 5.1 编号规则 (§6.3)

| 前缀 | 类型 | 数量上限 |
|---|---|---|
| E | paper / literature | 6+ |
| D | dataset | 3+ |
| R | repo / baseline | 3+ |
| N | note / user note | 后续扩展 |

- 同一 evidence_id 在全文编号稳定
- 排序: paper 优先 core/accepted → score; dataset/repo 同

### 5.2 过滤规则 (§4.5)

| review_status | 默认处理 |
|---|---|
| core / accepted / background | ✅ supports 引用 |
| needs_check | ❌ 不进 supports; 进 risk / todo (除非 include_low_confidence_refs=true) |
| rejected | ❌ 不进 supports; 可选 appendix (include_rejected_as_appendix=true) |

### 5.3 用户移除

用户通过 PATCH `/refs/review` 的 `mark_ref_wrong` / `remove_ref` 写 Trace; 下次 build 时通过 snapshot 重新挂载, 受相同过滤规则约束.

---

## 6. rejected / needs_check 处理规则 (§4.5)

✅ 已实现:
- `build_citation_map()` 过滤 rejected (默认) 和 needs_check (默认)
- `_build_sections()` 第九节风险预案收集 needs_check refs
- 第十三节待补证据收集 `missing_ref_reasons` + `wp.open_questions`
- 后端测试 test_05 / test_06 验证

---

## 7. 前端预览与下载变化

### 7.1 报告区 (`apps/web/index.html`)

新增 `<article id="block-report">` 在 #block-recommendation 后, 含:
- `#report-summary` chip 栏: ready / coverage / chars / sections / citations / warning
- `#btn-build-report` 生成按钮
- `#btn-rebuild-report` 重新生成 (build 后显示)
- `#btn-download-report` 下载 Markdown (build 后显示)
- `#btn-preview-report` 切换预览
- `<pre id="report-preview">` 预览容器

### 7.2 JS 逻辑 (`apps/web/app.js`)

- `renderReportBlock(projectId)` — 占位
- `buildReport()` — POST /final-package/build + 填充 summary + 显示 preview
- `refreshReportSummary()` — GET /final-package 自动加载已有缓存
- `renderReportSummary(pkg)` — 填 chip 数字
- `showReportPreview(md)` / `toggleReportPreview()` — 预览控制
- `downloadReport()` — `window.open(/markdown)` 触发浏览器下载
- `renderResult` 末尾自动 `refreshReportSummary()` 加载已有 FinalPackage

### 7.3 CSS (`apps/web/styles.css`)

新增 `.report__summary / .report__chip / .report__actions / .report__preview` 等样式.

---

## 8. 后端测试结果

新增 `apps/api/tests/test_session8_final_package.py` (13 tests, 全部通过):

```
test_01_build_from_snapshot                       PASSED
test_02_markdown_has_13_sections                  PASSED
test_03_markdown_has_citation_refs                PASSED
test_04_citation_numbering_stable                 PASSED
test_05_rejected_excluded_from_positive           PASSED
test_06_needs_check_only_in_risk                  PASSED
test_07_low_coverage_warning                      PASSED
test_08_unsupported_in_checklist                  PASSED
test_09_markdown_endpoint_content_type            PASSED
test_10_build_preserves_review_status             PASSED
test_11_user_remove_ref_excluded                  PASSED
test_12_no_snapshot_returns_409                   PASSED
test_13_summary_endpoint                          PASSED

13 passed in 0.33s
```

回归: `apps/api/tests/` 共 **85 passed** (72 Session 7 + 13 Session 8).

---

## 9. Playwright 测试结果

新增 `apps/web/e2e/test_one_topic_session8_final_package.py` (8 tests, 全部通过):

```
test_01_report_section_visible               PASSED
test_02_build_shows_chars                    PASSED
test_03_preview_contains_proposal_header     PASSED
test_04_preview_has_citation_refs            PASSED
test_05_preview_has_citation_list            PASSED
test_06_download_button_visible              PASSED
test_07_download_endpoint_returns_markdown   PASSED
test_08_rejected_not_in_positive_citations   PASSED

8 passed in 248.47s (4:08)
```

测试覆盖 (SOP §10.2):
1. 页面出现 "开题报告导出" 区域
2. 点击 "生成报告" 后显示 Markdown 字符数 (chars / sections / citations chip)
3. Markdown 预览包含 "开题报告" + "研究背景"
4. Markdown 预览包含 [E1]/[D1]/[R1] 引用编号
5. Markdown 预览包含证据引用清单表格
6. 下载按钮可见
7. /markdown 端点返回 text/markdown + attachment
8. rejected evidence 不进入 citation_list

实现细节:
- 测试 02-05 改用 `wait_for_selector(state="visible")` 替代固定 `wait_for_timeout`, 避免 race condition
- 添加 `sys.path.insert(0, str(ROOT / "apps" / "api"))` 让 pytest 能 import app.services
- `api_client` fixture 用 `ev_store.reset_all()` 保证 test 隔离

---

## 10. 真实 uvicorn smoke

启动 uvicorn 18182, 跑 YOLO 钢材:

- POST /final-package/build → 200, chars=3063, sections=13, citations=10, coverage=1.0
- GET /final-package → 200, summary OK
- GET /final-package/markdown → 200, Content-Type: text/markdown; charset=utf-8, filename=proposal_ot_xxx.md

Markdown 头部示例:
```
# 开题报告: 基于 YOLO 的 钢材 表面缺陷 研究
> 生成时间: 2026-06-18T...
> 证据覆盖率: 1.00
> 状态: 可提交草稿
```

正文示例:
```
## 一、研究背景与意义
研究方向: 基于 YOLO 的 钢材 表面缺陷 研究
支撑证据: [E3][E2][E1][D1][R1]
```

引用清单示例:
```
| 编号 | 类型 | 标题 | 状态 | 分数 | 链接 |
| E1 | paper | YOLOv8 Steel Defect Detection | accepted | 0.85 | https://arxiv.org/abs/... |
```

---

## 11. 双栏证据工作台灵感的预留情况 (SOP §8)

**未实现 UI**, 但预留逻辑入口:
- `EvidenceItem.review_status` 已是 `core / accepted / background / pending / needs_check / rejected`
- Markdown 渲染时: core 优先进入 "研究现状" / "可行性分析" / "工作包设计"
- 后续 Session 09 可加 `workspace_lane` 字段 (SOP §8.3) 而不破坏现有数据

---

## 12. Agent 助手卡片化灵感的预留情况 (SOP §9)

**未实现**, 但预留:
- `EvidenceItem.source_mode` 已支持 `auto_search / manual / upload / import`, 可后续扩展 `assistant_intake`
- Markdown 引用清单显示 `review_status` (如 `core` 来源可标 "用户已确认"), 但当前未区分 assistant intake
- 后续 Session 09 可加 `extraction_confidence / extraction_warnings / raw_input_*` 字段

---

## 13. 下一 Session 建议

按 SOP §13: **Session 09 — 证据工作台双栏化 + Agent Card Intake 入口**

P0:
- 双栏工作台最小 UI (左侧用户, 右侧系统)
- `workspace_lane: Literal["user_preferred", "system_found", "selected", "rejected"]` 字段
- 拖拽或按钮加入核心证据

P1:
- URL → EvidenceCard (POST /cards/intake)
- GitHub repo → RepoCard
- 数据集网页 → DatasetCard

P2:
- 图片 / 截图 → EvidenceCard
- PDF 片段 → PaperCard

仍围绕"证据工作台", 不跳到完整论文写作.

---

## 14. 一句话总结

Session 08 把 Session 07 复核过的 EvidenceRef 转成 13 章节 Markdown 开题报告初稿, 引用 [E1]/[D1]/[R1] 编号 + 末尾证据清单, 前端可预览可下载. coverage < 0.70 自动加 warning, rejected/needs_check 不进 supports.