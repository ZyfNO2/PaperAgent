# PaperAgent Re6.4：学术裁缝 2.0 SOP

> **制定日期**：2026-07-11  
> **承接**：R6-2 Router Unification。  
> **周期**：5 个有效开发日。  
> **阶段门**：无证据/first claim 不可通过 + NoveltyReviewAdapter 五项测试可用 + evolution log 不覆盖历史。  
> **后继**：R6-5 Robustness Lab。  
> **方法论来源**：[Paper-novelty-design](https://github.com/LaVineLeo/Paper-novelty-design) commit `9434234`，MIT 许可。

---

## 1. 目标与非目标

### 1.1 目标

实现证据约束下的创新点生成、审查、可证伪规划和演化闭环：

1. Problem–Method–Insight 三层主张；
2. 五类伪创新识别（缺 motivation、工程堆料、跨域移植、指标叙事、脆弱 first claim）；
3. 可证伪命题（support / refute / required test）；
4. 独立 reviewer pressure test；
5. 创新点版本演化日志（append-only）。

### 1.2 非目标

- 不生成或验证文献事实（仍由 retrieval/verifier/RAG 负责）；
- 不自动定稿创新点（用户决定 accept / revise）；
- 不做无文献证据时的 first claim；
- 不修改 Re5 检索链路或 RAG 管道；
- 不做前端创新工作台 UI 的完整实现（仅 API + 数据结构，UI 最小可用）。

---

## 2. 产物/输出清单

| 编号 | 产物 | 路径/模块 | 格式 |
|---|---|---|---|
| D-01 | EvidenceContext schema | `app/services/agents/graph/schemas/evidence_schema.py` | Pydantic v2 model |
| D-02 | NoveltyCandidate schema | 同上 | Pydantic v2 model |
| D-03 | DifferentiationMatrix schema | 同上 | Pydantic v2 model |
| D-04 | FalsifiableProposition schema | 同上 | Pydantic v2 model |
| D-05 | ReviewerPressurePoint schema | 同上 | Pydantic v2 model |
| D-06 | ContributionProofPlan schema | 同上 | Pydantic v2 model |
| D-07 | NoveltyRevision schema | 同上 | Pydantic v2 model |
| D-08 | Evidence Context Compiler | `app/services/agents/graph/nodes/evidence_context.py` | Python module |
| D-09 | Novelty Draft Generator 节点 | `app/services/agents/graph/nodes/novelty_draft.py` | Python module |
| D-10 | NoveltyReviewAdapter 节点 | `app/services/agents/graph/nodes/novelty_review.py` | Python module |
| D-11 | Falsifiability Planner 节点 | `app/services/agents/graph/nodes/falsifiability.py` | Python module |
| D-12 | Claim Judge 节点 | `app/services/agents/graph/nodes/claim_judge.py` | Python module |
| D-13 | Novelty Evolution Log | `app/services/agents/graph/nodes/novelty_evolution.py` | Python module |
| D-14 | 语义校验器 | `app/services/router/validators/novelty_validators.py` | Python module |
| D-15 | Prompt A/B/C 模板 | `app/services/agents/prompts/novelty_*.md` | Markdown prompts |
| D-16 | NoveltyReviewAdapter contract | `app/services/router/contracts.py`（注册） | StructuredOutputContract |
| D-17 | L0 单元测试 | `apps/api/tests/test_re6/novelty/` | pytest |
| D-18 | Novelty gold set | `apps/api/tests/test_re6/novelty/gold/` | JSON fixtures |
| D-19 | THIRD_PARTY_NOTICES 更新 | `THIRD_PARTY_NOTICES.md` | Markdown |

---

## 3. 规范

### 3.1 数据链路

```
Verified papers + RAG chunks
  → Evidence Context Compiler
  → Adjacent-work Differentiation Matrix
  → Novelty Draft Generator (Prompt A)
  → Binding Validator
  → NoveltyReviewAdapter (Prompt B)
  → Falsifiability Planner (Prompt C)
  → Claim Judge + Binding Validator
  → Novelty Evolution Log
  → User accept / revise
```

### 3.2 Schema 定义

#### EvidenceContext

```python
class EvidenceContext(BaseModel):
    candidate_id: str             # verified paper ID
    chunk_id: str | None           # RAG chunk ID（如有）
    snippet: str                   # 证据片段
    location: str                  # 页码 / 段落 / URL
    role: str                      # problem / method / insight / adjacent
    source_quality: str           # verified / user_uploaded / rag_extracted
```

#### NoveltyCandidate

```python
class NoveltyCandidate(BaseModel):
    candidate_id: str             # uuid4
    problem: str                   # 具体且有边界的未解决缺口
    method: str                    # 直接针对该缺口的干预
    insight: str                   # 忘掉模型名后仍可复用的条件性发现
    scope: str                     # 适用任务、数据条件和不适用边界
    evidence_ids: list[str]        # Problem/Method/Insight 各至少一个
    status: Literal[
        "draft", "needs_evidence", "needs_rewrite",
        "under_review", "accepted", "rejected", "needs_literature_verification"
    ]
    pseudo_innovation_risks: list[str] = []
```

ID 不存在、snippet 无定位、Insight 只有指标改善时，status 只能是 `needs_evidence`
或 `needs_rewrite`。

#### DifferentiationMatrix

```python
class DifferentiationMatrix(BaseModel):
    adjacent_work_id: str          # candidate_id 或外部引用
    adjacent_work_label: str
    problem_diff: str              # 问题差异
    method_diff: str               # 方法差异
    detail_diff: str              # 实现细节差异
    evidence_diff: str             # 证据差异
    insight_diff: str              # Insight 差异
```

#### FalsifiableProposition

```python
class FalsifiableProposition(BaseModel):
    proposition_id: str
    proposition: str               # 可证伪命题
    scoped_setting: str            # 适用设定
    observable_effect: str          # 可观测效应
    support_condition: str         # 支持条件
    refute_condition: str           # 反驳条件
    required_test: str             # 所需实验
    evidence_ids: list[str]
    status: Literal["verified", "planned_not_verified", "refuted"]
```

若现有资源无法执行 required_test，标为 `planned_not_verified`，不得写成已被证明。

#### ReviewerPressurePoint

```python
class ReviewerPressurePoint(BaseModel):
    point_id: str
    risk: Literal[
        "repetition", "motivation", "falsifiability",
        "differentiation", "story"
    ]
    question: str                  # 审稿人提问
    severity: Literal["high", "medium", "low"]
    repair: str                    # 建议修复
    evidence_ids: list[str]        # 引用的 evidence_id，缺证据写 "unknown"
```

#### ContributionProofPlan

```python
class ContributionProofPlan(BaseModel):
    contribution: str
    evidence_needed: list[str]     # 所需证据类型
    weakest_link: str              # 最薄弱环节
    threshold: str                 # 验证门槛
```

#### NoveltyRevision

```python
class NoveltyRevision(BaseModel):
    revision_id: str               # uuid4
    parent_revision_id: str | None  # 父版本，根为 None
    version: int                  # 版本号
    reason: str                   # 修订原因
    evidence_delta: list[str]     # 新增/删除的 evidence IDs
    next_falsification_test: str | None
    created_at: datetime
    candidate_snapshot: NoveltyCandidate  # 该版本的 candidate 快照
```

Evolution log 是 append-only：不覆盖历史版本，新版本追加。

### 3.3 Prompt A：证据约束的创新草案

```text
你是受证据约束的研究贡献设计者。只根据 EVIDENCE_CONTEXT 和 ADJACENT_WORKS
生成候选主张；不能发明文献、结果、机制或首次结论。

每个候选必须包含：
1. Problem：具体且有边界的未解决缺口；
2. Method：直接针对该缺口的具体干预；
3. Insight：忘掉模型名称后仍可复用的条件性发现；
4. scope：适用任务、数据条件和不适用边界；
5. evidence IDs：Problem、Method、Insight 各至少一个。

性能提升只能作为 evidence，不能单独作为 Insight。
无法形成 Insight 时输出 needs_evidence，不可包装模块拼接为创新。
返回 NoveltyCandidate JSON 数组。
```

合同：`contract_id = "novelty-candidate/v1"`，`task_role = novelty_draft`，
`repair_strategy = "same_model_once"`，`allow_heuristic = false`。

### 3.4 Prompt B：NoveltyReviewAdapter

```text
你是匿名审稿人。对 NOVELTY_CANDIDATE 执行 repetition、motivation、
falsifiability、differentiation、story 五项测试。

检查：
- Problem 是否具体且有证据；
- Method 是否真的解决 Problem，而非工程堆料；
- Insight 是否独立于指标提升；
- 跨域移植是否解释直接复制为何失败、做了什么适配、得到什么可迁移认识；
- first claim 是否标为待文献验证；
- 每条批评必须引用 evidence_id，缺证据时写 unknown。

返回 verdict、pseudo_innovation_risks、pressure_points、
differentiation_matrix、required_repairs。
```

合同：`contract_id = "novelty-review/v1"`，`task_role = evidence_critic`，
`repair_strategy = "fallback_model_once"`（正式模式优先不同模型），
`allow_heuristic = false`。

### 3.5 Prompt C：可证伪命题规划

```text
只把已通过 binding 的 Insight 转化为 1 至 3 条可证伪命题。

每条命题必须包含 scoped setting、observable effect、support condition、
refute condition、required test 和 evidence IDs。
若现有资源无法执行 required test，标为 planned_not_verified，
不得写成已被证明。
```

合同：`contract_id = "falsifiable-proposition/v1"`，`task_role = evidence_critic`。

### 3.6 不可跨越的规则

| 规则 | 说明 |
|---|---|
| 指标提升是 evidence，不是 Insight | 性能数字只作为支撑证据 |
| 无可定位 evidence → needs_evidence | 不输出创新结论 |
| 同模型生成与审查 → 标记 self-review | trace 和报告中显著标注 |
| 正式模式优先不同模型 reviewer | Cross-model 模式 |
| 用户决定 accept/revise | 系统只返回 proposal |
| first claim → requires_literature_verification | 除非有已审查的相邻工作差异矩阵 |
| evolution log append-only | 不覆盖历史 |

### 3.7 运行模式

**模型白名单**：`deepseek-v4-flash`（OpenCode proxy）和 `big-pickle`（OpenCode proxy），禁止第三个模型。

| 模式 | Generator | Reviewer | 适用 |
|---|---|---|---|
| Conservative | `big-pickle` 低温 | `big-pickle`，标 self-review | 本地快速迭代 |
| Cross-model | `big-pickle` | `deepseek-v4-flash`（或反过来） | 正式开题、投稿前 |
| Human-led | 系统生成问题/矩阵 | 用户判断，模型只改写 | 证据不足或高风险 |

Cross-model 模式仅在这两个模型之间切换。

### 3.8 文献真实性边界

NoveltyReviewAdapter 不得：
- 生成新的文献引用；
- 验证文献是否存在；
- 修改 retrieval 或 verifier 的结果；
- 覆盖 system instruction。

文献真实性仍由 retrieval、verifier、RAG evidence 负责。

### 3.9 THIRD_PARTY_NOTICES 更新

在 `THIRD_PARTY_NOTICES.md` 中追加：

```markdown
## Paper-novelty-design
- Source: https://github.com/LaVineLeo/Paper-novelty-design
- Commit: 9434234aa44d303102a6619cbb91e7ab7a92869a
- License: MIT
- Usage: 方法论与 prompt 模板参考；数据结构重定义为 PaperAgent Pydantic schema
```

---

## 4. 验证

### 4.1 L0：Schema 与语义单测

| 测试项 | 方法 | 门槛 |
|---|---|---|
| NoveltyCandidate schema | 构造合法/非法 candidate | 非法被拒绝 |
| evidence ID 完整性 | Problem/Method/Insight 缺少 evidence_id | 拒绝 |
| Insight 纯性能陈述 | `insight = "F1 提高了 5%"` | status = needs_evidence |
| first claim 降级 | 无相邻工作矩阵的 first claim | status = requires_literature_verification |
| DifferentiationMatrix 五层 | 缺少任一层 | 拒绝 |
| FalsifiableProposition 三要素 | 缺 support/refute/required_test | 拒绝 |
| planned_not_verified | required_test 不可执行 | status = planned_not_verified，不是 verified |
| ReviewerPressurePoint evidence | 缺 evidence_ids | 拒绝，或填 "unknown" |
| NoveltyRevision append-only | 尝试覆盖已有版本 | 拒绝 |
| Evolution log 版本递增 | 新版本 version > parent | 通过 |
| Binding validator | evidence_id 不存在于 verified_papers | 标记 stale |

### 4.2 Novelty Gold Set（24 题）

| 类型 | 数量 | 正确系统行为 |
|---|---|---|
| 强候选 | 4 | 有边界的 P-M-I 与命题，status = accepted |
| 工程堆料 | 4 | mostly_engineering 或 needs_motivation |
| 跨域移植 | 4 | 说明直接复制失败点、适配和可迁移认识 |
| 相邻工作重叠 | 4 | too_close 或 needs_literature_verification |
| 证据薄弱 | 4 | needs_evidence，不生成强贡献 |
| 指标故事 | 4 | 性能只作为 evidence，不作为 Insight |

### 4.3 创新点 P0（硬门）

- [ ] Problem、Method、Insight 都绑定可解析 evidence ID；
- [ ] Insight 不是纯性能/模型名陈述；
- [ ] first claim 降级为 requires_literature_verification；
- [ ] 命题有 support、refute、required test；
- [ ] 不可执行 test 为 planned_not_verified；
- [ ] reviewer point 有 target 与 evidence 或 unknown；
- [ ] evolution log 不覆盖历史；
- [ ] 用户未 accept 的 proposal 不进入最终报告。

### 4.4 创新点 P1（质量门）

| 指标 | 门槛 |
|---|---|
| P-M-I 完整且逻辑连通 | ≥ 85% |
| 伪创新风险召回 | ≥ 80% |
| 无证据强 claim 误放行 | 0% |
| first claim 正确降级 | 100% |
| 可证伪命题可执行率 | ≥ 85% |
| 相邻工作重叠识别 | 比 control 高 ≥ 10 个百分点 |
| reviewer independence 标注 | 100% |

### 4.5 阶段门

- [ ] NoveltyReviewAdapter 五项测试（repetition/motivation/falsifiability/differentiation/story）全部实现；
- [ ] 无证据/first claim 不可通过 binding validator；
- [ ] evolution log append-only 且可追溯；
- [ ] 同模型生成与审查时标记 self-review；
- [ ] THIRD_PARTY_NOTICES 已更新；
- [ ] L0 全绿，gold set P0 全过。
