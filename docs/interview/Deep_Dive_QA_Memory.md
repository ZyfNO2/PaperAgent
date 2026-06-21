# Deep Dive Q&A — Agent Memory / Replay（Session 38 补充）

> 面试时被连续追问 Memory 细节时，怎么稳定输出？
>
> **当前不足**：Snapshot 是 in-memory，未持久化到 SQLite；JSONL 性能受磁盘限制。
>
> **核心文件：** `apps/api/app/services/project_memory.py`、`apps/api/app/schemas_memory.py`、`apps/api/tests/test_session35_agent_memory_replay.py`、`docs/interview/Agent_Memory_Explainer.md`

---

## Q1: 为什么需要分层 Memory？

**短答：** 不同层有不同的生命周期和保真度需求，强行合并会顾此失彼。

| 单层方案 | 四层方案 |
|---|---|
| 所有数据放内存，刷新丢失 | ShortContext 丢失时 replay Transcript |
| 所有数据存盘，token 爆炸 | ProjectMemory 摘要让 cold start 不需要 replay 全部 events |
| 压缩时把 evidence 也合并掉 | EvidenceMemory 独立层，永不被覆盖 |

---

## Q2: 4 层 Memory 的边界？

| 层 | 生命周期 | 用途 | 可压缩 |
|---|---|---|---|
| ShortContext | 当前 session | 流式 UI 重建 | 否 |
| Transcript | 当前 session | 可 replay | 是（保留 critical） |
| ProjectMemory | 跨 session | cold start, audit | 否 |
| EvidenceMemory | 永久 | 不可变证据 | 否 |

---

## Q3: 压缩会丢什么？

**不会丢关键信息。**

6 类 critical 事件 100% 保留：
- user_patch
- gate / gate_*
- evidence_promotion
- url_verified
- readiness_check
- llm_call

**其余事件** 才被标 `is_compressed=True`：
- candidate_scored
- retrieval_completed
- heuristic_fallback

---

## Q4: 怎么恢复？

**3 步：**
1. 加载 `ProjectMemorySnapshot`（cold start 概要）
2. 加载 Transcript events（from_seq 之后）
3. 合并 step_states 供前端重建

**关键：** 不从 event 0 开始 replay，而是 snapshot + 最近 N events。

---

## Q5: `replay_source` 字段是什么？

API 返回里加 `replay_source` 告诉前端数据来源：
- `"snapshot"` — 仅来自 ProjectMemory
- `"transcript"` — 仅来自 RunEvent
- `"both"` — 两个都用了

**为什么需要？** 调试和审计时一眼看出 cold start 状态。

---

## Q6: 你的 Memory 怎么持久化？

- **Transcript**: `.runtime/runs/{project_id}/{run_id}/events.jsonl`
- **State**: `.runtime/runs/{project_id}/{run_id}/state.json`
- **ProjectMemorySnapshot**: in-memory（可持久到 SQLite）
- **EvidenceMemory**: in-memory（来自 Evidence Ledger，跨 session 持久）

---

## Q7: 上下文超限怎么办？

**两层防护：**
1. **Compression** — events 超过阈值（默认 200）自动压缩
2. **Snapshot** — token 重字段（proposal_markdown）剥离到 snapshot

**面试回答：**

> 「我们用 Snapshot 把 token 重的字段从 RunEvent 里剥离。Replay 时只加载 snapshot 概要 + 最近 N events，token 用量可控。」

---

## Q8: 刷新页面怎么恢复？

**ProjectMemory 层面：**
1. 断流检测 — 前端用 `run_state.json` 检测 last_seq
2. 断流后 — 显示「恢复」按钮
3. 点击恢复 — 调用 `/memory/replay`
4. 重建 Step Deck — step_states 把每个 step 跳到对应状态

---

## Q9: Short-term vs Long-term 怎么分？

| 维度 | Short (ShortContext+Transcript) | Long (ProjectMemory+EvidenceMemory) |
|---|---|---|
| 生命周期 | 当前 session | 跨 session |
| 大小 | 增长型（触发压缩） | 有界 |
| 用途 | 流式 UI 重建 | cold start, audit, regression |
| 可压缩 | 是 | 否 |
| API | `/memory/replay` | `/memory/snapshot` `/memory/evidence` |

---

## Q10: 和 LangChain Memory 有什么差异？

| LangChain Memory | PaperAgent Memory |
|---|---|
| 单一 buffer / summary | 四层分层 |
| 自动压缩（不易审计） | 显式 critical 事件分类 |
| 没有不可变层 | EvidenceMemory 独立层 |
| 与 chain 紧耦合 | 与 step deck 解耦 |

---

## Q11: EvidenceMemory 为什么不可变？

**3 个原因：**
1. **审计** — 引用关系不能改
2. **追溯** — 改了就失去因果链
3. **合规** — 学术引用必须稳定

**如何"修改"？** 添加新 Evidence，不修改旧的。

---

## Q12: Snapshot 多久生成一次？

**当前：** 每次 build_snapshot_from_run() 调用时（手动触发）。

**未来：**
- 每次 step 完成自动生成
- 定时任务
- 成本阈值触发

---

## Q13: 压缩率怎么算？

```
compression_rate = compressed_count / total_count
```

**典型：** 50%（100 个 events 压到 50 个）

**观察指标：** 压缩率过高 = critical 比例太低，应该收紧 keep_critical_types。

---

## Q14: 怎么测试 Memory？

**4 维测试：**
1. **写入** — event 能 append 到 JSONL
2. **读取** — replay 还原 step_states
3. **压缩** — critical 不丢
4. **不可变性** — EvidenceMemory 压缩后仍存在

**项目证据：** 14 个后端测试 + 6 个 Playwright。

---

## Q15: 你的 Memory 设计哲学？

**3 条原则：**
1. **不同层有不同生命周期** — 合并会顾此失彼
2. **关键事件永不被压缩** — 用户意图、决策路径
3. **不可变证据独立** — 学术引用必须稳定

**核心论点：** Memory 不是「存得越多越好」，而是「每一层只存适合它生命周期的东西」。

---

## Q16: 怎么支持跨 session？

**ProjectMemorySnapshot 跨 session 保留：**
- 存盘（未来接 SQLite）
- key: `project_id`
- value: `ProjectMemorySnapshot`

**Cold start 流程：**
1. 用户开新 session
2. 加载 snapshot（毫秒级）
3. 不需要重跑所有 step

---

## Q17: 怎么支持多人协作？

**当前：** 内存级 in-memory，不支持多人。

**未来：**
- Snapshot 存 SQLite
- EvidenceMemory 存远端 DB
- 冲突解决：最后写入获胜 + Trace 记录

---

## Q18: Replay 失败怎么办？

**降级：**
1. Snapshot 在 → 用 snapshot
2. Transcript 在 → 用 transcript
3. 都没有 → 显示 "项目需要重新开始"

**关键：** Replay 失败不丢数据，原始 events 还在磁盘。

---

## Q19: 为什么 Replay 用 JSONL 而不是 SQLite？

| 维度 | JSONL | SQLite |
|---|---|---|
| 简单 | ✅ 1 文件 | ❌ 需 schema |
| 调试 | ✅ cat 即可 | ❌ 需 SQL 客户端 |
| 并发 | ❌ 锁 | ✅ 行级锁 |
| 查询 | ❌ 全文扫描 | ✅ 索引 |
| 适合 | MVP / 调试 | 生产 |

**PaperAgent MVP 用 JSONL，证据充分后再迁 SQLite。**

---

## Q20: 你的 Memory 怎么支持 AB 实验？

**ProjectMemorySnapshot 包含全部字段：**
- `feasibility_verdict`
- `accepted_evidence`
- `core_evidence`

可以做：
- 同一 topic 不同 prompt 对比
- 不同 heuristic 对比
- 不同 readiness 阈值对比

---

> **面试重点：** PaperAgent 的 4 层 Memory 不是「有日志」，而是「有清楚分层的、生命周期合理的、压缩可审计的证据持久化」。关键事件永不被压缩，刷新页面可自动 replay 恢复。
