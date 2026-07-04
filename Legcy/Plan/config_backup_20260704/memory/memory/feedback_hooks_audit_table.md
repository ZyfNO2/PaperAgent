---
name: hooks-emit-human-audit-table
description: "Hooks must emit a human-readable audit TABLE (not raw JSON dumps) at the end of execution. The agent and user must see per-case results in a markdown table they can audit at a glance, not parse through 200-line json.dumps."
metadata:
  node_type: memory
  type: feedback
  originSessionId: 456ece0c-bb67-4c7a-9b58-3f62b6a4aebb
---

When the `user_completion_check` or `pre_report_audit` hook fires, the **user must be able to read the result without opening a json dump file**. The hook is the only audit-trail evidence the harness keeps — if it emits only structured data, the user has to dig through `tmp_s66v_traces/*.json` themselves.

**How to apply:**

1. **Always end the hook with a markdown table** that fits in a terminal screen, not nested dicts. Example template:

   ```python
   print("| 指标 | Case A (3D 损伤) | Case B (U-Net 钢材) |")
   print("|---|---|")
   print("| pool | 23 | 28 |")
   print("| Low-bar | needs_revision | PASS |")
   print("| citation_expand seeds | 5/0/5 | 5/2/3 |")
   ```

2. **Per-case rows must include**:
   - pool size (paper / dataset / repo breakdown)
   - ER tier counts (core / candidate / needs_manual / rejected)
   - Low-bar verdict (pass / needs_revision / stop) + can_continue
   - citation_expand stats (seeds_total / eligible / rejected)
   - synthesis paper_groups breakdown (baseline / parallel / reference / long_tail)

3. **Comparison tables** between Re02 v3 and Re03 (or any two versions) must show **delta** (% noise removed, core count delta, verdict upgrade). Without delta, the user cannot tell if Re03 actually improved anything.

4. **Format constraints:**
   - Use ASCII tables (not Unicode box-drawing) so they render in any terminal
   - Keep cells < 80 chars wide
   - NO `json.dumps()` in the audit output — that's a dump, not an audit
   - Include the time the audit ran (timestamp) so the user knows it's fresh

5. **Per-candidate rows are mandatory when audit covers a retrieval agent** (Re02 v3 / Re03+ / Research agent style deliverables):
   - Per-candidate rows MUST include: `cid` + `evidence_type` + `role` + `title (truncate to 80)` + `tier` (core/candidate/needs_manual/rejected) + `reason` (1 sentence from ER)
   - Show which titles were KEPT in pool, which were rejected at ER stage, and which were filtered at retriever stage
   - For each round_delta axis (raw tool / pool / ER / citation_expand / synthesis paper_groups), give a column with the delta
   - Example template:
     ```
     | cid | type | role | tier | title | reason |
     |---|---|---|---|---|---|
     | c-a1b2 | paper | parallel | candidate | MVCrackViT: Multi-View Crack Detection | multi-view + crack + point cloud |
     | c-a1b3 | paper | reference | rejected | Topological Control of Chirality | structured-light physics, no damage|
     ```
   - If only aggregate counts are shown (e.g. "9 rejected") the audit is incomplete — the user has to dig into the trace dump to know which titles were filtered.

6. **citation_expand seed audit table is mandatory when the agent expands seeds**:
   - One row per seed with `status` (seed_selected / seed_rejected) + `title` + `reason (matched_terms vs missing_terms)`
   - Show both seeds_selected and seeds_rejected so the user sees what was kept and what was filtered
   - `refs_added` count alone is not enough — show seeds_eligible=2/5 explanation

7. **Common mistake to avoid:**
   - Don't just print "OK" or "PASSED" — the user has to see **per-case row** to know which case passed
   - Don't truncate long values with `...` — show the full verdict + summary
   - Don't bury the table inside stderr only — mirror to stdout (Re03 lesson)
   - Don't show aggregate counts only ("9 rejected, 11 candidate") — show per-candidate rows
   - Don't skip the `reason` column — the user needs the WHY to audit, not just the WHAT

8. **Workflow**:
   - Hook detects completion → emits summary + END_OF_AUDIT marker → agent sees the table in transcript → agent reports it back to user in plain text
   - User can read the table and decide whether to continue, commit, or stop and fix

Related: [[incremental-updates-via-subagent]], [[no-llm-dead-path-deliverable]], [[report-bilingual-original-and-translation]]
