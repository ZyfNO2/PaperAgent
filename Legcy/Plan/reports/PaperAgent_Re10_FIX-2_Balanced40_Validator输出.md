=== Re10 FIX reflection-search validator (hard-fail) ===
  re10_dir:    tmp_re04_eval\re10_fix2_iter3_combined
  re08_sum:    G:\PaperAgent\tmp_re04_eval\balanced40_re08\summary.json
  re09_sum:    G:\PaperAgent\tmp_re04_eval\balanced40_re09_fresh\summary.json
  allow_no_llm: False
  skip_baseline_gates: True
  WARN: skipping H7 (Re08 seeds) + H8 (Re09 regression) — typical-case mode

--- per-case evidence (40 cases) ---
  case_id | re10_status | stop_reason | adapter_attempt_n | adapter_success_n | adapter_error_n | missing_client_n | new_candidates_n | accepted_candidates_n | query_repair_n | url_repair_n | llm_call_n | evidence_status
  ENG-THESIS-015 | max_rounds | max_rounds | 9 | 9 | 0 | 0 | 11 | 11 | 0 | 0 | 3 | pass
  ENG-THESIS-016 | max_rounds | max_rounds | 9 | 9 | 0 | 0 | 15 | 15 | 0 | 0 | 3 | pass
  ENG-THESIS-018 | max_rounds | max_rounds | 9 | 9 | 0 | 0 | 13 | 13 | 0 | 0 | 3 | pass
  ENG-THESIS-024 | max_rounds | max_rounds | 9 | 9 | 0 | 0 | 11 | 11 | 0 | 0 | 3 | pass
  ENG-THESIS-027 | max_rounds | max_rounds | 9 | 9 | 0 | 0 | 12 | 12 | 0 | 0 | 3 | pass
  ENG-THESIS-028 | max_rounds | max_rounds | 9 | 9 | 0 | 0 | 11 | 11 | 0 | 0 | 3 | pass
  ENG-THESIS-032 | max_rounds | max_rounds | 9 | 9 | 0 | 0 | 12 | 12 | 0 | 0 | 3 | pass
  ENG-THESIS-033 | max_rounds | max_rounds | 9 | 9 | 0 | 0 | 11 | 11 | 0 | 0 | 3 | pass
  ENG-THESIS-043 | max_rounds | max_rounds | 9 | 9 | 0 | 0 | 13 | 13 | 0 | 0 | 3 | pass
  ENG-THESIS-046 | max_rounds | max_rounds | 9 | 8 | 1 | 0 | 10 | 10 | 0 | 0 | 3 | pass
  ENG-THESIS-050 | max_rounds | max_rounds | 9 | 9 | 0 | 0 | 12 | 12 | 0 | 0 | 3 | pass
  ENG-THESIS-063 | max_rounds | max_rounds | 9 | 9 | 0 | 0 | 13 | 13 | 0 | 0 | 3 | pass
  ENG-THESIS-066 | max_rounds | max_rounds | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | blocked_tooling
  ENG-THESIS-074 | max_rounds | max_rounds | 9 | 9 | 0 | 0 | 14 | 14 | 0 | 0 | 3 | pass
  ENG-THESIS-075 | max_rounds | max_rounds | 9 | 9 | 0 | 0 | 14 | 14 | 0 | 0 | 3 | pass
  ENG-THESIS-080 | max_rounds | max_rounds | 9 | 9 | 0 | 0 | 12 | 12 | 0 | 0 | 3 | pass
  ENG-THESIS-091 | max_rounds | max_rounds | 9 | 7 | 2 | 0 | 14 | 14 | 0 | 0 | 3 | pass
  ENG-THESIS-092 | max_rounds | max_rounds | 9 | 7 | 2 | 0 | 11 | 11 | 0 | 0 | 3 | pass
  ENG-THESIS-093 | max_rounds | max_rounds | 9 | 7 | 2 | 0 | 9 | 9 | 0 | 0 | 3 | pass
  ENG-THESIS-096 | max_rounds | max_rounds | 9 | 7 | 2 | 0 | 5 | 5 | 0 | 0 | 3 | pass
  ENG-THESIS-002 | max_rounds | max_rounds | 9 | 7 | 2 | 0 | 14 | 14 | 0 | 0 | 3 | pass
  ENG-THESIS-003 | max_rounds | max_rounds | 9 | 7 | 2 | 0 | 8 | 8 | 0 | 0 | 3 | pass
  ENG-THESIS-004 | max_rounds | max_rounds | 9 | 7 | 2 | 0 | 11 | 11 | 0 | 0 | 3 | pass
  ENG-THESIS-005 | max_rounds | max_rounds | 9 | 6 | 3 | 0 | 8 | 8 | 0 | 0 | 3 | pass
  ENG-THESIS-010 | max_rounds | max_rounds | 9 | 7 | 2 | 0 | 8 | 8 | 0 | 0 | 3 | pass
  ENG-THESIS-014 | max_rounds | max_rounds | 9 | 7 | 2 | 0 | 8 | 8 | 0 | 0 | 3 | pass
  ENG-THESIS-022 | max_rounds | max_rounds | 9 | 7 | 2 | 0 | 9 | 9 | 0 | 0 | 3 | pass
  ENG-THESIS-035 | max_rounds | max_rounds | 9 | 7 | 2 | 0 | 13 | 13 | 0 | 0 | 3 | pass
  ENG-THESIS-040 | max_rounds | max_rounds | 9 | 7 | 2 | 0 | 8 | 8 | 0 | 0 | 3 | pass
  ENG-THESIS-048 | max_rounds | max_rounds | 9 | 7 | 2 | 0 | 13 | 13 | 0 | 0 | 3 | pass
  ENG-THESIS-051 | max_rounds | max_rounds | 9 | 7 | 2 | 0 | 13 | 13 | 0 | 0 | 3 | pass
  ENG-THESIS-058 | max_rounds | max_rounds | 9 | 7 | 2 | 0 | 9 | 9 | 0 | 0 | 3 | pass
  ENG-THESIS-060 | max_rounds | max_rounds | 9 | 7 | 2 | 0 | 8 | 8 | 0 | 0 | 3 | pass
  ENG-THESIS-064 | max_rounds | max_rounds | 9 | 7 | 2 | 0 | 11 | 11 | 0 | 0 | 3 | pass
  ENG-THESIS-072 | max_rounds | max_rounds | 9 | 7 | 2 | 0 | 8 | 8 | 0 | 0 | 3 | pass
  ENG-THESIS-073 | max_rounds | max_rounds | 9 | 6 | 3 | 0 | 9 | 9 | 0 | 0 | 3 | pass
  ENG-THESIS-079 | max_rounds | max_rounds | 9 | 6 | 3 | 0 | 11 | 11 | 0 | 0 | 3 | pass
  ENG-THESIS-083 | max_rounds | max_rounds | 9 | 7 | 2 | 0 | 8 | 8 | 0 | 0 | 3 | pass
  ENG-THESIS-089 | max_rounds | max_rounds | 9 | 6 | 3 | 0 | 5 | 5 | 0 | 0 | 3 | pass
  ENG-THESIS-100 | max_rounds | max_rounds | 9 | 7 | 2 | 0 | 11 | 11 | 0 | 0 | 3 | pass

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
