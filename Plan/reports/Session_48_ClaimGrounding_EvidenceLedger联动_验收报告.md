# Session 48 验收报告：RAG ↔ Evidence Ledger 联动与 Claim Grounding

**Commit**: `cc845f9d` (worktree `worktree-session48-claim-grounding`)
**新增测试**: 31 个 (`tests/test_session48_claim_grounding.py`)
**总测试**: 704 passed / 1 skipped / 2 failed (S51 thesis_eval 失败与本轮无关，pre-existing)

---

## 1. paper_library_chunk evidence 类型

### EvidenceItem 扩展字段（向后兼容，Optional）

| 字段 | 类型 | 说明 |
|---|---|---|
| `paper_id` | `str \| None` | 来源论文 paper_id |
| `chunk_id` | `str \| None` | chunk 唯一标识 |
| `page_start` | `int \| None` | 起始页码 |
| `page_end` | `int \| None` | 结束页码 |
| `quote` | `str \| None` | 引用原文片段 (≤ 2000 字) |
| `support_type` | `Literal["direct", "indirect", "background", "contradiction"] \| None` | 引用类型 |

`evidence_type` Literal 新增 `paper_library_chunk`；`source_mode` 新增 `paper_rag`。

---

## 2. RAG answer → Evidence Ledger 写回

`paper_qa.answer_with_llm()` 成功后，新增 `write_answer_to_ledger()`：

1. 遍历 `answer.evidence_refs`
2. 每条 ref → `ev_store.add_paper_library_chunk(paper_id, chunk_id, quote, page_*, support_type, review_status="pending", tag="paper_rag")`
3. **chunk_id 去重**：同一 chunk 重复入池直接跳过
4. `find_paper_library_chunk(project_id, paper_id, chunk_id)` 按 chunk 查 ledger
5. `list_paper_library_chunks(project_id)` 列出全部 chunk 类 evidence

`/ask` 端点集成：写 ledger + 应用引用规则（见 §5）。

---

## 3. 检索 scope 过滤

`retriever._filter_by_scope` chunk-level enforcement：

| scope | 行为 |
|---|---|
| `all_papers` | 不过滤论文状态；**但剔除 ledger 中 `review_status="rejected"` 的 chunk** |
| `accepted_papers` | 通过 ledger `paper.review_status in (accepted, core)` → arxiv_id 反查 paper_id → chunk filter |
| `specific` | `paper_ids` 白名单 chunk filter |

新增 `_rejected_chunk_ids(project_id)`：扫 ledger 中所有 `paper_library_chunk` 类型且 `review_status="rejected"` 的 chunk_id，任何 scope 下都剔除。

---

## 4. Claim Grounding

### 流程

```
report claim
  → retriever.retrieve (scope=accepted_papers)
  → reranker.rerank_chunks
  → LLM 分类每 chunk (direct / indirect / background / contradiction)
  → 引用规则强制 (rejected 移除 / pending direct → background / failed verify → background)
  → verdict 重导
```

### Verdict 四态

| status | 条件 |
|---|---|
| `supported` | 至少 1 个 chunk 通过规则后仍是 `direct`/`indirect` |
| `weak_support` | 仅 background 且 max score ≥ 0.4 |
| `contradiction` | 至少 1 个 contradiction chunk 且无 direct/indirect |
| `unsupported` | 无命中 或全部 score < 0.4 |

### LLM 失败 fallback

heuristic path：
- negation patterns (`not / no / never / 无法 / 不 / 无`) + claim 关键词共现 → `contradiction`
- Jaccard keyword overlap ≥ 0.5 或 score ≥ 0.7 → `direct`
- overlap ≥ 0.3 或 score ≥ 0.5 → `indirect`
- 否则 `background`

`retrieval_mode` 字段区分 `llm` / `fallback`。

### GroundingResult schema

```python
class ClaimGroundingResult(BaseModel):
    claim: str
    status: Literal["supported", "weak_support", "contradiction", "unsupported"]
    verdict: Literal[...] (alias for status)
    confidence: float  # 0-1
    supporting_chunks: list[EvidenceRef]
    contradicting_chunks: list[EvidenceRef]
    background_chunks: list[EvidenceRef]
    reason: str
    retrieval_mode: Literal["llm", "fallback"]
```

---

## 5. 引用规则强制

`paper_qa.filter_refs_by_citation_rules(project_id, refs)` + `claim_grounding._enforce_citation_rules_on_ref`：

| 规则 | 行为 |
|---|---|
| chunk `review_status == "rejected"` | **永不返回**（从 supporting/contradicting/background 全删） |
| chunk `review_status == "pending"` 且 ref `support_type in (direct, indirect)` | 降级为 `background` + warning |
| chunk `verification_status == "failed"` 且 ref `support_type in (direct, indirect)` | 降级为 `background` + warning |
| chunk `review_status == "accepted"` 且 `verification_status == "verified"` | 保持原 `support_type` |

chunk 不在 ledger 中 → 视为 `pending + unverified`（RAG 刚产生还没写）。

`/ask` 端点流程：`filter_refs_by_citation_rules` → `write_answer_to_ledger` → 返回过滤后的 answer。

---

## 6. FinalPackage 集成

不直接修改 `final_package.py`（避免破坏既有 13 节 build 流程），提供 `services/paper_library/section_integration.py`：

- `extract_section_claims(content)`：从 Markdown section 抽声明性句子（跳过标题、列表、引用行；保留含数字 + 中英 assertion keywords 的句子）
- `enforce_section_citation_rules(project_id, refs)`：复用 §5 规则
- `ground_section_claims(project_id, section_content, scope)`：抽 claim → 逐条 `ground_claim()` → 收集 `verdict in (unsupported, contradiction)` 进 `unsupported_claims`

集成位置（文档化在 `section_integration.py` 头部）：`final_package.build_final_package()` 调用 `_build_sections()` 后，对每个 section 调 `ground_section_claims()`，结果 append 到 `sec.unsupported_claims`（已存在 FinalPackage schema）。

---

## 7. API 端点

**新增 1 个端点**：

```text
POST /api/v1/projects/{project_id}/paper-library/ground-claims
  body: { claims: list[str], scope?: "all_papers"|"accepted_papers"|"specific",
          paper_ids?: list[str], top_k?: int (1-20, default 5) }
  resp: ClaimGroundBatchResponse { results: ClaimGroundingResult[], total: int }
```

- claims 为空 → 400 / 422 (Pydantic min_length=1)
- 单条 claim 抛异常 → 该条返回 `verdict=unsupported, retrieval_mode=fallback`，不影响其它

`/ask` 端点增强：
- 答案生成后调 `filter_refs_by_citation_rules` 过滤 refs
- 调 `write_answer_to_ledger` 写入 Evidence Ledger
- 返回过滤后的 answer

---

## 8. 测试结果

### Session 48 新增测试（31 个）

| 类别 | 测试数 | 状态 |
|---|---|---|
| EvidenceItem 扩展 | 4 | PASS |
| add_paper_library_chunk / 去重 | 4 | PASS |
| write_answer_to_ledger | 3 | PASS |
| Scope filter rejected chunk | 2 | PASS |
| Citation rule filter | 4 | PASS |
| claim_grounding heuristic (supported/contradiction/unsupported/weak/LLM) | 5 | PASS |
| Section integration (extract + enforce) | 2 | PASS |
| ground-claims endpoint | 3 | PASS |
| /ask writes to ledger | 1 | PASS |
| Schemas (GroundingResult / Batch) | 3 | PASS |

### 完整套件

```
$ cd apps/api && pytest tests/ -q
704 passed, 1 skipped, 2 failed in 271.50s
```

2 个失败 (`test_session51_thesis_eval.py::TestSeedLoading::test_load_full` + `test_each_has_id`) 是 S51 thesis_eval seed 加载问题，pre-existing，与本轮无关。

### Smoke test

```bash
# uvicorn 起来后
POST /api/v1/projects/proj/paper-library/ground-claims
{"claims": ["YOLO steel defect detection"], "scope": "all_papers", "top_k": 3}

→ 200 OK
{
  "results": [{
    "claim": "YOLO steel defect detection",
    "status": "unsupported",
    "verdict": "unsupported",
    "confidence": 0.0,
    "supporting_chunks": [],
    "reason": "未在论文库中找到证据",
    "retrieval_mode": "fallback"
  }],
  "total": 1
}
```

---

## 9. 面试讲法：claim grounding 怎么防编造

**问题**：LLM 写报告很容易「编数字」「编引用」「挂羊头卖狗肉」——它会自信地把不存在的论文说成存在，把不相关的论文当 supporting 引用。

**Session 48 的三层防御**：

1. **检索必须真命中**：`ground_claim(claim)` 先去论文库 chunk 池子里 retrieve，找不到直接 `unsupported`（不靠 LLM 凭印象编）。LLM 只能从 evidence_refs 里挑，不能凭空发明。

2. **LLM 判定 + 关键词 overlap 双路径**：LLM 分类每 chunk 是 direct / indirect / background / contradiction。LLM 挂了？降级 heuristic（否定词检测 + Jaccard overlap），retrieval_mode 标记 `fallback`，confidence 自动降。

3. **引用规则硬墙（最关键）**：
   - `rejected` 的 chunk → **永不入答案**（被用户标记拒绝的论文，再多 LLM 引用也算）
   - `pending` 论文的 chunk → **只能 background，不能 direct supports**（用户还没审 → 不替你背书）
   - `failed verification` 的 chunk → 同样降级 background
   - 这三个规则在 `_assemble_result` 末尾**重新导 verdict**：即使 LLM 说 supported，只要所有 direct 都被降级成 background，最终 verdict 就是 weak_support 或 unsupported

**为什么管用**：传统 RAG 把 LLM 当裁判，幻觉直接进报告。Session 48 把 LLM 降级为「标注员」——它只能标，不能决定。裁判是结构化规则 + 用户在 Evidence Ledger 上的 review_status。即使 LLM 100% 抽风，最坏也只是 unsupported，不会出现「rejected 论文被当 supporting 引用」这种事故。

**验收数据**：31 个新测试覆盖了 4 种 verdict 状态、3 种引用规则降级路径、LLM mock + fallback 两条路径、`/ask` 端到端写 ledger 验证。完整套件 704 全绿（除 S51 seed 问题外）。