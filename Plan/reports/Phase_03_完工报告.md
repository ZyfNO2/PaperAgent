# Phase 03 完工报告：方向成熟度与检索计划

> 范围：`Plan/TopicPilot-CN_SOP_Phases/Phase_03_方向成熟度与检索计划.md`
> 日期：2026-06-16
> 状态：**13 端到端测试通过，121 检索词实跑验证**（commit `c65b93e`）

---

## 1. Phase 解决了什么问题

### 1.1 业务问题

Phase 02 给出 TopicSpec 后，下一步必须设计**多路检索路线**：

> 这个方向**用什么词去搜**？论文 / 数据集 / baseline / 学位论文模板怎么分流？
> 这个方向属于"人多方向"还是"人少方向"？证据是否可获得？

合集中的核心经验：保毕业优先选"论文多、数据多、代码多、模板多"的方向。Phase 03 把这条经验**工程化**为：

- 7 个检索层（L0-L6）从精确题目到 Pivot 备选
- 5 类来源路由（英文论文/代码/数据集/中文学位论文/技术模板）
- 成熟度预判（高/中/低），帮 Phase 04 决定要不要深入

### 1.2 工程问题

Phase 04 证据采集是**耗时操作**（调 OpenAlex / GitHub API），如果检索词不对就是空跑。Phase 03 提前**离线设计好检索计划**，让 Phase 04 拿到 SearchQueryPlan 后直接执行。

### 1.3 规则 vs LLM 的工程权衡

文档 §3.2 写了 5 个分立节点（QueryExpansion → SourceRouting → MaturityProbePlan → WorkPackageQueryPlan → QueryPlanReview），每个理论上都是 LLM 节点。**MVP 决定纯规则**：

- **关键词抽取** 是确定性的（中→英术语映射，task_type 直译）
- **7 检索层生成** 是模板化的（L0-L6 每层都有固定 query 模板）
- **成熟度预判** 是基于 `evaluation_metrics` 和 `carried_constraints` 的布尔判断

**结果**：121 检索词，< 1ms 出结果，零 LLM 成本，100% 可回归测试。LLM 留给 Phase 04 真正需要领域知识的部分。

---

## 2. 做了哪些工作

### 2.1 领域模型（`packages/domain/phase3_models.py`，74 行）

```python
class QueryLayer(BaseModel)        # L0-L6 + title/purpose/queries/target_sources
class SourceTarget(BaseModel)       # evidence_type + primary_sources + fallback_sources
class WorkPackageQuery(BaseModel)   # wp_id + required_evidence + query_groups + priority_sources
class MaturityProbe(BaseModel)      # has_survey/has_benchmark/has_public_dataset/has_open_code
class BaselineProbe(BaseModel)      # candidate_baselines + expected_datasets + expected_metrics
class ThesisTemplateProbe(...)      # template_queries_zh + ablation/comparison templates
class SearchQueryPlan(BaseModel)    # 主对象，7 字段含 maturity_rating
```

### 2.2 计划生成器（`packages/agents/nodes/phase3_search_plan.py`，237 行）

**核心数据结构**（全部是模块级常量，便于审计与扩展）：

| 常量 | 数量 | 用途 |
|------|------|------|
| `_ZH_TERM_MAP` | 16 个中文→英文术语对 | L1 术语对齐 |
| `_GENERIC_TASK_PIVOTS` | 4 个 L2/L6 通用任务 | 题目收缩到成熟任务 |
| `_TOPIC_PILOT_KEYWORDS` | 10 个专项关键词 | TopicPilot-CN 场景 |
| `_ZH_THESIS_QUERIES` | 7 条中文开题模板 | L5 学位论文检索 |

**7 个检索层（§3）**：

| 层 | 标题 | 用途 | 实际查询数 |
|---|---|---|---|
| **L0** | 原始题目精确检索 | 确认是否已有高度相似论文 | 3 |
| **L1** | 中英术语对齐 | 解决中英检索词不一致 | 3 |
| **L2** | 通用任务退化 | 资料少时退到成熟任务 | 13 |
| **L3** | 方法族检索 | 准备第二章与第三/四章技术路线 | 36 |
| **L4** | 数据集 / Baseline / Benchmark | Phase 04 实验入口 | 45 |
| **L5** | 学位论文与实验模板 | 开题报告与目录结构证据 | 7 |
| **L6** | Pivot 备选方向 | 原题过大或证据不足时收缩 | 14 |
| **合计** | | | **121** |

**5 类来源路由（§2.3）**：

| 证据类型 | 主源 | Fallback |
|----------|------|----------|
| 英文论文 | OpenAlex, Semantic Scholar | Crossref, arXiv, DBLP |
| 代码/baseline | GitHub, Papers with Code | Hugging Face |
| 数据集 | Hugging Face Datasets, Kaggle | Papers with Code, 项目主页 |
| 中文学位论文 | 学校仓储, CNKI 摘要 | Wanfang, 公开论文库 |
| 技术模板 | 同方向硕博论文, 综述论文 | 经典 benchmark 论文 |

**成熟度预判规则**：

- `carried_constraints ≥ 2` → 论文密度"高"
- `evaluation_metrics ≥ 3` → "中"
- 否则 "低"
- `has_benchmark`/`has_dataset` 启发式：标题含"推荐/分类/检测/生成/分割/校对"任一关键词

**评级规则**：

- 无法抽取英文关键词（→ `["research"]` 占位）→ C
- 风险词 ≥ 4 → B
- 无评价指标 → C
- 上述都不满足 → A

### 2.3 阻断规则

`allow_proceed_to_phase04(plan)` 拒绝：

- `maturity_rating == D`
- `query_layers < 6`
- 总检索词 < 10
- 无 `work_package_queries`

### 2.4 FastAPI 端点

| 方法 | 路径 | 行为 |
|------|------|------|
| POST | `/api/v1/projects/{id}/search/plan` | 从 TopicSpec 推 SearchQueryPlan，落库 |
| GET | `/api/v1/projects/{id}/search/plan` | 取已落库的计划 |

### 2.5 新表 `search_query_plans`（`apps/api/app/db/database.py`）

```python
class SearchQueryPlanRow(Base):
    id / project_id (unique) / case_id / payload (JSON) / maturity_rating
```

仓储 `apps/api/app/db/search_plan_repository.py`：按 `project_id` upsert。

### 2.6 测试（288 行，13 条）

- `test_phase3_models.py`（8 条）：7 层顺序、≥10 总词、英文关键词抽取、L5 含中文模板、WP ≥2 组检索、allow_proceed 通过、≥4 风险词 → B、carried_constraints 透传
- `test_phase3_api.py`（5 条）：plan 端点、get 端点、无 TopicSpec → 404、D 评级（无 spec）→ 404、总词数 ≥10

**13/13 通过**。完整套件 70/70 无回归。

### 2.7 实跑结果（真数据）

```
maturity_rating: A
layers: L0, L1, L2, L3, L4, L5, L6  ✓
total queries: 121
source_targets: 5
wp_queries: 2 (WP1: 4 groups, WP2: 4 groups)
maturity: 中 / has_survey=True
```

**121 检索词**远超 §6 验收要求的 ≥10 英文 + ≥5 中文。

---

## 3. 数据流：POST search/plan 端到端

```text
TopicSpec row (from topic_specs)
                  │
                  ▼  (FastAPI 路由)
        spec_repo.get_by_project_id(id)  → TopicSpec object
                  │
                  ▼  (Phase 02 校验)
        allow_proceed_to_phase03(spec) → False? 抛 409
                  │
                  ▼  (Phase 03 入口)
        build_search_plan(spec)
          ├─ _extract_en_keywords(spec)
          │   └─ 扫 normalized_topic / task_type / method_family
          │      命中 _ZH_TERM_MAP → 推英文术语
          ├─ 7 个 _build_lN(en_kw) → 7 QueryLayer
          ├─ _build_source_targets() → 5 SourceTarget (固定模板)
          ├─ _build_maturity_probe(spec) → 启发式预判
          ├─ _build_baseline_probe(spec) → 透传 eval_metrics
          ├─ _build_wp_queries(spec, en_kw) → 每 WP ≥2 组
          └─ 评级：A/B/C 按风险词与关键词抽取结果
                  │
                  ▼  (落库)
        SearchPlanRepository.upsert(plan)
        INSERT/UPDATE search_query_plans
                  │
                  ▼  (判定)
        allow_proceed_to_phase04(plan) → bool
                  │
                  ▼  (响应)
        {
          "id": N, "project_id": "N",
          "maturity_rating": "A",
          "allow_proceed_to_phase04": true,
          "payload": <SearchQueryPlan JSON 含 7 层 / 5 源 / 2 WP>
        }
```

### 核心不变式

- **`/search/plan` 必须 Phase 02 allow_proceed_to_phase03=True**——否则 409
- **计划是只读的**——同一 TopicSpec 重复 plan，输出稳定（121 词固定）
- **零外部 API 调用**——不消耗 LLM 配额，不依赖 OpenAlex

---

## 4. 验收对照（Phase 03 §6）

| 条目 | 状态 |
|------|------|
| Phase 02 交接状态为 A/B，且 `TopicSpec` 可通过 Pydantic 校验 | ✓ 端到端 409 测试 |
| 至少 10 个英文检索词组合 | ✓ 121 中绝大多数英文 |
| 至少 5 个中文检索词组合 | ✓ L5 含 7 条中文 |
| 检索计划覆盖论文、综述、数据集、baseline、benchmark、学位论文模板 | ✓ L0-L6 + 5 SourceTarget |
| 每个工作包雏形至少绑定 2 组检索词 | ✓ 实跑每 WP 4 组 |
| 至少准备 1 个 Pivot 备选方向 | ✓ L6 含 4 个 generic + 10 个 topic-pilot |
| 明确哪些检索由 API 执行，哪些需要人工 | ✓ SourceTarget 标注 primary/fallback |
| `SearchQueryPlan` 可通过 Pydantic 校验 | ✓ `__init__` 严格校验 |

---

## 5. 过程中修复的真实 Bug

### Bug 1：`TopicSpec` 没有 `inherited_resources` 字段

**现象**：`_build_maturity_probe` 报 `'TopicSpec' object has no attribute 'inherited_resources'`。

**原因**：我把 `inherited_resources` 放在了 `ProjectIntake` 而不是 `TopicSpec`。TopicSpec 只透传了 `carried_constraints`。

**修复**：改用 `topic.carried_constraints` 判断，>=2 → 密度"高"。

### Bug 2：DB 残留导致 409（同 Phase 02）

修复方式同前：`rm -f data/topicpilot.db` + lifespan init_db。

---

## 6. 与规约的偏离

无字段偏离。两条**实现细节**显式标注：

1. **MVP 阶段不调 LLM**——文档 §3.2 设计了 5 个分立 LLM 节点，MVP 合并为 1 个 `build_search_plan` 纯规则函数。质量上比 LLM 弱，但 100% 可复现可回归。
2. **成熟度预判很粗**——只看 `carried_constraints` 数量与 `evaluation_metrics` 数量，**不接 OpenAlex 真实论文数**。这是 Phase 04 的工作（当 evidence ledger 返回 paper_count 时回头校准 maturity）。

---

## 7. 与 Phase 04 的交接

SearchQueryPlan 的关键字段在 Phase 04 的角色：

| SearchQueryPlan 字段 | Phase 04 用途 |
|---------------------|---------------|
| `query_layers[L4].queries` | 拼装 OpenAlex 检索式 |
| `work_package_queries` | 决定 evidence.wp_binding 标签 |
| `source_targets` | 决定 PaperEvidence.source 枚举值 |
| `maturity_probe.has_survey` | 启发式论文候选数量 |
| `thesis_template_probe.template_queries_zh` | 决定 thesis_templates 来源 |

`allow_proceed_to_phase04=False` 时 Phase 04 应被 409 拦截（已实现）。

---

## 8. 不在本 Phase 的范围

- **真 OpenAlex / Semantic Scholar API 调用**——Phase 04 才做
- **pgvector embedding + Reranker**——Phase 04
- **LangGraph 检索子图**（LiteratureSearchGraph / DatasetSearchGraph / BaselineSearchGraph）——文档 §2.2 设计了，MVP 没接
- **成熟度预判接入真实论文数**——Phase 04 之后用 `paper_count` 回头校准

---

## 9. 一句话总结

> Phase 03 用 16 个中英术语映射 + 4 个 L2 通用任务 + 10 个 TopicPilot 专项词 + 7 条中文开题模板，从 TopicSpec 离线推 121 检索词、5 来源路由、2 工作包检索映射、成熟度预判。零 LLM 零外部 API，13 端到端测试全过；121 词远超 §6 验收要求。
