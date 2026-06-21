# Agent 记忆系统面试讲解（Session 35）

> 把项目整理成面试可讲的「四层 Agent 记忆」架构。
> 不只是「我们存了日志」，而是「我们有清楚的分层记忆」。

---

## 1. 一句话定位

PaperAgent 使用 **四层 Agent 记忆**：ShortContext（浏览器运行时）→ Transcript（RunEvent JSONL）→ ProjectMemory（项目摘要）→ EvidenceMemory（不可变证据）。压缩策略保留 critical 事件不丢，刷新页面后可自动 replay 恢复。

---

## 2. 四层记忆架构

```
┌──────────────────────────────────────────────┐
│  Layer 1: ShortContext                       │
│  - 当前 Step Deck 的 runState                │
│  - 浏览器内存                               │
│  - 刷新可能丢失                             │
└──────────────────────────────────────────────┘
                  ↓ 写入
┌──────────────────────────────────────────────┐
│  Layer 2: Transcript                         │
│  - RunEvent JSONL (events.jsonl)            │
│  - 可 replay                                │
│  - 超过阈值触发压缩                         │
└──────────────────────────────────────────────┘
                  ↓ 压缩 + 摘要
┌──────────────────────────────────────────────┐
│  Layer 3: ProjectMemory                      │
│  - ProjectMemorySnapshot (项目级摘要)        │
│  - 跨 session 保留                          │
│  - token 重字段从 transcript 剥离           │
└──────────────────────────────────────────────┘
                  ↓ 升格为不可变
┌──────────────────────────────────────────────┐
│  Layer 4: EvidenceMemory                     │
│  - EvidenceRef + URLVerified + Promotion     │
│  - 不可压缩 / 不可覆盖                      │
│  - 最高可信                                 │
└──────────────────────────────────────────────┘
```

---

## 3. 为什么需要分层？

| 单层方案 | 四层方案 |
|---|---|
| 所有数据都放内存，刷新丢失 | ShortContext 丢失时 replay Transcript |
| 所有数据都存盘，token 爆炸 | ProjectMemory 摘要让 cold start 不需要 replay 全部 events |
| 压缩时把 evidence 也合并掉 | EvidenceMemory 是独立层，永不被覆盖 |

**关键差异：** 不同层有不同的生命周期和保真度需求，强行合并会顾此失彼。

---

## 4. 关键事件分类 (压缩保留)

```python
CRITICAL_EVENT_TYPES = {
    "user_patch",         # 用户对 run 的修正
    "gate",               # 任何 Gate 决策 (keyword_gate / evidence_gate / readiness_gate)
    "evidence_promotion", # Candidate → Evidence 晋升
    "url_verified",       # URL 验证结果
    "readiness_check",    # 导出前检查结果
    "llm_call",           # LLM 调用记录（debug 关键）
}
```

**为什么这些是 critical？**

- `user_patch` — 用户意图不可丢
- `gate_*` — 决策路径是审计 trail
- `evidence_promotion` — 证据晋升链路可追溯
- `url_verified` — URL 验证结果影响后续判断
- `readiness_check` — 导出决策历史
- `llm_call` — debug + 成本审计

---

## 5. 压缩策略

```python
def compress_transcript(project_id, run_id):
    events = load_all(project_id, run_id)
    if len(events) <= MAX_EVENTS: return  # 不压

    # 1. 关键事件全保留
    critical = [e for e in events if e.is_critical]

    # 2. 最近 N 个全保留（保留 freshness）
    recent = events[-KEEP_LAST_N:]

    # 3. 其余的标 is_compressed = True
    keep_set = {e.event_id for e in critical + recent}
    for e in events:
        if e.event_id not in keep_set:
            e.is_compressed = True

    # 4. 生成 ProjectMemorySnapshot
    snapshot = build_snapshot(events)
    snapshot.compressed_event_count = len(events) - len(keep_set)
    return snapshot
```

**压缩不会丢什么？**

- 关键事件：100% 保留
- 最近 N 个事件：100% 保留
- snapshot：保留每个字段的「最后一次写入」
- EvidenceMemory：100% 保留，独立于 transcript

---

## 6. Replay 恢复流程

```
用户刷新页面 / 断流恢复
   ↓
GET /{project_id}/memory/replay
   ↓
1. 加载 ProjectMemorySnapshot（cold start）
   ↓
2. 加载 Transcript events (from_seq 之后)
   ↓
3. 合并 step_states 供前端恢复 Step Deck
   ↓
前端用 step_states 重建 step 状态
   ↓
用户看到「恢复完成」提示
```

**Replay 返回结构：**

```json
{
  "project_id": "p1",
  "run_id": "run_xxx",
  "strategy": "replay",
  "snapshot": { "raw_topic": "...", "feasibility_verdict": "..." },
  "recent_events": [...],
  "step_states": {
    "keyword_review": { "confirmed_keywords": ["YOLO", "defect"] },
    "feasibility": { "verdict": "可做" }
  },
  "last_seq": 42,
  "replay_source": "both"  // 或 "snapshot" / "transcript"
}
```

`replay_source` 字段告诉前端这次恢复是来自 snapshot、transcript 还是两者。

---

## 7. 上下文超过限制怎么办？

**两层防护：**

1. **Compression** — 当 events 超过阈值（默认 200），自动压缩
2. **Snapshot** — token 重的字段（proposal_markdown 长文本）剥离到 snapshot

**面试回答模板：**

> 「我们用 ProjectMemorySnapshot 把 token 重的字段从 RunEvent 里剥离。当 Replay 时只加载 snapshot 概要 + 最近 N 个 events，token 用量可控。即使完全断流 + 压缩后，我们也能恢复到关键决策点。」

---

## 8. 刷新或断流后怎么恢复？

**ProjectMemory 层面的恢复：**

1. **断流检测** — 前端用 `run_state.json` 检测 last_seq 与当前 SSE 连接状态
2. **断流后** — 显示「恢复」按钮
3. **点击恢复** — 调用 `/memory/replay` 拿 step_states
4. **重建 Step Deck** — 用 step_states 把每个 step 跳到对应状态

**关键设计：** 不是从事件 0 开始 replay，而是从最近的 snapshot + 最近 events 恢复。

---

## 9. 短期 vs 长期记忆区分

| 维度 | 短期 (ShortContext + Transcript) | 长期 (ProjectMemory + EvidenceMemory) |
|---|---|---|
| 生命周期 | 当前 session | 跨 session |
| 大小 | 增长型（触发压缩） | 有界（snapshot 字段固定） |
| 用途 | 流式 UI 重建 | cold start, audit, regression |
| 可压缩 | 是（保留 critical） | 否（不可压缩） |
| API | `/memory/replay` | `/memory/snapshot` `/memory/evidence` |

---

## 10. 面试常见追问

### Q1: 压缩会不会丢关键信息？

不会。我们把 6 类事件标记为 critical（user_patch / gate / evidence_promotion / url_verified / readiness_check / llm_call），压缩时 100% 保留。EvidenceMemory 独立于 transcript，永不被压缩。

### Q2: 你的记忆怎么持久化？

- Transcript: `.runtime/runs/{project_id}/{run_id}/events.jsonl`
- State: `.runtime/runs/{project_id}/{run_id}/state.json`
- ProjectMemorySnapshot: in-memory（可持久到 SQLite）
- EvidenceMemory: in-memory（来自 Evidence Ledger，跨 session 持久）

### Q3: 上下文超限怎么办？

两层防护：Compression（events 超过阈值自动压缩）+ Snapshot（token 重字段从 transcript 剥离）。Snapshot 保留「最后一次写入」的字段状态。

### Q4: Agent 多步骤怎么避免 Token 爆炸？

- 每个 step 只往 transcript 写自己的 payload
- Snapshot 合并多个 step 的状态
- Replay 时按需加载（snapshot + 最近 N events）

### Q5: 你的记忆和 LangChain Memory 有什么差异？

| LangChain Memory | PaperAgent Memory |
|---|---|
| 单一 buffer / summary | 四层分层 |
| 自动压缩（但不易审计） | 显式 critical 事件分类 |
| 没有不可变层 | EvidenceMemory 独立层 |
| 与 chain 紧耦合 | 与 step deck 解耦，可独立 replay |

---

## 11. 可展示文件清单

- `apps/api/app/schemas_memory.py` — 四层记忆的 Pydantic 模型
- `apps/api/app/services/project_memory.py` — Project Memory + 压缩 + Replay
- `apps/api/tests/test_session35_agent_memory_replay.py` — 14 个测试
- `docs/interview/Agent_Memory_Explainer.md` — 本文档

---

## 12. 未来扩展

- Snapshot 持久化到 SQLite
- EvidenceMemory 反向引用 candidate
- 跨 project 共享 ground truth
- 用户主动删除记忆的 API
- 压缩率统计面板

---

> **面试重点强调：** PaperAgent 不是「有日志」，而是「有四层记忆，每层有不同的生命周期和保真度」。压缩不丢关键事件，刷新页面可自动 replay 恢复。