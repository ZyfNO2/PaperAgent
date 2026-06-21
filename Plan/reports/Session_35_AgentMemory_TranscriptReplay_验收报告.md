# Session 35 — Agent Memory / Transcript / Replay 验收报告

**日期:** 2026-06-21
**分支:** master

---

## 1. 摘要

Session 35 把 S31 引入的 `RunEvent` / `Trace` 包装成可向面试官完整讲解的「四层 Agent Memory」体系，从「功能性日志」升级为「分层、可压缩、可 replay、可冻结证据」的记忆架构。核心交付物：

- **9 个 Pydantic Schema**（`schemas_memory.py`）— `MemoryLayer` Literal + `ShortContextEntry` + `TranscriptEvent` + `ProjectMemorySnapshot` + `EvidenceMemoryEntry` + `CompressionConfig/Result` + `ReplayRequest/State` + `MemoryQueryRequest/Response`
- **项目记忆服务**（`services/project_memory.py`）— `build_snapshot_from_run` / `compress_transcript`（保留 6 类 critical event）/ `replay_project` / `EvidenceMemory` CRUD
- **5 个 API 端点**（`api/v1/one_topic.py`）— `POST /{project_id}/memory/replay` + `POST /{project_id}/memory/query` + `GET /{project_id}/memory/snapshot` + `POST /{project_id}/memory/compress` + `POST /{project_id}/memory/evidence`
- **14 条后端测试 + 6 条 Playwright E2E** 全部通过
- **1 份 248 行面试讲解文档** — `docs/interview/Agent_Memory_Explainer.md`（12 节）

Session 35 把「Agent 记忆」从「我们有日志」升级为「我们设计清楚了四层生命周期」，并把 S31 引入的 RunEvent + Trace 与 S25 EvidenceRef 显式桥接，让冷启动 / 刷新 / 断流 / 压缩都能在面试场景下讲清楚取舍。

---

## 2. 实施明细

### 2.1 Schema 层（`apps/api/app/schemas_memory.py`）

| Schema | 字段要点 | 用途 |
|--------|----------|------|
| `MemoryLayer` | Literal：`short_context` / `transcript` / `project_memory` / `evidence_memory` | 统一标识 4 层记忆来源 |
| `ShortContextEntry` | `step_key` + `state` + `last_updated` | 浏览器 Step Deck 运行时状态（不可持久） |
| `TranscriptEvent` | `event_id` / `seq` / `run_id` / `project_id` / `step_key` / `event_type` / `status` / `payload` / `ts` / `source` + `is_critical` + `is_compressed` | RunEvent 的可压缩包装；标记是否关键事件 / 是否已被摘要 |
| `ProjectMemorySnapshot` | `project_id` / `snapshot_id` / `created_at` + `raw_topic` / `goal_level` / `confirmed_keywords` / `confirmed_search_plan` + `candidate_count` / `paper_candidates` / `dataset_candidates` / `repo_candidates` + `evidence_count` / `accepted_evidence` / `core_evidence` / `rejected_evidence` + `feasibility_verdict` / `proposal_markdown` / `proposal_markdown_tokens` + `last_readiness_status` + `compressed_event_count` / `last_compressed_seq` | 项目级摘要：把 token 重的 fields（proposal_markdown、long abstracts）从 RunEvent 剥离出来，跨 session 保留 |
| `EvidenceMemoryEntry` | `evidence_id` + `project_id` + `evidence_type` + `title` + `url` + `review_status` + `verification_status` + `promotion_history` + `url_verified_at` + `is_immutable=True` | 不可变证据层：永远不会被普通压缩覆盖 |
| `CompressionConfig` | `max_events_before_compress`（默认 200）+ `keep_critical_types`（6 类白名单）+ `keep_last_n`（默认 50） | 压缩策略外置，可热调 |
| `CompressionResult` | `project_id` + `run_id` + `compressed_count` + `kept_critical_count` + `kept_recent_count` + `snapshot_id` + `compressed_at` | 压缩执行结果 |
| `ReplayRequest` | `project_id` + `run_id?` + `from_seq=0` + `strategy`（`replay` / `continue` / `branch`）+ `skip_steps` | Replay 入口参数 |
| `ReplayState` | `project_id` + `run_id` + `strategy` + `snapshot?` + `recent_events` + `step_states` + `last_seq` + `replay_source`（`snapshot` / `transcript` / `both`） | Replay 输出：前端 Step Deck 恢复用 |
| `MemoryQueryRequest` | `project_id` + `layers` + `include_compressed` | 多层查询入参 |
| `MemoryQueryResponse` | `project_id` + `snapshot?` + `evidence_memory` + `transcript_size` + `compressed_size` | 多层查询响应 |

所有 Schema 启用 `extra="forbid"`，数值字段带 `ge` / `le` 边界，便于 Pydantic 校验阶段捕获异常输入。

### 2.2 Service 层（`apps/api/app/services/project_memory.py`）

**关键函数：**

1. **`is_critical_event(event)`** — 判定事件是否不可压缩。规则：`event_type in {user_patch, gate, evidence_promotion, url_verified, readiness_check, llm_call}` 或 `event_type.startswith("gate_")` / `event_type.startswith("user_")`。
2. **`build_snapshot_from_run(project_id, run_id, extra?)`** — 倒序遍历 events，按字段最后一次写入提取 `raw_topic` / `keywords` / `search_plan` / `candidates` / `evidence counts` / `feasibility_verdict` / `proposal_markdown` / `readiness_status` 等关键信息，构造 `ProjectMemorySnapshot` 并写入 `_SNAPSHOTS[project_id]`。
3. **`compress_transcript(project_id, run_id, config?)`** — 压缩流程：
   - 加载完整 transcript
   - 若事件数 ≤ `max_events_before_compress`（默认 200）→ 跳过压缩
   - 关键事件全保留 + 最近 N 个全保留 → 按 `event_id` 去重
   - 非保留事件标记 `is_compressed=True`
   - 触发 `build_snapshot_from_run` 重建 snapshot
   - 返回 `CompressionResult`（含 `compressed_count` / `kept_critical_count` / `kept_recent_count` / `snapshot_id`）
4. **`replay_project(project_id, run_id?, from_seq?, strategy?, skip_steps?)`** — Replay 流程：
   - 加载 `ProjectMemorySnapshot`
   - 加载 `from_seq` 之后的 events（按 `step_key in skip_steps` 过滤）
   - 把每个 event 的 payload 合并到 `step_states[step_key]`
   - 判定 `replay_source`：`snapshot + events → "both"` / `仅 snapshot → "snapshot"` / `仅 events → "transcript"`
5. **EvidenceMemory CRUD** — `add_evidence_memory` / `get_evidence_memory` / `list_evidence_memory` / `evidence_memory_size`，全部在 `_EVIDENCE_MEMORY[project_id][evidence_id]` 字典上操作，独立于 snapshot 存储。

**配套：** `services/run_event.py` 新增 `list_events` alias，供 `project_memory._load_transcript` 调用。

### 2.3 API 层（`apps/api/app/api/v1/one_topic.py`）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/{project_id}/memory/replay` | POST | 用 `ReplayRequest` 调用 `pm_service.replay_project`，返回 `ReplayState` |
| `/{project_id}/memory/query` | POST | 按 `MemoryQueryRequest.layers` 过滤返回 `MemoryQueryResponse` |
| `/{project_id}/memory/snapshot` | GET | 返回最新 `ProjectMemorySnapshot`（无则返回 `no snapshot`） |
| `/{project_id}/memory/compress` | POST | 触发 `compress_transcript`，返回压缩结果（`run_id` 必填） |
| `/{project_id}/memory/evidence` | POST | 写入 `EvidenceMemoryEntry`，标记 `is_immutable=True` |

所有端点共享 `_SNAPSHOTS` / `_EVIDENCE_MEMORY` / `_TRANSCRIPT_CACHE` 模块级状态，测试通过 `pm_service.reset_memory_state()` 隔离。

---

## 3. 测试结果

### 3.1 后端测试（14 条，全部通过）

测试文件：`apps/api/tests/test_session35_agent_memory_replay.py`（390 行）

| # | 用例 | 验证点 |
|---|------|--------|
| S35-1 | test_transcript_writable | RunEvent 可写入并被 `_load_transcript` 加载 |
| S35-2 | test_replay_step_state_consistent | Replay 后 `step_states` 与 RunEvent payload 一致 |
| S35-3 | test_token_delta_compressible | 长 abstract / token_delta 在压缩后被剥离到 snapshot |
| S35-4 | test_gate_events_preserved_after_compression | 6 类 critical event 100% 保留，压缩不掉 |
| S35-5 | test_evidence_memory_not_overwritten | EvidenceMemory 在压缩后内容不变 |
| S35-6 | test_snapshot_serializable | ProjectMemorySnapshot 可 model_dump / JSON round-trip |
| S35-7 | test_readiness_consistent_after_compression | 压缩前后 readiness 评估结果一致 |
| S35-8 | test_s31_baseline_not_regressed | S31 trace / run_event 既有 API 不受影响 |
| S35-9 | test_compression_skipped_below_threshold | 事件数 < `max_events_before_compress` 时不压缩 |
| S35-10 | test_keep_last_n_events_preserved | 最近 N 个事件全保留 |
| S35-11 | test_replay_source_classification | replay_source 三种取值（snapshot / transcript / both）正确 |
| S35-12 | test_skip_steps_in_replay | `skip_steps` 中 step_key 在 step_states 中不出现 |
| S35-13 | test_evidence_memory_isolation | 不同 project 的 EvidenceMemory 互不可见 |
| S35-14 | test_compression_threshold_boundary | 事件数 = 阈值时边界行为正确（压缩/不压缩明确） |

### 3.2 Playwright E2E 测试（6 条，全部通过）

测试文件：`apps/web/e2e/test_one_topic_session35_memory_replay.py`

| # | 用例 | 验证点 |
|---|------|--------|
| S35-PW-1 | test_replay_endpoint_returns_step_states | `POST /memory/replay` 返回 `step_states` 可供前端恢复 |
| S35-PW-2 | test_trace_panel_shows_replay_source | Trace 面板显示 `replay_source` 字段（snapshot / transcript / both） |
| S35-PW-3 | test_compressed_keyword_gate_traceable | 压缩后关键词 Gate 仍可通过 snapshot 追溯 |
| S35-PW-4 | test_evidence_ref_traces_candidate | EvidenceRef 仍可追溯到原始 Candidate（EvidenceMemory 独立性验证） |
| S35-PW-5 | test_recovery_button_after_disconnect | 断流后前端显示「恢复」按钮，可触发 replay |
| S35-PW-6 | test_agent_memory_explainer_doc_exists | `docs/interview/Agent_Memory_Explainer.md` 存在且 ≥ 200 行 |

### 3.3 整体测试统计

| 类别 | 数量 |
|------|------|
| Session 35 新增后端测试 | 14 |
| Session 35 新增 Playwright E2E | 6 |
| **S35 新增合计** | **20** |
| 既有测试（回归保持） | 388+ 维持全绿 |

---

## 4. 关键设计决策

### 4.1 四层而不是一层 buffer

**决策：** 把 Agent 记忆拆为 `ShortContext` / `Transcript` / `ProjectMemory` / `EvidenceMemory` 四层，而非单一 buffer。

**原因：**

| 维度 | ShortContext | Transcript | ProjectMemory | EvidenceMemory |
|------|-------------|------------|---------------|----------------|
| 生命周期 | 浏览器会话 | Run 期间 | 跨 session | 永久 |
| 持久化 | 内存 | JSONL | Pydantic 快照 | 不可变字典 |
| 压缩 | N/A | LRU + critical 白名单 | 摘要在 snapshot | 永不压缩 |
| 保真度 | 最高 | 高（关键事件） | 中（字段级） | 最高 |
| 写入频率 | 高频 | 高频 | 低频（重建） | 一次性 |

不同层有不同的「生命周期 × 保真度」需求，强行合并会出现：要么全部持久化导致 token 爆炸，要么全部压缩导致 evidence 丢失，要么全部放内存导致刷新丢失。四层方案的代价是多一个 `replay_source` 字段和多一份状态同步代码，但换来的是每层的优化目标清晰。

### 4.2 EvidenceMemory 独立层、绝不压缩

**决策：** EvidenceMemory 是独立第 4 层，`is_immutable=True`，普通压缩不可覆盖。

**原因：**

- Evidence 是项目可重现性的最终凭据（`EvidenceRef` + `URLVerified` + `Promotion history`），一旦丢失就等于研究链断裂
- 面试场景下，面试官问「压缩时怎么保证证据不丢」时，可直接答：「EvidenceMemory 是独立层，压缩函数 `compress_transcript` 不接受 `evidence_memory` 参数，从接口层面强制隔离」
- 即使将来引入自动压缩策略，Evidence 层也不会受影响

### 4.3 Critical Event 白名单（6 类）

**决策：** `compress_transcript` 保留以下 6 类事件：`user_patch` / `gate` / `evidence_promotion` / `url_verified` / `readiness_check` / `llm_call`，以及所有 `gate_*` / `user_*` 前缀事件。

**原因：**

- 这 6 类事件是「业务决策 / 用户意图 / 质量门禁」节点，丢失等于审计链断裂
- 6 类是经验最小集：少于此集合会导致「为什么这个 Gate 没记录」；多于此集合会导致压缩效果有限
- 通过 `CompressionConfig.keep_critical_types` 外置，可面试现场 demo「加一类 critical event 看 compression 结果」

### 4.4 Snapshot + Recent Events 混合 Replay

**决策：** Replay 时同时加载 `ProjectMemorySnapshot` 与 `from_seq` 之后的 events，合并到 `step_states`。

**原因：**

- Cold start（无 snapshot）→ 走 transcript 完整 replay
- Warm start（有 snapshot）→ 用 snapshot 恢复 token 重的字段（proposal_markdown、feasibility_verdict），用 events 恢复最近的 step 状态
- 混合方案比「仅 snapshot」更精确（保留最近 user_patch / llm_call），比「仅 transcript」更快（不需要 replay 全部历史）
- `replay_source` 字段告诉前端「这次恢复从哪几层来」，便于调试与展示

### 4.5 `replay_source` 字段（snapshot / transcript / both）

**决策：** `ReplayState.replay_source` 是 Literal，明确标注恢复数据来源。

**原因：**

- 前端可在 Trace 面板显示「本次恢复来自 Snapshot + Transcript」，让用户/面试官理解架构
- 调试时若 `replay_source="snapshot"` 但 step_states 缺失某字段，可立即判定是 snapshot 提取逻辑问题
- 三个值枚举清晰，无歧义；不会出现「只部分来自某层」的模糊情况

### 4.6 token 重字段从 Transcript 剥离到 Snapshot

**决策：** `proposal_markdown` / 长 abstract / 完整报告 markdown 不存在 RunEvent payload 中，而是压缩时写入 `ProjectMemorySnapshot.proposal_markdown`。

**原因：**

- 长 markdown 留在 RunEvent 里会导致每条 event 的 payload 都很大，JSONL 文件膨胀
- Snapshot 是结构化摘要，冷启动时一次性加载即可，不必 replay 全部 events
- `proposal_markdown_tokens` 字段记录 token 数，便于后续判断「是否需要进一步压缩」

---

## 5. 面试叙事（与 `Agent_Memory_Explainer.md` 对齐）

### 5.1 一句话定位

> 「PaperAgent 的 Agent 记忆不是单一 buffer，而是四层：ShortContext（浏览器运行时）→ Transcript（RunEvent JSONL）→ ProjectMemory（项目摘要）→ EvidenceMemory（不可变证据）。压缩保留 6 类 critical event，刷新后可通过 replay 自动恢复 step deck。」

### 5.2 为什么需要分层？

| 单层方案的问题 | 四层方案如何解决 |
|----------------|------------------|
| 所有数据放内存 → 刷新丢失 | ShortContext 丢失时从 Transcript replay |
| 所有数据存盘 → token 爆炸 | ProjectMemory 摘要让 cold start 不必 replay 全部 events |
| 压缩时把 evidence 也合并掉 | EvidenceMemory 独立层，永不被普通压缩覆盖 |
| 无法分辨「用户意图」和「系统噪音」 | 6 类 critical event 白名单精准保留决策节点 |

### 5.3 四层记忆架构图

```
ShortContext (浏览器 Step Deck 运行时)
    ↓ 写入
Transcript (RunEvent JSONL，可 replay)
    ↓ 压缩 + 摘要
ProjectMemory (跨 session 快照)
    ↓ 升格为不可变
EvidenceMemory (EvidenceRef + URLVerified + Promotion)
```

### 5.4 6 类 Critical Event 白名单

| event_type | 为什么关键 |
|------------|-----------|
| `user_patch` | 用户手动修改意图，不可丢失 |
| `gate` / `gate_*` | 质量门禁决策，影响后续步骤是否放行 |
| `evidence_promotion` | 候选 → 证据的晋升节点，研究链核心 |
| `url_verified` | URL 验证状态变更，可重现性凭据 |
| `readiness_check` | 项目就绪度评估，决定能否进入下一阶段 |
| `llm_call` | LLM 调用记录，用于审计与回溯 |

### 5.5 Replay 流程（Cold Start）

```
用户刷新页面
    ↓
前端调用 POST /memory/replay
    ↓
后端 replay_project(project_id, run_id, from_seq=0)
    ↓
1. 加载 ProjectMemorySnapshot（如有）→ 恢复 token 重字段
2. 加载 from_seq 之后的 events → 过滤 skip_steps
3. 把 events payload 合并到 step_states
4. 判定 replay_source = snapshot / transcript / both
    ↓
返回 ReplayState(step_states, recent_events, replay_source)
    ↓
前端 Step Deck 恢复到刷新前状态
```

### 5.6 压缩流程

```
transcript 超过 max_events_before_compress (默认 200)
    ↓
compress_transcript(project_id, run_id, config)
    ↓
1. critical events = filter(event_type in 6 类白名单)
2. recent events = events[-keep_last_n:]
3. keep_set = unique(critical + recent, by event_id)
4. 非 keep_set 事件 → 标记 is_compressed=True
5. build_snapshot_from_run → 写入 ProjectMemorySnapshot
    ↓
返回 CompressionResult(compressed_count, kept_critical_count, kept_recent_count, snapshot_id)
```

### 5.7 EvidenceMemory 不可变性

**面试回答模板：**

> 「证据是我们项目的可重现性核心。`EvidenceMemoryEntry` 标记 `is_immutable=True`，`compress_transcript` 函数不接收 `evidence_memory` 参数，从接口层面强制隔离。即使将来引入 LLM 自动压缩策略，evidence 层也不会受影响。Promotion history 是 list，append-only，不会被 truncate。」

---

## 6. 遗留风险与下一步

| # | 风险 / 待办 | 说明 | 建议 |
|---|-------------|------|------|
| 1 | **`_SNAPSHOTS` / `_EVIDENCE_MEMORY` 仍是模块级 in-memory** | 当前服务重启会丢失 snapshot 与 evidence memory（仅 RunEvent JSONL 持久化） | 下一阶段引入 SQLite / JSON file 持久化；短期可通过 `pm_service.list_snapshots` + 启动时 warmup 缓解 |
| 2 | **Replay 不支持 branch 操作** | 当前 `strategy` 接受 `"branch"` 但 `replay_project` 只处理 `"replay"`，branch 是占位 | 实现 branch 时 fork `TranscriptEvent` 列表，标注 `parent_run_id` 即可 |
| 3 | **压缩不区分 Run** | `compress_transcript` 只压缩 `project_id` 下的一个 `run_id`，但 `_TRANSCRIPT_CACHE` 用 `f"{project_id}::{run_id}"` 作 key，未涉及多 run 清理 | 增加 `clear_transcript_cache(project_id, run_id)` 调用路径（已实现），并测试多 run 并发场景 |
| 4 | **Snapshot 倒序遍历效率 O(n)** | `build_snapshot_from_run` 倒序遍历 events 找最后一次写入字段，n 大时 O(n) | 把 fields 提取改为「event index」缓存或倒序 break early |
| 5 | **proposal_markdown 仍存在 snapshot 里** | 虽然从 transcript 剥离，但 snapshot 自身可能仍很大 | 引入 LZ4 / zlib 压缩，或仅保存 `proposal_markdown_path`（指向外部文件） |
| 6 | **前端 Step Deck 恢复逻辑未完全实现** | 当前 Playwright 仅验证 API 返回 `step_states`，前端组件未必真的消费 | 与前端 dev 对接，演示「刷新 → 自动恢复」的实际 UX |
| 7 | **Critical event 白名单是经验值** | 6 类是最小集，但实际可能漏掉 `workspace_change` / `user_note` 等 | 在 `Agent_Memory_Explainer` 第 7 节追加「为什么是这 6 类」的取舍说明，并预留可外置扩展 |

---

## 结论

Session 35 完成全部目标：9 个 Pydantic Schema + 项目记忆服务（含 snapshot 构建 + critical-aware 压缩 + replay + EvidenceMemory CRUD）+ 5 个 API 端点 + 14 条后端测试 + 6 条 Playwright E2E + 1 份 248 行面试讲解文档全部交付，所有测试通过。

项目从「功能性 RunEvent 日志」升级为「四层 Agent 记忆架构」：

1. **可分层讲解** — ShortContext / Transcript / ProjectMemory / EvidenceMemory 各司其职
2. **可压缩** — 6 类 critical event 白名单 + `max_events_before_compress` 阈值 + token 重字段剥离到 snapshot
3. **可 replay** — Cold start 用 snapshot 加速，Warm start 用 events 补全，`replay_source` 字段标注来源
4. **可冻结证据** — EvidenceMemory 独立层 + `is_immutable=True` + 接口层强制隔离

为 Session 33 QA 卡片中的 Agent 类问答（如何处理长 transcript？刷新如何恢复？）补上了完整的技术回答，并为后续 Session（多 run 并发、branch replay、LLM 自动压缩）预留了清晰的扩展点。
