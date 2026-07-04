---
name: report-bilingual-original-and-translation
description: "When the user asks to see 报告 (deliverable) data / architecture results in a human-readable way, display them with original English source preserved (paper titles, code names, repo names, dataset names, English jargon) + Chinese translation / explanation alongside. Do NOT create a separate feedback_hooks_audit_table.md file — embed the bilingual output directly in the report. This is a different request from the hook audit table rule."
metadata:
  node_type: memory
  type: feedback
  originSessionId: 456ece0c-bb67-4c7a-9b58-3f62b6a4aebb
---

When the user says "把报告中数据/架构成果用人能看的方式给我看 + 原文保留 + 中文翻译", the intent is:

- **Embed bilingual content directly in the report** (e.g. `PaperAgent_Re03_审计细节_保留与剔除.md`, `PaperAgent_Re03_完工报告.md` §X)
- **Keep original English identifiers** — paper titles, repo names, dataset names, code symbols, technical English jargon (e.g. `evidence_review`, `seed_relevance`, `core/candidate/needs_manual/rejected`, `paper_groups`)
- **Add a Chinese column / sentence** alongside for explanation (title → 标题含义, role → 中文角色, reason → 一句话中文解释, code path → 模块作用中文)
- This is **NOT** the same as the `hooks-emit-human-audit-table` rule (which is about hook stdout/stderr audit emissions)

**How to apply (when user asks for "报告显示数据/架构 + 中英对照"):**

1. **Don't** create a separate `feedback_hooks_audit_table.md` style artifact — the user wants the **report's own** data tables to be readable
2. **Don't** translate English technical terms to Chinese-only (e.g. don't replace `evidence_review` with `证据审查` everywhere — the user reads the code, they need the symbol)
3. **Do** give a bilingual row format like:

   ```
   | cid | 原文 title (English) | 中文含义 | 角色 (role) | 中文 reason |
   ```

4. **Do** add a Chinese summary section after each architecture/data block explaining the flow in Chinese (e.g. "ER → seed_relevance 闸门 → core / candidate 分桶" 的中文版流程)
5. **Do** preserve all code paths, function names, env vars as-is (e.g. `citation_expand`, `source_ledger`, `tmp_s66v_traces/`, `MINIMAX_*`)

**Common mistake to avoid:**

- ❌ Generating a separate "审计规则文件" thinking that's what the user wanted — they wanted the **report's content** translated, not a new rule artifact
- ❌ Translating everything to Chinese and dropping the English originals (user reads code, needs symbols)
- ❌ Mixing this up with the `hooks-emit-human-audit-table` rule (that one is about hook output, not report content)

**Example of correct output style:**

```markdown
| cid | 原文 title | 中文含义 | ER 角色 | reason |
|---|---|---|---|---|
| c-8e220e87 | MVCrackViT: Robust Multi-View Crack Detection For Point Cloud Segmentation | 多视图点云裂纹检测 | 核心 (core) | 多视图+裂纹+点云三轴全中 |
| c-35b480e8 | Topological Control of Chirality and Spin with Structured Light | 拓扑控制与结构光 | 已剔除 (rejected) | 结构光物理领域，与损伤无关 |
```

Related: [[hooks-emit-human-audit-table]] (different rule — about hook output, not report content)
