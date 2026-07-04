---
name: never-deliver-llm-dead-path
description: "LLM-dead path output MUST NOT be used as deliverable evidence; it is connectivity-test only. Always run LLM-online for验收, and freely burn MiniMax quota / parallelize."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 456ece0c-bb67-4c7a-9b58-3f62b6a4aebb
---

When validating an agent pipeline (PaperAgent Re02-style), the "LLM-dead path" (heuristic fallback) output is for **connectivity / smoke testing only**. It must NEVER be written into a 完工报告, accepted as test evidence, or quoted to the user as "this is what the agent produced".

**Why:** the user got burnt by Re02 完工报告 — I had set `SESSION66_LLM_BUDGET=0` to save MiniMax quota, ran 4 cases, and shipped a 报告 full of generic ML papers ("Changing Data Sources in the Age of Machine Learning for Official Statistics", awesome-machine-learning, etc.) claiming the agent returned them. But those came from the heuristic fallback's `query_atoms_en = "machine learning"`, not from the agent working. The user pointed out that Re01 (LLM-online) returned real COLMAP / nnU-Net / NEU-DET hits for the same case shapes, so Re02's "real" output should match that.

**How to apply:**

1. 完工报告 / 验收 / 给用户看的候选清单 → MUST be from a run with LLM online (no `SESSION66_LLM_BUDGET=0`).
2. Connectivity smoke (imports, schemas, no-network sanity) → OK to use `SESSION66_LLM_BUDGET=0` or fake `chat_json_strict`. Label clearly.
3. MiniMax quota is not a budget constraint for verification — burn as much as needed. If a run is slow, parallelize via subagents (one agent per case) rather than serializing.
4. Whenever tempted to write "heuristic fallback returned X, but the LLM path would return Y" in a 报告 → do NOT write that. Run the LLM path first, then write what it actually returned.
5. If the LLM call genuinely fails (network / key), surface that as a blocker in the 报告 — do not silently fall back to heuristic output.
6. The same applies to my own subagents — dispatch as many parallel subagents as needed (one per case / one per verification angle). My own quota / time budget should not gate what is needed for project-positive work; the user explicitly OK'd this.

Related: [[project-topicpilot-claude-md-rules]]
