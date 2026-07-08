# Re3.1 Changelog

## Phase 6 (前端打通 SOP): recursion_limit + asyncio 嵌套 + heuristic dataset

### Fix 1.1: recursion_limit

#### `apps/api/app/api/v1/research.py`
- `_run_case_sync` 的 `g.invoke()` 添加 `"recursion_limit": 100`。
- LangGraph 默认 25 步不够（20 节点 + repair loop + citation expansion 二次循环 + devils_advocate 回环），导致 graph 截断 → 前端空。

#### `apps/api/scripts/re30_batch_run.py`
- 同样添加 `"recursion_limit": 100`。

### Fix 1.2: search_agent asyncio 嵌套

#### `apps/api/app/services/agents/graph/nodes/search_agent.py`
- 新增 `_run_tool_sync()` 函数：同步调用适配器，兼容已有 event loop。
  - 检测 `asyncio.get_event_loop().is_running()` → 用 ThreadPoolExecutor 在新线程中跑
  - 无 loop → `asyncio.run()`
  - 已有 loop 但未运行 → `loop.run_until_complete()`
- `search_agent_node` 中的 `asyncio.run(_run_tool(...))` 替换为 `_run_tool_sync(...)`。
- **根因**：`_run_case_sync` 在 FastAPI BackgroundThread 中运行，如果线程中已有 event loop，`asyncio.run()` 会报 `RuntimeError: This event loop is already running`。

### Fix 1.3: research_narrative 字段名
- **已验证**：state.py 使用 `research_narrative`（单数），所有文件统一。Re3.0 Fix 2.1 已完成。

### Phase 2 补充: heuristic dataset extraction from verified_papers titles

#### `apps/api/app/services/agents/graph/nodes/dataset_repo_extractor.py`
- 扩展 `known_dataset_names` 列表（新增 PlantVillage, PlantDoc, IP102, SDNET2018, BDD100K, VisDrone, Matterport3D, ETH3D, LIDC-IDRI, LUNA16, ADE20K, VOC2012, Synthia, FlyingChairs, Sintel, TartanAir, NYUv2, Make3D, FlyingThings3D）。
- 新增从 `verified_papers` 的 title + abstract 中 heuristic 提取已知数据集名。
- 来源标记为 `paper_title_heuristic`。
- **效果**：即使 LLM 提取失败，只要论文标题/摘要提到 KITTI/COCO/PlantVillage 等已知数据集名，dataset_candidates 就非空。

## 前面 Phase 1-5（质量打磨 SOP）

### `apps/api/app/services/agents/prompts/re11_dataset_repo_extractor.py`
- **SYSTEM prompt**: 增加指示 LLM 从论文标题、摘要、全文中提取数据集名和代码链接。明确指出论文标题常含数据集名（如 "NEU-DET", "KITTI"）或方法名（如 "YOLOv5"）。
- **USER_TEMPLATE**: 增加 "Extract dataset names, benchmark names, code/repo URLs, and project page URLs from the TITLE, ABSTRACT, and SNIPPET above. Pay special attention to the title" 指令。
- **build()**: 新增 `fulltext` 参数，当全文可用时作为 snippet 传入（比摘要更丰富）。
- **OUTPUT CONTRACT**: 添加 `[OUTPUT CONTRACT]` 约束。
- **title 截断**: 从无截断改为 300 字符截断，防止过长标题破坏 JSON。

### 验证
- GitHub→repo_candidates: 已确认生效（Re2.2 fix）
- innovation_points heuristic: 已确认存在（known_dataset_names 匹配）
- DataCite: 不在 adapter REGISTRY 中，无连接需求

## Phase 2: devils_advocate prompt 调优 + research_narrative 字段名

### `apps/api/app/services/agents/graph/nodes/devils_advocate_node.py`
- **已验证**: `research_narrative`（单数）字段名已在 Re3.0 Fix 2.1 中修正。state 读取、narrative_builder 输出、devils_advocate 读取均使用单数形式。

### `apps/api/app/services/agents/prompts/devils_advocate_graph.py`
- **已验证**: prompt 已包含正确的 verdict 判定规则：
  - 有 baseline + 有创新点 + 有工作包 → ACCEPT
  - 创新点描述模糊 → MINOR_REVISION（不是 BLOCK）
  - BLOCK 仅用于编造证据或 baseline 完全缺失

### `apps/api/app/api/v1/research.py`
- **已验证**: `case_narrative` 端点读取 `research_narrative`（单数）。

## Phase 3: 用户上传论文功能

### `apps/api/app/services/agents/graph/state.py`
- 新增 `user_papers: list[dict[str, Any]]` 字段。

### `apps/api/app/services/agents/graph/nodes/intake.py`
- intake 节点现在检查 `user_papers`，将其注入 `verified_papers`（verdict=accept）和 `seed_papers`（relevance_score=1.0）。

### `apps/api/app/api/v1/research.py`
- 新增 `_USER_PAPERS` 内存存储。
- `_run_case_sync`: 从 `_USER_PAPERS` 弹出 case 的用户论文，注入到 `state_in`。
- 新增 `POST /{case_id}/papers` 端点：
  - 接收 title, doi, arxiv_id, url, role
  - `_enrich_paper()` 异步函数：
    - 有 DOI → 查 Crossref 补全标题/摘要/作者/年份
    - 有 arXiv ID → 查 arXiv 补全标题/摘要/URL
    - 只有标题 → 直接使用
  - 论文存储到 `_USER_PAPERS`，如果 case 已完成则同时追加到 state.json
- 新增 `GET /{case_id}/papers` 端点：列出用户上传的论文。

### `apps/web/index.html`
- 新增上传 UI 区域（标题、DOI、arXiv ID、role 下拉、添加按钮）。
- `uploadPaper()` / `renderUploadList()` JavaScript 函数。
- `renderPapers()` 添加 `[用户上传]` 标记。
- `startResearch()` 使用 `currentCaseId`（如果已有上传论文）。

## Phase 4: 搜索结果去重 + Crossref 表格过滤

### `apps/api/app/services/agents/graph/nodes/search_agent.py`
- 新增 `_dedup_key()` 函数：normalized title（strip punctuation + collapse whitespace）+ DOI 优先。
- 论文和 repo 去重均使用 `_dedup_key()`。
- 新增 `arxiv_id` 字段传递到 entry。
- 新增 `_crossref_type` 字段传递到 entry。

### `apps/api/app/services/agents/graph/nodes/retrieve.py`
- 去重逻辑增强：strip punctuation + DOI 优先（与 search_agent 一致）。
- 新增 `arxiv_id` 字段传递到 entry。
- 新增 `_crossref_type` 字段传递到 entry。

### `apps/api/app/services/agents/graph/nodes/quality_filter.py`
- `_pre_filter()` 新增 Crossref type 过滤：
  - `type=component` → drop（表格/图片组件，不是论文）
  - `type=book-section` / `book-part` / `book-series` → drop

## Phase 5: arXiv 全文获取

### `apps/api/app/services/retrieval/arxiv_fulltext.py` (新文件)
- `fetch_arxiv_fulltext(arxiv_id)`: 异步下载 arXiv PDF，用 pypdf 提取文本。
  - 最多 10 页，截断到 5000 字符。
  - 超时 30s，失败返回空字符串（不阻塞管道）。
- `fetch_arxiv_fulltext_sync(arxiv_id)`: 同步包装，用于 ThreadPoolExecutor。

### `apps/api/app/services/agents/graph/nodes/dataset_repo_extractor.py`
- `_extract_one()`: 如果论文有 `arxiv_id`，先获取全文，然后传给 `P.build(title, abstract, fulltext=fulltext)`。
- 全文获取失败不阻塞，降级为仅用摘要。

### `apps/api/app/services/agents/graph/nodes/search_agent.py` / `retrieve.py`
- `arxiv_id` 从原始 hit 传递到 entry，确保 dataset_repo_extractor 能访问。

## 测试结果

### Re3.1 集成测试 (tmp_re31_eval/test_re31_phases.py)

25/25 passed, 0 failed, 0 skipped

```
=== Phase 1: dataset/repo extractor prompt ===
  [OK] build() with fulltext param -- fulltext_len=933
  [OK] SYSTEM prompt mentions title
  [OK] OUTPUT CONTRACT present

=== Phase 2: devils_advocate field name ===
  [OK] state uses research_narrative (singular)
  [OK] devils_advocate reads singular field
  [OK] narrative_builder outputs singular field
  [OK] API case_narrative reads singular field
  [OK] devils_advocate prompt has verdict rules

=== Phase 3: User paper upload ===
  [OK] ResearchState has user_papers field
  [OK] intake injects user_papers -- vp=1, sp=1
  [OK] API endpoints exist
  [OK] _enrich_paper function exists
  [OK] _USER_PAPERS storage exists
  [OK] _run_case_sync injects user_papers

=== Phase 4: Dedup + Crossref table filter ===
  [OK] _dedup_key: DOI + title normalization -- doi_key=doi:10.1234/test, title_key=title:yolov5 realtime object detection
  [OK] retrieve.py enhanced dedup
  [OK] quality_filter drops Crossref component -- dropped=2
  [OK] search_agent propagates _crossref_type
  [OK] retrieve.py propagates _crossref_type

=== Phase 5: arXiv full-text retrieval ===
  [OK] arxiv_fulltext module imports
  [OK] empty arxiv_id returns empty string
  [OK] real arXiv PDF download + text extraction -- len=5000, elapsed=7.1s
  [OK] dataset_repo_extractor integrated with fulltext
  [OK] arxiv_id propagated in search_agent
  [OK] arxiv_id propagated in retrieve.py

Total: 32 passed, 0 failed, 0 skipped
```

### Phase 6 (前端打通 SOP) — 新增 7 项

```
=== Phase 6: Frontend fixes (recursion_limit + asyncio) ===
  [OK] research.py sets recursion_limit=100
  [OK] re30_batch_run.py sets recursion_limit
  [OK] _run_tool_sync exists in search_agent
  [OK] search_agent uses _run_tool_sync (no asyncio.run nesting)
  [OK] _run_tool_sync works (real arxiv call) -- got 3 results
  [OK] heuristic dataset extraction from paper titles
  [OK] functional: KITTI found from paper title -- datasets=['KITTI']
```

### 已有 pytest 回归测试

17/19 passed, 2 pre-existing failures

- `test_re1_3_loop1_quality_filter.py`: 10 passed
- `test_re1_1_dataset_repo_from_papers.py`: passed
- `test_re1_2_retrieve_parallel.py`: 4 passed
- `test_re1_2_search_planner_template.py`: passed
- `test_re1_2_topic_parser_guards.py`: passed
- `test_re1_2_verify_limit.py`: 1 passed
- `test_re1_2_graph_nodes.py`: 2 FAILED (pre-existing)
  - `test_graph_compiles_and_smoke_runs`: checks for `paper_retriever` (renamed to `search_agent` in Re3.0)
  - `test_node_modules_expose_expected_node_funcs`: checks for `paper_retriever` module

### 修复的依赖

- 安装 `pypdf` (已在 pyproject.toml 中声明但未安装)
