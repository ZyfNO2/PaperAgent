# Checklist

## Step 1: Round 0 artifact 修复

- [ ] 1.1: smoke_e2e.py 每题导出 verdict + stop_reason[] + claim_judge_verdict + low_bar_status + human_gate_status + provider_chain[]
- [ ] 1.2: artifact JSON 为 UTF-8 BOM-free，可被 json.load 重读
- [ ] 1.3: aggregate_round0.py 能读取所有 batch_*.json 并输出汇总表
- [ ] 1.4: 现有 4 个 batch JSON 可被聚合脚本重读（向后兼容）

## Step 2: 五档 verdict

- [ ] 2.1: _compute_final_verdict 支持 5 档: GO / CONDITIONAL / RISKY / PIVOT / STOP
- [ ] 2.2: CONDITIONAL 条件: claim_judge == ACCEPT + blocked_items 非空
- [ ] 2.3: PIVOT 条件: claim_judge == REVISE + devils_advocate fundamental flaw
- [ ] 2.4: _compute_stop_reason 覆盖所有 5 档
- [ ] 2.5: 原有 GO/RISKY/STOP 语义不变（向后兼容）

## Step 3: UNAVAILABLE 决策状态

- [ ] 3.1: claim_judge.py LLM exception fallback: REJECT → UNAVAILABLE
- [ ] 3.2: claim_judge.py fallback dict: overall_verdict "REJECT" → "UNAVAILABLE"
- [ ] 3.3: claim_judge.py no innovation points: 保持 REJECT (genuine rejection)
- [ ] 3.4: _compute_final_verdict: UNAVAILABLE → RISKY (not STOP)
- [ ] 3.5: _compute_stop_reason: UNAVAILABLE 有明确 reason

## Step 4: 3 题校准 smoke

- [ ] 4.1: XD-01 verdict 匹配 GO (或至少不是 STOP)
- [ ] 4.2: XD-04 verdict 匹配 RISKY (或至少不是 STOP)
- [ ] 4.3: XD-10 verdict 匹配 STOP
- [ ] 4.4: 每题 stop_reason 可读且语义正确
- [ ] 4.5: 每题 claim_judge_verdict 不是 UNAVAILABLE (真实调用成功)
- [ ] 4.6: 每题 provider_chain 非空

## Step 5: 重跑 10 题

- [ ] 5.1: 10 题全部完成，无 crash
- [ ] 5.2: ≥8/10 verdict 匹配 expected_verdict
- [ ] 5.3: 每题有完整归因 artifact

## Step 6: holdout 题

- [ ] 6.1: 5 个新 holdout 题 (XD-11 ~ XD-15) 覆盖新领域
- [ ] 6.2: holdout 题有明确 expected_verdict
- [ ] 6.3: holdout 题跑通且 verdict 合理

## Step 7: provider-call timeline

- [ ] 7.1: verify.py 每次 LLM 调用记录 provider/model/contract_id/elapsed_s
- [ ] 7.2: smoke_e2e.py 导出 provider_calls[] 列表
- [ ] 7.3: verify 耗时根因已定位（batch 重试 / provider 排队 / timeout / repair）
- [ ] 7.4: repair loop 轮数已统计，>2 轮的 case 有 early exit 建议

## 回归检查

- [ ] 全量 pytest 无新增失败
- [ ] CHANGELOG 已更新
- [ ] git log 包含每 Step 的 commit
