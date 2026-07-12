# Checklist

## Step 1: Round 0 artifact 修复

- [x] 1.1: smoke_e2e.py 每题导出 verdict + stop_reason[] + claim_judge_verdict + low_bar_status + human_gate_status + provider_chain[]
- [x] 1.2: artifact JSON 为 UTF-8 BOM-free，可被 json.load 重读
- [x] 1.3: aggregate_round0.py 能读取所有 batch_*.json 并输出汇总表
- [x] 1.4: 现有 4 个 batch JSON 可被聚合脚本重读（向后兼容）

## Step 2: 五档 verdict

- [x] 2.1: _compute_final_verdict 支持 5 档: GO / CONDITIONAL / RISKY / PIVOT / STOP
- [x] 2.2: CONDITIONAL 条件: claim_judge == ACCEPT + blocked_items 非空
- [x] 2.3: PIVOT 条件: claim_judge == REVISE + devils_advocate fundamental flaw
- [x] 2.4: _compute_stop_reason 覆盖所有 5 档
- [x] 2.5: 原有 GO/RISKY/STOP 语义不变（向后兼容）

## Step 3: UNAVAILABLE 决策状态

- [x] 3.1: claim_judge.py LLM exception fallback: REJECT → UNAVAILABLE
- [x] 3.2: claim_judge.py fallback dict: overall_verdict "REJECT" → "UNAVAILABLE"
- [x] 3.3: claim_judge.py no innovation points: 保持 REJECT (genuine rejection)
- [x] 3.4: _compute_final_verdict: UNAVAILABLE → RISKY (not STOP)
- [x] 3.5: _compute_stop_reason: UNAVAILABLE 有明确 reason

## Step 4: 3 题校准 smoke

- [x] 4.1: stop_reason 导出 bug 修复验证通过 (从 [] 变为非空)
- [x] 4.2: 文件名竞态 bug 修复 (batch 文件名加入 case_id)
- [ ] 4.3: XD-01 verdict 匹配 GO — **阻塞: SSL 网络故障**
- [ ] 4.4: XD-04 verdict 匹配 RISKY — **阻塞: SSL 网络故障**
- [ ] 4.5: XD-10 verdict 匹配 STOP — **阻塞: SSL 网络故障**
- [ ] 4.6: 每题 stop_reason 可读且语义正确 — **部分验证 (降级运行下 stop_reason 非空)**
- [ ] 4.7: 每题 claim_judge_verdict 不是 UNAVAILABLE — **阻塞: SSL 网络故障**
- [ ] 4.8: 每题 provider_chain 非空 — **阻塞: SSL 网络故障**

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
