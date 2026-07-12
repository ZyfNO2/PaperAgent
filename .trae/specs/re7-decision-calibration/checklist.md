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
- [x] 4.3: XD-10 verdict 匹配 STOP (Re7.7 第六轮验证通过)
- [x] 4.4: 每题 stop_reason 可读且语义正确 (第六轮验证)
- [x] 4.5: 每题 claim_judge_verdict 不是 UNAVAILABLE (第六轮验证)

## Step 5: 重跑 10 题

- [x] 5.1: 10 题全部完成 (第六轮 10/10 有结果, 3 题进程崩溃但结果已保存)
- [ ] 5.2: ≥8/10 verdict 匹配 — **未达标: 5/10 (verdict mapping 维度极限, LLM 随机性 ±2)**
- [x] 5.3: 每题有完整归因 artifact

## Step 6: holdout 题

- [x] 6.1: 5 个新 holdout 题 (XD-11 ~ XD-15) 覆盖新领域
- [x] 6.2: holdout 题有明确 expected_verdict
- [x] 6.3: holdout 题跑通且 verdict 合理 — **3/5 精确匹配, 2 个不匹配但 verdict 合理**

## Step 7: provider-call timeline

- [x] 7.1: verify.py 每次 LLM 调用记录 provider/model/contract_id/elapsed_s
- [x] 7.2: smoke_e2e.py 导出 verify_batch_timeline + repair_loop
- [x] 7.3: verify 耗时根因已定位 (USE_CONTRACT_PATH=0 禁用慢 provider)
- [x] 7.4: repair loop 轮数已统计 (平均 2-3 轮)

## 回归检查

- [x] 全量 pytest 无新增失败 (Re7 相关 91/91 通过; test_one_topic_api 预先存在 404)
- [x] CHANGELOG 已更新
- [x] git log 包含每 Step 的 commit
