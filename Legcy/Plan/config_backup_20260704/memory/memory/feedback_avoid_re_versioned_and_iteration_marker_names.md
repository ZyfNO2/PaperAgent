---
name: avoid-re-versioned-and-iteration-marker-names
description: "Function / file / class names + module docstring headers must describe function not iteration (no re04_entry / S66v LLM-first / Re07); Re0X history lives in a History: block in the docstring only"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 8c37837b-7238-4edd-bdb1-4535500e9597
---

Functions, classes, files, modules, and module-level docstring
**headers** must NOT carry Re0X versions, S66v, "LLM-first", "v2",
"Re04", or any other iteration / direction markers as their primary
identifier.

**Why:** User explicit ask 2026-07-03 — re-versioned names AND
iteration-marker docstring banners (e.g. `research_agent.py` with a
giant `"""S66v LLM-first\n... 1200 lines of history prose..."""`
header) both leak process state into a stable API. New readers see
the banner and think the function is "S66v-only" or "Re04-era" when
in fact it is the project's current main entry. Iteration is a
*history*; the identifier should describe *what* the code does today.

**How to apply:**

1. **Code identifiers** describe the *function*, not the *iteration*:
   - `re04_entry.py` → `agent_main.py` (or `run_agent.py`)
   - `re08_to_csv.py` → `audit_to_csv.py` (or `balanced40_to_csv.py`)
   - `reclassify_balanced40_re08.py` → `rerun_audit.py`
   - `eval_compute_resource_status()` stays; do NOT rename to
     `re07_compute_resource_status()`
2. **Module docstring headers** describe the *current* contract
   first; version history goes in a single `History:` block, not as
   the docstring title or as scattered prose:
   ```python
   """Resource-retrieval audit harness.

   Public contract:
     compute_resource_status(result) -> dict
     aggregate_metrics(per_case) -> dict
     write_markdown_report(per_case, path) -> None

   History (commit log, do NOT pull into the name):
     Re05: introduced raw-dump reclassification.
     Re07: wired in evidence_consistency auditor + relaxed scoring.
     Re08: added quarantine + axis_status + 4-way report.
   """
   ```
   BAD example (this is what's currently in `research_agent.py`):
   ```python
   """S66v LLM-first research-agent orchestrator.

   1200 lines of history prose about S66v vs S04 vs ... — this should
   not be the module's title."""
   ```
3. **Test filenames** also avoid `re07_*.py` / `re09_*.py`. Use
   `test_candidate_verifier.py` /
   `test_metadata_repair_executor.py` etc.; the SOP/feature name in
   the docstring header tells you which iteration introduced the test.
4. **Variable / field names** (`re08_status`, `re09_fresh_*`,
   `balanced40_re09_fresh`) — also rename. Use
   `previous_iteration_status`, `fresh_*` (drop version), `fresh_run/`
   (drop `balanced40_re09_` prefix in favor of
   `tmp_re04_eval/fresh_run/`).
5. **When writing a new module for a new Re0X session**:
   - Pick a functional name first
   - Add a brief `History:` block in the docstring
   - If two modules have the same functional role but different
     version histories, MERGE them (keep the new one) instead of
     versioning

**Related:**
- [[feedback_dont_design_without_sop]]
- [[project_v0_1_rc1_released]]