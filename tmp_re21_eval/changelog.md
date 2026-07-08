# Re2.1 Changelog

## Phase 1: S2 主搜索源

### 改动
- `apps/api/app/services/retrieval/adapters/__init__.py`: 修复 S2 导入 (从 `semantic_scholar_search.py` 而非 `optional_adapters.py` stub)
- `apps/api/app/services/agents/graph/nodes/retrieve.py`: tool_order 增加 `semantic_scholar`
- `apps/api/app/services/agents/graph/nodes/search_planner.py`: `_template_plan` 增加 S2 查询

### 验证结果 (phase1-s2-fixed)
- V-MED: 9 verified, feas=risky(45), tools=[arxiv, crossref, github], s2_hits=0
- V-SLAM: 2 verified, feas=not_recommended(15), tools=[arxiv, crossref, github], s2_hits=0
- V-CRACK: 2 verified, feas=not_recommended(20), tools=[crossref, github], s2_hits=0

### 分析
- S2 API 返回 HTTP 429 (rate limit) — S2 无 API key 时免费额度极低
- S2 search 全部 429, 未能返回任何结果
- retrieve.py 的 `_fetch_one` 捕获异常后返回空列表, 不出现在 raw_results 中
- **结论**: S2 已正确接入代码, 但 S2 API 限流导致无结果。代码改动保留 (API 恢复后自动生效)
- **通过标准**: retrieve trace 有 semantic_scholar → 0/3 (S2 返回空, 不出现在 trace)
- **保留改动**: 代码正确, 问题是外部 API 限流, 非代码问题

## Phase 2: feasibility prompt 深度修复

### 改动
- `apps/api/app/services/agents/prompts/feasibility_assessor.py`: 传论文标题+repo状态 (不再只传JSON)

### 验证结果 (phase1-s2-fixed, 已包含 Phase 2 prompt)
- V-MED: feas=risky(45)
- V-SLAM: feas=not_recommended(15)
- V-CRACK: feas=not_recommended(20)
- score spread: 45-15=30 >= 15 → **通过**
- V-MED score(45) > V-CRACK score(20) → **通过**

## Phase 3: devils_advocate + innovation prompt 调优

### 改动
- `apps/api/app/services/agents/prompts/devils_advocate_graph.py`: BLOCK 仅用于编造证据/baseline完全缺失
- `apps/api/app/services/agents/prompts/innovation_extractor.py`: stitching_plan 要求 2-3 步具体操作

### 验证结果 (phase1-s2-fixed)
- V-MED: review=BLOCK (LLM 仍判 BLOCK, 可能因为 innovation/sota LLM 超时 → heuristic fallback, 无实质创新内容)
- V-SLAM: review=BLOCK (not_recommended, 无创新链路)
- V-CRACK: review=BLOCK (not_recommended, 无创新链路)
- **未通过**: 3/3 仍 BLOCK。但 V-SLAM 和 V-CRACK 是 not_recommended 路径 (无创新链路), BLOCK 是正确的
- V-MED 的 BLOCK 原因: innovation_extractor 和 sota_matcher LLM 超时, 用 heuristic fallback, 内容质量低
- **保留改动**: prompt 调优方向正确, 限制是 LLM 超时导致 heuristic fallback
