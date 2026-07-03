# PaperAgent Re10 FIX — SearchTrace 索引

> 起草日: 2026-07-04  
> 范围: Re10 FIX SOP §3 (必跑典型样例) + §6 交付物  
> 来源根目录: `G:\PaperAgent\tmp_re04_eval\re10_fix_typical_cases\`  
> 配套: [PaperAgent_Re10_FIX_典型样例审计.md](PaperAgent_Re10_FIX_典型样例审计.md) / [典型样例审计.csv](PaperAgent_Re10_FIX_典型样例审计.csv)

## 1. 目录结构

```
G:\PaperAgent\tmp_re04_eval\re10_fix_typical_cases\
├── summary.json                  # 5-case 汇总 (by_stop_reason / by_round_count / repairs)
├── run_manifest.json             # run_id=re10_refl_20260704_003632_a30d2f, llm=minimax/MiniMax-M3
├── reflection_stats.json         # audit_version=Re10-reflection, n_total=5, trace_coverage 5/5
├── batch1\                       # runner 副本 (本索引不展开)
│   ├── TYPICAL-01.json
│   ├── TYPICAL-02.json
│   ├── TYPICAL-03.json
│   ├── TYPICAL-04.json
│   └── TYPICAL-05.json
└── traces\                       # validator 读取的 canonical trace
    ├── TYPICAL-01.json
    ├── TYPICAL-02.json
    ├── TYPICAL-03.json
    ├── TYPICAL-04.json
    └── TYPICAL-05.json
```

## 2. 5 个 trace 文件索引

每个 trace 都遵循统一 schema:

```text
{
  case_id, topic, max_rounds, seed_sources,
  rounds: [
    {
      round, agent, input_summary,
      actions: [{type, tool, query, status, result_count, duration_sec, candidate_ids, error}],
      observations: {
        executed_queries, tool_results, good_candidates, noise_candidates,
        empty_url_candidates, empty_query_results,
        dataset_gap, baseline_gap, repo_gap,
        query_placeholder_leaks, useful_terms_discovered,
        url_repair_n, failed_queries, tool_stats
      },
      reflection: {
        diagnosis: [{problem, evidence, root_cause, next_action}],
        next_round_focus: [str]
      },
      new_candidates_n, accepted_candidates_n, rejected_candidates_n,
      url_repair_n, query_repair_n
    }
  ],
  final: {stop_reason, paper_n, baseline_n, parallel_n, dataset_n, repo_n, remaining_gaps}
}
```

### TYPICAL-01: 基于Unet的钢材裂缝分割

- 路径: `G:\PaperAgent\tmp_re04_eval\re10_fix_typical_cases\traces\TYPICAL-01.json`
- 大小: 13.7 KB
- rounds: 2 (round1 + round2)
- stop_reason: `no_new_signal`
- 关键 action 数: 7 (openalex×4, github×2, arxiv×1)
- 关键 noise_candidates (round1): DeepCrack: A deep hierarchical feature learning architecture for crack segmentation / Deep Learning Techniques for Automatic MRI Cardiac Multi-Structures Segmentation and Diagnosis: Is the Problem Solved? / CrackFormer Network for Pavement Crack Segmentation / Deep Metallic Surface Defect Detection: The New Benchmark and Detection Network / Review of vision-based steel surface inspection systems
- 关键 noise_candidates (round2): Extreme Narrow Escape / Traversing Narrow Paths: A Two-Stage Reinforcement Learning Framework for Robust and Safe Humanoid Walking / The Prevalence of Narrow Optical Fe II Emission Lines in Type 1 Active Galactic Nuclei (← arxiv 字面命中 "narrow" 的串题)
- remaining_gaps: dataset_gap, repo_gap, baseline_gap, paper_shortage
- 异常点: round2 url_repair_n=3 但 reflection_stats 报 url_repair_total=3 全归到这一 case

### TYPICAL-02: 基于三维成像的损伤智能检测

- 路径: `G:\PaperAgent\tmp_re04_eval\re10_fix_typical_cases\traces\TYPICAL-02.json`
- 大小: 11.8 KB
- rounds: 2
- stop_reason: `no_new_signal`
- 关键 action 数: 6 (openalex×4 全部 HTTP 429, github×2 no_results)
- 没有 noise_candidates (全部 429 → 无返回)
- failed_queries: openalex `damage detection task benchmark` / `structural damage object benchmark` / `基于三维成像的损伤智能检测 dataset benchmark` / `基于三维成像的损伤智能检测 baseline method` — 4 条全部 `HttpError('HTTP 429 ...')`
- remaining_gaps: dataset_gap, repo_gap, baseline_gap, paper_shortage
- 异常点: runner 没有 openalex 429 → crossref circuit breaker，导致两轮 4 次重复 429

### TYPICAL-03: 基于多时相遥感数据的作物早期识别

- 路径: `G:\PaperAgent\tmp_re04_eval\re10_fix_typical_cases\traces\TYPICAL-03.json`
- 大小: 11.9 KB
- rounds: 2
- stop_reason: `no_new_signal`
- 关键 action 数: 6 (openalex×4 HTTP 429, github×2 no_results)
- failed_queries: `early crop identification task benchmark` / `cropland object benchmark` / `基于多时相遥感数据的作物早期识别 dataset benchmark` / `... baseline method` — 同上 4 条 429
- remaining_gaps: dataset_gap, repo_gap, baseline_gap, paper_shortage
- 与 TYPICAL-02 同形 (同一 runner bug)

### TYPICAL-04: 基于大语言模型的医学问答答案可信度评估

- 路径: `G:\PaperAgent\tmp_re04_eval\re10_fix_typical_cases\traces\TYPICAL-04.json`
- 大小: 5.4 KB (最小, 因为只跑 1 round 就 stop)
- rounds: **1**
- stop_reason: `blocked_tooling`
- 关键 action 数: 3 (openalex×2 HTTP 429 + github×1 HTTP 403)
- **唯一触发 H2 的 case**: adapter_success_n=0
- **reflection 异常**: diagnosis[0].evidence = `["三", "条", " ", "e", "x"]` / diagnosis[1].evidence = `["f", "a", "l", "l", "b"]` / diagnosis[2].evidence = `["g", "o", "o", "d", "_"]` — 碎字符, root_cause 和 next_action 部分为空字符串
- next_round_focus: **空数组** — reflection 没产出下一轮 focus, runner 立即 stop
- remaining_gaps: dataset_gap, repo_gap, baseline_gap, paper_shortage

### TYPICAL-05: X dynamic scene dataset (占位符修复测试)

- 路径: `G:\PaperAgent\tmp_re04_eval\re10_fix_typical_cases\traces\TYPICAL-05.json`
- 大小: 13.3 KB
- rounds: 2
- stop_reason: `no_new_signal`
- 关键 action 数: 3 (openalex×2 HTTP 429 round1, 然后 round2 触发 query_repair × 3)
- **唯一触发 H4 的 case**: observations.query_placeholder_leaks 含 3 条
  - `X dynamic scene dataset dataset benchmark`
  - `X dynamic scene dataset baseline method`
  - `X dynamic scene dataset github implementation`
- query_repair 全部返回 `needs_clarification`, error 包含 `SOP §4.4 hard rule never returned as repaired (has_brace=False, has_bare_x=True)`
- reflection.diagnosis 加了 3 条 `problem="query_placeholder"` 诊断, 但 runner 仍然把原 query 写进 executed_queries

## 3. 跨 trace 共性

| 现象 | 频率 | 涉及 trace |
|---|---|---|
| round1 input_summary.must_search_n=2 + fallback repo `U-Net semantic segmentation github implementation` | 5/5 | 全部 |
| openalex HTTP 429 至少 2 次 | 5/5 | 全部 |
| good_candidates 始终为空 | 5/5 | 全部 |
| remaining_gaps 包含 `paper_shortage` | 5/5 | 全部 |
| reflection.next_round_focus 长度 = 4 | 4/5 (除 TYPICAL-04 外) | 01 / 02 / 03 / 05 |
| reflection.next_round_focus 长度 = 0 | 1/5 | TYPICAL-04 (reflection 碎字符) |

## 4. validator 读取路径

```bash
cd /g/PaperAgent
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe apps/api/scripts/validate_re10_reflection_search.py \
    --re10-dir tmp_re04_eval/re10_fix_typical_cases \
    --allow-no-llm --skip-baseline-gates
```

- `validate_re10_reflection_search.py` 从 `summary.json` 取 5-case 汇总, 从 `traces/TYPICAL-*.json` 取 per-case evidence。
- H6 gate 校验 `trace_coverage.with_trace == n_total`, 本次 5/5 PASS。
- H4 gate 读取 `observations.query_placeholder_leaks` 长度, TYPICAL-05 = 3 → FAIL。

## 5. 5 trace 关键字段快照 (供后续 Re10 FIX-2 / Re11 快速 diff)

| case | rounds | final.stop | final.paper_n | good_cand | noise_cand | q_placeholder_leak | tool_error_n 总和 |
|---|:---:|---|:---:|:---:|:---:|:---:|---:|
| TYPICAL-01 | 2 | no_new_signal | 0 | 0 | 8 | 0 | 1 |
| TYPICAL-02 | 2 | no_new_signal | 0 | 0 | 0 | 0 | 4 |
| TYPICAL-03 | 2 | no_new_signal | 0 | 0 | 0 | 0 | 4 |
| TYPICAL-04 | 1 | blocked_tooling | 0 | 0 | 0 | 0 | 3 |
| TYPICAL-05 | 2 | no_new_signal | 0 | 0 | 0 | **3** | 2 |

> 5 个 trace 的 `final.paper_n / baseline_n / parallel_n / dataset_n / repo_n` 全部 = 0 — 没有任何 case 进入 7-bucket 收口阶段。Re10 FIX 必须先修工具链 + parse_topic, 再谈 reflection 闭环。