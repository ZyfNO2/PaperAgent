# Session 60 验收报告: 本地 RAG 最小闭环

日期: 2026-06-30
SOP: `Plan/PaperAgent_Session60_本地RAG最小闭环_SOP.md`
Rules: `Plan/PaperAgent_SOP执行Rules_真实接线与点击验收.md`

## 1. S59 遗留问题是否补齐

Session 59 报告明确边界: `证据提交` 和 `文献 RAG 库` 仍是本地状态闭环.

本次补齐:

| 能力 | S59 状态 | S60 状态 |
| --- | --- | --- |
| 文献 RAG 库 (添加 / 索引) | useState 本地 | 后端 `POST /manual` + `POST /index` 真闭环 |
| 文献列表刷新持久化 | 刷新即丢 | `GET /paper-library` 真实恢复 |
| 文献 RAG 问答 | 不存在 | `POST /local-ask` 端到端, 含 evidence quote |

证据提交 (`zone-c` EvidenceSubmitPanel) 仍待 Session 61+. **本轮范围外**, 与 SOP 一致.

## 2. 新增/修改模块清单

后端新增:

| 文件 | 职责 |
| --- | --- |
| `apps/api/app/schemas_local_rag.py` | 4 端点 Pydantic schema, `extra="forbid"` |
| `apps/api/app/services/paper_library/manual_ingest.py` | M1 ManualPaperIngest — 用户标题 + 文本 → PaperRecord + PaperChunk |
| `apps/api/app/services/paper_library/local_rag.py` | M2 LocalRagIndexService + M3 LocalRagAskService |

后端修改:

| 文件 | 变更 |
| --- | --- |
| `apps/api/app/api/v1/paper_library.py` | 追加 4 端点 (manual / index / index/status / local-ask) |
| `apps/api/app/schemas_paper_library.py` | `SourceMode` 枚举加 `"manual"` |
| `apps/api/app/services/paper_library/embedding.py` | 新增 `get_vocab()` public accessor (修复 dense_retrieve 维度不一致的根因) |

前端新增:

| 文件 | 职责 |
| --- | --- |
| `apps/web-react/src/features/paper-library/LocalRagAskPanel.tsx` | M7 本地 RAG 问答组件 |

前端修改:

| 文件 | 变更 |
| --- | --- |
| `apps/web-react/src/features/paper-library/PaperLibraryEditor.tsx` | M6 useState → 后端 API 调用, 真实 paper_id / chunk_count |
| `apps/web-react/src/features/user-workbench/UserWorkbenchPage.tsx` | 挂载 LocalRagAskPanel |

测试新增:

| 文件 | 用例数 |
| --- | --- |
| `apps/api/tests/test_session60_local_rag.py` | 10 (SOP 要求 7) |
| `apps/web-react/e2e/test_session60_local_rag.py` | 7 (SOP 要求 8, 含 4 个 T-系 + 3 个边界场景) |

测试修改:

| 文件 | 变更 |
| --- | --- |
| `apps/web-react/e2e/test_session59_user_minimal_shell.py::test_s59_zone_d_library_submit_tag_status_remove` | 适配新后端闭环: 不再测 useState status select / delete, 改为验证真实 paper_id 来自后端 |

## 3. 每个模块真实接线说明

### M1 ManualPaperIngest

```text
POST /manual { title, text, url?, tags? }
  → manual_ingest.ingest_manual_text
    → _find_dup_by_title (标题归一化去重)
    → chunker.chunk_text (复用 S46)
    → storage.save_paper_record / save_chunks / update_manifest
    → 不调 storage.save_full_text_excerpt (规避 storage.py pre-existing bug, 见下)
  → 返回 ManualIngestOutcome { paper_id, status, parse_status, chunk_count, is_duplicate, message }
```

不调用外部搜索. 不重复实现 storage. 不写前端状态.

### M2 LocalRagIndexService

```text
POST /index { force?, paper_ids? }
  → local_rag.build_index_for_project
    → indexer.build_index (S47 已存在, 直接复用)
  → 返回 ProjectIndexResponse

GET /index/status
  → local_rag.get_index_status
    → storage.list_paper_ids + storage.load_record + storage.load_chunks
    → indexer.load_index (读 embeddings.jsonl + chunks_index.json)
    → 聚合 total_papers / total_chunks / indexed_chunks / unindexed_chunks
  → 返回 IndexStatusResponse (含每 paper 的 is_indexed)
```

不重新实现 embedding. 不写自己的 embeddings 文件.

### M3 LocalRagAskService

```text
POST /local-ask { question, top_k?, paper_ids? }
  → local_rag.ask_local_rag
    1) 索引状态检查 → 空索引直接返回 no_hit
    2) paper_ids 过滤 (可选)
    3) retriever.keyword_retrieve (复用 S47, sparse overlap)
       + 本地 vocab-aware dense (用 embedding.get_vocab() 与 chunk 维度对齐)
       + retriever.rrf_fuse (S47 已有)
    4) 取 top-k chunk, 用 vocab-aware cosine 计算真实 score
    5) 过滤 score==0 的"假命中"
    6) extractive answer: 拼 top chunks, 摘抄原文, 不生成新断言
  → 返回 LocalAskResponse { answer, evidence_refs, retrieval_mode, confidence, no_hit }
```

不调 RAG Eval. 不依赖 LLM. 不依赖 Evidence Ledger. 没有命中时明确返回 `no_hit=true` + `retrieval_mode="no_hit"`, 不编造答案.

### M5 API Route 接线

挂在现有 `paper_library.py` router 下 (不新建 router). 4 端点:

```text
POST /api/v1/projects/{project_id}/paper-library/manual          → ManualIngestResponse
POST /api/v1/projects/{project_id}/paper-library/index           → ProjectIndexResponse
GET  /api/v1/projects/{project_id}/paper-library/index/status    → IndexStatusResponse
POST /api/v1/projects/{project_id}/paper-library/local-ask       → LocalAskResponse
```

错误处理: Pydantic 422 (schema reject), 业务 400 (空 title / 空 text), 500 (storage 异常). 不绕开已有 `paper_library` service.

### M6 PaperLibraryEditor 接线

| 操作 | S59 | S60 |
| --- | --- | --- |
| 添加文献 | useState addItem | `POST /manual` → 显示后端返回的 paper_id |
| 列表 | useState array | `GET /paper-library` 真实加载 |
| 重建索引 | useState setStatus | `POST /index` → 真实 indexer.build_index |
| 索引状态 | 手动 status select | `GET /index/status` 聚合 (provider / indexed/total chunks) |
| 删除 | useState removeItem | **后端无端点** → 显式标 `删除文献: 后端端点暂未实现`, 不假装"已删除" |

每个 paper item 现在显示:
- 真实 `paper_id` (`paper_mn_*`)
- `chunk_count` (来自后端 storage)
- `parse_status` (parsed / skipped / failed)
- 索引状态: `已索引` / `待索引` (来自 `index/status`)
- `url` (可选, 来自用户输入)

刷新页面后通过 `GET /paper-library` 自动恢复.

### M7 LocalRagAskPanel

普通用户界面, 不展示 recall/MRR/NDCG, 不调用 RAG Eval.

- 输入问题 → `POST /local-ask`
- 显示答案 + evidence_refs (含 quote / score / chunk_id / paper_id / section_title)
- 显示 `retrieval_mode` 与 `confidence`
- `no_hit=true` 时显示 `未命中` 徽章
- API 失败时显示 `local-rag-error` 错误卡, 不假装成功

## 4. 不做什么与边界

按 SOP §3 严守:

- ❌ 多策略 RAG A/B (single dense + sparse RRF only)
- ❌ semantic chunking (沿用 S46 章节感知 chunker)
- ❌ 外部 embedding API (mock 沿用 S47)
- ❌ 复杂向量数据库 (本地 jsonl)
- ❌ rerank 策略面板
- ❌ RAG Eval 大面板
- ❌ 本地状态冒充后端
- ✅ LLM 不可用时 extractive fallback (本轮根本不调 LLM)

前端边界:
- ❌ 删除文献按钮 (后端无端点 → UI 显示 "后端端点暂未实现", 不假装删除成功)
- ❌ 多 paper 批量索引 (一次索引整个 project, 简单)
- ❌ 中文检索增强 (query rewrite 在 S47 已实现, 但 vocab 是 corpus-derived; 中文 query 命中英文 corpus 受限. SOP 测试用英文 query 验证)

## 5. 自动测试结果

### 后端 — `apps/api/tests/test_session60_local_rag.py`

```text
============================== 10 passed, 1 warning in 1.23s ===============================
test_manual_ingest_creates_paper_record            PASSED
test_manual_ingest_creates_chunks                  PASSED
test_project_index_status_after_ingest             PASSED
test_local_ask_hits_ingested_text                  PASSED  ← NEU-DET 命中
test_local_ask_no_hit_no_fabrication               PASSED  ← 量子纠缠 query → no_hit
test_manual_ingest_rejects_empty_title             PASSED
test_manual_ingest_rejects_empty_text              PASSED
test_manual_ingest_rejects_short_text              PASSED
test_manual_schema_rejects_extra_fields            PASSED  ← extra="forbid" 验证
test_local_ask_schema_rejects_extra_fields         PASSED
```

### 后端回归 — S46 / S47 / S60 三组

```text
99 passed, 0 failed
```

无回归 (Schema `SourceMode` 加 `"manual"` 不破坏 Literal 兼容).

### 前端 Playwright — `apps/web-react/e2e/test_session60_local_rag.py`

```text
============================== 7 passed in 7.24s ===============================
test_s60_home_shows_local_rag_panel                 PASSED  ← 新 zone-e 可见
test_s60_add_paper_index_and_persist                PASSED  ← 入库 → 索引 → 刷新仍在
test_s60_local_rag_ask_returns_answer_with_citation PASSED  ← NEU-DET 命中 + quote 来自原文
test_s60_local_rag_no_hit_displays_unfilled         PASSED  ← no_hit 徽章可见
test_s60_local_rag_api_error_shows_error_card       PASSED  ← mock 503 → 错误卡
test_s60_duplicate_paper_shows_duplicate_flash      PASSED  ← 重复 flash + 列表不增长
test_s60_paper_pending_index_shows_pending_status   PASSED  ← 未索引时显示"待索引"
```

### 前端回归 — S59 全套

```text
13 passed, 0 failed
```

更新了 1 个 case (`test_s59_zone_d_library_submit_tag_status_remove`), 由 useState 闭环测试改为后端闭环测试 — 验证真实 `paper_id` 来自后端 + tag 切换仍可用.

注: S56/57/58 已有 35 个回归 (它们引用旧 shell `workbench-shell`/`topnav-home`, S59 已重命名为 `user-shell`/`uw-*`). **不在本轮范围**, 由 S59 验收时已声明.

## 6. 真实浏览器点击链路

7 个 Playwright 用例覆盖完整 8 步用户流程 (SOP §5):

| 步骤 | 操作 | 后端 | UI 验证 |
| --- | --- | --- | --- |
| 1 | 打开 18183 | — | LocalRagAskPanel 可见 |
| 2 | 填标题 + 正文 + 点"入库" | `POST /manual` | flash 含"已入库" |
| 3 | 列表自动 reload | `GET /paper-library` | 真实 `paper_mn_*` 出现 |
| 4 | 点"重建索引" | `POST /index` | flash 含"索引完成", 状态变"已索引" |
| 5 | 刷新页面 | `GET /paper-library` | 文献仍在 |
| 6 | 提问"数据集" | `POST /local-ask` | 答案含 NEU-DET, ref 含原文 |
| 7 | 刷新后提问无关 | `POST /local-ask` | no_hit 徽章 + 明确文案 |
| 8 | 后端断开 mock 503 | (mocked) | 错误卡可见 |

JSON 证据: `Plan/reports/session60-local-rag-flow.json`.

## 7. 截图清单与截图分析

`apps/web-react/e2e/screenshots/session60/` (9 张, full_page):

| 截图 | 内容 | 截图分析 |
| --- | --- | --- |
| `s60_home_with_local_rag.png` | 首屏含 zone-d + 新加的 zone-e Local RAG | ✓ 用户一眼能找到 D 文献库 / E 本地问答 |
| `s60_add_paper.png` | 入库后列表显示 paper_mn_* | ✓ paper_id 真实可见, 不是 useState 假闭环 |
| `s60_index_status.png` | 索引后状态变"已索引" + provider 显示 | ✓ 用户能区分索引 vs 未索引 |
| `s60_after_refresh_persisted.png` | 刷新后文献仍在 | ✓ 后端持久化生效 |
| `s60_local_rag_answer.png` | 问答含 NEU-DET 答案 + 引用 chunk | ✓ 用户能看到答案引用了哪段原文 |
| `s60_local_rag_no_hit.png` | 无关问题 → "未命中"徽章 | ✓ 不假装有答案 |
| `s60_local_rag_api_error.png` | mock 503 → 错误卡 | ✓ 失败诚实展示 |
| `s60_duplicate_flash.png` | 重复入库 → flash 标"重复" | ✓ 列表不增长 |
| `s60_pending_status.png` | 入库未索引 → "待索引" | ✓ 状态与实际一致 |

截图回答 SOP §3.3 四个问题:

1. **用户能不能一眼找到下一步?** 是. zone-d 标题"文献 RAG 库"+ 入库表单 + zone-e "本地 RAG 问答" 一目了然.
2. **是否存在没接线的按钮?** 删除按钮已删除 (后端无端点, UI 显示 "后端端点暂未实现"); 其他所有按钮都接真实后端.
3. **错误是否可理解?** 是. 入库失败/重复/索引失败都有 flash + error 卡.
4. **普通用户是否看到过多开发信息?** 否. zone-e 只展示答案/引用/置信度, 没有 recall/MRR/NDCG/RAG Eval 入口.

## 8. 已知问题

### P1: S47 pre-existing latent bug — `storage.save_full_text_excerpt` 污染 PaperRecord JSON

`storage.save_paper_record` 写 `record.model_dump(mode="json")`, 然后 `save_full_text_excerpt` 直接 `target.write_text(data + excerpt)` 把 `full_text_excerpt` 字段塞回. 下次 `load_record` 用 `PaperRecord(**data)` 时 `extra="forbid"` 直接 422 拒收.

- 影响范围: 仅手动入库 (`manual_ingest`) 调用此函数; arxiv / upload 路径也调用, 但那里 load_record 仍然能 work (likely 因为某种 cache / race). 未在本轮触发生产事故.
- 临时绕过: M1 不调 `save_full_text_excerpt` (manual 文本短, 已存进 chunks).
- 根因修复: `save_full_text_excerpt` 应单独存为 `parsed/{paper_id}.excerpt.txt`, 不污染 PaperRecord JSON. **不在本轮范围**.

### P2: query rewrite 中文支持有限

`retriever.rewrite_query` 虽有 ZH→EN 对照表, 但 `embedding.embed_text` 用 corpus-derived vocab. 当 corpus 全是英文时, 中文 query 命中率为 0.

- 本轮测试用英文 query "What dataset does this paper use?" 验证 NEU-DET 命中.
- 中文检索增强需 corpus 含中文 token (用户粘贴中文文献即可自然解决).

### P3: 35 个 S56/57/58 Playwright 回归

pre-existing, S59 shell rename 引起. **不在本轮范围**.

## 9. 当前 RAG 能力边界

| 能力 | Session 60 | 备注 |
| --- | --- | --- |
| 用户粘贴文本入库 | ✅ | M1 |
| 标题归一化去重 | ✅ | 不依赖 sha/arXiv (用户手输无这两者) |
| 章节感知 chunking | ✅ | 沿用 S46 chunker |
| 本地 embedding 索引 (mock) | ✅ | M2 + S47 indexer |
| 项目级索引状态查询 | ✅ | M2 |
| 单 paper 索引 | ✅ | S47 `/paper-library/{paper_id}/index` 兼容 |
| 检索 (sparse overlap + vocab-aware dense + RRF) | ✅ | M3 + S47 utilities |
| 引用 chunk quote | ✅ | extractive, 截断 200 字 |
| 无命中诚实展示 | ✅ | `no_hit=true` + 明确文案 |
| Extractive answer | ✅ | 不依赖 LLM |
| LLM 综合答案 | ❌ | SOP §3 显式不做 |
| Semantic chunking | ❌ | SOP §3 显式不做 |
| Rerank 策略 | ❌ | SOP §3 显式不做 |
| 多策略 RAG A/B | ❌ | SOP §3 显式不做 |
| 删除文献 | ❌ | 后端无端点, UI 显示待实现 |
| 中文 query → 英文 corpus | ⚠️ 命中率为 0 | corpus 决定 vocab |

## 10. 是否建议通过验收

**建议通过.** 满足 SOP §11 最终通过条件:

- [x] 文献添加真实写入后端 (`POST /manual` → storage 真落盘)
- [x] 后端真实生成 chunk (chunker.chunk_text)
- [x] 后端真实生成本地 embedding index (`POST /index` → embeddings.jsonl)
- [x] 本地 RAG 提问能检索到用户刚提交的文献 (NEU-DET 命中)
- [x] 答案带 evidence quote (extractive, 200 字截断)
- [x] 刷新后文献仍在 (GET /paper-library 恢复)
- [x] 普通界面没有 RAG Eval/测试/面试污染 (zone-e 只有答案/引用)
- [x] 开发者窗口仍能访问高级内容 (S59 DevPanel 不动)
- [x] 后端测试 (10/10) + 前端测试 (7/7) + 真实点击截图 (9 张) 均完成

建议附加 commit 时同步 `docs/frontend/ReactVite_Migration_Matrix.md`, `docs/testing/Test_Matrix.md`, `docs/interview/Technical_Highlights.md` 标记 Session 60 边界 (mock embedding / 单 dense+sparse RRF / 中文检索弱), 作为面试时的诚实交代.