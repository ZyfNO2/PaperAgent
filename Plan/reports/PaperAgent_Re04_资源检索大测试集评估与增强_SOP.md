# PaperAgent Re04 资源检索大测试集评估与增强 SOP

> 阶段目标：先把“输入题目 -> 检索论文 / 数据集 / Repo / Baseline 与平行方案候选”这一段做扎实。  
> 本阶段不评估 `difficulty_labels.json`，不做难度 / 周期真值打分，不新增 HumanGate 主流程，不做论文网状引用图。  
> 参考资料：`C:\Users\ZYF\Desktop\Paper\AutoResearchClaw`、`C:\Users\ZYF\Desktop\Paper\academic-research-skills`、`G:\PaperAgent\Plan\PaperAgent_工科学位论文爬取测试集_100篇.md`、Re03 完工与审计报告。

---

## 0. 本轮技术判断

Re03 的方向是对的：它开始拆分 QueryMatrix、Seed Gate、EvidenceReview、RoleClassifier、SourceLedger，并且 Case A/B 的噪声污染已有明显改善。但从代码和报告看，当前问题不是“检索还差一点”，而是“增强模块没有完全接入真实主链路，评估样本太少，真实资源召回仍不稳定”。

关键依据：

- `apps/api/app/services/agents/query_matrix.py:74` 仍然存在 `"machine learning"` fallback，和文件头部“不产生 machine learning fallback”的约束矛盾。
- `apps/api/app/services/agents/retrieval_orchestrator.py:64-67` 记录了 QueryMatrix，但 Round 1 仍调用旧 `multi_round_fetch(parsed_topic, plan)`，没有按 query family 分发真实检索。
- `apps/api/app/services/agents/retrieval_orchestrator.py:81` 明确写着 Round 2 生成的 query 不实际调用 adapter，因此“Dynamic Result Expansion”目前更像日志，不是召回增强。
- `apps/api/app/services/agents/research_agent.py:2549-2680` 主入口仍是 `run_research_agent_re02()`，只在 Re02 链路上插入 citation_expand 和 round_delta，没有真正切到 Re03 5-round orchestrator。
- Re03 完工报告只完整跑了 Case A / B；Case C / D 被推迟到 Re04。当前不能用 2 个 online case 证明资源检索已稳定。
- `test_re03_online_cases.py` 对 Case C/D 只检查旧噪声没有泄漏，没有检查“是否搜到了中文主观题评分 / 多时相遥感作物识别的有效资源”。

本轮推荐方案：先建立可重复评估，再修检索主链路。不要先继续堆新 Agent。

---

## 1. Re03 审计结论

### 1.1 可以保留

- `seed_relevance.py` 的 seed pre-flight gate：保留，不允许用硬编码黑名单处理 AIn't / AGN / cosmic ray 这类噪声。
- `EvidenceReview` 的 core / candidate / needs_manual / rejected 四层结构：保留，并要求所有保留 / 剔除都有中文一句话原因。
- `SourceLedger` 的 per-round / per-adapter 记录：保留，但必须记录真实调用，不允许记录“计划了但没查”的伪增量。
- `literature_role_classifier.py` 的 Baseline / Parallel / Reference / Dataset / Repo 角色分桶：保留，但要以真实候选和证据审查结果驱动。

### 1.2 必须修

1. **Re03 orchestrator 没有接入主链路**  
   当前实际入口仍调用旧 `multi_round_fetch`。Re04 必须新增明确入口 `run_research_agent_re04()` 或将现有 API 切到 `run_5_round_retrieval()`，并用测试证明前端 / API 调用的是新链路。

2. **QueryMatrix 只生成，不负责真实分发**  
   Re04 必须实现 `QueryFamilyDispatcher`：把 core / method_task / object_task / dataset / repo / survey / benchmark / baseline 分别 dispatch 到 arXiv / OpenAlex / Crossref / Semantic Scholar / GitHub / WebSearch 适配器。

3. **Round 2 expansion 没有实际检索**  
   Re04 必须把 `expand_from_round1()` 输出送入 adapter；如果某轮因为配额或断路器跳过，ledger 必须写 `skipped_rate_limited`，不能写 `empty` 或沉默。

4. **OpenAlex 单点失败导致 citation_expand 贫血**  
   按 AutoResearchClaw 的做法，引入 Semantic Scholar fallback。引用扩展顺序建议：OpenAlex references -> Semantic Scholar references/citations -> arXiv title fallback。

5. **测试标准过弱**  
   Case C/D 不应只测“没有出现 old noise”。必须测：论文候选数量、数据集 / Repo 候选、Baseline / Parallel 分桶、无关论文不得进入 core / baseline / parallel。

6. **pytest 环境警告**  
   本轮离线单测 `16 passed`，但出现 `Unknown config option: asyncio_mode`。Re04 预检要确认 pytest-asyncio 是否安装并生效，否则 async online 测试可信度不足。

---

## 2. 评估参考设计

### 2.1 从参考工程提炼的检索原则

来自 AutoResearchClaw：

- `researchclaw/literature/search.py` 使用 OpenAlex -> Semantic Scholar -> arXiv 的跨源检索，失败时尝试 cache fallback。
- `search_papers_multi_query()` 对多个 query 做 union，并在全局去重后按 `citation_count, year` 排序。
- `_deduplicate()` 按 DOI -> arXiv ID -> normalized title 去重，重复项保留 citation_count 更高的版本。
- `researchclaw/prompts/ml.py` 的 search_strategy 要求至少 3 个策略、至少 8 个 query、每个 query 3-6 words，覆盖 core topic / related methods / benchmarks / datasets / foundations / applications。
- `literature_screen` prompt 明确要求拒绝跨领域 false positive，即使共享表面关键词也不能通过。

来自 academic-research-skills：

- `literature_strategist_agent.md` 要求先定义 2-4 个核心概念、同义词、缩写和布尔组合，并记录 exact search strings。
- 文献检索采用多层策略：Boolean search -> Citation chaining -> Forward tracking -> Semantic search。
- 筛选要分 Title/Abstract screening 与更深入审查；保留候选不是问题，但必须有层级、原因和可追溯来源。
- `academic-pipeline` 的 integrity 思路可借用为轻量 gate：引用 / 来源 / 数据必须区分 verified、partial、unverified，不允许把推断写成事实。

### 2.2 Re04 评估对象

只评估资源检索，不评估难度 / 周期：

- 题目解析质量：method / task / object / domain_route / query_atoms。
- 检索计划质量：query families 是否覆盖方法、对象、任务、数据集、Repo、基线、平行论文。
- 真实召回质量：论文、数据集、Repo、Baseline 候选是否够用。
- 分桶质量：Baseline / Parallel / Reference / Dataset / Repo / Rejected 是否合理。
- 噪声控制：无关但表面命中的论文可以留在 long_tail 或 rejected，但不得进入 core / baseline / parallel。
- 证据日志质量：每条候选能回溯到 query、adapter、round、source URL。

明确不评估：

- `difficulty_labels.json`
- 难度准确率、周期邻档准确率、毕业可迭代次数
- 最终论文开题报告质量
- 引用网络图 / 论文-数据集-Repo 关系图

---

## 3. 测试集分层

### 3.1 数据来源

主数据源：

- `G:\PaperAgent\Plan\PaperAgent_工科学位论文爬取测试集_100篇.md`

执行者需要新增转换脚本：

- `apps/api/scripts/build_re04_resource_eval_cases.py`

输出文件：

- `apps/api/tests/fixtures/re04_engineering_resource_cases.jsonl`
- `apps/api/tests/fixtures/re04_smoke_20_ids.txt`
- `apps/api/tests/fixtures/re04_balanced_40_ids.txt`

JSONL 字段：

```json
{
  "id": "ENG-THESIS-074",
  "title": "基于深度学习的混凝土桥梁裂缝检测研究",
  "year": 2021,
  "domain": "土木/交通基础设施损伤检测",
  "source_url": "https://cdmd.cnki.com.cn/Article/...",
  "paperagent_test": "比较适合作为...",
  "active_eval": ["query_plan", "resource_retrieval", "role_bucket", "evidence_ledger"],
  "excluded_eval": ["difficulty", "cycle", "repeatability"]
}
```

该模块不应该：

- 读取或依赖 `difficulty_labels.json`。
- 用难度 / 周期字段计算通过率。
- 把测试集中的预估实验需求当作模型输出真值直接喂给 Agent。
- 改写原始题名或 source_url。

### 3.2 Re04 首批样本

Smoke 20 直接采用原文件第 7 节的推荐样本：

```text
ENG-THESIS-015, ENG-THESIS-016, ENG-THESIS-018, ENG-THESIS-024,
ENG-THESIS-027, ENG-THESIS-028, ENG-THESIS-032, ENG-THESIS-033,
ENG-THESIS-043, ENG-THESIS-046, ENG-THESIS-050, ENG-THESIS-063,
ENG-THESIS-066, ENG-THESIS-074, ENG-THESIS-075, ENG-THESIS-080,
ENG-THESIS-091, ENG-THESIS-092, ENG-THESIS-093, ENG-THESIS-096
```

Balanced 40 在 Smoke 20 基础上补：

```text
ENG-THESIS-002, ENG-THESIS-003, ENG-THESIS-004, ENG-THESIS-005,
ENG-THESIS-010, ENG-THESIS-014, ENG-THESIS-022, ENG-THESIS-035,
ENG-THESIS-040, ENG-THESIS-048, ENG-THESIS-051, ENG-THESIS-058,
ENG-THESIS-060, ENG-THESIS-064, ENG-THESIS-072, ENG-THESIS-073,
ENG-THESIS-079, ENG-THESIS-083, ENG-THESIS-089, ENG-THESIS-100
```

全量 100 只做 nightly / manual eval，不作为本轮每次提交必跑。

---

## 4. 评估指标

### 4.1 Query Plan 指标

| 指标 | 定义 | 合格线 |
|---|---|---:|
| query family 覆盖率 | core / method_task / object_task / dataset / repo / benchmark / baseline 至少 6 类非空 | smoke ≥ 0.90 |
| 禁用泛化 fallback | 不出现 `machine learning` / `deep learning` 作为唯一英文 query atom | 100% |
| 中英 query 可追溯 | 每个英文 query 能回指 method / task / object 至少一轴 | ≥ 0.90 |
| 查询可执行率 | query 不为空、不全中文、长度符合 adapter 限制 | ≥ 0.95 |

### 4.2 Resource Retrieval 指标

| 指标 | 定义 | 合格线 |
|---|---|---:|
| 论文候选非空率 | 每题至少 8 篇 paper-like 候选，或明确 source_gap 原因 | smoke ≥ 0.85 |
| 多源覆盖率 | 每题至少 2 个 paper source 有真实返回，或 ledger 解释限流 / 空结果 | smoke ≥ 0.75 |
| Dataset 候选召回率 | 视觉 / 遥感 / 缺陷 / 医学类题目至少 1 个 dataset 候选或明确 gap | smoke ≥ 0.80 |
| Repo 候选召回率 | CV / DL / SLAM / 检测类题目至少 1 个 GitHub repo 候选或明确 gap | smoke ≥ 0.80 |
| Baseline 候选召回率 | 每题至少 1 个 baseline-like 候选，允许来自 paper 或 repo | smoke ≥ 0.80 |
| Parallel 候选召回率 | 每题至少 2 个 parallel paper 候选，允许 related engineering paper | smoke ≥ 0.75 |

### 4.3 Filter / Role 指标

| 指标 | 定义 | 合格线 |
|---|---|---:|
| 强噪声误入率 | 明显跨领域候选进入 core / baseline / parallel 的比例 | ≤ 0.03 |
| 候选保留透明率 | candidate / long_tail / needs_manual 都有 matched / missing terms | ≥ 0.95 |
| rejected 原因完整率 | 每个 rejected 有中文一句话原因 | 100% |
| Baseline 绑定率 | 工作包建议引用的 baseline_id 必须存在于候选池 | ≥ 0.95 |
| 不硬编码过滤 | 不允许用标题黑名单删除 AIn't / AGN / cosmic ray 等个案 | 100% |

### 4.4 Ledger 指标

| 指标 | 定义 | 合格线 |
|---|---|---:|
| exact search string 记录率 | 每次 adapter 调用记录 query / adapter / round / target_role | 100% |
| skip 原因记录率 | 因限流、断路器、空 query、无 key 跳过时必须记录状态 | 100% |
| 伪 delta 禁止 | 没有真实调用的 round 不得计入 result_count | 100% |
| 原始 dump 留存 | online eval 每题保存 raw JSON 到 `tmp_re04_eval/` | 100% |

---

## 5. Re04 实施任务

### Task 1：评估集转换器

创建：

- `apps/api/scripts/build_re04_resource_eval_cases.py`
- `apps/api/tests/test_re04_eval_dataset_loader.py`

功能：

- 从 `Plan/PaperAgent_工科学位论文爬取测试集_100篇.md` 解析 Markdown 表格。
- 输出 JSONL fixtures。
- 生成 smoke 20 / balanced 40 ID 文件。
- 保留 `title / year / domain / source_url / paperagent_test`。

该模块不应该：

- 调网络。
- 调 LLM。
- 读取 difficulty labels。
- 修改源 Markdown。
- 把 `experiment_need` 直接作为 Agent 已知上下文注入检索。

验收：

- 能解析 100 条样本。
- smoke 20 ID 全部存在于 JSONL。
- URL 保留原始链接。
- `excluded_eval` 中明确包含 difficulty / cycle / repeatability。

### Task 2：Resource Retrieval Eval Harness

创建：

- `apps/api/app/services/agents/eval/resource_retrieval_eval.py`
- `apps/api/tests/test_re04_resource_eval_offline.py`
- `apps/api/tests/test_re04_resource_eval_smoke_online.py`

功能：

- 输入一个 case title，调用真实 `run_research_agent_re04()`。
- 汇总 query plan、candidate_pool、evidence_review、paper_groups、source_ledger。
- 输出单题评估 JSON。
- 输出批量 Markdown 报告。

该模块不应该：

- 用 LLM 自评替代指标计算。
- 因 online adapter 失败直接判 Agent 通过。
- 静默吞掉空结果。
- 把 difficulty / cycle 纳入评分。

验收：

- offline fixture eval 可无网络运行。
- online smoke 支持 `--max-cases 3 / 5 / 20`。
- 每个 case 输出 `resource_status: pass | weak | fail | blocked`。

### Task 3：接入 Re04 主检索链路

创建或修改：

- `apps/api/app/services/agents/research_agent.py`
- `apps/api/app/services/agents/retrieval_orchestrator.py`
- `apps/api/app/services/agents/query_matrix.py`
- `apps/api/app/services/agents/result_expander.py`

要求：

- 新增 `run_research_agent_re04()`，不要继续把 Re04 伪装成 Re02。
- API / 前端若使用最新 Agent，必须显式调用 Re04 入口。
- `run_5_round_retrieval()` 必须真实 dispatch query family。
- Round 2 dynamic expansion 必须真实调用 adapter。
- 删除 `machine learning` fallback；无法解析时返回 `needs_clarification` 或使用 raw topic 的英文翻译 / LLM parse 输出，不能用泛化词。

该模块不应该：

- 只记录 query_matrix 但不检索。
- 只改测试不改入口。
- 在 `multi_round_fetch` 里继续堆临时 if 分支。
- 为某个题目硬编码 dataset / baseline。
- 用固定模板生成“复现 baseline + 加注意力机制”工作包。

验收：

- `rg "run_research_agent_re04" apps/api` 能看到 API 或服务入口调用。
- `run_research_agent_re04("基于深度学习的混凝土桥梁裂缝检测研究")` 的 ledger 中出现至少 4 类 query family 的真实调用。
- Round 2 delta 不再只有 `n_queries`，而是包含 adapter result_count。

### Task 4：Semantic Scholar fallback

创建：

- `apps/api/app/services/retrieval/adapters/semantic_scholar_search.py`
- `apps/api/tests/test_re04_semantic_scholar_adapter.py`

参考：

- `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw\researchclaw\literature\semantic_scholar.py`
- `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw\researchclaw\literature\search.py`

功能：

- 支持 query search。
- 支持按 paperId / DOI / title 做 citation/reference fallback。
- 返回统一字段：`title, abstract, year, venue, citation_count, doi, arxiv_id, url, source`.
- 适配器失败时写 ledger，不得静默。

该模块不应该：

- 要求必须有 API key 才能运行基本搜索。
- 把 Semantic Scholar 失败当作整体失败。
- 覆盖 OpenAlex / arXiv 的已有结果。

验收：

- 无 key 情况下至少能返回 clear error / skipped_without_key / rate_limited 状态。
- 有 key 或公开接口可用时，能进入真实候选池。
- Citation expand 顺序可配置。

### Task 5：跨源去重与排序

创建或增强：

- `apps/api/app/services/agents/resource_deduper.py`
- `apps/api/tests/test_re04_resource_deduper.py`

参考 AutoResearchClaw：

- DOI 优先。
- arXiv ID 次之。
- normalized title 兜底。
- 重复项合并 source / query / round provenance。
- 排序先 role / relevance tier，再 citation_count，再 year，不要单纯按分数。

该模块不应该：

- 只按标题完全相等去重。
- 丢失多个来源的 provenance。
- 用 citation_count 把离题高引论文推到 core。

验收：

- 同一论文从 arXiv + OpenAlex + Semantic Scholar 命中时只保留 1 个 candidate。
- provenance 中保留所有来源。
- 离题高引论文不能越过 relevance gate。

### Task 6：LLM Evidence Review 提示词收紧

修改：

- `apps/api/app/services/agents/prompts/*.py`
- `apps/api/app/services/agents/evidence_review.py`

提示词硬规则：

```text
你是工程学位论文选题资源审查员。你的任务不是少给候选，而是把候选分层：
1. core：与题目方法/任务/对象至少两轴强相关，可作为开题直接证据。
2. baseline：可复现基础方案，可以来自论文或工程 Repo。
3. parallel：同对象/同任务/相近工程场景的平行方案，用于学习“Baseline + 模块”的写法。
4. dataset：数据集或数据集论文。
5. repo：工程实现或复现仓库。
6. long_tail：弱相关但可能启发，不进入开题核心。
7. rejected：跨领域或仅表面关键词命中。

不要因为候选不完美就删除。只要与参考文献、数据集、Repo、工程对象存在可解释关系，就保留到 candidate/long_tail，并写明关系。
但不得把跨领域 false positive 放进 core/baseline/parallel。
必须输出 matched_terms、missing_terms、relation_reason、source_confidence。
禁止编造不存在的数据集、指标、作者结论。
```

该模块不应该：

- 在 LLM 失败时静默用 heuristic 生成看似完整的结论。
- 把 prompt 中的示例标题写进候选。
- 让工作包建议脱离 candidate_id。
- 用“注意力机制”作为默认创新模块。

验收：

- LLM JSON parse 失败时返回 `llm_blocker`，Low-bar 不得 pass。
- Work package 每条建议必须绑定 `baseline_candidate_id` 和至少 1 个 `parallel_candidate_id` 或 `dataset_candidate_id`。
- 没有 baseline 时只能输出“请先选 baseline”，不能生成完整工作包。

---

## 6. 测试用例

### 6.1 Offline 单元测试

必须新增并通过：

```bash
python -m pytest ^
  apps/api/tests/test_re04_eval_dataset_loader.py ^
  apps/api/tests/test_re04_resource_deduper.py ^
  apps/api/tests/test_re04_resource_eval_offline.py ^
  apps/api/tests/test_re04_semantic_scholar_adapter.py -q
```

通过线：

- 所有测试通过。
- 不出现 `Unknown config option: asyncio_mode`；如仍出现，先修测试环境配置。

### 6.2 Online Smoke 5

首批 online 只跑 5 个，节省配额但覆盖足够广：

| id | title | 重点 |
|---|---|---|
| ENG-THESIS-074 | 基于深度学习的混凝土桥梁裂缝检测研究 | 土木裂缝，必须搜到裂缝检测论文 / 数据集 / repo 候选 |
| ENG-THESIS-080 | 基于三维重建裂缝损伤检测算法研究 | 3D 重建，不能退化成普通 2D YOLO |
| ENG-THESIS-028 | 基于YOLOv5的绝缘子检测与缺陷识别方法研究 | 电力巡检，必须搜到 insulator / defect / power line 相关资源 |
| ENG-THESIS-092 | 海上风机叶片缺陷检测及分类 | 能源装备，必须识别风机叶片 / defect / dataset 或 gap |
| ENG-THESIS-016 | 基于深度学习的视觉SLAM语义地图的研究 | SLAM，必须搜到 SLAM / semantic mapping / dataset 或 repo |

命令建议：

```bash
python -m pytest apps/api/tests/test_re04_resource_eval_smoke_online.py -q --re04-cases 5
```

每题验收：

- paper-like candidates >= 8，或 `source_gap` 写清楚具体 adapter / query 失败原因。
- 至少 1 个 baseline-like 候选，或明确 `baseline_gap`。
- 至少 1 个 repo 或 dataset 候选，若没有必须给出可复查的检索 query。
- rejected 中允许有噪声，但 core / baseline / parallel 不得出现明显跨领域噪声。
- ledger 必须包含 exact search strings。

### 6.3 Balanced 40

通过 Online Smoke 5 后再跑 balanced 40。执行者不得跳过 Smoke 5 直接报 balanced 40。

输出：

- `G:\PaperAgent\Plan\reports\PaperAgent_Re04_balanced40_eval.md`
- `G:\PaperAgent\tmp_re04_eval\balanced40_summary.json`
- 每题 raw dump：`G:\PaperAgent\tmp_re04_eval\<case_id>.json`

Balanced 40 合格线：

- `resource_status in pass/weak` 的比例 >= 0.80。
- `fail` case 必须附失败链路：parse / query_plan / adapter / filter / synthesis。
- 强噪声进入 core / baseline / parallel 的 case 数 <= 1。
- 不能出现 10 个以上 case 共用同一组泛化候选。

---

## 7. 完工报告硬性格式

完工报告写到：

- `G:\PaperAgent\Plan\PaperAgent_Re04_完工报告.md`

必须包含：

1. **代码接线证明**：Re04 入口实际被 API / service 调用的文件与行号。
2. **评估集构建结果**：100 条解析、Smoke 20、Balanced 40。
3. **离线测试结果**：命令 + 通过数 + 警告。
4. **Online Smoke 5 结果表**：每题 paper / dataset / repo / baseline / parallel 数量。
5. **失败案例链路分析**：至少列 top 5 失败点，不允许只写“网络原因”。
6. **SourceLedger 摘要**：每个 adapter 的 call / ok / empty / skipped / rate_limited。
7. **保留 / 剔除审计表**：中文原因；paper title 可英文。
8. **下一阶段建议**：只允许围绕资源检索继续增强，不得突然扩展到难度真值或 HumanGate。

完工报告不应该：

- 只贴测试通过，不给 raw dump 路径。
- 用“已实现”替代验收数据。
- 把 Case A/B 的结论复用到 100 篇测试集。
- 把 difficulty / cycle 指标写成已验收。

---

## 8. 最终验收通过条件

Re04 可以通过，必须同时满足：

- 代码层：Re04 主链路真实接入，不再只是 Re03 模块单测。
- 评估层：100 篇 JSONL 构建完成，Smoke 20 / Balanced 40 可运行。
- 检索层：Online Smoke 5 全部完成，至少 4/5 为 `pass` 或 `weak`，且无强噪声进入 core / baseline / parallel。
- 日志层：每个 online case 有 raw dump、ledger、query family、保留 / 剔除原因。
- 测试层：新增 Re04 offline 测试全过；pytest async 配置警告消除或在报告中解释并修复。
- 边界层：不纳入 `difficulty_labels.json`，不评估难度 / 周期。

如不满足，不能进入下一阶段；只能继续 Re04-fix。

---

## 9. Re04 后续但暂不实现

- 引用网络图：论文 -> 引用论文 -> 数据集 -> Repo 的知识网。
- HumanGate：人工选择 baseline 后再生成工作包。
- 难度 / 周期真值评估：等 `difficulty_labels.json` 对齐后另开 Re05。
- 面试项目化包装：等资源检索稳定后再做。

