# Session 34 — RAG Hybrid / Rerank / Eval 验收报告

**日期:** 2026-06-21
**分支:** master

---

## 1. 摘要

Session 34 为「面试级 RAG 检索评估与 Hybrid / Rerank 设计」冲刺，将既有 `CandidateResource` 检索流包装为可向面试官完整讲解的 RAG 流水线。核心交付物：

- **5 个 Pydantic Schema**（`schemas_rag_eval.py`）— `RetrievalCandidate` 扩展、`RagPipelineConfig`（5 因子权重 + 4 top_k + RRF k + 2 阈值）、`RagEvalReport`（8 评估指标）、`FailureCase`（5 类型）、`RagPipelineRequest/Response`
- **6 步 RAG Pipeline**（`services/rag_pipeline.py`）— sparse_retrieve（mock BM25 Jaccard）→ dense_retrieve（mock embedding proxy）→ rrf_fuse（Cormack 2009）→ rerank_candidates（5 因子加权）→ URL unverified *0.4 硬惩罚 → top_k_final
- **8 维评估器**（`services/rag_evaluator.py`）— Recall@5/10/20、MRR、Citation Coverage、Evidence Precision、URL Verified Rate、Candidate→Evidence Rate、3 类型覆盖率 + 5 失败案例检测器
- **2 个 API 端点**（`api/v1/one_topic.py`）— `POST /{project_id}/rag/pipeline` + `GET /{project_id}/rag/eval-report`
- **25 + 8 = 33 条测试**全部通过
- **1 份面试讲解文档** — `docs/interview/RAG_Design_Explainer.md`（10 节、175 行）

Session 34 把「非向量 7 层检索架构」从概念升级为可量化的 4 层可测试 RAG 流水线，并为 Session 33 QA 卡片 RAG 类（Q1-Q5）的「评估方法」缺口补上 Recall@K / MRR / Precision 等量化指标。

---

## 2. 实施明细

### 2.1 Schema 层（`apps/api/app/schemas_rag_eval.py`）

| Schema | 字段要点 | 用途 |
|--------|----------|------|
| `RetrievalCandidate` | 扩展 S14：`sparse_score` / `dense_score` / `fused_score` / `rerank_score` 4 层评分；`matched_keywords` / `rerank_reasons` 可解释；`url_verified` + `evidence_potential` | RAG 流水线统一候选形态 |
| `RagPipelineConfig` | 4 个 top_k（sparse/dense/fused/final）+ RRF k + 5 个 rerank 权重（keyword 0.35 / url 0.20 / repro 0.25 / type 0.10 / recency 0.10）+ 2 阈值（min_keyword_overlap 0.3 / min_rerank_score 0.1） | 可配置超参数，面试可现场调权重看排序变化 |
| `RagEvalReport` | Recall@5/10/20、MRR、citation_coverage、evidence_precision、url_verified_rate、candidate_to_evidence_rate、paper/dataset/repo 3 类覆盖率、failure_cases | 自动化回归 + 面试量化指标展示 |
| `FailureCase` | 5 类型：`no_dataset` / `no_repo` / `url_unverified` / `low_relevance` / `type_imbalance` | 失败模式结构化记录 |
| `RagPipelineRequest` / `Response` | 支持 `config` 覆盖与 `query_plan_override` | API 入参出参 |

`extra="forbid"` 严格模型，禁用未声明字段；所有数值字段带 `ge` / `le` 边界，便于在 Pydantic 校验阶段捕获异常配置。

### 2.2 Pipeline 层（`apps/api/app/services/rag_pipeline.py`）

6 步流水线，全部纯函数 + 模块级状态（`reset_rag_state()` 测试可清空）：

1. **sparse_retrieve** — Mock BM25：`_keyword_overlap_score` 用 Jaccard 系数计算 query_keywords 与候选 title + abstract 的 token overlap（中英分词分别处理：英文按 `[a-z]+`，中文按字）。返回 `(candidate, score)` 排序列表。
2. **dense_retrieve** — Mock embedding proxy：同 sparse 但加权 `year`（年份越新分越高），模拟 dense 向量「语义相近 + 时效新」偏好。
3. **rrf_fuse** — Reciprocal Rank Fusion（Cormack et al. 2009）：`score = Σ 1 / (k + rank_i)`，k 默认 60。RRF 只用 rank 不用绝对分，对不同 scale 的 retriever 更鲁棒。
4. **rerank_candidates** — 5 因子加权：
   - `keyword_match` 0.35 — 关键词覆盖
   - `reproducibility` 0.25 — 有 repo / dataset / DOI 的优先级
   - `url_verified` 0.20 — URL 验证状态
   - `type_coverage` 0.10 — 鼓励 dataset / repo 出现，避免 paper 单一化
   - `recency` 0.10 — 年份权重
5. **URL unverified *0.4 硬惩罚** — 在 rerank 完成后乘以 0.4（hard penalty，不是软信号），让未验证 URL 显著下沉。
6. **top_k_final** — 按 rerank_score 截断输出。

返回 `RagPipelineResponse`，附带 rerank_reasons 解释每一项为何得到该分（可解释性）。

### 2.3 Evaluator 层（`apps/api/app/services/rag_evaluator.py`）

**8 项评估指标：**

| 指标 | 计算方式 |
|------|----------|
| Recall@5 / @10 / @20 | 命中已知相关 candidate 的比例，按 top_k 截断 |
| MRR | 第一个相关 candidate 的倒数排名均值 |
| Citation Coverage | rerank 后 candidate 中带 DOI / arxiv_id / repo_full_name / dataset_slug 的比例 |
| Evidence Precision | candidate 中 evidence_potential=high 的比例 |
| URL Verified Rate | url_verified=True 的比例 |
| Candidate→Evidence Rate | 后续晋升为 evidence 的 candidate 比例（与 S25 WorkspaceBoard 联动） |
| Paper / Dataset / Repo Coverage | 3 类各占 top_k_final 的比例 |

**5 项失败案例检测器：**

| case_type | 触发条件 |
|-----------|----------|
| `no_dataset` | dataset_coverage == 0 |
| `no_repo` | repo_coverage == 0 |
| `url_unverified` | url_verified_rate < 0.5 |
| `low_relevance` | 平均 keyword_overlap < 0.3 |
| `type_imbalance` | 任一类覆盖率 > 0.8（垄断） |

### 2.4 API 层（`apps/api/app/api/v1/one_topic.py`）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/{project_id}/rag/pipeline` | POST | 在最近一次 retrieval run 上执行 RAG pipeline，可覆盖 config |
| `/{project_id}/rag/eval-report` | GET | 返回最近一次 eval report（RagEvalReport） |

两个端点共用 `_RUNS` 模块级状态（与现有 retrieval run 存储一致），测试通过 `reset_rag_state()` 隔离。

---

## 3. 测试结果

### 3.1 后端测试（25 条，全部通过）

测试文件：`apps/api/tests/test_session34_rag_pipeline_eval.py`（441 行）

| 类别 | 测试数 | 说明 |
|------|--------|------|
| Schema 校验（`RetrievalCandidate` / `RagPipelineConfig` / `RagEvalReport` / `FailureCase`） | 6 | extra="forbid" 边界 + 字段范围 + 5 failure_case 类型 |
| Sparse Retriever（mock BM25 Jaccard） | 4 | 中文 / 英文 / 混合关键词；空输入；排序稳定性 |
| Dense Retriever（mock embedding + year） | 3 | 年份权重；中英 token；空候选 |
| RRF Fusion | 3 | 两路融合公式正确；k 参数生效；空输入 |
| 5 因子 Rerank | 4 | 权重归一化；URL unverified *0.4 硬惩罚；type_coverage 提权；min_rerank_score 过滤 |
| Evaluator 8 指标 | 3 | Recall@K / MRR / Citation Coverage / type coverage 计算正确 |
| 5 Failure Case 检测器 | 2 | 各自触发条件正确；互斥性 |
| **合计** | **25** | **全部通过** |

### 3.2 Playwright E2E 测试（8 条，全部通过）

测试文件：`apps/web/e2e/test_one_topic_session34_rag_eval.py`（232 行）

| # | 用例 | 验证点 |
|---|------|--------|
| 1 | test_rag_pipeline_endpoint_exists | `POST /rag/pipeline` 端点可调用 |
| 2 | test_rag_pipeline_returns_candidates | 响应含 candidates 列表 |
| 3 | test_rag_eval_report_endpoint | `GET /rag/eval-report` 返回结构化报告 |
| 4 | test_rag_pipeline_with_config_override | 自定义 config 生效 |
| 5 | test_rag_pipeline_runs_on_real_topic | 真实 Topic 上端到端可走通 |
| 6 | test_eval_report_has_8_metrics | 8 指标字段齐全 |
| 7 | test_failure_cases_in_report | failure_cases 字段含正确类型 |
| 8 | test_rag_pipeline_idempotent | 同输入两次调用结果一致 |

### 3.3 整体测试统计

| 类别 | 数量 |
|------|------|
| Session 34 新增后端测试 | 25 |
| Session 34 新增 Playwright E2E | 8 |
| **S34 新增合计** | **33** |
| 既有测试（回归保持） | 388+ 维持全绿 |

---

## 4. 关键设计决策

### 4.1 Mock dense / sparse 而非真实向量库

**决策：** 当前 dense 用「标题+摘要 token overlap + 年份权重」作为 embedding 代理；sparse 用 Jaccard 关键词 overlap 作为 BM25 代理。

**原因：**
- 学术文献检索的难点不在 embedding 模型本身，而在**多源 / 别名 / 版本**问题（如同一个方法在不同论文里有 3-4 个名字）
- Mock 实现使 8 项评估指标在无网络依赖下可重复、可 CI
- **接口预留**：`_tokenize` / `_keyword_overlap_score` 均为纯函数，真实 BM25 / sentence-transformers 接入只需替换这两个函数，pipeline 其他步骤不变
- 面试官问「为什么不接 Milvus / Qdrant」时，可答：「学术文献在 baseline 上的主要瓶颈是别名归一化与多源对齐，纯向量召反而是次要的；我们 RAG 评估更看重 rerank 层的可解释性」

### 4.2 RRF 而非加权融合

**决策：** 两路 sparse / dense 融合用 RRF（Cormack et al. 2009），而非 `α * sparse + (1-α) * dense`。

**原因：**
- RRF 只用 rank 不用绝对分，对不同 scale 的 retriever 更鲁棒（BM25 与 cosine similarity 分值范围差几个数量级）
- k=60 是 Cormack 原文的默认值，文献可追溯
- 加权融合需要调 α，且对 outlier 敏感

### 4.3 URL unverified * 0.4 硬惩罚

**决策：** URL 未验证的候选在 rerank 完成后乘 0.4（hard penalty），不是软信号。

**原因：**
- URL 未验证意味着「可重现性不可证」 — 在工程意义上等价于候选无效
- 软信号（如加 0.1 权重）会被其他高分项盖过，无法可靠下推
- 0.4 是经验值：足以让 URL 未验证项掉到 top_k_final 之外，但仍保留在 RAG 输出供后续 manual review

### 4.4 type_coverage 作为 rerank 因子

**决策：** 5 因子之一是 `type_coverage`（paper / dataset / repo 多样性），权重 0.10。

**原因：**
- 学术论文检索的最大陷阱是「paper 一家独大」 — 数据集 / 代码库被淹没
- 题目若涉及可复现性，必须出现 repo / dataset，否则 Evidence Promotion Gate 会卡死
- 0.10 权重是关键：足以打破 paper 垄断，但不喧宾夺主于 keyword_match（0.35）

### 4.5 5 因子权重全部外置为 Config

**决策：** `RagPipelineConfig` 暴露全部 5 个权重 + 4 个 top_k + RRF k + 2 阈值。

**原因：**
- 面试可现场 demo「改 w_url_verified 从 0.20 到 0.50，看排序变化」
- 面试官问「如何调参」时，可直接展示 config 切换
- 默认值是经验最优，但不绑定 — 不同领域（CV vs NLP vs RL）应有不同侧重

### 4.6 Failure Cases 结构化

**决策：** 5 类失败案例结构化为 `FailureCase`（case_type / description / affected_candidates）。

**原因：**
- 便于自动化回归（连续跑 N 个 topic，看 failure case 分布变化）
- 便于面试展示（直接打印 failure_cases 列表）
- `affected_candidates` 提供反查链路，调试时可定位具体哪个候选触发了失败

---

## 5. 面试叙事（与 `RAG_Design_Explainer.md` 对齐）

### 5.1 一句话定位

> 「TopicPilot-CN 的 RAG 不是单纯的向量召回，而是 4 层可测试流水线：QueryPlan → Sparse → Dense → RRF → Rerank，每层都有可解释的中间产物与评估指标。」

### 5.2 为什么不用单一向量库

学术文献检索与开放域 QA 不同：
1. **多源 / 别名**：同一方法在不同论文里有 3-4 个名字（YOLO / You Only Look Once，单向量召回命中率低）
2. **可重现性优先**：URL 验证 > 文本相似度，未验证 URL 的论文等同于无效证据
3. **类型多样**：paper / dataset / repo 三类候选，召回后需 rerank 平衡

### 5.3 流水线（4 层）

```
QueryPlan (S24) → Sparse (BM25) → Dense (Embedding proxy) → RRF → Rerank (5-factor) → top_k_final
                                                                       ↓
                                                              URL unverified *0.4 硬惩罚
                                                                       ↓
                                                              RagEvalReport (8 metrics)
```

### 5.4 5 因子 Rerank 权重

| 因子 | 权重 | 触发逻辑 |
|------|------|----------|
| keyword_match | 0.35 | query 与 title+abstract 关键词覆盖 |
| reproducibility | 0.25 | 有 repo_full_name / dataset_slug / DOI 优先 |
| url_verified | 0.20 | URL 已验证优先（叠加 *0.4 硬惩罚） |
| type_coverage | 0.10 | 提升 paper 单调列表外的 dataset / repo |
| recency | 0.10 | 年份越近分越高 |

### 5.5 8 项评估指标

- **Recall@K**（@5/@10/@20）— 命中已知相关候选比例
- **MRR** — 首个相关候选的倒数排名
- **Citation Coverage** — 候选中带 DOI / arxiv / repo / dataset 标识的比例
- **Evidence Precision** — evidence_potential=high 的比例
- **URL Verified Rate** — url_verified=True 的比例
- **Candidate→Evidence Rate** — 后续晋升为 evidence 的比例（与 S25 联动）
- **Type Coverage** — paper / dataset / repo 3 类各占比例

### 5.6 5 类失败案例

`no_dataset` / `no_repo` / `url_unverified` / `low_relevance` / `type_imbalance` — 全部结构化为 `FailureCase`，便于回归与展示。

---

## 6. 遗留风险与下一步

| # | 风险 / 待办 | 说明 | 建议 |
|---|-------------|------|------|
| 1 | **Mock dense / sparse 与真实向量库差距未量化** | 当前用 token overlap 模拟 embedding，真实 sentence-transformers 接入后指标会变化 | 在 RAG_Design_Explainer 中明确标注「Mock 阶段」，并预留真实模型接入的对照实验 |
| 2 | **Recall@K 需要 ground truth** | 当前若 topic 没有标注相关候选，Recall=0，无法反映真实质量 | 引入 ground truth 标注流程（人工标注 5-10 个典型 topic 作为 baseline） |
| 3 | **5 因子权重为经验值** | 0.35 / 0.20 / 0.25 / 0.10 / 0.10 是合理起点，但未在多 topic 上扫参 | 后续可用 `scripts/full_smoke.py` 的多 topic 跑批，统计不同权重组合下的 MRR |
| 4 | **Candidate→Evidence Rate 需要 S25 联动** | 当前评估器假设 candidate 后续会晋升为 evidence，但实际晋升路径在 S25 WorkspaceBoard | 加一个端到端集成测试：从 retrieval → RAG pipeline → evidence promotion → 回算 rate |
| 5 | **前端尚未可视化 RAG 报告** | `RagEvalReport` 仅有 API 端点，UI 暂未渲染 | 下一阶段可在 OneTopic 前端新增「RAG Eval」面板，展示 8 指标 + failure cases |
| 6 | **RAG_Design_Explainer.md 仅 10 节** | 已涵盖核心问答，但缺与 LangGraph / Agent Memory 的对比 | 若面试追问 RAG vs Agent 边界，可在文档追加 1 节 |

---

## 结论

Session 34 完成全部目标：5 个 Pydantic Schema + 6 步 RAG Pipeline + 8 维评估器 + 2 个 API 端点 + 25 条后端测试 + 8 条 Playwright E2E + 1 份 175 行面试讲解文档全部交付，所有测试通过。项目从「功能性 RAG」升级为「可量化、可解释、可面试讲解的 RAG 流水线」，为 Session 33 的 QA 卡片 RAG 类（Q1-Q5）补上 Recall@K / MRR 等量化指标的缺口，并预留真实向量库的接入点。