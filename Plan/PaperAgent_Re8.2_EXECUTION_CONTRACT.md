# PaperAgent Re8.2 统一执行合同

> Status: **ACTIVE**  
> Scope: Re8.2 implementation and verification  
> Base repository state: `master@e811d2b7daf05b5140d3d9c6dfdc9a90584390a7`  
> Audit correction commit: `4c1b5e938888a228e0ce476b0d486b2608ba6220`

## 1. Canonical document set

Re8.2 的执行依据由以下文档共同构成：

1. `Plan/PaperAgent_Re8.2_SeedAudit收敛_Gate路由修复与真实E2E_SOP.md`；
2. `Plan/PaperAgent_Re8.2_SOP_AUDIT_AND_EXECUTION_CORRECTIONS.md`；
3. 本文件。

发生冲突时，优先级为：

```text
本统一执行合同
> SOP 审计与执行修订
> 原始 Re8.2 SOP
```

任何执行者不得只读取原始 SOP 后直接实现。审计修订中的 evaluation/reuse/cycle 分离、稳定 fingerprint 投影、stable candidate ID、critical conflict、source failure、冻结回归集与真实 Provider 脱敏合同均为强制要求。

## 2. 工作包顺序

```text
WP1 Gate evaluation/reuse/cycle
→ WP1 离线回归与 vit_dr 真实 smoke
→ WP2 Seed Repair 2.0
→ WP3 Seed Audit reason code / repair target
→ WP4 三案例真实重跑
→ WP5 真实 backend/frontend E2E
→ WP6 最终交接
```

在 WP1 未通过离线回归前，不并行修改 Seed Repair、Prompt 或前端类型。

## 3. WP1 已选架构

采用审计修订后的方案 A：**稳定输入 fingerprint + reusable pass + 独立 cycle**。

### 3.1 兼容层

保留现有 `reflection_gates.py` 作为单次 Gate evaluator、schema normalizer、round cap 和路由的来源。Re8.2 在其外增加：

- `reflection_gate_reuse.py`：稳定投影、SHA-256、cycle 隔离、pass reuse；
- `tailor_gate_entry.py`：运行模式 guard，禁止把 `skip` 当作真实可复用 pass；
- `final_recommendation_re82.py`：把 evaluation/reuse/cycle 审计信息加入最终研究包。

不修改：

- `REFLECTION_GATE_MAX_ROUNDS=2`；
- ablation 最少 4 项；
- fused verdict 和 quality hard constraints；
- 原 Gate prompt；
- 原结果 fixture。

### 3.2 状态合同

新增 additive 状态：

```text
last_gate_pass
gate_cycle_id
gate_cycle_start_index
gate_input_fingerprint
gate_reuse_count
gate_evaluation_events
gate_reuse_events
```

定义：

- `reflection_gate_results`：仅真实 evaluator 结果；reuse 不追加；
- `evaluation_round_idx`：当前 cycle 内的真实 evaluation 索引；
- `reuse_count`：复用次数，不消耗 round；
- `cycle_id`：稳定语义输入改变时递增；
- `gate_cycle_start_index`：当前 cycle 在历史 evaluation log 中的起始位置。

### 3.3 Fingerprint 合同

Tailor fingerprint 使用 canonical JSON + SHA-256。投影包含：

- Tailor 方法语义输出；
- evidence gap 的 `gap_id/status/evidence_delta/evidence_ids`；
- Seed identity/role；
- ablation 与 compatibility 结构。

必须排除：

```text
raw_input
pdf_bytes
本地路径
trace / ledger
timestamp / elapsed
provider request id
```

业务集合按稳定键排序，不依赖异步返回顺序。

### 3.4 Reuse 合同

仅当以下条件全部满足时复用：

1. 当前运行启用 `full_agent + react_reflection`；
2. 存在真实 pass；
3. pass fingerprint 与当前 fingerprint 完全一致；
4. 缓存结果不是 `generated_by=skip`。

Reuse 必须：

- 不调用 evaluator/LLM；
- 不追加 `reflection_gate_results`；
- 不增加 evaluation round；
- 追加 reuse event、trace 和 ledger；
- 保留原 pass 的 rationale、cycle 和 round 来源。

## 4. WP1 验收命令

```bash
python -m py_compile \
  apps/api/app/services/agents/graph/state.py \
  apps/api/app/services/agents/graph/nodes/reflection_gate_reuse.py \
  apps/api/app/services/agents/graph/nodes/tailor_gate_entry.py \
  apps/api/app/services/agents/graph/nodes/final_recommendation_re82.py

ruff check \
  apps/api/app/services/agents/graph/state.py \
  apps/api/app/services/agents/graph/nodes/reflection_gate_reuse.py \
  apps/api/app/services/agents/graph/nodes/tailor_gate_entry.py \
  apps/api/app/services/agents/graph/nodes/final_recommendation_re82.py

pytest -q \
  apps/api/tests/test_re82_gate_reuse.py \
  apps/api/tests/test_re82_tailor_gate_entry.py \
  apps/api/tests/test_re82_final_package_gate_audit.py

pytest -q apps/api/tests -k "re8"
```

离线测试通过后，真实 smoke 必须验证：

```text
vit_dr:
- Tailor 首次真实 pass；
- final_review repair 回到 evidence_context；
- Tailor semantic fingerprint 不变；
- trace 出现 gate_pass_reused；
- Tailor evaluation log 长度不增加；
- fused verdict 不再因 Tailor 重入 cap 而 BLOCKED。
```

## 5. 真实测试边界

离线 pytest、Fake evaluator、rule fallback 和 Graph 单元测试不能表述为真实 Provider 或真实 E2E。

真实 Mistral smoke 仅在以下条件满足后执行：

- Secret 通过运行时 Secret 注入，不进入仓库、artifact、trace 或日志；
- 冻结 model ID、endpoint、max tokens、timeout 和成本上限；
- 当前执行环境可解析并访问 `api.mistral.ai`；
- WP1 离线回归已通过。

网络无法到达 Provider 时，状态必须写为 `BLOCKED BY EXECUTION ENVIRONMENT / KEY NOT VERIFIED`，不得推断为 401、403 或 Key 无效。

## 6. 当前范围边界

本工作分支只实现 WP1。以下内容不得在本分支伪装为完成：

- WP2 Seed Candidate 统一模型和 stable candidate ID；
- `repair_target/reason_code` API/前端全链路；
- xlm_r / yolo_steel 真实消歧；
- 三案例真实 Provider 重跑；
- 无 mock 的真实 backend/frontend E2E。
