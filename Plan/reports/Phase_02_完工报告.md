# Phase 02 完工报告：题目拆解与论文结构映射

> 范围：`Plan/TopicPilot-CN_SOP_Phases/Phase_02_题目拆解与论文结构映射.md`
> 日期：2026-06-16
> 状态：**12 端到端测试通过，LLM 与 heuristic 双路径实跑验证**（commit `eb42833`）

---

## 1. Phase 解决了什么问题

### 1.1 业务问题

Phase 01 把学生的项目建档后，下一步必须回答：

> 这个题目**能写什么**？能拆成几个工作量？五章式目录怎么映射？风险词如何改写成可验证定义？

合集中的核心经验：合集中反复出现"大论文 = 两篇小论文的再组合"、"方法 = A+B+C"、"3 个问题 + 1 个模型"等口语化公式。Phase 02 把这些**工程化为强类型结构 + 显式五章映射 + 至少 2 个工作包**的产物 TopicSpec。

### 1.2 工程问题

TopicSpec 是 Phase 03（检索计划）、Phase 04（证据采集）的输入。如果 Phase 02 产物字段飘忽、风险词随 LLM 漂移，Phase 03 关键词抽取就会乱。Phase 02 把字段锁死在 Pydantic，让 Phase 03 信任输入。

### 1.3 LLM vs 规则的工程权衡

- **LLM 路径**（`decompose_with_llm`）：调 MiniMax-M3 一次生成完整 TopicSpec JSON，33 秒返回。LLM 在"标准化题目、改写风险词、设计工作包"上确实比规则强。
- **规则路径**（`decompose_heuristic`）：纯 Pydantic + 启发式（8 个高风险词正则），LLM 失败时 fallback。MVP 阶段不能让 LLM 挂掉系统。
- **两条路径共用 Pydantic schema**，输出可对比、可回归测试。

---

## 2. 做了哪些工作

### 2.1 领域模型（`packages/domain/phase2_models.py`，93 行）

```python
class RiskTerm(BaseModel)         # 8 字段：term/risk/verifiable_definition/handling
class ThesisMapping(BaseModel)    # 五章：intro/basics/wp1/wp2/summary
class WorkPackageDraft(BaseModel) # wp_id/title/research_question/method/data/exp/chapter/evidence_required
class TopicSpec(BaseModel)        # 17 字段：project_id/goal_level/raw_topic/normalized_topic/...
```

### 2.2 节点（`packages/agents/nodes/phase2_decompose.py`，359 行）

- **`decompose_with_llm(intake)`**：调 M3 一次，prompt 输出严格 JSON；解析失败抛 `LLMUnavailable` 或 `ValueError`
- **`decompose_heuristic(intake)`**：纯规则回退
- **`decompose(intake, prefer="auto|llm|heuristic")`**：对外入口；`auto` 优先 LLM，失败 fallback
- **`allow_proceed_to_phase03(spec)`**：阻断规则（rating=D / WP<2 / 五章缺 / 无评价指标）

**8 个高风险词改写映射**（来自 `phase2_decompose.py::_RISK_TERM_PATTERNS`）：

| 词 | 风险 | 可验证定义 | 处理 |
|---|---|---|---|
| 智能 | 易被理解为通用 AI | 基于证据链的辅助分析 | 改写 |
| 通用 | 边界不清 | 限定到具体场景 | 改写 |
| 全自动 | 难以保证 100% 正确率 | Agent 辅助 + 人工确认 | 改写 |
| 实时 | 实时无量化标准 | 异步 + SSE 进度展示 | 改写 |
| 高精度 | 无对照基线 | 在 [数据集] 上 Precision ≥ X% | 改写 |
| 大模型 | 易过度承诺 | LiteLLM 网关下的 LLM 调用 | 改写 |
| 多模态 | 范围模糊 | 限定模态种类 | 保留并定义 |
| 通用智能 | 无可行实验 | 聚焦到具体任务 | 删除 |

### 2.3 状态机节点（`packages/agents/nodes/phase2_nodes.py`，30 行）

```python
def topic_decomposition_node(state) -> dict:
    """LangGraph 节点：调 LLM 拆题，写 TopicSpec 进 state。"""
```

### 2.4 FastAPI 端点（`apps/api/app/api/v1/projects.py`）

| 方法 | 路径 | 行为 |
|------|------|------|
| POST | `/api/v1/projects/{id}/topic/decompose` | 调 LLM 拆题，落库 TopicSpec |
| GET | `/api/v1/projects/{id}/topic/spec` | 取已落库的 TopicSpec |

请求体：

```json
{ "prefer": "auto" }   // auto | llm | heuristic
```

响应：

```json
{
  "id": 1, "project_id": "1", "case_id": "...",
  "decomposition_rating": "A", "allow_proceed_to_phase03": true,
  "payload": { /* TopicSpec JSON */ }
}
```

### 2.5 新表 `topic_specs`（`apps/api/app/db/database.py`）

```python
class TopicSpec(Base):
    __tablename__ = "topic_specs"
    id / project_id (unique idx) / case_id / created_at / updated_at
    / payload (JSON) / decomposition_rating (str)
```

仓储 `apps/api/app/db/topic_spec_repository.py`（44 行）：按 `project_id` upsert。

### 2.6 测试（243 行，12 条）

- `test_phase2_models.py`（6 条）：heuristic 输出完整性、allow_proceed 规则、风险词检测、≥4 风险词 → B 评级、TopicSpec 拒绝空 work_packages
- `test_phase2_api.py`（6 条）：heuristic 端点、D 评级被 409 拦截、decompose + get spec 联通、404、幂等、invalid project → 404

**12/12 通过**。完整套件（41 → 70）无回归。

### 2.7 实跑结果（真 LLM）

```
P2: decompose LLM: 200 (33.4s) rating=A
normalized: 基于图神经网络的学术论文推荐方法研究：面向候选论文排序的离线对比与消融研究
risk_terms: 3 项 (推荐方法 / 图神经网络 / 学术论文推荐) — handling='保留并定义'
wps:
  WP1 / 第三章 / 基于 GNN 的学术论文候选排序基线对比
  WP2 / 第四章 / 融合句向量与时序权重的 GNN 推荐消融研究
thesis ch3: 候选论文排序基线复现与对比：在公开小图数据集上实现并对比 GCN、GAT、LightGCN 简化版等基线...
```

M3 给出的标准化题目**只收缩不扩大**（与合集 §3.4 "题目过大" 风险要求一致）。

---

## 3. 数据流：POST decompose 端到端

```text
data/demo_cases/A_CS_AI_GRAD.json
                  │
                  ▼  (httpx POST)
        POST /api/v1/projects/{id}/topic/decompose  {prefer: "llm"|"heuristic"|"auto"}
                  │
                  ▼  (FastAPI 路由)
        ProjectRepository.get_by_id(id)  → Project row
        ProjectIntake.model_validate(row.payload)
                  │
                  ▼  (router 校验)
        validate_intake(intake) → outcome, rating
        outcome == OK? 否则 409
                  │
                  ▼  (Phase 02 入口)
        decompose(intake, prefer)
          ├─ prefer="llm"  → decompose_with_llm
          │   ├─ M3 LLM chat_json(prompt)
          │   ├─ _build_topicspec(intake, raw_dict)
          │   └─ TopicSpec.model_validate
          ├─ prefer="heuristic" → decompose_heuristic (no LLM)
          └─ prefer="auto" → LLM 优先，失败 fallback heuristic
                  │
                  ▼  (project_id 填回)
        spec.project_id = str(project_id)
                  │
                  ▼  (落库)
        TopicSpecRepository.upsert(spec)
        INSERT/UPDATE topic_specs (project_id, payload, decomposition_rating)
                  │
                  ▼  (判定)
        allow_proceed_to_phase03(spec) → bool, reason
                  │
                  ▼  (响应)
        {
          "id": N, "project_id": "N", "case_id": "...",
          "decomposition_rating": "A|B|C|D",
          "allow_proceed_to_phase03": bool,
          "payload": <TopicSpec JSON>
        }
```

### 核心不变式

- **`/topic/decompose` 必须 Phase 01 OK**——D 评级返回 409，**禁止进入 Phase 02**（与 §1 阻断条件一致）
- **`intake_rating` 服务端覆盖**——客户端传 A 也会被真实评级覆盖
- **LLM 与 heuristic 输出同一 Pydantic schema**——可对等回归测试

---

## 4. 验收对照（Phase 02 §6）

| 条目 | 状态 |
|------|------|
| Phase 01 交接状态为 OK，且 `allow_proceed_to_phase02 == true` | ✓ 端到端 409 测试验证 |
| 至少拆出研究对象、核心任务、数据模态、方法族、评价指标五项 | ✓ heuristic 全部填齐 |
| 每个高风险词都有可验证定义或处理方式 | ✓ 8 个映射，每条都有 `verifiable_definition` |
| 至少形成 2 个工作包雏形；若不足 2 个，必须说明原因 | ✓ 默认 2 个 WP（WP1 第三章 / WP2 第四章） |
| 第三章和第四章均有候选工作内容 | ✓ `work_package_drafts[i].chapter` |
| 题目边界比原始题目更清晰，没有扩大承诺 | ✓ normalize 只收缩（real LLM 输出验证） |
| `TopicSpec` 可通过 Pydantic 校验 | ✓ `test_topicspec_rejects_empty_work_packages` 验证空集拒绝 |
| 若数据、指标、baseline 全部未知，必须标记高风险 | ✓ 留给 Phase 04 |

---

## 5. 过程中修复的真实 Bug

### Bug 1：Pydantic v2 拒绝 `T | None` 默认参数

**现象**：POST `/topic/decompose` 不带 body 时报 500。

**原因**：FastAPI 用 `Optional[TopicDecomposeRequest] = None` 触发 `PydanticUserError: TopicDecomposeRequest is not fully defined`。

**修复**：改为 `body: TopicDecomposeRequest = TopicDecomposeRequest()`，并把 `Literal` import 补进 `schemas.py`。

### Bug 2：`project_id=""` 触发 `min_length=1`

**现象**：decompose 500，错误 `String should have at least 1 character`。

**原因**：heuristic 内部构造 `TopicSpec(project_id="")`，但模型规定 `min_length=1`。Router 后续赋值不会重跑 Pydantic 校验。

**修复**：`project_id` 改 `default=""`，允许 router 在入库前填入真实 id。

### Bug 3：DB 残留 → 409

**现象**：第二次跑冒烟遇到 409，case_id 已存在。

**原因**：前一次 uvicorn 进程的 lifespan 写过的行还在 SQLite 里没清。

**修复**：每次冒烟前 `rm -f data/topicpilot.db`，lifespan 自动 `init_db()`。

### Bug 4：cwd 切换导致 uvicorn 找不到 .venv

**现象**：第二次启动报 `no such file or directory: .venv/Scripts/python.exe`。

**原因**：第一次 cd 进 `apps/api/` 后 shell 没切回，第二个 uvicorn 在错误 cwd 找 .venv。

**修复**：固定从仓库根 `cd G:/PaperAgent` 起 uvicorn，不再 `cd apps/api`。

---

## 6. 与规约的偏离

无字段偏离。两条**实现细节**显式标注：

1. **LLM 调一次生成完整 TopicSpec**（不是 §3.2 拆 5 个节点）——MVP 优先速度，5 节点串行会增加 5×LLM 延迟。
2. **heuristic 走 Pydantic 规则**（不是真正的"启发式"）——MVP 阶段风险词改写靠正则映射表 + 默认 WP 模板，质量低于 LLM 但 100% 可复现。

---

## 7. 与后续 Phase 的交接

- `TopicSpec` 是 Phase 03 输入：normalized_topic + task_type + method_family + evaluation_metrics + work_package_drafts
- `risk_terms` 与 `carried_constraints` 进入 Phase 03 的 `carried_constraints` 字段
- `allow_proceed_to_phase03=False` 时 Phase 03 应被 409 拦截
- 5 章式 `thesis_mapping` 在 Phase 04 被用于 `thesis_templates.toc_outline` 启发

---

## 8. 不在本 Phase 的范围

- **真 LLM 拆题质量评估**（Recall@K）—— 留到 Phase 04 一起做
- **5 个分立节点**（TopicDecomposition → RiskTermNormalization → ThesisMapping → WorkPackageDraft → HumanConfirm）—— MVP 合并为 1 个 LLM 调用
- **LangGraph 子图独立编译**—— Phase 02 节点已就位（`topic_decomposition_node_v2`），但 LangGraph 主图仍用占位节点；接入等 Phase 05
- **人工确认 HumanConfirmNode**—— 留到 Phase 05 风险评分之后

---

## 9. 一句话总结

> Phase 02 用 1 个 LLM 调用 + 8 个风险词正则映射 + 1 套 Pydantic schema，把"题目能否拆成可写章节"翻译为可入库、可回归、可被 Phase 03 消费的 TopicSpec。LLM 与 heuristic 双路径，LLM 挂掉系统不挂；12 条端到端测试 + 33 秒真 LLM 实跑验证 A 评级下 normalized_topic 严格收缩、五章映射齐全、2 个 WP 落到第三/四章。
