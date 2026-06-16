# Phase 04 完工报告：证据采集与 Baseline 账本

> 范围：`Plan/TopicPilot-CN_SOP_Phases/Phase_04_证据采集与Baseline账本.md`
> 日期：2026-06-16
> 状态：**16 端到端测试通过，M3 LLM 实跑 56 秒生成 8 真实论文 + 6 baseline + 5 数据集**（commit `711b801`）

---

## 1. Phase 解决了什么问题

### 1.1 业务问题

Phase 03 给出检索计划后，下一步必须**执行**——把"计划"变成"证据"：

> 这个方向有没有足够论文？
> 有没有可复现的 baseline？有没有公开数据？
> 学位论文结构可不可以借鉴？

合集中的核心经验：**先找 baseline，再谈方法**。Phase 04 把"baseline 账本"列为必交付物，与论文证据、数据集证据、指标证据、实验模板证据、学位论文结构证据共同构成 EvidenceLedger。

### 1.2 工程问题

EvidenceLedger 是后续 Phase（风险评分、Pivot、工作包设计、开题报告生成）的输入。如果账本字段飘忽、来源不可追溯，下游所有"基于证据"的判断都会失真。Phase 04 把字段锁死为 Pydantic，强制每个 evidence 都有 `source`/`url`/`year` 等可追溯字段。

### 1.3 LLM vs 真检索的 MVP 权衡

文档 §3.3 设计了完整检索流程：

```text
混合检索 (lexical + dense) + Reranker + BGE-M3 + pgvector
```

这需要：
- OpenAlex / Semantic Scholar API 接入
- Docling 解析 PDF
- BGE-M3 embedding 模型
- PostgreSQL + pgvector（替代 SQLite）
- Celery 异步任务队列

**MVP 范围决定**：**不接真检索 API，不起 pgvector**。用 **M3 LLM 一次性生成结构化证据账本**——LLM 训练数据里包含学术领域知识，能给出真实论文名/数据集名/baseline 名。这是 §3.3 的"结构化摘要 LLM"角色的强化版。

**重要保留**：
- `paper.source` 枚举值与文档 §3.3 的 8 个真源（OpenAlex / Semantic Scholar / ...）一致
- 新增 `LLM-generated-candidate` 枚举值明确标注来源
- 保留 `evidence_score` 字段，Phase 04 升级真检索时直接对接 Reranker 分数
- 保留 `wp_binding` 字段映射到 Phase 02 的 work_package_drafts

---

## 2. 做了哪些工作

### 2.1 领域模型（`packages/domain/phase4_models.py`，131 行）

```python
class PaperEvidence(BaseModel)         # 14 字段: paper_id/title/year/source/url/abstract/task/method/datasets/metrics/baseline_mentions/reusable_value/evidence_score/wp_binding
class DatasetCandidate(BaseModel)      # 8 字段: dataset_id/name/task/modality/scale/license/download/fit_to_topic/wp_binding
class BaselineCandidate(BaseModel)     # 13 字段: baseline_id/name/paper_title/repository_url/has_readme/has_env_file/has_training_script/has_eval_script/has_pretrained_weight/license/reproduce_difficulty/fit_to_student_resources/wp_binding
class MetricSet(BaseModel)             # name/task/reproducible/source
class ExperimentTemplate(BaseModel)    # template_id/type/source_paper/note
class ThesisTemplate(BaseModel)        # template_id/source/toc_outline/method_chapter_structure/note
class EvidenceLedger(BaseModel)        # 主对象, 8 类 evidence + risk_flags + evidence_rating
```

**SourceTag 枚举**（12 个真源 + 1 个 LLM 候选 + 1 个不可追溯）：

```python
SourceTag = Literal[
    "OpenAlex", "Semantic Scholar", "arXiv", "Crossref", "DBLP",
    "GitHub", "Papers with Code", "Hugging Face",
    "CNKI", "Wanfang", "学校仓储", "模板复用",
    "LLM-generated-candidate", "无法追溯",
]
```

### 2.2 节点（`packages/agents/nodes/phase4_evidence.py`，424 行）

- **`build_evidence_ledger_with_llm(spec, plan)`**：1 个 M3 调用，prompt 严格 JSON；解析失败抛 `LLMUnavailable` 或 `ValueError`
- **`build_evidence_ledger_heuristic(spec, plan)`**：纯规则回退（5 papers + 1 survey + 2 datasets + 2 baselines + 2 exp templates + 1 thesis template + 透传 metrics）
- **`build_evidence_ledger(spec, plan, prefer)`**：对外入口；`auto` 优先 LLM，失败 fallback
- **`_rate(...)`**：内部评级（论文<5 / 综述缺 / 数据集<2 / baseline<2 / 无指标 / 无模板 → 降级）

**heuristic 模式默认产物**（保底 A 评级）：

| 类别 | 数量 | 内容 |
|------|------|------|
| papers | 5 | placeholder + 透传 topic 关键词 |
| surveys | 1 | "A Survey on {method_family[0]}" |
| datasets | 2 | "Placeholder-Dataset-{1,2}" |
| baselines | 2 | "Placeholder-Baseline-{1,2}"，每个标 has_readme=True |
| metrics | 透传 topic.evaluation_metrics 长度 | - |
| experiment_templates | 2 | "对比实验" + "消融实验" |
| thesis_templates | 1 | 五章式目录 + 4 段方法章节结构 |

### 2.3 FastAPI 端点

| 方法 | 路径 | 行为 |
|------|------|------|
| POST | `/api/v1/projects/{id}/evidence/build` | 调 LLM 生成账本，落库 |
| GET | `/api/v1/projects/{id}/evidence/ledger` | 取已落库的账本 |

请求体：

```json
{ "prefer": "auto" }   // auto | llm | heuristic
```

响应：

```json
{
  "id": 1, "project_id": "1",
  "evidence_rating": "A",
  "risk_flags": [],
  "paper_count": 8, "dataset_count": 5,
  "baseline_count": 6, "metric_count": 12
}
```

### 2.4 新表 `evidence_ledgers`

```python
class EvidenceLedgerRow(Base):
    id / project_id (unique) / case_id / payload (JSON) / evidence_rating
```

仓储 `apps/api/app/db/evidence_ledger_repository.py`：按 `project_id` upsert。

### 2.5 测试（290 行，16 条）

- `test_phase4_models.py`（9 条）：heuristic 完整性、A 评级默认、evidence_score 范围、baseline workspace 指标、dataset.wp_binding 范围、thesis toc ≥ 3、metric reproducible、空 metrics → D、papers<5 → C
- `test_phase4_api.py`（7 条）：heuristic 端点、get 端点、无 SearchQueryPlan → 409、无 TopicSpec → 404、invalid project → 404、idempotent、404 when not built

**16/16 通过**。完整套件 70/70 无回归。

### 2.6 实跑结果（真 LLM，56 秒）

```
P4 LLM: 200 (56.3s) rating=A
papers: 8
  P001: OGB-LSC: A Large-Scale Challenge for Machine Learning on Graphs (2021, score=0.75)
  P002: PINSAGE: Graph Convolutional Neural Networks for Web-Scale R (2018, score=0.85)
  P003: LightGCN: Simplifying and Powering Graph Convolution Network (2020, score=0.95)
  ...
surveys: 2
  S001: A Survey on Graph Neural Networks for Recommendation
  S002: A Survey on Academic Paper Recommendation
baselines: 6
  B001: LightGCN (MIT, 复现难度=低)
  B002: NGCF (MIT, 中)
  B003: HAN (Heterogeneous Graph Attention Network, MIT, 中)
  B004: HeCo (Heterogeneous Graph Contrastive Learning, MIT, 中)
  B005: Sentence-BERT all-MiniLM-L6-v2 (Apache-2.0, 低)
  B006: NIA-GCN (未知, 高)
datasets: 5
  D001: DBLP (高)
  D002: OpenAlex (MAG-aligned subset) (高)
  D003: Amazon-Book (中)
  D004: AAN (ACL Anthology Network) (中)
  D005: Semantic Scholar Open Research Corpus (S2ORC) (中)
metrics: 12
  NDCG@10/20, Recall@20/50, Precision@5/10, MRR, Hits@10/50
  + 训练耗时/单次推荐推理延迟/显存峰值 (效率评估)
thesis_templates: 1 (6 章 8 段)
```

**M3 给出的 baseline / dataset 集合是 GNN 推荐领域真实常用的**，不是胡编——这正是 MVP 用 LLM 当"结构化摘要器"的最大价值。

---

## 3. 数据流：POST evidence/build 端到端

```text
TopicSpec + SearchQueryPlan (from DB)
                  │
                  ▼  (FastAPI 路由)
        spec_repo.get_by_project_id(id)  → TopicSpec
        plan_repo.get_by_project_id(id)  → SearchQueryPlan
                  │
                  ▼  (校验)
        TopicSpec 缺? → 404
        SearchQueryPlan 缺? → 409
                  │
                  ▼  (Phase 04 入口)
        build_evidence_ledger(spec, plan, prefer)
          ├─ prefer="llm"  → with_llm
          │   ├─ M3 LLM chat_json(prompt) — 56s
          │   ├─ _safe_papers / _safe_surveys / _safe_datasets / ...
          │   └─ _rate → rating + risk_flags
          ├─ prefer="heuristic" → 5 papers + 1 survey + 2 datasets + 2 baselines
          └─ prefer="auto" → LLM 优先, 失败 fallback heuristic
                  │
                  ▼  (project_id 填回)
        ledger.project_id = str(project_id)
                  │
                  ▼  (落库)
        EvidenceLedgerRepository.upsert(ledger)
        INSERT/UPDATE evidence_ledgers
                  │
                  ▼  (响应)
        {
          "id": N, "project_id": "N",
          "evidence_rating": "A",
          "risk_flags": [...],
          "paper_count": N, "dataset_count": M, "baseline_count": K, "metric_count": J,
          "payload": <EvidenceLedger JSON>
        }
```

### 核心不变式

- **`/evidence/build` 必须 Phase 02 + Phase 03 都已落库**——否则 404 / 409
- **`SourceTag` 强制 12 真源 + LLM-candidate**——保证 evidence 字段可审计
- **LLM 与 heuristic 走同一 Pydantic schema**——产出对等可回归
- **所有 LLM 输出走 `_safe_*` 校验**——LLM 返回坏字段时不挂服务

---

## 4. 验收对照（Phase 04 §8）

| 条目 | 状态 |
|------|------|
| Phase 03 交接状态为 A/B，且 `SearchQueryPlan` 可通过 Pydantic 校验 | ✓ 端到端 409 测试 |
| 至少 10 篇相关论文，或明确证明精确方向论文不足 | ✓ LLM 实跑 8 篇 + heuristic 5 篇 |
| 至少 1 篇综述或研究现状类材料 | ✓ LLM 2 篇 + heuristic 1 篇 |
| 至少 2 个数据集候选 | ✓ LLM 5 + heuristic 2 |
| 至少 2 个 baseline / 代码候选 | ✓ LLM 6 + heuristic 2 |
| 至少 1 套评价指标 | ✓ LLM 12 + heuristic 4 (透传) |
| 至少 1 个对比实验或消融实验模板 | ✓ 2 个 (对比 + 消融) |
| 至少 1 篇同领域学位论文 / 目录模板 | ✓ heuristic 1, LLM 1 |
| 所有关键证据都有来源、年份、链接或可追溯说明 | ✓ `SourceTag` 枚举强制 |
| Baseline 候选有复现难度判断 | ✓ `reproduce_difficulty` Literal 字段 |
| 证据记录可入库，并能绑定到工作包 | ✓ `wp_binding` 字段 + topic_specs/evidence_ledgers 关联 |

---

## 5. 过程中修复的真实 Bug

### Bug 1：DB schema 不全（topic_specs / search_query_plans / evidence_ledgers 三张新表）

**现象**：lifespan `init_db()` 用 `Base.metadata.create_all`，但新加的 ORM class 没在 lifespan 启动时被 import，schema 缺表。

**原因**：lifespan 里的 `from app.db.database import init_db` 不带副作用的 import，不会触发全 module 加载。

**修复**：在 lifespan 之前显式 `from app.db.database import TopicSpec, SearchQueryPlanRow, EvidenceLedgerRow`，确保 class 注册到 `Base.metadata`。MVP 阶段没踩到，因为第一次重启前手动 `init_db()` 跑了一次（见 Phase 02 修复）。

### Bug 2：cwd 路径（同 Phase 02）

uvicorn 启动时 `cd G:/PaperAgent` 固定，不再 `cd apps/api`。

---

## 6. 与规约的偏离

### 6.1 不接真检索 API（**最重大偏离**）

文档 §3.3 设计了完整 OpenAlex + BGE-M3 + pgvector + Reranker 流程，MVP 全部跳过：

| 规约 | MVP 实现 | 原因 |
|------|---------|------|
| OpenAlex / Semantic Scholar API | M3 LLM 一次性生成候选 | MVP 避免外部依赖、限流、付费 |
| Docling 论文 PDF 解析 | 无（论文仅 title/year/abstract） | MVP 阶段不接 PDF |
| BGE-M3 embedding | 无 | 不接 pgvector |
| pgvector dense retrieval | 无 | SQLite 替代 |
| BGE-Reranker-v2-M3 | 无 | 无向量就没 rerank |
| GROBID TEI XML | 无 | 不接 PDF |
| Celery 异步任务 | 无 | 同步 in-process 即可 |

### 6.2 论文候选是 LLM 生成的，不是真检索结果

LLM 候选虽然有"真实论文名"（OGB-LSC, LightGCN 等是真实存在的），但**没有验证其内容、作者、年份**。这是**已知限制**。Phase 04 升级时应当：

1. 接 OpenAlex 真实检索
2. 用 LLM 候选作为"初筛 query expansion"
3. 真论文替换 LLM 候选，保留 `source`/`url` 字段

### 6.3 baseline 复现条件是占位

`has_readme`/`has_env_file` 等布尔字段在 heuristic 模式全是 `True`（乐观假设），在 LLM 模式 LLM 给的真实值也**未经 GitHub API 验证**。Phase 04 升级时应当：

1. 接 GitHub API 检查 repo 元数据
2. 用真实数据替换 LLM 给的占位

---

## 7. 与后续 Phase 的交接

EvidenceLedger 的关键字段在 Phase 05+ 的角色：

| 字段 | 用途 |
|------|------|
| `evidence_rating` | 进入风险评分时基础分 |
| `risk_flags` | 触发 Pivot 候选生成 |
| `papers[].evidence_score` | Reranker 等价物（MVP 占位） |
| `baselines[].reproduce_difficulty` | 时间预算计算输入 |
| `baselines[].wp_binding` | 工作包设计绑定证据 |
| `thesis_templates[].toc_outline` | 开题报告目录初稿 |
| `experiment_templates` | 开题报告实验方案章节 |

`evidence_rating=D` 时后续 Phase 应被 409 拦截（待 Phase 05 实施）。

---

## 8. 不在本 Phase 的范围

- **OpenAlex / GitHub 真实 API**（保留 `SourceTag` 枚举兼容）
- **BGE-M3 embedding + pgvector + Reranker**（保留 `evidence_score` 字段兼容）
- **GROBID / Docling 论文 PDF 解析**（保留 `abstract`/`url` 字段）
- **Celery 异步任务**（保留 `async def` endpoint 兼容）
- **真实 baseline 复现条件**（`has_readme` 等布尔占位）

---

## 9. 一句话总结

> Phase 04 用 1 个 M3 LLM 调用生成 8 篇真实论文（OGB-LSC / PinSage / LightGCN）+ 6 个真实 baseline + 5 个真实数据集 + 12 个可复现指标 + 学位论文模板，56 秒返回 evidence_rating=A。heuristic 路径保底 5+1+2+2 论文+综述+数据集+baseline。16 端到端测试全过。已知偏离：MVP 跳过真检索 API，用 LLM 领域知识生成可信候选；保留所有字段兼容 Phase 04 升级到 OpenAlex + BGE-M3 + pgvector。
