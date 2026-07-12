# Tasks

## Step 1: 修复 Round 0 artifact 格式

- [ ] 1.1: 修改 `smoke_e2e.py` 导出完整归因字段
  - 每题保存: verdict, stop_reason[], claim_judge_verdict, low_bar_status, human_gate_status, provider_chain[]
  - 从 final state 中提取归因字段，而非只保存 verdict
  - 确保输出为 UTF-8 BOM-free JSON
- [ ] 1.2: 写 `scripts/aggregate_round0.py` 聚合脚本
  - 读取所有 batch_*.json，输出汇总表 (case_id, verdict, expected, stop_reason, claim_judge_verdict, low_bar_status)
  - 可被后续校准步骤重读
- [ ] 1.3: 验证现有 4 个 batch JSON 可被聚合脚本重读

## Step 2: 扩展 final verdict 为五档

- [ ] 2.1: 修改 `content.py:_compute_final_verdict` 从 3 档到 5 档
  - 新增 CONDITIONAL: claim_judge == ACCEPT + blocked_items 非空
  - 新增 PIVOT: claim_judge == REVISE + devils_advocate 标记 fundamental flaw
  - 需要从 state 中读取 devils_advocate 结果判断 PIVOT
- [ ] 2.2: 修改 `_compute_stop_reason` 覆盖 5 档
  - CONDITIONAL reason: "X claim(s) blocked but core claims accepted"
  - PIVOT reason: "fundamental flaw identified by devils_advocate, pivot recommended"
- [ ] 2.3: 更新 `final_recommendation_node` 确保新 verdict 传递到 output

## Step 3: 增加 UNAVAILABLE 决策状态

- [x] 3.1: 修改 `claim_judge.py` 三处 fallback
  - No innovation points (line 99-105): 保持 REJECT (genuine: nothing to judge)
  - LLM call exception (line 133-139): REJECT → UNAVAILABLE
  - Fallback dict (line 121-126): overall_verdict "REJECT" → "UNAVAILABLE"
- [x] 3.2: 修改 `content.py:_compute_final_verdict` 处理 UNAVAILABLE
  - UNAVAILABLE → RISKY (not STOP)
  - 添加 stop_reason: "claim judge unavailable, cannot assess novelty"
- [x] 3.3: 更新 `_compute_stop_reason` 覆盖 UNAVAILABLE 场景

## Step 4: 3 题校准 smoke

- [x] 4.1: 跑 XD-01 (期望 GO), XD-04 (期望 RISKY), XD-10 (期望 STOP)
  - 第一轮: stop_reason 空数组 bug → 修复 state.py + content.py
  - 第二轮: SSL 网络故障 (stepfun provider 全挂), pipeline 降级运行
  - stop_reason 修复验证通过: 从 [] 变为 ["human gate did not pass: "]
  - 五档 verdict 逻辑未能完整验证 (LLM 全挂未走到 claim_judge/low_bar)
  - 硬停条件: SSL 网络故障连续 3 次重跑未改善 (环境问题非代码问题)
- [x] 4.2: 修复文件名竞态 bug (并发运行时 batch_{timestamp}.json 互相覆盖)

## Step 5: 重跑 10 题

- [ ] 5.1: 3 题校准通过后，重跑全部 10 题
  - 并行分发子 agent (4 batch × 2-3 题)
  - 每题保存完整归因 artifact
- [ ] 5.2: 汇总 10 题结果，验证 ≥8/10 verdict 匹配 expected

## Step 6: 新增 5 个 holdout

- [ ] 6.1: 在 `cross_domain_cases.py` 新增 5 个 holdout 题 (XD-11 ~ XD-15)
  - 覆盖不在原 10 题中的领域
  - 每题有明确 expected_verdict
- [ ] 6.2: 跑 5 个 holdout 题验证泛化性

## Step 7: provider-call timeline + verify/repair loop 优化

- [ ] 7.1: 在 `verify.py` 添加 provider-call timeline
  - 每次 LLM 调用记录: provider, model, contract_id, elapsed_s, n_papers, batch_size
  - 导出到 state["trace_events"]
- [ ] 7.2: 在 `smoke_e2e.py` 导出 provider-call timeline
  - 每题 artifact 包含 provider_calls[] 列表
- [ ] 7.3: 分析 verify 耗时根因
  - 是 batch 重试？provider 排队？timeout？repair？
  - 基于数据决定优化方向（不加 timeout）
- [ ] 7.4: 分析 repair loop 轮数
  - 统计每题 narrative_builder / low_bar_review 执行轮数
  - 如果 >2 轮，考虑 early exit 条件

# Task Dependencies

- Step 2, Step 3 可并行（互相不依赖）
- Step 4 依赖 Step 1+2+3
- Step 5 依赖 Step 4 通过
- Step 6 依赖 Step 5 通过
- Step 7 可与 Step 5/6 并行（是 instrumentation，不改判定逻辑）
