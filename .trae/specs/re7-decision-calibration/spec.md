# Re7.7 Decision Calibration Spec

## Why

Re7.6 Round 0 smoke test 暴露了三个结构性问题：
1. **决策 taxonomy 不一致**：跨域标答有 5 档 (GO/CONDITIONAL/RISKY/PIVOT/STOP)，但 `_compute_final_verdict` 只输出 3 档 (GO/RISKY/STOP)
2. **Claim Judge 失败误判为 STOP**：`claim_judge.py` 三处 fallback 返回 `REJECT`，`content.py:400` 将 `REJECT` 无条件映射为 `STOP`，把"裁判不可用"误写成"课题不可做"
3. **STOP 缺乏可审计归因**：Round 0 artifact 只保存最终 verdict，未导出 `stop_reason` / `claim_judge_verdict` / `low_bar_review` / `provider-chain`，无法校准阈值

## What Changes

- 修复 Round 0 artifact 格式：UTF-8 BOM-free、每题保存完整归因字段
- 扩展 `_compute_final_verdict` 从 3 档到 5 档：新增 CONDITIONAL 和 PIVOT
- 新增 `UNAVAILABLE` / `PARTIAL` 决策状态：Claim Judge 调用失败时不自动 REJECT → STOP
- 拆分"真实拒绝"与"调用失败 fallback"：`claim_judge_verdict` 新增 `UNAVAILABLE` 值
- 3 题校准 smoke 验证 verdict 准确性
- 重跑 10 题验证一致性 (≥8/10)
- 新增 5 个 holdout 题
- provider-call timeline + verify/repair loop 优化

## Impact

- Affected code:
  - `apps/api/app/services/agents/graph/nodes/content.py` — `_compute_final_verdict`, `_compute_stop_reason`
  - `apps/api/app/services/agents/graph/nodes/claim_judge.py` — 三处 fallback 逻辑
  - `apps/api/app/services/cross_domain_cases.py` — 新增 5 个 holdout
  - `apps/api/scripts/smoke_e2e.py` — artifact 导出格式
  - `apps/api/app/services/agents/graph/nodes/verify.py` — provider-call timeline
- Backward compatible：原有 GO/RISKY/STOP 语义不变，新增 CONDITIONAL/PIVOT/UNAVAILABLE

## ADDED Requirements

### Requirement: Five-tier verdict taxonomy

The system SHALL support five verdict tiers: GO, CONDITIONAL, RISKY, PIVOT, STOP.

#### Scenario: CONDITIONAL verdict
- **WHEN** claim_judge_verdict == ACCEPT but blocked_items is non-empty
- **THEN** final verdict = CONDITIONAL

#### Scenario: PIVOT verdict
- **WHEN** claim_judge_verdict == REVISE AND devils_advocate identifies fundamental flaw
- **THEN** final verdict = PIVOT

### Requirement: UNAVAILABLE decision state

The system SHALL distinguish "judge call failed" from "judge rejected claims".

#### Scenario: Claim Judge LLM call fails
- **WHEN** claim_judge LLM call raises exception or returns fallback
- **THEN** claim_judge_verdict = "UNAVAILABLE" (not "REJECT")
- **AND** final verdict MUST NOT be STOP solely due to UNAVAILABLE

### Requirement: Auditable STOP attribution

The system SHALL export per-case attribution fields in Round 0 artifacts.

#### Scenario: Artifact contains attribution
- **WHEN** any case completes
- **THEN** artifact JSON contains: verdict, stop_reason[], claim_judge_verdict, low_bar_status, human_gate_status, provider_chain[]

## MODIFIED Requirements

### Requirement: _compute_final_verdict

Modified from 3-tier to 5-tier with UNAVAILABLE handling.

Decision logic (in order):
1. low_bar_review.status == "blocked" → STOP
2. claim_judge_verdict == "REJECT" → STOP (genuine rejection only)
3. claim_judge_verdict == "UNAVAILABLE" → RISKY (cannot judge = uncertain, not stop)
4. human_gate not pass → STOP
5. claim_judge_verdict == "REVISE" + devils_advocate fundamental → PIVOT
6. claim_judge_verdict == "REVISE" → RISKY
7. claim_judge_verdict == "ACCEPT" + blocked_items → CONDITIONAL
8. blocked_items → RISKY
9. else → GO

### Requirement: Claim Judge fallback

Modified from REJECT to UNAVAILABLE in all three fallback paths:
- No innovation points → keep REJECT (this is genuine: nothing to judge)
- LLM call exception → UNAVAILABLE
- Fallback dict → UNAVAILABLE
