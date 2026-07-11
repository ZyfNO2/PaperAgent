# Checklist — SOP 剩余阶段（Phase C/E/F）

## Phase C — Job Worker

- [x] C-1: `is_cancelled` / `is_budget_exhausted` 方法已实现且单元测试覆盖
- [x] C-2: `probe_cancel_budget` helper 在无 job_id 时不抛异常
- [x] C-3: worker `_execute_job` 每个节点前调用 probe，cancel 后立即停止
- [x] C-4: 扩展测试全 PASS（cancel 拦截 + budget 耗尽 + 无 job_id 跳过）
- [x] C-5: job worker 17 个测试全 PASS，已 commit

## Phase E — Eval Harness

- [x] E-1: `--live` 模式能调用真实 graph 或 RAG pipeline
- [x] E-2: `--round0` 能自动跑 10 跨域题并合并产物
- [x] E-3: `--holdout` 模式有代码冻结检查
- [x] E-4: 149/123/108 口径解释正确
- [x] E-5: `--mock` 118 fixture 全 PASS，已 commit

## Phase F — 真实链路 Smoke Test

- [x] F-1: unified_router 默认值修复（8 nodes），逐链路 31.9s 通过
- [x] F-2: XD-01 完整 graph 36 nodes，verdict=STOP，per-node 计时已记录
- [x] F-3: 10/10 跨域题完成，每题有 JSON 结果文件
- [x] F-4: SOP 状态更新为 Round 0 基线已生成，PASS 条件全打勾

## 回归检查

- [x] 全量 pytest 无新增失败（28 passed, 12 环境权限 ERROR 非本次改动）
- [x] CHANGELOG 已更新
- [x] git log 包含每 Phase 的 commit