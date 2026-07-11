# SOP 剩余阶段（Phase C/E/F）Spec

## Why
Re7.6 SOP 的 7 个 PASS 条件中还有 3 个未完成：Job worker 内部 cancel/budget probe（Phase C）、eval harness 与 Round 0 artifact（Phase E）、真实 LLM 链路 smoke test（Phase F）。需要全部完成才能将 SOP 从 HOLD/NO-GO 推进到 Round 0 可验证状态。

## What Changes
### Phase C — Job Worker 内部 cancel/budget probe
- `job_worker.py`：在 graph 内部关键节点前增加 cancel/budget probe，通过 state 中的 `job_id` 查询 repo
- `job_repository.py`：新增 `is_cancelled(job_id)` / `is_budget_exhausted(job_id)` 查询方法
- 新增 `_util.py` 或复用现有 helper：`probe_job_cancel_or_budget(state, repo)` 供各节点调用
- 扩展 `test_re7_job_worker.py`：cancel 后 probe 在第一个节点拦截、budget 耗尽标记 resumable

### Phase E — Eval Harness live 模式 + Round 0 artifact
- `re6_eval.py`：实现 `--live` 模式，接入真实 `run_round0_seq.py` 或单独 graph 调用
- 支持 `--round0` flag，自动跑 10 跨域题并合并产物
- 补齐 `--holdout` 模式下代码冻结检查
- 统一 pytest 口径解释（149/123/108）
- 产物路径：`artifacts/re7_6/eval/<run_id>/` 下 manifest.json + JUnit XML + failure_taxonomy.json + trace_summary.json

### Phase F — 真实 LLM 链路 smoke test
- 修复 XD-03 超时（定位到具体节点，增加 timeout/retry）
- 跑 XD-01 钢材题端到端，确认 `final_recommendation.verdict` 非空且合理
- 跑全部 10 跨域题（`run_round0_seq.py`），产出一致性 manifest
- 更新 SOP 状态为 Round 0 基线已生成

## Impact
- Affected specs: SOP §9.1 PASS 条件 3/5/6/7
- Affected code: `job_worker.py`, `job_repository.py`, `nodes/_util.py`, `re6_eval.py`, `run_round0_seq.py`, `cross_domain_cases.py`
- 外部依赖：真实 LLM provider（Phase F 需要调用 stepfun API）

## ADDED Requirements

### Requirement: Job Worker 内部 Cancel/Budget Probe
系统 SHALL 在 graph 执行的关键节点前通过 state 中的 `job_id` 查询 job 状态，若 job 被取消或预算耗尽则立即停止执行，不继续调用 LLM。

#### Scenario: Cancel 在第一个节点被拦截
- **GIVEN** 一个 pending job 被 worker 获取
- **WHEN** 用户在 graph 执行前 cancel 该 job
- **THEN** worker 在第一个节点执行前检测到 cancelled 状态，标记 job 为 cancelled，不执行任何 LLM 调用

#### Scenario: Budget 耗尽标记 resumable
- **GIVEN** 一个 job 的 budget_tokens=500，已消耗 500 tokens
- **WHEN** worker 执行下一个节点前检查 budget
- **THEN** worker 标记 job 为 resumable，记录已完成节点，不再继续

#### Scenario: 正常执行完成
- **GIVEN** 一个 pending job 未被 cancel 且 budget 充足
- **WHEN** worker 执行完整 graph
- **THEN** job 状态变为 completed，所有事件按序记录

### Requirement: Eval Harness Live 模式
系统 SHALL 支持 `--live` 模式调用真实 research graph 或 RAG pipeline 进行评测，产出 manifest.json、JUnit XML、failure_taxonomy.json、trace_summary.json。

#### Scenario: Mock 模式验证 fixture
- **WHEN** 运行 `python scripts/re6_eval.py --mock`
- **THEN** 所有 118 个 fixture 被正确分类和校验，产出 JUnit XML 报告

#### Scenario: Live 模式跑真实 graph
- **WHEN** 运行 `python scripts/re6_eval.py --live --cases XD-01`
- **THEN** 调用真实 graph 跑 XD-01 钢材题，产出包含 `final_verdict` 的 manifest

#### Scenario: Round 0 全量执行
- **WHEN** 运行 `python scripts/re6_eval.py --round0`
- **THEN** 自动调用 `run_round0_seq.py` 跑 10 跨域题，合并产物到 eval 目录

### Requirement: 真实链路 Smoke Test
系统 SHALL 在真实 LLM provider 下完成 10 跨域题端到端执行，每题的 `final_recommendation.verdict` 非空且可解释。

#### Scenario: XD-01 钢材题端到端
- **WHEN** 运行 `run_round0_seq.py --case XD-01`
- **THEN** `final_recommendation.verdict` 非空（GO/RISKY/STOP），`final_recommendation.feedback_bar` 存在

#### Scenario: XD-03 超时修复
- **WHEN** 运行 XD-03（水声信号船舶识别）
- **THEN** 在 300s 内完成，不因超时而 crash

#### Scenario: 10/10 跨域题完成
- **WHEN** 运行 `run_round0_seq.py` 全部 10 题
- **THEN** 10/10 完成，每题有 manifest 条目，SOP 状态更新为 Round 0 基线已生成

## MODIFIED Requirements
无。Phase C/E/F 全部为新增。

## REMOVED Requirements
无。