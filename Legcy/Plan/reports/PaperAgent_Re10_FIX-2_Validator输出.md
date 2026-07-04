=== Re10 FIX reflection-search validator (hard-fail) ===
  re10_dir:    tmp_re04_eval\re10_fix2_typical_cases
  re08_sum:    G:\PaperAgent\tmp_re04_eval\balanced40_re08\summary.json
  re09_sum:    G:\PaperAgent\tmp_re04_eval\balanced40_re09_fresh\summary.json
  allow_no_llm: False
  skip_baseline_gates: True
  WARN: skipping H7 (Re08 seeds) + H8 (Re09 regression) — typical-case mode

--- per-case evidence (5 cases) ---
  case_id | re10_status | stop_reason | adapter_attempt_n | adapter_success_n | adapter_error_n | missing_client_n | new_candidates_n | accepted_candidates_n | query_repair_n | url_repair_n | llm_call_n | evidence_status
  TYPICAL-01 | max_rounds | max_rounds | 9 | 7 | 2 | 0 | 9 | 9 | 0 | 0 | 3 | pass
  TYPICAL-02 | max_rounds | max_rounds | 9 | 7 | 2 | 0 | 8 | 8 | 0 | 0 | 3 | pass
  TYPICAL-03 | max_rounds | max_rounds | 9 | 7 | 2 | 0 | 7 | 7 | 0 | 0 | 3 | pass
  TYPICAL-04 | max_rounds | max_rounds | 9 | 7 | 2 | 0 | 7 | 7 | 0 | 0 | 3 | pass
  TYPICAL-05 | max_rounds | max_rounds | 9 | 7 | 2 | 0 | 6 | 6 | 0 | 0 | 3 | pass

--- hard-fail gates ---
  PASS  H6 trace_coverage.with_trace == n_total
  PASS  H1 missing_client_n == 0
  PASS  H2 adapter_success_n > 0 (when adapter_attempt_n > 0)
  PASS  H3 llm_call_n > 0 (use --allow-no-llm to skip)
  PASS  H4 no query_placeholder_leaks in trace observations
  PASS  H5 url_repair_n > 0 when empty_url_n > 0
  SKIP  H7 Re08 seeds preserved (skip_baseline_gates=True)
  SKIP  H8 Re09 regression cases (skip_baseline_gates=True)
  PASS  H9 pass+weak (evidence-driven) > 0

=== ALL HARD-FAIL GATES PASSED ===
