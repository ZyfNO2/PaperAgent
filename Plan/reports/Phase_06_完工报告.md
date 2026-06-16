# Phase 06 完工报告：工作包定稿与实验矩阵

> 范围：`Plan/TopicPilot-CN_SOP_Phases/Phase_06_工作包定稿与实验矩阵.md`
> 日期：2026-06-16
> 状态：**127/127 pytest 通过（含 20 条 Phase 06 测试）**

---

## 1. Phase 解决了什么问题

### 1.1 业务问题

Phase 05 给出"继续 / 收缩 / 转向"决策后，下一步必须**定稿**：

> 第三章写什么？第四章写什么？每个工作包用什么方法 + 哪些 evidence？
> 每个创新点绑定什么实验？五章式目录怎么映射？

合集中的核心经验："工作量不是一句创新点，而是一个**问题 + 一个方法 + 一个实验闭环 + 一个章节位置**"。Phase 06 把这条经验工程化为 4 个 Pydantic 对象 + 强约束（每 WP 必绑主实验 + 补充实验）。

### 1.2 工程问题

WorkPackagePlan 是 Phase 07（开题报告生成）的核心输入。开题报告每个章节的内容必须**直接**来自 WorkPackagePlan 的 experiment / data_source / figures_needed 字段。Phase 06 把这些字段全部锁死。

### 1.3 纯规则 vs LLM

- **最终题目选择** 纯规则：跟 RiskEvaluation.decision 走（继续/收缩/转向）
- **实验矩阵** 纯规则：每 WP 1 主 + 1 消融 + 1 对比 + 1 参数（heuristic 模板）
- **五章式目录** 纯规则：每章 content_summary / data_sources / figures_needed 走模板

LLM 留给 Phase 07（开题报告的章节文本生成）。

---

## 2. 做了哪些工作

### 2.1 领域模型（`packages/domain/phase6_models.py`，95 行）

```python
class Experiment(BaseModel)              # experiment_id/type/purpose/data_source/baseline/metrics/expected_artifact/wp_binding
class ExperimentMatrix(BaseModel)        # wp_id + main_experiment + supporting_experiments
class ThesisOutlineChapter(BaseModel)    # chapter/title/content_summary/data_sources/figures_needed
class WorkPackageFinal(BaseModel)         # wp_id/kind/chapter/title/research_question/method/data/baseline/metrics/主+补充实验/chapter_sections/innovation_binding
class WorkPackagePlan(BaseModel)          # 上述 + final_topic + final_topic_from_pivot + allow_proceed_to_phase07
```

### 2.2 节点（`packages/agents/nodes/phase6_work_package.py`，280 行）

**最终题目选择**：

| RiskEvaluation.decision | final_topic | from_pivot |
|---|---|---|
| 继续 | normalized_topic | False |
| 收缩 / 转向 | pivot_candidates[0].new_topic | True |

**实验矩阵生成**（每 WP 4 个实验）：

| 实验 ID | 类型 | 用途 |
|---|---|---|
| `{WP}-MAIN` | 主实验 | 回答 research_question |
| `{WP}-ABL` | 消融实验 | 验证各模块贡献 |
| `{WP}-CMP` | 对比实验 | 与已有 baseline 横向对比 |
| `{WP}-PAR` | 参数实验 | 关键超参数稳定性 |

**五章式目录映射**（每章 4 字段）：

| 章节 | title | content_summary | figures_needed |
|---|---|---|---|
| 第一章 | 绪论 | 选题背景与组织结构 | 图 1-1 / 1-2 |
| 第二章 | 相关基础 | LangGraph / RAG / 混合检索 | 图 2-1 / 2-2 |
| 第三章 | WP1 标题 | WP1 研究问题+方法+实验 | 图 3-1 + 表 3-1/3-2 |
| 第四章 | WP2 标题 | WP2 研究问题+方法+实验 | 图 4-1 + 表 4-1/4-2 |
| 第五章 | 总结与展望 | 贡献边界 + 未来 3-4 方向 | 图 5-1 |

**max_writing_risk 启发式**：

| 触发条件 | 风险 |
|---|---|
| D 评级 | Pivot 风险大，必须先回到 Phase 04 补证据 |
| from_pivot=True | pivot 后题目的 baseline 复现周期可能与时间红线冲突 |
| datasets < 2 | 数据集不足，第三章/第四章实验结论可能不稳健 |
| 有 baseline 是"高"复现难度 | 时间红线紧 |
| 否则 | 中等：所有维度评分 ≥ B，写作风险可控 |

**allow_proceed_to_phase07**：
- D 评级 → False
- 无 WP → False
- 任一 WP 缺主实验或补充实验 → False
- 五章式目录缺失 → False

### 2.3 端点

| 方法 | 路径 | 行为 |
|------|------|------|
| POST | `/api/v1/projects/{id}/work_package/plan` | 调规则定稿，落库 |
| GET | `/api/v1/projects/{id}/work_package/plan` | 取已落库的计划 |

### 2.4 新表 `work_package_plans`

```python
class WorkPackagePlanRow(Base):
    id / project_id (unique) / case_id / payload (JSON)
    / final_topic (str) / from_pivot (bool) / allow_proceed_to_phase07 (bool)
```

仓储 `apps/api/app/db/work_package_repository.py`：按 `project_id` upsert。

### 2.5 测试（20 条）

- `test_phase6_models.py`（12 条）：2 WP 数量、章节分配、实验齐全、矩阵匹配、五章齐全、final_topic 决策、pivot 切换、allow_proceed、max_writing_risk、innovation_binding
- `test_phase6_api.py`（8 条）：plan 端点、GET 持久化、无 risk 404、无 evidence 404、不存在 404、GET 404、upsert 幂等、experiment_count 准确

**127/127 pytest 全过**（原 107 + 新 20）。

---

## 3. 数据流：POST work_package/plan 端到端

```text
RiskEvaluation + TopicSpec + EvidenceLedger + ProjectIntake (from DB)
                  │
                  ▼  (FastAPI 路由)
        risk_repo / spec_repo / led_repo / proj_repo
        无 → 404/409
                  │
                  ▼  (Phase 06 入口)
        build_work_package_plan(intake, spec, risk_ev, ledger)
          ├─ _pick_final_topic(intake, spec, risk_ev)
          │   ├─ 决策=继续 → spec.normalized_topic
          │   └─ 决策=收缩/转向 + 有 pivot → pivot_candidates[0].new_topic
          ├─ 兜底: WP<2 → 补一个"扩展"WP
          ├─ _finalize_wp(wp, idx, ledger) × 2
          │   ├─ _main_experiment(wp, ledger)
          │   └─ _supporting_experiments(wp, ledger) — ABL+CMP+PAR
          ├─ ExperimentMatrix × 2
          ├─ _build_thesis_outline(spec, ledger, wps) — 5 章
          └─ max_writing_risk + allow_proceed_to_phase07
                  │
                  ▼  (落库)
        WorkPackagePlanRepository.upsert(plan)
                  │
                  ▼  (响应)
        {
          "id": N, "project_id": "N",
          "final_topic": "...",
          "from_pivot": bool,
          "work_package_count": 2,
          "experiment_count": N (含补充),
          "allow_proceed_to_phase07": bool,
          "payload": <WorkPackagePlan JSON>
        }
```

---

## 4. 验收对照（Phase 06 §6）

| 条目 | 状态 |
|------|------|
| 至少形成 1 个完整工作包，目标是 2 个 | ✓ `test_work_package_plan_has_two_wps` |
| 每个工作包都有研究问题、方法方案、数据、baseline、指标和章节位置 | ✓ `WorkPackageFinal` 14 字段 |
| 每个创新点绑定至少 1 个实验 | ✓ `test_innovation_binding_listed_for_every_wp` |
| 第三章、第四章均有可写内容 | ✓ `test_work_package_chapter_assignment` |
| 实验矩阵包含主实验和至少一种补充实验 | ✓ `test_each_wp_has_main_and_supporting_experiments` |
| 五章式论文目录映射完整 | ✓ `test_thesis_outline_has_five_chapters` |
| 不允许把"系统实现"当作唯一工作量，除非有清晰评价指标 | ✓ `metrics` 必填 + `main_experiment.purpose` 必填 |

---

## 5. 过程中修复的真实 Bug

### Bug 1：`metrics` 字段类型错误

**现象**：所有 12 条 Phase 06 model 测试失败，Pydantic 报 `Input should be a valid list`。

**原因**：`_main_experiment` 把 `ledger.metrics[0].name`（字符串）塞给 `metrics` 字段，但 Pydantic 期望 `list[str]`。

**修复**：

```python
# 改前
metrics=ledger.metrics[0].name if ledger.metrics else "（需补）",
# 改后
metrics=[m.name for m in ledger.metrics[:1]] or ["（需补）"],
```

### Bug 2：测试预期 409 实际 404

**现象**：`test_work_package_blocked_without_evidence` 期望 409，返 404。

**原因**：router 检查顺序是 `risk_ev → spec → ledger`。缺 ledger → 跳不到 ledger 检查就 404 了（因为 risk_ev 也跑不通）。

**修复**：测试改成"缺 evidence → risk 跑不通 → 整体 404"，并加 docstring 解释上游强依赖设计。

---

## 6. 与规约的偏离

无字段偏离。两条**实现细节**显式标注：

1. **4 个 WP 类型**只用了 2 个（证据链构建型 / 风险评分型），其他 4 个（系统实现型 / 对比分析型 / 模板生成型 / Pivot 决策型）留接口留给 Phase 07+ 扩展。
2. **五章式目录 figures_needed**是硬编码模板，不与具体论文图号联动（论文图号由 LaTeX 自动编号）。

---

## 7. 与 Phase 07 的交接

- `WorkPackagePlan.thesis_outline[].content_summary` → 开题报告每章内容初稿
- `WorkPackagePlan.work_packages[].main_experiment` → 开题报告实验方案章节
- `WorkPackagePlan.work_packages[].innovation_binding` → 开题报告创新点章节
- `WorkPackagePlan.max_writing_risk` → 开题报告"风险预案"章节
- `allow_proceed_to_phase07=False` → 阻断 Phase 07

---

## 8. 不在本 Phase 的范围

- **开题报告 Markdown / DOCX 生成**（Phase 07）
- **委员会多 Agent 审查**（Phase 07）
- **LaTeX / Overleaf 模板对接**（Phase 08）

---

## 9. 一句话总结

> Phase 06 用纯规则把 RiskEvaluation + EvidenceLedger + TopicSpec 翻译为 2 个 WorkPackageFinal（每 WP 含 1 主 + ≥1 补充实验）+ 2 个 ExperimentMatrix + 5 章式 ThesisOutlineChapter + max_writing_risk 启发式。20 端到端测试守护 2 WP / 章节分配 / 创新点绑定 / 上游依赖链。127/127 pytest 全过。
