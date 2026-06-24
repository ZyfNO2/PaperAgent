# Session 49 验收报告：已有小论文扩展 (Track B 闭环)

> Session 49 — 把 Session 45 的两档画像 (保毕业 / 已有小论文) 中"已有小论文"路径做成真正闭环.
> 对应 SOP: `Plan/PaperAgent_Session49_已有小论文扩展_TrackB_SOP.md` + 设计文档 B §9-§12 + 文档 C §15、§16.

## 1. 目标达成

| 项 | 状态 |
|---|---|
| `SmallPaperCard` schema 落地 | OK |
| 小论文贡献抽取 (LLM + heuristic fallback) | OK |
| 小论文 → 大论文章节映射 (5 章 + unmapped) | OK |
| 缺口分析 (intro only → 4 missing) | OK |
| 扩展实验建议 (含 fills_chapter / 优先级) | OK |
| 重复风险检测 (4 类 category) | OK |
| `paper_extension` 报告模板 8 节 | OK |
| 3 端点 (extract / extension-plan / repeat-risks) | OK |
| 前端 Track B 入口 (goal_level 切换 + 按钮) | OK |
| pytest 全绿 + 31 新增 | OK |

## 2. 数据模型 (`apps/api/app/schemas_small_paper.py`)

| Schema | 关键字段 | 备注 |
|---|---|---|
| `SmallPaperCard` | paper_id, project_id, title, contribution_points, method_modules, datasets, baselines, metrics, experiment_tables, limitations, reusable_chapter_sections, missing_for_thesis, evidence_refs, extraction_confidence, extraction_mode | extraction_mode ∈ {llm, heuristic} |
| `ChapterMapping` | small_paper_section, thesis_chapter, reuse_type, note | thesis_chapter 7 选 1; reuse_type 4 选 1 |
| `ExtensionExperiment` | experiment_id, title, description, datasets, baselines, estimated_effort, priority, fills_chapter | priority 1-5; fills_chapter 标补哪章 |
| `WorkPackageSuggestion` | wp_id, title, goal, deliverable, estimated_effort, dependencies | 第二/第三工作包 |
| `ExtensionPlan` | paper_id, project_id, covered_chapters, missing_chapters, gap_analysis, extension_experiments, second_work_package, third_work_package, reuse_risks, thesis_outline | 完整扩展规划 |
| `RepeatRiskWarning` | category, severity, note, related_section | category 4 选 1; severity 3 选 1 |

请求 / 响应模型: `SmallPaperExtractRequest/Response`, `SmallPaperExtensionPlanRequest/Response`, `SmallPaperRepeatRisksRequest/Response`.

## 3. 服务模块 (`apps/api/app/services/small_paper/`)

| 文件 | 职责 |
|---|---|
| `__init__.py` | 导出 `extract_small_paper_card`, `build_extension_plan`, `detect_repeat_risks` |
| `contribution_extractor.py` | LLM (chat_json) + heuristic (regex + 复用 `_METHOD_HINTS` / `_PUBLIC_DATASET_OBJECTS` / 新增英文公开数据集匹配) 双路径抽取 |
| `chapter_mapper.py` | section_title 关键词 + chunk_type 映射到 7 个 thesis_chapter; reference / unknown 跳过 |
| `gap_analyzer.py` | `STANDARD_CHAPTERS` 5 章标准 → `compute_missing_chapters` / `build_gap_analysis` / `suggest_thesis_outline` |
| `extension_planner.py` | 缺口 → `_GAP_TO_EXPERIMENTS` 表 → 1-5 条 `ExtensionExperiment` + WP2/WP3 |
| `repeat_risk.py` | 4 类风险: `verbatim_copy` / `incremental_only` / `no_extension` / `method_reuse_only` |

## 4. 抽取 LLM + heuristic 双路径

| 路径 | 触发 | 置信度 |
|---|---|---|
| LLM (auto 优先) | `MINIMAX_API_KEY` 存在 + chat_json 成功 | 0.8 |
| heuristic (auto fallback) | LLM 抛 `LLMUnavailable` / JSON 解析失败 | 0.4 |
| heuristic 强制 | `prefer="heuristic"` | 0.4 |
| llm 强制 | `prefer="llm"`; 失败 → 抛 503 | 0.8 |

heuristic 抽取规则:
- `contribution_points`: abstract / introduction 里 `we propose / we present / 本文提出` 等触发词所在句
- `method_modules`: 复用 `_METHOD_HINTS` (YOLO / Transformer / 数字孪生 / PINN ...)
- `datasets`: 复用 `_PUBLIC_DATASET_OBJECTS` (中文键) + 英文公开数据集 (NEU-DET / DeepPCB / CODEBRIM ...)
- `baselines`: "vs / compared with / baseline / state-of-the-art" 后大写词
- `metrics`: mAP / Recall / F1 / BLEU / PSNR 等关键词
- `experiment_tables`: "Table N" 标题截取
- `limitations`: conclusion / experiment 里 `limitation / future work / 局限性` 等

## 5. 章节映射表

| 小论文内容 | 大论文章节 | reuse_type | 备注 |
|---|---|---|---|
| 标题 / 摘要 / 引言 | ch1_intro | summarize | 扩成大论文研究背景 |
| 相关工作 | ch2_related | extend | 需扩展为系统综述 |
| 方法主体 / 消融 | ch3_method | direct_reuse | 大论文核心方法章基础 |
| 实验 / 实验结果 | ch4_experiment | direct_reuse | 需扩展数据集 / baseline |
| 局限性 / 结论 | ch5_conclusion | extend | 失败案例 / 边界研究 |
| 参考文献 | unmapped | cannot_reuse | 不进大论文 |
| 未识别 | unmapped | cannot_reuse | 需人工处理 |

## 6. 缺口分析 — 关键场景

| 小论文覆盖 | 缺失章节 | 缺口提示 |
|---|---|---|
| intro only | ch2/ch3/ch4/ch5 (4) | "当前小论文可支撑第 3 章, 但第 4 章工作量不足, 建议: 跨数据集泛化 / 工程系统集成 / 数据集扩展 / 轻量化部署 / 失败案例" |
| intro + method | ch2/ch4/ch5 (3) | "缺少第 2 章相关工作综述" 等 |
| intro + method + experiment | ch2/ch5 (2) | 提示补相关工作 + 结论 |
| 5 章齐全 | 0 | "5 章齐全, 仍需补实验规模 / 工作量 / 工业落地" |

## 7. 扩展实验建议表

| 缺口 | 扩展实验 (fills_chapter) |
|---|---|
| ch4 不足 | 跨数据集泛化 (ch4), 工程系统集成 (ch4/appendix), 轻量化部署 (ch4) |
| ch2 不足 | 数据集扩展与对比分析 (ch2) |
| ch5 不足 | 失败案例与边界研究 (ch5) |
| ch3 不足 | 消融实验 (ch3/ch4) |
| ch1 不足 | 研究背景扩展 (ch1) |

兜底: 5 章齐全时仍给 1 条消融实验, 避免"无扩展"的扩展报告.

## 8. 重复风险检测规则

| category | 触发条件 | severity |
|---|---|---|
| `method_reuse_only` | direct_reuse 占比 > 60% 且无 extension_experiments | high |
| `method_reuse_only` | experiment_tables 全 direct_reuse 且无扩展 | medium |
| `incremental_only` | 贡献点 < 2 + baselines < 2 | medium |
| `no_extension` | 5 章齐全 + 无 extension_experiments | medium |
| `verbatim_copy` | 标题含 "survey / overview / 综述" | low |
| `incremental_only` | contribution_points 为空 | low |

## 9. paper_extension 报告模板 (`docs/templates/opening_report_paper_extension.md`)

8 节模板:
1. 小论文贡献摘要 (paper_info + contributions)
2. 大论文章节映射 (ChapterMapping 表格)
3. 缺口分析 (gap_analysis)
4. 扩展实验建议 (ExtensionExperiment 列表)
5. 重复风险提示 (RepeatRiskWarning 列表)
6. 工作包规划 (WP2 / WP3)
7. 复用现有 chunk 引用 (evidence_refs + excerpt)
8. 大论文目录建议 (thesis_outline)

`report_templates.py` 注册 + `render_paper_extension_sections()` 函数把 card / mappings / plan / risks 渲染成 9 个 placeholder (含 thesis_outline).

`thesis_track=paper_extension` 选对模板: `list_template_keys()` 返回 4 个 (default / engineering / cv_ai / paper_extension).

## 10. 3 端点

| Method + Path | 用途 | 状态码 |
|---|---|---|
| `POST /api/v1/projects/{pid}/paper-library/small-paper/extract` | 抽 SmallPaperCard | 200/404/503 |
| `POST /api/v1/projects/{pid}/paper-library/small-paper/extension-plan` | 生成 ExtensionPlan | 200/404/503 |
| `POST /api/v1/projects/{pid}/paper-library/small-paper/repeat-risks` | 检重复风险 | 200/404 |

503 场景: `prefer=llm` + 无 `MINIMAX_API_KEY`.

## 11. 前端 Track B 入口

`apps/web/index.html`:
- `input-goal` 下拉新增 `<option value="已有小论文">已有小论文 (Track B)</option>`
- 选 `已有小论文` 时, 显示 `track-b-panel` (含 paper_id 输入框 + 3 个按钮: 抽卡片 / 生成扩展规划 / 检测重复风险 + 3 个展示 div).

`apps/web/app.js`:
- `initTrackB()` 监听 `input-goal` 变化切换面板
- `_trackBCall(path, body)` 通用 fetcher (要求 `state.projectId` 已存在)
- `_trackBRenderCard / Plan / Risks` 三个渲染函数
- click handler 绑定 3 个按钮

`apps/web/styles.css`: 末尾追加 `.track-b` / `.track-b__row` / `.track-b__card` 样式.

## 12. pytest 结果

| 项 | 数值 |
|---|---|
| 新增测试 (test_session49_track_b.py) | 31 |
| Session 49 失败 | 0 |
| 全量测试 | 737 passed, 1 skipped |
| 此前 (S48 + S51) | 706 passed |
| 净增长 | +31 |

测试覆盖 (8 个 TestClass):
- `TestSchemas` (4): 字段 shape
- `TestContributionExtractorHeuristic` (3): heuristic 路径 / intro-only / invalid id
- `TestContributionExtractorLLM` (3): mock LLM 路径 / fallback heuristic / force llm 抛错
- `TestChapterMapper` (5): 5 chapters + reference 跳过 + unknown 跳过
- `TestGapAnalyzer` (2): intro only 4 missing / 全覆盖 0 missing
- `TestExtensionPlanner` (3): ≥1 experiment / WP2 / thesis_outline
- `TestRepeatRisk` (3): method_reuse_only / well_extended / incremental_only
- `TestPaperExtensionTemplate` (3): 模板注册 / 8 节 / render 9 placeholders
- `TestEndpoints` (5): 404 / extract shape / plan shape / risks shape / 503

附带修改: `test_session19_report_templates.py::test_08_list_templates_endpoint` 模板数 3 → 4 + 验证 `paper_extension` 在 keys 里.

## 13. 与 Track A 的区别

| 维度 | Track A (保毕业) | Track B (已有小论文) |
|---|---|---|
| 入口 | 题目 + 关键词 (one_topic.analyze) | 已有小论文 (paper-library/small-paper/*) |
| 证据来源 | 系统三线检索 (paper / dataset / repo) | 单篇小论文全文 RAG + 扩展检索 |
| 模板 | default / engineering / cv_ai | paper_extension |
| 报告主轴 | 题目可行性 + 工作包 | 章节映射 + 缺口 + 扩展实验 |
| 风险提示 | evidence 不足 / 数据集缺 | 重复风险 (verbatim_copy / incremental_only) |
| 工作包 | 1-3 个 (题目驱动) | 1 个方法 (复用) + WP2/WP3 (扩展) |

## 14. 面试讲法

> 用户场景: "我手里有一篇小论文, 想扩成大论文, 怎么扩?"
>
> 系统答: 上传 / 检索小论文 PDF → S46 论文库入库 + S47 RAG 索引 → S49 Track B 抽 SmallPaperCard (LLM 抽贡献点 / heuristic 兜底) → 映射小论文章节到 7 个大论文章节 → gap_analyzer 计算缺失章节 → extension_planner 按缺口给扩展实验 (跨数据集 / 工程系统 / 轻量化) + WP2/WP3 → repeat_risk 提示别把方法直接塞进大论文 → paper_extension 模板 8 节报告.
>
> 关键设计取舍: 小论文扩展不是 "再写一篇小论文", 而是补齐 5 章 + 实验规模; 直接复用率 > 60% 会被打高风险; 缺哪章就生成哪章对应的扩展实验, 不是堆 LLM 自由发挥.
>
> 与 Track A 区别: 保毕业是题目可行性 (题目 → 证据 → 工作包); 已有小论文是单篇 → 章节映射 → 缺口 → 扩展 (反方向: 从已有成果出发).

## 15. 与 S46-48 的复用

| 能力 | 复用自 |
|---|---|
| 小论文 PDF 上传入库 | S46 `paper_library.ingest_upload / ingest_arxiv` |
| 全文 chunk 切分 | S46 `chunker.chunk_text` |
| 全文 RAG (extract 用) | S47 `retriever / paper_qa` (读取 chunks) |
| chunk 关联 Evidence Ledger | S48 `EvidenceItem.paper_id / chunk_id` (extract 自动挂载) |
| 报告模板分流 | S19 `_TEMPLATE_FILES` / `normalize_template_key` |

## 16. 文件清单

### 新增 (10)
- `apps/api/app/schemas_small_paper.py` (188 行)
- `apps/api/app/services/small_paper/__init__.py`
- `apps/api/app/services/small_paper/contribution_extractor.py` (~280 行)
- `apps/api/app/services/small_paper/chapter_mapper.py` (~120 行)
- `apps/api/app/services/small_paper/gap_analyzer.py` (~110 行)
- `apps/api/app/services/small_paper/extension_planner.py` (~180 行)
- `apps/api/app/services/small_paper/repeat_risk.py` (~95 行)
- `docs/templates/opening_report_paper_extension.md` (40 行)
- `apps/api/tests/test_session49_track_b.py` (31 tests, ~520 行)
- `Plan/reports/Session_49_SmallPaperExtension_TrackB_验收报告.md` (本文件)

### 修改 (5)
- `apps/api/app/services/report_templates.py` (注册 paper_extension + render_paper_extension_sections)
- `apps/api/app/api/v1/paper_library.py` (+ 3 端点 + imports)
- `apps/web/index.html` (input-goal 选项 + track-b-panel)
- `apps/web/app.js` (initTrackB + 3 个 click handler + render)
- `apps/web/styles.css` (末尾追加 .track-b*)
- `apps/api/tests/test_session19_report_templates.py` (模板数 3→4)

## 17. 已知限制 / 不做

- LLM 抽取需联网 + `MINIMAX_API_KEY`; 测试中 mock 验证.
- 模板不替换 FinalPackage 现有的 14 章节, 仅作为 `template_key=paper_extension` 的附加报告.
- 单篇小论文扩展; 多篇融合留给后续 Session.
- 章节映射基于 chunk_type + section_title 关键词, 复杂手稿可能需要用户复核.
- 前端 UI 是最小可用 (3 按钮 + 3 div), 不替代完整编辑器.
