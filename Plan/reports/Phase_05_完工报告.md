# Phase 05 完工报告：风险评分与 Pivot 决策

> 范围：`Plan/TopicPilot-CN_SOP_Phases/Phase_05_风险评分与Pivot决策.md`
> 日期：2026-06-16
> 状态：**107/107 pytest 通过（含 21 条 Phase 05 测试）**（commit `df1a5dd` 之后）

---

## 1. Phase 解决了什么问题

### 1.1 业务问题

Phase 04 给出 EvidenceLedger 后，下一步必须**做决策**：

> 当前题目能稳定毕业吗？是"继续"还是"Pivot"？
> 哪一维度风险最高？数据 / baseline / 时间红线哪一项最危险？

合集中的核心经验：合集 §3.4 "需要规避的题目" 和 §2 "三类方法流派"反复强调"保毕业优先成熟方向；不造航母；数据/baseline/指标/工作量可拆"。Phase 05 把这条经验**工程化为六维评分 + 决策建议**。

### 1.2 工程问题

RiskEvaluation 是 Phase 06（工作包定稿）和 Phase 07（开题报告）的输入。如果六维评分飘忽或 Pivot 候选随 LLM 漂移，Phase 06 不知道"该工作化哪个方向"、Phase 07 不知道"该写哪个题目的开题"。Phase 05 把六维、总体评级、决策、Pivot 候选全部锁死在 Pydantic。

### 1.3 规则 vs LLM 的工程权衡

- **六维评分**纯规则：从 EvidenceLedger 字段数 / 字段质量 / TopicSpec 字段推，100% 可复现
- **总体评级**按 `goal_level` 调阈值（保毕业要求更严）
- **Pivot 候选**走 LLM（需要创造力地"收缩题目"或"换方向"），heuristic fallback 给 2 个固定模板

---

## 2. 做了哪些工作

### 2.1 领域模型（`packages/domain/phase5_models.py`，70 行）

```python
class DimensionScore(BaseModel)   # 6 维: 方向成熟度/数据可得性/baseline 清晰度/实验可行性/工作量可拆性/毕业时间风险
class RiskScore(BaseModel)         # 6 维 + overall_score/overall_rating/min_viable_path
class PivotCandidate(BaseModel)    # pivot_id/pivot_type(收缩|换向)/new_topic/rationale/preserved/new_evidence_needed/residual_risk
class RiskEvaluation(BaseModel)    # 6 维 + decision(继续|收缩|转向)/pivot_candidates/must_supplement
```

### 2.2 节点（`packages/agents/nodes/phase5_risk.py`，300 行）

**六维评分规则**：

| 维度 | 评分依据 | 满分 |
|------|---------|------|
| **方向成熟度** | `min(papers×4, 40) + min(surveys×10, 20) + min(thesis_templates×15, 25) + (≥5 papers && ≥1 survey → +15)` | 100 |
| **数据可得性** | `min(datasets×25, 60) + min(inherited_available×20, 40)` | 100 |
| **baseline 清晰度** | `sum(diff_score: 低30/中18/高5/未知12) + 10` 上限 100 | 100 |
| **实验可行性** | `min(metrics×8, 50) + min(exp_templates×15, 40) + 10` | 100 |
| **工作量可拆性** | `min(wp×35, 70) + min(bound_wp×15, 30)` | 100 |
| **毕业时间风险** | `80 - high_diff_baselines×15`（无 first_result_deadline → 20） | 100 |

**总体评级按 goal_level 调阈值**：

| goal_level | A | B | C | D |
|------------|---|---|---|---|
| 保毕业 | ≥70 | ≥55 | ≥40 | <40 |
| 稳中求新 | ≥65 | ≥50 | ≥35 | <35 |
| 冲高水平 | ≥60 | ≥45 | ≥30 | <30 |

**Pivot 决策**：
- A → "继续" + 1 个收缩候选（防御性）
- B → "继续" + 至少 1 个 pivot（备选）
- C → "收缩" + 至少 1 个 pivot
- D → "转向" + 至少 1 个 pivot

**min_viable_path 跟 rating 联动**（独立于 LLM）：

| Rating | min_viable_path |
|--------|-----------------|
| A | 先复现 1 个低难度 baseline，first_result_deadline 前出主结果表 |
| B | 继续但并行准备 1 个 pivot；1 个月内 baseline 复现失败立刻切换 |
| C | 先做 1-2 周证据补强；仍不到位则 pivot |
| D | 不建议继续；从 pivot 选新方向 |

**heuristic Pivot 模板**（2 个）：

```
P01 收缩: 把"大模型/通用/全自动/智能/实时"高风险词替换为"基于证据链的辅助"
P02 换向: 切到 evaluation_metrics / experiment_templates 保留的任务
```

**LLM Pivot 路径**（auto 模式）调 M3 一次生成 1-3 个候选，失败 fallback heuristic。

### 2.3 端点

| 方法 | 路径 | 行为 |
|------|------|------|
| POST | `/api/v1/projects/{id}/risk/evaluate` | 调规则六维评分 + LLM/heuristic pivot，落库 |
| GET | `/api/v1/projects/{id}/risk/evaluation` | 取已落库的 RiskEvaluation |

### 2.4 新表 `risk_evaluations`

```python
class RiskEvaluationRow(Base):
    id / project_id (unique) / case_id / payload (JSON)
    / overall_rating (str) / decision (str)
```

仓储 `apps/api/app/db/risk_repository.py`：按 `project_id` upsert。

### 2.5 测试（21 条）

- `test_phase5_models.py`（13 条）：六维齐全、heuristic 默认 A/B、min_viable_path 非空、max_risk_dimension 是最低分维度、heuristic pivot ≥1、decision ∈ 有效集、allow_proceed、空 ledger → C/D、D → 决策 "转向"、C/D 必须有 pivot、pivot_id 唯一、score ∈ [0,100]
- `test_phase5_api.py`（8 条）：heuristic 端点、GET 持久化、无 EvidenceLedger 409、无 SearchQueryPlan 409、无 TopicSpec 404、不存在 404、GET 404、upsert 幂等

**107/107 pytest 全过**（原 86 + 新 21）。

---

## 3. 数据流：POST risk/evaluate 端到端

```text
TopicSpec + SearchQueryPlan + EvidenceLedger (from DB)
                  │
                  ▼  (FastAPI 路由)
        spec_repo / plan_repo / led_repo / proj_repo
        各自校验: 无 → 404/409
                  │
                  ▼  (Phase 05 入口)
        build_risk_evaluation(intake, spec, plan, ledger, prefer)
          ├─ build_risk_score(intake, spec, ledger)
          │   ├─ 6 个 _score_*(ledger) → 6 DimensionScore
          │   ├─ _overall(goal_level, dims) → (avg, rating)
          │   └─ _min_viable_path(intake, ledger, rating)
          ├─ build_pivots(intake, spec, ledger, risk, prefer)
          │   ├─ auto / llm → _llm_pivots (M3 chat_json)
          │   ├─ 失败 / heuristic → _heuristic_pivots (2 模板)
          │   └─ 决策 (继续/收缩/转向) 跟 rating 联动
          └─ must_supplement 自动汇总
                  │
                  ▼  (project_id 填回)
        ev.project_id = str(project_id)
                  │
                  ▼  (落库)
        RiskEvaluationRepository.upsert(ev)
                  │
                  ▼  (响应)
        {
          "id": N, "project_id": "N",
          "overall_rating": "A|B|C|D",
          "overall_score": 0-100,
          "decision": "继续|收缩|转向",
          "max_risk_dimension": "...",
          "pivot_count": N,
          "allow_proceed_to_phase06": bool,
          "payload": <RiskEvaluation JSON 含 6 维 / 决策 / pivots>
        }
```

### 核心不变式

- **`/risk/evaluate` 必须 Phase 02/03/04 都已落库** — 否则 404/409
- **D 评级决策必须 = "转向"** — 测试守护
- **C/D 评级必须 ≥1 Pivot** — 测试守护
- **总体评级阈值跟 goal_level 联动** — 保毕业要求最严

---

## 4. 验收对照（Phase 05 §6）

| 条目 | 状态 |
|------|------|
| 输入 `EvidenceLedger` 已通过 Phase 04 验收 | ✓ `test_risk_blocked_without_evidence` 验证 |
| 六维风险评分均有证据依据 | ✓ `evidence_summary` 字段必填 + `test_risk_score_has_six_dimensions` |
| 综合评级为 A/B/C/D 之一 | ✓ `Literal["A","B","C","D"]` |
| 若评级为 C/D，必须给出至少 1 个 PivotCandidate | ✓ `test_cd_evaluation_must_have_pivot` |
| 若建议继续，必须说明数据、baseline、指标和工作量均可支撑 | ✓ min_viable_path + must_supplement |
| 输出最小可行毕业路线 | ✓ `test_risk_score_min_viable_path_present` |
| 不允许编造论文、数据、baseline 或实验结果 | ✓ SourceTag 枚举 + `_safe_*` 校验沿用 Phase 04 |

---

## 5. 过程中修复的真实 Bug

### Bug 1：Lifespan 没注册新 ORM class

**现象**：第 1 次启动 uvicorn 报 `'TopicSpec' object has no attribute 'queries'`（实际是 lifespan `init_db()` 没找到 `RiskEvaluationRow` 表）。

**原因**：lifespan 之前显式 `from app.db.database import TopicSpec, SearchQueryPlanRow, EvidenceLedgerRow`，但没加 `RiskEvaluationRow`。

**修复**：同 Phase 02 修复模式——`lifespan` 内显式 import 新加的 ORM class。

> 这是第二次踩同一个坑。应该写进 CLAUDE.md 的"不要做的事"。

### Bug 2：`Literal` 没在 schemas.py 顶部 import

**现象**：lifespan 启动失败报 `RiskEvaluationRequest is not fully defined`。

**原因**：schemas.py 之前 import 了 Literal（Phase 02 修过），但 RiskEvaluationRequest 用 `Literal["auto", "llm", "heuristic"]` 时没刷新 import 状态。

**修复**：确认 `from __future__ import annotations` + `from typing import Literal` 在 schemas.py 顶部。

---

## 6. 与规约的偏离

无字段偏离。两条**实现细节**显式标注：

1. **六维评分纯规则，不调 LLM**——文档 §3 没明确说必须 LLM，规则版可控可回归。
2. **Pivot 候选 LLM 调一次**（不是 §3.2 设计的多节点 RiskEvaluationGraph + PivotPlanningGraph）——MVP 合并。

---

## 7. 与 Phase 06 的交接

- `RiskEvaluation.decision` 决定 Phase 06 的工作包定稿方向（继续 → 定稿原题目；收缩 → 用 P01；转向 → 用 P02）
- `RiskEvaluation.pivot_candidates` 是 Phase 06 的备选输入
- `RiskEvaluation.must_supplement` 是 Phase 06 决定"补什么证据"的依据
- `allow_proceed_to_phase06` 阻断：D 评级必须 转向 + 必须有 pivot

---

## 8. 不在本 Phase 的范围

- **多节点 LangGraph 子图**（RiskEvaluationGraph + PivotPlanningGraph）——MVP 合并
- **风险雷达图前端**（§7 界面 MVP 后置）
- **用户选 pivot 后的项目分支**（Phase 06 范围）

---

## 9. 一句话总结

> Phase 05 用 6 个纯规则评分函数 + goal_level 阈值表 + 1 个 LLM pivot 候选调用，把 EvidenceLedger 翻译为 6 维 0-100 分 + A/B/C/D 综合评级 + "继续/收缩/转向"决策 + Pivot 候选。21 端到端测试守护 D 评级必须换向 + C/D 必须有 pivot + min_viable_path 必填。107/107 pytest 全过。
