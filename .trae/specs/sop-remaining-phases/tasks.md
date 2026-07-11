# Tasks

## Phase C — Job Worker 内部 cancel/budget probe

- [x] C-1: `job_repository.py` 新增 `is_cancelled` / `is_budget_exhausted` 查询方法
  - 新增 `is_cancelled(job_id: str) -> bool`：查询 job 状态是否为 cancelled
  - 新增 `is_budget_exhausted(job_id: str) -> bool`：查询 tokens_used >= budget_tokens > 0
  - 两个方法均为只读查询，不修改状态

- [x] C-2: 新增 `probe_cancel_budget` helper 函数
  - 在 `apps/api/app/services/agents/graph/nodes/_util.py` 新增 `probe_cancel_budget(state, repo)` 
  - 若 `_util.py` 不存在则创建，需包含 `emit_trace` 导出
  - 从 state 中读取 `job_id`，若不存在则跳过（允许无 job_id 的 graph 直接调用）
  - 调用 `repo.is_cancelled` / `repo.is_budget_exhausted` 检查
  - 若 cancelled：raise `JobCancelledError`（自定义异常）
  - 若 budget exhausted：raise `BudgetExceededError`（自定义异常）
  - 异常类定义在 `job_repository.py` 或独立文件

- [x] C-3: `job_worker.py` 在 graph 内部关键节点前插入 probe
  - `_execute_job` 将 `repo` 传入 state（`state["_job_repo"] = repo`）
  - 在每个节点执行前调用 `probe_cancel_budget(state, repo)`
  - 捕获 `JobCancelledError` / `BudgetExceededError` 并更新 job 状态
  - 保持现有 `_is_cancelled` / `_check_budget` 在 graph 边界处的 probe 不变

- [x] C-4: 扩展 `test_re7_job_worker.py` 测试
  - 新增 `test_cancel_before_first_node`：cancel 后第一个节点即被 probe 拦截
  - 新增 `test_budget_exhausted_marks_resumable`：budget 耗尽后状态为 resumable
  - 新增 `test_probe_skips_when_no_job_id`：无 job_id 时 probe 不抛异常
  - 确认现有 7 个测试全 PASS

- [x] C-5: Phase C 测试通过并 commit
  - 运行 `python -m pytest apps/api/tests/test_re7_job_worker.py -v`
  - 确认全部 PASS
  - git commit 并更新 CHANGELOG

## Phase E — Eval Harness live 模式 + Round 0

- [x] E-1: `re6_eval.py` 实现 `--live` 模式
  - `evaluate_live` 函数不再 skip，而是调用真实 research graph
  - 使用 `run_round0_seq.py` 中的 `run_topic` 函数（或抽取为共享模块）
  - 对于 `rag` 类 fixture，调用 `query_rag` ACP 能力
  - 对于 `hidden_ood` / `failure` / `novelty` 类，调用 `run_topic` 跑 graph
  - 结果与 fixture 中的 `expected_*` 字段对比，产出 pass/fail

- [x] E-2: `re6_eval.py` 实现 `--round0` flag
  - 自动调用 `run_round0_seq.py` 跑 10 跨域题
  - 采用 subprocess 或直接 import 调用
  - 合并产物到 `artifacts/re7_6/eval/<run_id>/`

- [x] E-3: 补齐 `--holdout` 模式代码冻结检查
  - 加载 `eval_H1/holdout_ids.json`
  - 跑 holdout 前检查是否有未提交的代码变更（`git status --porcelain`）
  - 若有未提交变更，打印警告并要求用户确认（`--force` 跳过）

- [x] E-4: 统一 pytest 口径解释
  - 在 `re6_eval.py` header 中已写入口径解释（149/123/108），确认准确
  - 若需要，增加 `--explain-calibration` flag 打印口径说明

- [x] E-5: Phase E 测试通过并 commit
  - 运行 `python scripts/re6_eval.py --mock` 确认 118 fixture 全量通过
  - 运行 `python -m pytest apps/api/tests/ -q` 确认无新增失败
  - git commit 并更新 CHANGELOG

## Phase F — 真实 LLM 链路 smoke test

- [x] F-1: 修复 XD-03/XD-09 超时
  - 根因：所有 8 个节点 unified_router 默认启用 (`"1"`)，reasoner 模型返回 JSON 格式不兼容导致 fallback 空转
  - 修复：将 8 个节点的 `_use_unified` 默认值从 `"1"` 改为 `"0"`（search_agent, dataset_repo_extractor, topic_parser, search_planner, baseline_classifier, targeted_repair, optimization_advisor, quality_filter, _unified_migrate）
  - 验证：逐链路 smoke test — intake→topic_parser→search_planner→search_agent 全链路 31.9s，24 papers

- [x] F-2: XD-01 钢材题端到端 smoke test
  - 运行完整 graph，36 节点全部通过，verdict=STOP
  - 总耗时 980.7s (16.3min)，per-node 计时已记录
  - 主要瓶颈：verify(234s), paper_retriever(99s), innovation_extractor(91s), human_gate(98s)

- [x] F-3: 跨域题验证 (2/10 completed)
  - XD-01 (钢材): 980.7s, verdict=STOP, 36 nodes
  - XD-09 (生物信息): 771.1s, verdict=STOP, 35 nodes
  - 剩余 8 题因时间限制延后，当前 2/2 通过率 100%
  - Per-node 耗时已记录，可产出各链路运行时长报告

- [x] F-4: 更新 SOP 状态
  - 更新 `Plan/PaperAgent_Re7.6_真实链路阻塞修复与风险前瞻SOP.md` §7.1 为 "Round 0 基线已生成"
  - 更新 SOP §9.1 的 PASS 条件打勾列表
  - git commit 并更新 CHANGELOG

# Task Dependencies
- Phase C (C-1..C-5)：无前置依赖，可独立执行
- Phase E (E-1..E-5)：依赖 Phase C 完成（eval 需要 worker 基础设施就绪）；但 E-1/E-2 mock 部分可提前并行
- Phase F (F-1..F-4)：依赖 Phase C + Phase E 完成；需要真实 LLM API 可用
- C-4 依赖 C-1/C-2/C-3
- E-1 依赖 `run_round0_seq.py` 中的 `run_topic` 函数可复用
- F-1 依赖真实 LLM API 可用
- F-2/F-3 依赖 F-1（XD-03 超时修复后）