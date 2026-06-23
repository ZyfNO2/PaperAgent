# PaperAgent Session 27 SOP：真实流式 RunEvent 持久化与回放

> 日期：2026-06-21  
> 前置：Session 21-24 的流式主要是前端 mock。  
> 本轮目标：补齐真实 RunEvent、SSE/NDJSON、事件落盘与 replay，让 Step Deck 不再只依赖前端 mock。

---

## 1. 目标

```text
把 mock stream 替换为可选真实事件流：
后端生成 RunEvent；
前端消费 SSE/NDJSON；
事件写入 .runtime；
刷新后可以 replay。
```

---

## 2. 端点

```text
POST /api/v1/one-topic/{project_id}/runs
GET  /api/v1/one-topic/{project_id}/runs/{run_id}/events
GET  /api/v1/one-topic/{project_id}/runs/{run_id}/stream
POST /api/v1/one-topic/{project_id}/runs/{run_id}/resume
```

MVP 可先支持：

```text
application/x-ndjson
```

再支持：

```text
text/event-stream
```

---

## 3. RunEvent Schema

```text
event_id
seq
run_id
project_id
step_key
event_type
status
payload
ts
source: backend | llm | user | system
```

事件类型沿用：

```text
run_started
step_started
token_delta
card_delta
artifact_ready
step_pause
user_patch_required
step_resumed
run_completed
run_failed
```

---

## 4. 持久化

建议：

```text
.runtime/runs/{project_id}/{run_id}/events.jsonl
.runtime/runs/{project_id}/{run_id}/state.json
.runtime/runs/{project_id}/{run_id}/user_patches.jsonl
```

要求：

```text
seq 单调递增；
重复写入同 event_id 幂等；
replay 顺序稳定；
写盘失败不导致核心流程崩溃，但必须返回 warning。
```

---

## 5. 前端改造

新增：

```text
apps/web/stream_client.js
```

函数：

```text
startBackendRun(projectId, payload)
consumeNDJSON(response)
consumeSSE(response)
replayRun(projectId, runId)
resumeRun(projectId, runId, patch)
```

保留：

```text
mock stream 作为测试 fallback。
```

---

## 6. 测试

后端：

```text
1. create run 返回 run_id；
2. stream 返回 run_started；
3. events.jsonl 写入；
4. seq 单调递增；
5. replay 返回同序列；
6. resume 写 user_patch；
7. step_pause 后不继续；
8. run_failed 可记录 error；
9. 写盘失败 warning；
10. S17 baseline 不回退。
```

Playwright：

```text
S27-PW-1：前端可选择 backend stream；
S27-PW-2：流式文本出现；
S27-PW-3：keyword_review 暂停；
S27-PW-4：刷新后 replay 恢复事件；
S27-PW-5：resume 后继续；
S27-PW-6：断流显示可恢复；
S27-PW-7：mock stream 仍可用；
S27-PW-8：S25/S26 不回退。
```

---

## 7. 验收标准

```text
1. 后端 RunEvent schema 完成；
2. 至少一种真实流式协议可用；
3. events.jsonl 可 replay；
4. 前端可从真实流恢复 Step Deck；
5. keyword gate 仍有效；
6. mock fallback 保留；
7. 后端测试通过；
8. Playwright 通过。
```

---

## 8. 完工报告

```text
Plan/reports/Session_27_RunEvent_Streaming_Replay_验收报告.md
```

