# PaperAgent v0.1 State 与 Schema 合同

> Version: `v0.1`  
> Status: `CONTRACT FROZEN FOR TDD`

## 1. 目标

State 只负责跨节点共享的必要数据，不承载任意缓存、Prompt 文本、Provider 实例或旧版兼容字段。

```python
class PaperAgentState(TypedDict, total=False):
    run: RunContext
    request: ResearchRequest
    plan: ResearchPlan | None
    retrieval: RetrievalState
    evidence: EvidenceBundle
    synthesis: EvidenceSynthesis | None
    method: MethodProposal | None
    quality: QualityDecision | None
    report: FinalReport | None
    execution: ExecutionMeta
    trace: Annotated[list[TraceEvent], operator.add]
```

## 2. 全局规则

- 所有 Pydantic 模型使用 `extra="forbid"`；
- 所有 schema 带 `schema_version="0.1"`；
- ID、Clock 和随机性必须可注入；
- 节点只返回 `StatePatch`；
- list 字段仅在明确 reducer 下追加；
- Artifact 默认整体替换，不做隐式深合并；
- `None` 和“字段缺失”语义必须明确；
- State 中禁止保存 API key、原始 CoT 和未经脱敏的 Provider payload。

## 3. RunContext

```python
class RunContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["0.1"] = "0.1"
    engine_version: Literal["v0.1"] = "v0.1"
    run_id: str
    thread_id: str
    created_at: datetime
    model_profile: str
    network_policy: Literal["offline", "allow_search"]
    budgets: RunBudgets
```

```python
class RunBudgets(BaseModel):
    max_llm_calls: int = 6
    max_retrieval_rounds: int = 2
    max_method_repairs: int = 1
    max_queries_per_round: int = 5
    max_evidence_items: int = 30
```

测试：默认值、负数、超大值、序列化、frozen。

## 4. ResearchRequest

```python
class ResearchRequest(BaseModel):
    question: str
    domain_hint: str | None = None
    required_constraints: list[str] = []
    optional_preferences: list[str] = []
    user_material_refs: list[str] = []
    clarification_answer: str | None = None
```

语义校验：

- question trim 后长度 3—4000；
- required constraints 去重但保持顺序；
- material refs 只保存 locator，不读取内容；
- clarification answer 不自动拼进 question。

## 5. ResearchPlan

```python
class ResearchPlan(BaseModel):
    schema_version: Literal["0.1"] = "0.1"
    status: Literal["ready", "need_human", "blocked"]
    problem_statement: str
    scope: str
    research_questions: list[str]
    evidence_gaps: list[EvidenceGap]
    search_queries: list[SearchQuery]
    success_criteria: list[str]
    risks: list[str]
    clarification_question: str | None = None
    block_reason: str | None = None
```

不变量：

- ready 必须至少有一个 gap 和 query；
- need_human 必须有 clarification_question；
- blocked 必须有 block_reason；
- query 必须绑定已存在的 gap_id；
- query 数量不能超过预算。

## 6. RetrievalState

```python
class RetrievalState(BaseModel):
    round: int = 0
    max_rounds: int = 2
    prepared_queries: list[PreparedQuery] = []
    completed_query_ids: list[str] = []
    raw_candidates: list[SearchCandidate] = []
    tool_errors: list[ToolErrorRecord] = []
    budget_exhausted: bool = False
```

不变量：

- `0 <= round <= max_rounds`；
- completed query ID 不重复；
- prepared query 必须绑定 gap_id；
- budget exhausted 后不允许再次调用 Search Provider。

## 7. EvidenceBundle

```python
class EvidenceItem(BaseModel):
    evidence_id: str
    source_type: Literal["paper", "dataset", "repository", "web", "user_material"]
    title: str
    locator: str
    retrieved_at: datetime
    verification_status: Literal[
        "accepted",
        "rejected",
        "pending",
        "failed_verification",
    ]
    supports_gap_ids: list[str]
    summary: str
    content_hash: str
```

```python
class EvidenceBundle(BaseModel):
    items: list[EvidenceItem] = []
    accepted_ids: list[str] = []
    rejected_ids: list[str] = []
    pending_ids: list[str] = []
    failed_verification_ids: list[str] = []
    coverage_by_gap: dict[str, int] = {}
    conflicts: list[EvidenceConflict] = []
```

不变量：

- 每个 item 恰好属于一个 status ID 集；
- ID 全局唯一；
- coverage 只计算 accepted evidence；
- rejected/pending/failed 不得传给 synthesis LLM；
- content hash 对规范化内容稳定。

## 8. EvidenceSynthesis

```python
class GapAssessment(BaseModel):
    gap_id: str
    status: Literal["supported", "partial", "unsupported", "conflicted"]
    evidence_ids: list[str]
    summary: str
    limitations: list[str]
```

```python
class EvidenceSynthesis(BaseModel):
    schema_version: Literal["0.1"] = "0.1"
    gap_assessments: list[GapAssessment]
    verified_findings: list[Claim]
    conflicts: list[ConflictAssessment]
    feasibility: Literal["feasible", "partially_feasible", "not_feasible", "unknown"]
    limitations: list[str]
```

不变量：所有 evidence_ids 必须来自 accepted IDs。

## 9. MethodProposal

```python
class MethodProposal(BaseModel):
    schema_version: Literal["0.1"] = "0.1"
    status: Literal["proposed"] = "proposed"
    baseline: BaselineProposal
    modules: list[MethodModule]
    integration_contracts: list[IntegrationContract]
    problem_method_insight: str
    falsifiable_hypothesis: str
    minimum_key_experiment: ExperimentPlan
    ablations: list[AblationPlan]
    risks: list[str]
    stop_conditions: list[str]
    evidence_ids: list[str]
```

不变量：

- status 固定 proposed；
- 至少一个 baseline；
- hypothesis 必须可被实验否证；
- experiment 含 metric、baseline、success threshold；
- evidence IDs 仅来自 accepted IDs。

## 10. QualityDecision

```python
class QualityDecision(BaseModel):
    verdict: Literal[
        "pass",
        "repair_retrieval",
        "repair_method",
        "human_review",
        "blocked",
    ]
    reason_codes: list[str]
    repair_target: Literal["retrieval", "method"] | None = None
    missing_gap_ids: list[str] = []
    invalid_evidence_ids: list[str] = []
    human_question: str | None = None
```

原因码初始集合：

```text
Q_MISSING_REQUIRED_GAP
Q_INSUFFICIENT_COVERAGE
Q_UNKNOWN_EVIDENCE_ID
Q_UNSUPPORTED_CLAIM
Q_MISSING_BASELINE
Q_MISSING_HYPOTHESIS
Q_MISSING_EXPERIMENT
Q_MISSING_ABLATION
Q_MISSING_STOP_CONDITION
Q_REPAIR_BUDGET_EXHAUSTED
Q_RETRIEVAL_BUDGET_EXHAUSTED
Q_HUMAN_DECISION_REQUIRED
Q_LEGACY_ENTITY_LEAKAGE
```

## 11. FinalReport

```python
class FinalReport(BaseModel):
    schema_version: Literal["0.1"] = "0.1"
    status: Literal["completed", "blocked", "partial"]
    executive_summary: str
    verified_findings: list[ReportClaim]
    inferred_findings: list[ReportClaim]
    proposed_method: str | None
    experiment_plan: str | None
    limitations: list[str]
    next_actions: list[str]
    evidence_ids: list[str]
```

不变量：

- completed 不允许缺少 limitations；
- blocked 必须解释 block reason；
- report evidence IDs 是 accepted IDs 子集；
- report 不允许引入新的 source locator。

## 12. ExecutionMeta

```python
class ExecutionMeta(BaseModel):
    current_node: str | None = None
    status: Literal["running", "waiting_human", "completed", "blocked", "failed"]
    llm_call_count: int = 0
    repair_count: int = 0
    repair_target: Literal["retrieval", "method"] | None = None
    last_error: NodeErrorRecord | None = None
    human_action_required: HumanAction | None = None
```

## 13. TraceEvent

```python
class TraceEvent(BaseModel):
    schema_version: Literal["0.1"] = "0.1"
    event_id: str
    run_id: str
    span_id: str
    parent_span_id: str | None
    event_type: str
    node: str
    timestamp: datetime
    status: Literal["started", "completed", "failed", "decided"]
    input_hash: str | None = None
    output_hash: str | None = None
    prompt_version: str | None = None
    fixture_key: str | None = None
    model_name: str | None = None
    token_usage: TokenUsage | None = None
    duration_ms: int | None = None
    route: str | None = None
    error_code: str | None = None
```

## 14. Reducer 规则

| State field | Reducer |
|---|---|
| trace | append |
| evidence.items | explicit merge by evidence_id inside verification node |
| retrieval.tool_errors | explicit append in tool node |
| all artifacts | replace |
| execution | replace with validated copy |

禁止对整个 State 使用通用深合并。

## 15. Schema TDD 最低要求

每个 schema 至少包含：

- valid fixture；
- missing required field；
- unknown field；
- wrong enum；
- cross-field invariant；
- JSON round trip；
- deterministic serialization；
- mutation protection（适用时）。
