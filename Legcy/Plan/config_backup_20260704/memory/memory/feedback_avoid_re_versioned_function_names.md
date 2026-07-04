---
name: avoid-re-versioned-function-names
description: "Never use \"re04_entry\", \"re05_*\", \"re07_*\", etc. as function or file names — Re0X belongs in docstrings / comments, not in code identifiers"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 8c37837b-7238-4edd-bdb1-4535500e9597
---

Functions, classes, files, and modules must NOT be named with their
Re0X version (e.g. `re04_entry`, `re05_orchestrator`, `re07_eval`,
`re08_to_csv`). The version is a *history* marker, not a *structural*
one.

**Why:** User explicit ask 2026-07-03 — re-versioned names leak process
state into the API. A `re04_entry` function called from `re09` code
is misleading; new readers see the name and think the function is
"re04-only" when in fact it is the project's current main entry. The
re-numbering leaks session boundary into a stable identifier.

**How to apply:**

1. **Code identifiers** describe the *function*, not the *iteration*:
   - `re04_entry.py` → `research_agent.py` (or `agent_main.py`)
   - `re08_to_csv.py` → `audit_to_csv.py` (or `balanced40_to_csv.py`)
   - `reclassify_balanced40_re08.py` → `rerun_audit.py`
   - `eval_compute_resource_status()` stays; do NOT rename to
     `re07_compute_resource_status()`
2. **Comments / docstrings** carry the version history:
   ```python
   def run_balanced40_audit(...):
       """Re-audit Balanced40 raw dumps with the current eval rules.

       History:
         - Re05: introduced this re-audit harness (then named
           ``reclassify_balanced40_re05.py``).
         - Re07: wired in evidence_consistency auditor.
         - Re08: added repair_plan attachment + 4-way report.
       """
   ```
3. **Test filenames** also avoid `re07_*.py` / `re09_*.py`. Use
   `test_candidate_verifier.py` / `test_metadata_repair_executor.py`
   etc.; the SOP/feature name in the docstring header tells you which
   iteration introduced the test.
4. **Variable / field names** (`re08_status`, `re09_fresh_*`,
   `balanced40_re09_fresh`) — also rename. Use `previous_iteration_status`,
   `fresh_*` (drop version), `fresh_run/` (drop balanced40_re09 prefix
   in favor of `tmp_re04_eval/fresh_run/`).
5. **When writing a new module for a new Re0X session**:
   - Pick a functional name first
   - Add a Re0X-history comment at the top of the file
   - If two modules have the same functional role but different version
     histories, MERGE them (keep the new one) instead of versioning

**Related:**
- [[feedback_dont_design_without_sop]]
- [[project_v0_1_rc1_released]]