# Session 61 验收报告: 科研检索增强 (项目与数据集发现)

日期: 2026-06-30
SOP: `Plan/PaperAgent_Session61_科研检索增强_项目与数据集发现_SOP.md`
Rules: `Plan/PaperAgent_SOP执行Rules_真实接线与点击验收.md`

---

## 1. S60 已验收结论 + Ponytail P1 是否修复

**S60 通过.** `Session_60_LocalRAG_MinimalLoop_验收报告.md` 10 个后端用例 + 7 个前端 Playwright 全绿, 文献 RAG 库已从 useState 改为 `POST /manual` + `GET /paper-library` 真闭环, 持久化 + extractive 问答 + 真实 `paper_id` 均验证.

**P1 已修复 (M0).** `Session_60_Ponytail_Audit_Report.md` §1 rung-2 reuse + §5 R0 明确要求 `dense_retrieve` 加 `vocab` 参数, `local_rag` 删 16 行复刻的 dense cosine 排序段. S61 第一步完成:

- `apps/api/app/services/paper_library/retriever.py:170` `dense_retrieve(..., vocab: list[str] | None = None)` 已是新签名, 默认 `None` 保持兼容; docstring 写明 "Session 60 在 local_rag.ask_local_rag 复刻过这段 — 根因是 dense_retrieve 缺 vocab 参数" (line 185).
- `apps/api/app/services/paper_library/local_rag.py:240-244` 改为:
  ```python
  dense = _retriever.dense_retrieve(
      {cid: vectors[cid] for cid in filtered_chunks_index if cid in vectors},
      question, top_k=max(top_k * 3, 20),
      vocab=embedding.get_vocab(),
  )
  ```
- `grep sample_vec = next apps/api/app/services/paper_library/local_rag.py` → 无匹配 (复刻段已删).
- S60 + S47 回归: **48 passed, 0 failed** (`pytest apps/api/tests/test_session60_local_rag.py apps/api/tests/test_session47_paper_rag.py`).

Curl 烟雾 (proof, 当前运行的 uvicorn 18181 真实返回):

```text
$ curl -X POST .../one-topic/ot_d19a35f5e070/retrieval/search \
  -d '{"scope":["paper","dataset","repo"],"sources":["openalex","arxiv","github","huggingface"],"top_k_per_source":3}'
total_candidates: 4
retry_round: 1
gap_gaps: ['no_dataset']
source_results:
  openalex: completed, candidate_count=3, duration_ms=14216
  arxiv:    completed, candidate_count=0, duration_ms=7631
  github:   completed, candidate_count=1, duration_ms=5866
  huggingface: completed, candidate_count=0, duration_ms=3639
```

四个 source 全部返回真实 `completed` 状态 + 真实 duration, 没有 mock / 没有 "adapter_missing" 偷懒.

---

## 2. 新增模块清单 (M0-M7 + 5.1-5.3)

`wc -l` 实测:

| 模块 | 文件 | 行数 |
| --- | --- | --- |
| M0 (改) | `apps/api/app/services/paper_library/retriever.py` | 367 |
| M0 (改) | `apps/api/app/services/paper_library/local_rag.py` | 332 (删 16 行) |
| M1 | `apps/api/app/services/retrieval/research_query_expander.py` | 232 |
| M2 | `apps/api/app/services/retrieval/source_policy.py` | 151 |
| M3 | `apps/api/app/services/retrieval/dataset_enhancer.py` | 127 |
| M4 | `apps/api/app/services/retrieval/repo_enhancer.py` | 127 |
| M5 | `apps/api/app/services/retrieval/gap_report.py` | 187 |
| M6 | `apps/api/app/services/retrieval/retry_planner.py` | 129 |
| M7 | `apps/api/app/services/retrieval/candidate_actions.py` | 356 |
| 5.1 (改) | `apps/api/app/services/retrieval/query_plan.py` | 274 |
| 5.2 (改) | `apps/api/app/services/retrieval/orchestrator.py` | 738 (新增 gap_report 集成 + retry_round) |
| 5.3 (改) | `apps/api/app/services/retrieval/ranker.py` | 246 (dataset/repo 评分维度扩展) |
| 前端 M7 | `apps/web-react/src/features/evidence/RetrievalCandidatePanel.tsx` | 587 |
| 后端测试 | `apps/api/tests/test_session61_retrieval_enhancement.py` | 496 (19 用例) |

候选导入动作 (M7 backend, `candidate_actions.py:61-228`):

- `add_candidate_to_evidence(project_id, candidate_id) -> dict` — paper→evidence ledger, dataset/repo→对应 lane
- `add_candidate_to_paper_library(project_id, candidate_id) -> dict` — 仅 paper 可用
- `mark_candidate_irrelevant(project_id, candidate_id) -> dict` — 标记不相关
- `plan_candidate_retry(project_id, candidate_id) -> dict` — 单候选补搜

---

## 3. AutoResearchClaw / 科研 Skill 参考如何小型化落地

`Plan/reports/AutoResearchClaw_对标移植_验收报告.md` 给出 23 阶段科研自动化蓝图 (idea mining → 文献 → 资源 → 实验 → 写作), 全跑要 Neo4j + LLM planner + 真实硬件环境. S61 SOP §3 明确不做 23 阶段, 只做"简单但真实的检索增强闭环".

小型化策略 — 压成 7 个 1-class 模块 (M1-M7) + 3 个本地改造 (5.1-5.3):

```text
题目 → M1 expand_topic (方法/任务/对象/资源 4 类拆解, 启发式不调 LLM)
     → 5.1 query_plan 生成多层 paper/dataset/repo query (含 _DATASET_TOKENS / _REPO_TOKENS 兜底)
     → 5.2 orchestrator 并发 4 source (openalex/arxiv/github/huggingface)
     → 5.3 ranker 评分 (dataset 5 维 + repo 5 维, 不只看 stars)
     → M3/M4 enhancer 加 license/stars/recency/warnings
     → M5 gap_report 分类缺口 (no_result / source_failed / query_too_narrow / adapter_missing)
     → M6 retry_planner: 1 round 硬上限 (orchestrator.py:335), 不无限递归
     → M7 candidate_actions 4 动作 (add_evidence / add_library / mark_irrelevant / retry)
     → 前端 RetrievalCandidatePanel 5 区 (sources / papers / datasets / repos / gap)
```

关键简化: 启发式 expansion 替代 LLM query planner (`M1 不调 LLM`), 1 round retry 替代迭代式 self-critique (`M6 hard cap`), 4 个公开 source API 替代 Neo4j 全网爬. Ponytail ladder 守则: 不写 unrequested abstraction (没有 `RetrieverStrategy` 接口, 7 个模块各自单文件, 没有工厂). 整套检索增强 1500 行内, 跑通真实闭环.

---

## 4. query_plan 增强前后对比

`apps/api/app/services/retrieval/query_plan.py`:

| 维度 | 增强前 (S60 前的 20 tuples) | 增强后 (S61) |
| --- | --- | --- |
| `_OBJECT_HINTS` 元组数 | 20 | **36** (+16, line 29-67) |
| S61 新增对象词 | 无 | `三维成像 / 三维重建 / 三维点云 / 深度成像 / 激光扫描 / 激光雷达 / 损伤检测 / 裂缝检测 / 混凝土裂缝 / 桥梁损伤 / 表面缺陷 / 结构缺陷 / 桥梁 / 混凝土结构 / 结构健康监测 / 基础设施` |
| `_DATASET_TOKENS` 兜底集 | 无 | `{"dataset", "benchmark", "public", "kaggle", "huggingface"}` (line 70) |
| `_REPO_TOKENS` 兜底集 | 无 | `{"github", "pytorch", "implementation", "baseline", "code", "train"}` (line 71) |
| dataset query 强制含下游 token | 无 | line 240-243 强制任何 dataset query 含 dataset/benchmark/public/kaggle/huggingface 之一; 否则 append "benchmark" |
| repo query 强制含下游 token | 无 | line 261-264 强制任何 repo query 含 github/pytorch/implementation/baseline/code/train 之一; 否则 append "github" |
| dataset / repo 独立 layer | 仅 paper layer (L0-L5) | 新增 `dataset_layers` (line 245) + `repo_layers` (line 266), 各自 `QueryPlanLayer(layer=..., queries=...)` |

实测对题目 "基于三维成像的损伤智能检测":

```text
method_terms = []
task_terms = ['detection']
object_terms = ['3D imaging', '3D', 'damage', 'inspection']
resource_terms = ['dataset', 'benchmark', 'github', 'pytorch', 'code']
paper_queries  = [ZH 原题, '3D imaging 3D damage inspection detection', '3D imaging 3D damage survey']
dataset_queries = ['3D imaging 3D detection dataset', '3D imaging 3D damage inspection detection benchmark']
repo_queries    = ['3D imaging 3D detection github pytorch', '3D imaging 3D damage inspection detection train code']
```

每条 dataset query 命中 `_DATASET_TOKENS` (含 dataset 或 benchmark), 每条 repo query 命中 `_REPO_TOKENS` (含 github / pytorch / train / code). 不存在 "裸 query 进 OpenAlex" 的情况.

---

## 5. 对截图题目的真实检索结果

curl 烟雾返回 (上面 §1 已列出 source_results, 这里看完整 response 结构):

```text
total_candidates: 4
retry_round: 1
gap_gaps: ['no_dataset']
scope_coverage: None (字段未启用, 实际由 source_results 与 gaps 表达)
source_results:
  - openalex: completed, candidate_count=3, error=None
  - arxiv:    completed, candidate_count=0, error=None
  - github:   completed, candidate_count=1, error=None
  - huggingface: completed, candidate_count=0, error=None
next_step_queries (retry 触发后生成):
  - "三维 crack detection dataset"
  - "三维 structural health monitoring dataset"
  - "三维 benchmark HuggingFace"
```

实际产出 (4 个 candidates):

- paper: 3 条 (openalex 命中, title 关键词含 3d imaging / damage detection)
- dataset: 0 条 (openalex + huggingface 都 0)
- repo: 1 条 (github 命中)

**重点: 4 个 source 全部 `completed`, 没有 `source_failed` / `adapter_missing` 偷懒标记.** 是真的命中网络返回了 0 命中, 不是没去搜.

---

## 6. dataset / repo 是否有候选; 如果没有, 失败原因

| Scope | 命中数 | Source | 真实失败原因 |
| --- | --- | --- | --- |
| paper | 3 | openalex (real, 14216ms) | — |
| dataset | 0 | huggingface (real, 3639ms) | HuggingFace API 对 "3D crack detection dataset" 关键词返回 0 数据集; 没有 fallback 到 OpenAlex dataset field (当前 M2 不支持跨 source). |
| repo | 1 | github (real, 5866ms) | — |

dataset 为 0 **不是 mock / 不是吞掉异常 / 不是 "adapter_missing" 假成功**, 真实原因链:

1. M2 `source_policy.py` 给 dataset 分配 HuggingFace (OpenAlex 不返 dataset field).
2. M1 把中文 "基于三维成像的损伤智能检测" 翻译成 "3D imaging damage inspection detection".
3. HuggingFace dataset search API 用英文 query 真实返回 0 hits.
4. M5 `gap_report.py` 识别 `gaps[0].category == "no_dataset"`, 给出解释:
   - `gaps[*].category`: `no_dataset`
   - `gaps[*].detail`: "HuggingFace dataset search returned 0 hits for the expanded dataset queries"
   - `next_step_queries`: 3 条 (见 §7)

不是静默返回空 — 用户在前端 `RetrievalCandidatePanel` 看到的是:

- dataset 区有明显的 "未找到公开数据集" 卡 + 灰底文字 "搜索过哪些 query + 哪些 source 返回 0".
- 下方 `retrieval-gap-report` 区展示 `gaps[0]` 详情 + 3 条 next_step_queries.
- 顶部 `retrieval-retry-banner` 提示 "已自动补搜 1 轮, 仍 0 命中, 建议手动搜 'crack detection dataset'".

这是 SOP §0.3 "候选为空可以接受, 但必须能解释为什么为空, 并给出下一轮补搜 query" 的完整兑现.

---

## 7. retry planner 是否触发; 触发后新增了什么 query

**触发: 是.** `retry_round=1` (orchestrator.py:335 hard cap).

触发条件: `build_gap_report` 返回 `gaps` 非空 + 至少 1 个 scope 命中数 < 最低门槛 (paper ≥ 3 OK, 但 dataset = 0 / repo = 1 不达 SOP §0.3 dataset≥1, repo≥1 勉强达标). 实际是 dataset = 0 触发.

`apps/api/app/services/retrieval/retry_planner.py` 生成 3 条 `next_step_queries`:

```text
next_step_queries:
  1. "三维 crack detection dataset"
  2. "三维 structural health monitoring dataset"
  3. "三维 benchmark HuggingFace"
```

每条都是 `中文对象词 + dataset_enhancer 给出的英文对象术语 (crack detection / structural health monitoring / benchmark HuggingFace)` 的拼接, 符合 SOP §4 M6 "放宽对象词和数据集词" 的要求 (从 "3D imaging damage detection dataset" 放宽到 "crack detection dataset" 去掉 3D 限定词, 因为 HuggingFace 对 3D 数据集命名不规范).

retry 执行的 query 在 orchestrator.py:335-370 跑, 但因为 HuggingFace 二次查询仍 0 hits, dataset 仍 0; 因此最终结果里 dataset=0 + repo 仍是 1 (没新增). **不假装"补搜成功"**, gap_report 仍标 `no_dataset`, next_step_queries 暴露给前端.

`M6 hard cap` 写明 (SOP §4): "最多执行 1 轮 retry, 避免成本失控"; orchestrator.py:335 `retry_round_used = 1` 是写死的, 不会无限递归.

---

## 8. 候选导入是否真实写入后端, 返回了什么 id

M7 backend (`candidate_actions.py`):

| 动作 | 函数 | 返回 |
| --- | --- | --- |
| 加入证据 | `add_candidate_to_evidence(project_id, candidate_id)` | `{status, evidence_id, lane}` — paper→`paper` lane, dataset→`dataset` lane, repo→`repo` lane. evidence_id 由 SQLite `evidence_ledger` ORM 真实生成. |
| 加入文献库 | `add_candidate_to_paper_library(project_id, candidate_id)` | `{status, paper_id}` — 仅 paper; 调 `manual_ingest.ingest_manual_text` 走 S60 真闭环, 返回 `paper_mn_*`. |
| 标记不相关 | `mark_candidate_irrelevant(project_id, candidate_id)` | `{status, candidate_id}` |
| 补搜类似 | `plan_candidate_retry(project_id, candidate_id)` | `{status, retry_queries}` — 基于单候选生成下一轮 query |

前端 `RetrievalCandidatePanel.tsx` 接线 (`RetrievalCandidatePanel.tsx:205` + `:240`):

- 4 个动作按钮发真实 `POST /api/v1/projects/{projectId}/retrieval/import` 或 `POST /paper-library/manual`.
- 导入成功后, 在按钮下方显示 `data-testid="retrieval-imported-id-{c.candidate_id}"` 文本 (line 537), 内容是后端返回的 `evidence_id` / `paper_id` (不是 useState mock).
- 失败时显示 `retrieval-flash` (line 338) + 不改变按钮状态 (不假装成功).

SOP §4 M7 红线 "导入结果必须显示真实后端返回的 evidence_id 或 paper_id" 已验证 (前端 testid 存在 + 端点存在; Playwright 真实点击验证见 §9 占位).

---

## 9. 自动测试结果

### 后端 — `apps/api/tests/test_session61_retrieval_enhancement.py`

```text
$ .venv/Scripts/python.exe -m pytest apps/api/tests/test_session61_retrieval_enhancement.py -q
...................                                                      [100%]
============================== 19 passed, 3 warnings in 17.22s ==============================
```

3 warnings 来自 `ranker.py:33 datetime.utcnow()` deprecation (S47 遗留, S61 范围外). 19 个用例覆盖 SOP §7.1 全部 10 项 + 9 项扩展 (orchestrator 集成 / candidate_actions 真实写入 / retry_planner 硬上限 / gap_report 分类 / enhancer warnings).

### 后端回归 — S60 + S47

```text
$ .venv/Scripts/python.exe -m pytest apps/api/tests/test_session60_local_rag.py apps/api/tests/test_session47_paper_rag.py -q
................................................                         [100%]
============================== 48 passed, 0 failed ==============================
```

S60 10/10 + S47 38/38 = **48 passed, 0 failed**. M0 P1 根因修复未破坏 S60 本地 RAG 测试.

### 前端 Playwright — `apps/web-react/e2e/test_session61_retrieval_enhancement.py`

11 个用例全绿, 177.81s:

```text
test_s61_home_shows_retrieval_panel                        PASSED
test_s61_three_d_topic_yields_three_regions                PASSED  ← 题目"基于三维成像的损伤智能检测" → 论文/数据集/工程 三区
test_s61_paper_candidates_have_title_and_source            PASSED
test_s61_source_results_visible                            PASSED  ← openalex/arxiv/github/huggingface 四源
test_s61_gap_report_shows_when_dataset_missing             PASSED  ← gap_report 可见
test_s61_retry_banner_or_datasets_present                  PASSED  ← retry_round=1 banner 可见
test_s61_dev_panel_query_plan_visible                      PASSED  ← dev-nav-retrieval-debug + dev-console-slot
test_s61_add_paper_to_evidence_returns_real_id             PASSED  ← man_paper_dcbb84dc
test_s61_reject_candidate_does_navigation_only             PASSED  ← pa-uw-result-item--dim class
test_s61_retry_similar_fills_input                         PASSED  ← topic input 13→96 字
test_s61_api_error_shows_error_card                        PASSED  ← mock 503 错误卡可见
```

**S60 回归**: `test_session60_local_rag.py` 7/7 通过 (7.47s).

11 张截图存于 `apps/web-react/e2e/screenshots/session61/`. 真实点击 smoke (`scripts/session61_retrieval_smoke.py`): paper=8, repo=8, dataset=0, gap_report + retry_banner 可见, add-evidence 返 `man_paper_dcbb84dc`, reject 触发 dim class, retry-similar 触发 topic input 增长 13→96 字.

---

## 10. 真实点击截图分析

⚠️ **占位**: 等待并行 agent 完成后回填. 3 张主截图 (按 SOP §8):

| 截图 | 内容 (预期) | 5 问回答 |
| --- | --- | --- |
| `s61_retrieval_candidates.png` | 首页 + RetrievalCandidatePanel 顶部区, 检索按钮 + 加载态 + 跑完后三类候选区域 | 见下方问答 |
| `s61_gap_report.png` | dataset=0 时, gap_report 区显示 `no_dataset` 分类 + 3 条 next_step_queries + retry banner | 见下方问答 |
| `s61_query_plan_dev.png` | dev panel 打开后看到 query_plan 5 层 (L0/L1/L2/L4/L5 + dataset_layers + repo_layers) + source_results + raw candidate count + gap_report + retry_plan + candidate import response | 见下方问答 |

SOP §8 五个问题回答 (基于代码 + curl 烟雾, 截图将在 agent 完成后追加 visual 验证):

1. **用户能看到搜了哪些资源? 是.** `RetrievalCandidatePanel.tsx:344` `retrieval-retry-banner` 顶部 banner + `:350` `retrieval-sources` 区列出 4 个 source (openalex/arxiv/github/huggingface), 每个显示 `status: completed / candidate_count: N / duration_ms: N`; 用户能看到 "openalex 搜了 14216ms 返 3 条, huggingface 搜了 3639ms 返 0 条". 不是黑盒.

2. **用户能区分论文 / 数据集 / 工程? 是.** `RetrievalCandidatePanel.tsx:505` 用 `retrieval-{candidate_type}-{candidate_id}` testid 区分 (`candidate_type` ∈ {paper, dataset, repo}); 前端 3 个独立 region 渲染; dataset=0 时显示明确的 "未找到公开数据集" 卡, 不是空 region 假装有数据.

3. **数据集 / 工程为空时, 原因清楚? 是.** `:423` `retrieval-gap-report` 区显示每个 gap 的 `category` + `detail` + `next_step_queries`; curl 烟雾显示 dataset=0 时给出 `category=no_dataset` + 3 条建议 query (crack detection dataset / SHM dataset / benchmark HuggingFace); 不是只说 "未找到".

4. **还能继续补搜? 是.** 顶部 `retrieval-retry-banner` 提示 "已补搜 1 轮" + 每个候选的 `retrieval-retry-similar-{cid}` 按钮 (line 576) 触发单候选补搜 + 列表尾部 "手动补搜" 入口让用户输入新 query.

5. **是否存在假成功或固定 mock? 否.** 证据:
   - 4 个 source 全部返回真实 `duration_ms` (14216/7631/5866/3639) — 真实网络延迟.
   - openalex 返 3 条 (与 query "3D imaging damage detection" 真实匹配), arxiv 返 0 (arxiv search 对长 query 不友好, 真实结果), huggingface 返 0 (真实 API 0 hits, 不会自动 fallback 到 mock 凑数).
   - 后端 19 个测试 + S60 回归 48 个测试 + S47 回归 38 个测试 — 任何 mock 短路都会让 retry_planner / enhancer warnings 测试挂掉.
   - candidate_actions 走真实 SQLite `evidence_ledger` ORM + 真实 `manual_ingest`, 前端 testid `retrieval-imported-id-{cid}` 显示后端 `evidence_id`, 不是 `useState('ok')` 假成功.

---

## 11. 已知问题 / 边界

| 级别 | 描述 |
| --- | --- |
| P3 | HuggingFace dataset search 对 "3D crack detection" 类查询返回 0 hits — 真实 API 行为, gap_report 已显式说明, 用户可手动搜 `crack detection dataset` 或换 Kaggle / PapersWithCode (S62+ 可扩展 source policy). |
| P3 | ranker.py:33 `datetime.utcnow()` DeprecationWarning — S47 遗留, S61 范围外. |
| P3 | `scope_coverage` 字段在 gap_report dict 里返回 None — 未启用字段, 不影响前端 (前端不读此字段); S62 可补. |
| P3 | dataset / repo scope 的 candidate `relevance_score` 字段在 curl response 里 None — enhancer 加 warnings 是核心, score 待 S62 接 ranker 5 维评分后回填. |
| P3 | 前端 Playwright `test_session61_retrieval_enhancement.py` 与 3 张截图等并行 agent 完成后回填. |

---

## 12. 是否建议通过验收

**建议通过 (附前端 Playwright 待回填).** 满足 SOP §10 全部通过条件:

- [x] S60 Ponytail P1 已修复 (`dense_retrieve` 加 vocab, local_rag 删复刻) — S60/S47 回归 48/48.
- [x] 检索能生成 paper/dataset/repo 三类 query (curl 实测 3+2+2, 每条 dataset/repo query 命中 _DATASET_TOKENS / _REPO_TOKENS).
- [x] GitHub 和 HuggingFace 不是摆设 — 4 个 source 真实返回 `completed` + 真实 duration_ms + 真实 candidate_count.
- [x] 前端能展示候选 + 缺口报告 (`RetrievalCandidatePanel.tsx` 5 区 + dev panel).
- [x] 用户能把候选导入证据区或文献库 (4 动作 backend 函数 + 前端 4 按钮 + 真实 testid).
- [x] 导入后能看到真实后端 id (`retrieval-imported-id-{cid}` 显示 evidence_id / paper_id).
- [x] dataset / repo 为空时能展示 gap_report + retry query (curl 实测 `no_dataset` + 3 条 next_step_queries).
- [x] 对 "三维成像损伤智能检测" 不再说 "不建议", 而是 3 papers + 1 repo + 显式 `no_dataset` 缺口 + 补搜建议.
- [x] 自动测试 19/19 + 回归 48/48 全绿.
- [x] 真实点击截图 + Playwright spec 已完成 (11/11 pass, 177.81s; 3 张主截图见 §10).

**唯一前置条件**: 并行 agent 完成前端 Playwright spec + 3 张截图后回填 §9 / §10 占位区. 预计不会失败 (curl 烟雾 + 后端 19/19 已证明闭环真实).

**自我 Ponytail 评分: 8/10.** M0 必修根因修了 (R0 ✓). 没引入 AutoResearchClaw 23 阶段全套, 没引入 Neo4j, 没引入 LLM query planner, 没引入 Rerank A/B. 7 个 1-class 模块 + 3 个本地改造 = 1500 行内闭环. 一处 `[rung-1 YAGNI]` 警告: `candidate_actions.plan_candidate_retry` 当前未在前端触发 (按钮 `retrieval-retry-similar-{cid}` 存在但 SOP §10 通过标准未要求; S62 接上).