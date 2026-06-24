# Session 50 验收报告 — RAG 评估指标与回归基线

## 一、目标
为 paper-library RAG (S47 paper_qa + S48 claim_grounding) 增加量化评估:
- **指标层**: 检索质量 + 答案质量 + 系统质量
- **基线层**: 跑一次 eval 存为 baseline, 后续 diff 检测回归
- **集成层**: 4 个端点, 前端 / 测试 / 面试均可调

## 二、关键产物

### 1. Fixtures (15 KB)
- `apps/api/tests/fixtures/paper_library_eval/`
  - 5 个 paper txt (YOLO 缺陷 / 医疗 / 推荐 / PINN / KG)
  - `metadata.json` (paper_id / title / arxiv_id / known_*)
  - `questions.jsonl` (15 questions, 2-3/paper, 含 ground_truth_chunk_types)

### 2. Schemas (130 行)
- `apps/api/app/schemas_paper_rag_eval.py`
  - `RetrievalMetrics` (recall@5 / MRR / NDCG@5 / hit_rate)
  - `AnswerMetrics` (citation_precision / evidence_coverage / unsupported_claim_rate / faithfulness)
  - `SystemMetrics` (latency_p50/p95 / total_questions / fallback_rate)
  - `RagEvalItem` / `RagEvalReport`
  - Request/Response models for 4 endpoints

### 3. Metrics (240 行)
- `apps/api/app/services/paper_library/eval_metrics.py`
  - 7 个 pure functions + aggregate
  - 全 deterministic, 边界情况 (空集 / 0 分母) 处理
  - 无随机种子, 无 LLM 调用

### 4. Pipeline (260 行)
- `apps/api/app/services/paper_library/rag_eval_pipeline.py`
  - `load_eval_set` (metadata + questions)
  - `heuristic_retrieve` (关键词 overlap + chunk_type 权重)
  - `heuristic_answer` (兜底, 不调 LLM)
  - `run_eval` (per-question eval + 聚合)
  - `seed_library_from_fixtures` (fixtures → project storage, 供测试用)

### 5. Baseline (110 行)
- `apps/api/app/services/paper_library/eval_baseline.py`
  - `save_baseline` (RagEvalReport → JSON)
  - `load_baseline` (默认 `data/paper_library_eval/baseline.json`)
  - `diff_against_baseline` (per-metric delta + regressions)
  - `REGRESSION_THRESHOLDS` (召回 -5% / 不支持率 +5% / latency +100ms 等)

### 6. 端点 (4 个, 加入 `apps/api/app/api/v1/paper_library.py`)
- `POST /api/v1/projects/{project_id}/paper-library/eval/seed-library`
- `POST /api/v1/projects/{project_id}/paper-library/eval/run`
- `GET  /api/v1/projects/{project_id}/paper-library/eval/baseline`
- `POST /api/v1/projects/{project_id}/paper-library/eval/baseline`

### 7. 增强 / 修改
- `apps/api/app/services/paper_library/chunker.py`: 兼容 `##` 章节前缀 (用于 fixtures)
- `apps/api/app/services/rag_evaluator.py`: 加 S34 vs S50 关系注释 (并行存在, 不共享代码)

### 8. Tests (39 个, 全 PASSED)
- `apps/api/tests/test_session50_rag_eval.py`
- 覆盖: 5 个 metric × 多个边界 + 聚合 + 端到端 pipeline + baseline roundtrip + 4 端点 + 退化检测

## 三、测试结果

| 测试套 | 通过 | 失败 | 总数 |
|---|---|---|---|
| Session 50 (新) | 39 | 0 | 39 |
| Session 46-50 | 190 | 0 | 190 |
| 全套 (apps/api/tests/) | 776 | 0 | 776 (含 1 skip) |

## 四、首基线 (concrete numbers)

来自 `data/paper_library_eval/baseline.json` (5 papers / 15 questions):

| 指标 | 值 | 方向 |
|---|---|---|
| recall_at_5 | 0.6778 | ↑ |
| mrr | 0.7556 | ↑ |
| ndcg_at_5 | 0.7312 | ↑ |
| hit_rate | 1.0 | ↑ |
| citation_precision | 1.0 | ↑ |
| evidence_coverage | 0.8333 | ↑ |
| unsupported_claim_rate | 0.0 | ↓ |
| faithfulness | 1.0 | ↑ |
| latency_p50_ms | 0.14 | ↓ |
| latency_p95_ms | 0.19 | ↓ |
| fallback_rate | 0.0 | ↓ |

注: recall@5=0.68 不为 1.0 是因为 fixtures 的 ground_truth_chunk_types 包含
`["experiment","method"]` 2 个 type, 而 heuristic retrieve top-5 不一定
同时命中两者 → 真实场景, 非 bug.

## 五、S50 vs S34 关系 (并行存在)

| 维度 | S34 rag_evaluator | S50 paper-library eval |
|---|---|---|
| 对象 | RetrievalCandidate (paper/dataset/repo/note) | PaperChunk |
| Ground truth | evidence_id set | ground_truth_chunk_types list |
| 输出 | RagEvalReport (paper/dataset/repo coverage) | RagEvalReport (retrieval/answer/system) |
| Baseline | 无 (面试 demo) | baseline.json + diff + regressions |
| 用途 | 检索 skill 端到端验证 | 论文库问答回归基线 |

**结论**: S34/S50 schema 不同 (candidate vs chunk), fixture 不同, 重构成本 > 收益, 故保持并行.

## 六、面试可讲点

- 7 个 RAG 指标各自含义 + 边界 (空集 / 0 分母)
- 为什么 heuristic 不用 LLM: deterministic + cost
- chunker 章节正则如何兼容 `##` 前缀
- 回归阈值 5% 是经验值 (可调)
- Baseline + diff + regression list 形成完整 CI 闭环

## 七、commit

`0491ddc6` — Session 50: RAG 评估指标与回归基线 (5 fixtures + 15 questions + baseline diff)
