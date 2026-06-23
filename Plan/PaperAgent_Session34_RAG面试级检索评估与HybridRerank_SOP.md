# PaperAgent Session 34 SOP：RAG 面试级检索评估与 Hybrid/Rerank 设计

> 日期：2026-06-21  
> 前置：S24 已有 CandidateResource，S31 已有全链路 baseline。  
> 本轮目标：把“候选资源检索”升级成面试可讲的 RAG Pipeline，补 Hybrid Search、Rerank、Evaluation 的设计和最小实现。

---

## 1. 面试解释

### 面试官可能会问

```text
你的 RAG 为什么不是简单向量库？
怎么保证召回质量？
为什么需要 rerank？
怎么评估 RAG？
RAG 找错了怎么办？
```

### 为什么需要这么改

公司面经和 Agent/RAG 项目实战资料都强调：面试官已经不满足于“我用了向量库”。一个 RAG 项目要能讲清分块、召回、重排、评估和失败降级。PaperAgent 当前已有 CandidateResource，但还需要把候选生成包装成可配置、可评估的 RAG 流程。

### PaperAgent 的回答

```text
PaperAgent 的 RAG 分三层：
1. QueryPlan 根据用户确认关键词生成 paper/dataset/repo 三类 query；
2. Retriever 同时支持 sparse/dense/mock 三类召回；
3. Reranker 根据关键词匹配、URL 可用性、复现信号、资源类型覆盖进行重排；
4. Evaluator 用 Recall@K、Citation Coverage、Evidence Precision 评估结果。
```

---

## 2. 实现范围

新增：

```text
apps/api/app/schemas_rag_eval.py
apps/api/app/services/rag_pipeline.py
apps/api/app/services/rag_evaluator.py
apps/api/tests/test_session34_rag_pipeline_eval.py
apps/web/e2e/test_one_topic_session34_rag_eval.py
docs/interview/RAG_Design_Explainer.md
```

可先不接真实向量库，用 mock dense / sparse 结果模拟 Hybrid Search。

---

## 3. 核心模型

```text
RetrievalCandidate
  candidate_id
  kind
  title
  url
  source
  query_id
  sparse_score
  dense_score
  fused_score
  rerank_score
  matched_keywords[]
  evidence_potential

RagEvalReport
  recall_at_k
  mrr
  citation_coverage
  evidence_precision
  url_verified_rate
  candidate_to_evidence_rate
  failure_cases[]
```

---

## 4. Pipeline

```text
QueryPlan
  -> SparseRetriever(BM25/mock keyword)
  -> DenseRetriever(embedding/mock semantic)
  -> RRF Fusion
  -> Reranker
  -> CandidateResource
  -> RagEvalReport
```

---

## 5. UI 改造

在候选资源页增加：

```text
检索策略标签：keyword / dense / hybrid；
重排解释：为什么排在前面；
评估面板：Recall@K / Coverage / URLVerified；
失败案例：没有数据集、没有代码、URL 失败。
```

---

## 6. 测试

后端：

```text
1. QueryPlan 能生成三类 query；
2. sparse/dense 结果可融合；
3. RRF 排序稳定；
4. rerank_score 改变排序；
5. url_unverified 降权；
6. paper/dataset/repo 覆盖率可计算；
7. RagEvalReport 可序列化；
8. 无候选时返回 failure_case；
9. S24 CandidateResource 不回退；
10. S31 baseline 不回退。
```

Playwright：

```text
S34-PW-1：候选页显示 Hybrid/Rerank 标签；
S34-PW-2：候选卡显示排序理由；
S34-PW-3：评估面板显示 Recall@K / Coverage；
S34-PW-4：切换检索策略后候选顺序变化；
S34-PW-5：URL 未验证资源降权；
S34-PW-6：空结果显示失败建议；
S34-PW-7：RAG 面试解释文档存在；
S34-PW-8：S31 全链路不回退。
```

---

## 7. 验收标准

```text
1. RAG Pipeline 结构明确；
2. Hybrid Search / Rerank 即使是 mock 也有可测合同；
3. RAG EvalReport 可生成；
4. UI 能解释排序原因；
5. docs/interview/RAG_Design_Explainer.md 可用于面试讲解；
6. 后端测试通过；
7. Playwright 通过；
8. 完工报告包含“面试解释”。
```

---

## 8. 完工报告

```text
Plan/reports/Session_34_RAG_Hybrid_Rerank_Eval_验收报告.md
```

