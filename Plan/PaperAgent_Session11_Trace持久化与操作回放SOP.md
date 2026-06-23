# PaperAgent Session 11 SOP：Trace 持久化与操作回放

> 日期：2026-06-19  
> 阶段定位：承接 Session 09/10 后快速增长的用户操作，把当前 in-memory Trace 升级为可持久化、可回放、可进入报告的项目决策记录。  
> 本轮目标：保存证据从 intake → verify → selected/rejected → EvidenceRef → FinalPackage 的关键路径，让系统能解释“为什么这条证据被采用/排除”。

---

## 1. 当前状态判断

截至 Session 10，系统已经具备：

| 能力 | 状态 |
|---|---|
| 双栏证据工作台 | 已完成 |
| Agent Card Intake | 已完成 |
| URL / 元数据轻验证 | 已完成 |
| EvidenceRef priority | 已接入 workspace_lane + verification_confidence |
| Markdown 报告引用清单 | 已显示 verification 状态 |
| Trace | 仍主要是 in-memory，重启后丢失 |

当前最大缺口不是“不会生成”，而是：

```text
用户做了很多关键决策，但这些决策没有稳定保存。
```

典型丢失的信息：

```text
用户为什么把某篇论文移到左侧；
用户为什么把某个 repo 标为核心；
用户为什么拒绝某个 dataset；
某条 assistant_intake 卡片什么时候被验证；
某条证据为什么从 pending 变成 core；
报告引用为什么选择 E1 而不是 E3。
```

---

## 2. Session 11 目标

Session 11 名称：

```text
Trace 持久化与操作回放
```

目标：

```text
Trace event
→ 本地持久化
→ 项目操作历史
→ 前端可查看
→ Markdown 报告可附关键决策记录
```

完成后，用户应能：

```text
1. 查看当前项目的关键操作历史；
2. 看到证据从导入、验证、移动、标核心、拒绝到报告引用的路径；
3. 在报告中看到“关键决策记录”；
4. 服务重启后 Trace 不丢失；
5. 按 project_id 查询 Trace。
```

---

## 3. 本阶段不做什么

| 不做 | 原因 |
|---|---|
| 不做完整 Research Wiki | 只保证当前 project 的操作回放 |
| 不做跨项目推荐 | 历史知识复用后置 |
| 不做复杂数据库迁移 | MVP 优先 jsonl 或轻量本地存储 |
| 不做撤销/回滚 | 本阶段只记录，不实现状态回滚 |
| 不做多人协作审计 | 单用户本地 MVP 足够 |
| 不记录敏感全文 | 只记录 evidence_id、动作、摘要和原因 |

---

## 4. Trace 事件模型

建议新增或规范化：

```python
class TraceEvent(BaseModel):
    trace_id: str
    project_id: str
    ts: str
    actor: Literal["system", "user", "agent"]
    action: str
    target_type: str | None = None
    target_id: str | None = None
    evidence_id: str | None = None
    before: dict = Field(default_factory=dict)
    after: dict = Field(default_factory=dict)
    reason: str | None = None
    source: str | None = None
    session: str | None = None
```

必须记录的动作：

```text
card_intake_created
workspace_move
review_status_changed
verification_run
manual_verification
ref_rebuild
ref_review
final_package_build
report_download
pivot_selected
keyword_regenerated
```

---

## 5. 持久化方案

### 5.1 MVP 推荐：jsonl

路径：

```text
.runtime/traces/{project_id}.jsonl
```

每行一个 JSON：

```json
{"trace_id":"tr_xxx","project_id":"ot_xxx","ts":"2026-06-19T...","actor":"user","action":"workspace_move","evidence_id":"paper_001"}
```

优点：

```text
实现快；
可直接审计；
方便后续导入 SQLite；
不会引入重型依赖。
```

### 5.2 后续可选：SQLite

后续如果 Trace 查询复杂，再迁移到：

```text
.runtime/paperagent.sqlite
trace_events(project_id, ts, actor, action, evidence_id, payload)
```

本阶段不强制。

---

## 6. API 设计

### 6.1 获取项目 Trace

```text
GET /api/v1/one-topic/{project_id}/trace
```

参数：

```text
limit=100
action=workspace_move
actor=user
since=...
```

输出：

```json
{
  "project_id": "ot_xxx",
  "events": [],
  "total": 25
}
```

### 6.2 获取 Evidence Timeline

```text
GET /api/v1/one-topic/{project_id}/evidence/{evidence_id}/timeline
```

用途：

```text
查看某条证据从创建到报告引用的路径。
```

### 6.3 Trace 摘要

```text
GET /api/v1/one-topic/{project_id}/trace/summary
```

输出：

```json
{
  "project_id": "ot_xxx",
  "user_actions": 8,
  "system_actions": 14,
  "key_decisions": [
    "用户将 repo_001 标为核心",
    "用户拒绝 dataset_002",
    "系统生成 FinalPackage"
  ]
}
```

---

## 7. 前端设计

新增 Trace 面板或增强现有 Trace 区：

```text
操作历史
├── 全部
├── 用户操作
├── 证据操作
├── 验证操作
└── 报告操作
```

每条展示：

```text
时间 · actor · action · evidence_id · reason
```

证据卡片增加：

```text
查看路径
```

点击后展示：

```text
创建 → 导入 → 验证 → 移到左侧 → 标核心 → 被报告引用
```

---

## 8. Markdown 报告联动

FinalPackage 增加一节或附录：

```markdown
## 十四、关键决策记录

| 时间 | 操作 | 对象 | 说明 |
|---|---|---|---|
| ... | 标为核心 | repo_001 | 用户确认该 repo 可作为 baseline |
```

规则：

```text
只放关键事件；
不放所有系统内部 step；
用户操作优先；
证据被拒绝、手动验证、标核心、报告生成必须列入。
```

---

## 9. 测试要求

### 9.1 后端测试

新增：

```text
apps/api/tests/test_session11_trace_persistence.py
```

覆盖：

```text
1. append_trace 写入 jsonl
2. get_trace 能按 project_id 读取
3. 服务内存 reset 后 jsonl 仍可读取
4. workspace_move 写入 trace
5. card_intake_created 写入 trace
6. verification_run 写入 trace
7. final_package_build 写入 trace
8. evidence timeline 能按 evidence_id 过滤
9. trace summary 能生成 key_decisions
10. trace 不改变 evidence review_status
```

### 9.2 Playwright

新增：

```text
apps/web/e2e/test_one_topic_session11_trace_persistence.py
```

覆盖：

```text
1. 页面显示操作历史面板
2. 移动证据后出现 trace
3. 验证证据后出现 trace
4. 生成报告后出现 trace
5. 点击证据“查看路径”能看到 timeline
6. 刷新页面后 trace 仍显示
```

---

## 10. 验收标准

通过条件：

```text
1. Trace 持久化到本地文件或轻量存储；
2. 重启或 reset 后仍能读取；
3. 关键用户操作均写入 Trace；
4. Evidence timeline 可查询；
5. 前端能查看操作历史；
6. Markdown 报告能附关键决策记录；
7. 后端测试通过；
8. Playwright 测试通过。
```

---

## 11. 完工报告要求

完成后新增：

```text
Plan/reports/Session_11_Trace_Persistence_验收报告.md
```

报告包含：

```text
范围；
持久化位置；
TraceEvent 模型；
新增 API；
前端变化；
报告联动；
测试结果；
未做项；
下一 Session 建议。
```

---

## 12. 下一 Session 预告

Session 12：报告质量检查与低门槛委员会复核。

理由：

```text
有了证据验证和操作历史后，系统可以检查报告是否真正由证据支撑，
并给出开题阶段的低门槛审核意见和修改清单。
```
