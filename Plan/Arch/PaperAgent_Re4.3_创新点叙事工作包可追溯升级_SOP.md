# PaperAgent Re4.3：创新点、叙事与工作包的可追溯升级 SOP

> **承接**：Re4.2 前端基线完成（React + Vite shell，8 e2e PASS，端到端 case 260s ACCEPT）。
>
> **本 SOP 覆盖 Day 3 全部任务**：schema 扩展（InnovationPoint / NarrativeRevision /
> WorkPackage）、binding validator、devil's advocate 证据级 critique、依赖 DAG、
> 叙事约束编辑 + 再生成、3 个历史 case 离线契约回归。
>
> **预计时长**：6–8 小时，分 7 个 Phase。
> **参考项目复用**：academic-research-skills (CC BY-NC) `claim_verification_protocol.md`
> / `integrity_review_protocol.md` (B 级)；Draftpaper_loop (NC) `stale_sync.py`
> artifact drift 思想 + `quality_gate.py` quality gate 思想 (B 级)。
> 不复制代码。

---

## 0. 当前事实基线（已验证）

### 现有 schema 与不足

| 节点 | 现有 state 字段 | 现有 schema（LLM 输出） | 不足 |
|---|---|---|---|
| `innovation_extractor` | `innovation_points: list[dict]` | `{description, baseline_used, stitched_modules[], stitching_plan, estimated_difficulty, evidence_ref}` | `evidence_ref` 只是一个论文标题字符串，无 candidate_id 绑定；无 `evidence_snippets`；无评分维度 |
| `narrative_builder` | `research_narrative: dict` | `{three_problems[], nick_model_name, narrative_summary, chapter_outline, abstract_draft}` | 无修订记录；每次覆写前一次叙事，无 diff；`narrative_revision_count` 只是一个 int |
| `work_package` | `work_packages: list[dict]` | `{title, research_question, baseline, improved_module_source, data_source, experiment_metrics, risk, estimated_workload}` | 缺 `objective/method/deliverable/effort/risk/prerequisite_ids`；依赖关系无结构化表达 |
| `devils_advocate` | `review_report: dict` | `{dimension_scores[], overall_verdict, fabrication_alerts[], risks_identified[]}` | critique 泛泛评价，不指向具体 evidence ID；不针对 innovation/narrative 溯源 |
| `low_bar_review` | `low_bar_review: dict` | `{status, issues[], n_packages_reviewed, n_packages_after_review}` | 只检查 title 字符串匹配，不做 candidate_id 绑定 |

### 现有 graph 控制流（关键路径）

```
work_package → innovation_extractor ──┐
                sota_matcher ──────────┤→ narrative_builder → low_bar_review
                                                              ↓
                                                    optimization_advisor → devils_advocate
                                                              ↓
                                            ACCEPT → human_gate → final
                                            MINOR_REVISION → narrative_builder (max 2)
                                            BLOCK → optimization_advisor (max 1)
```

`narrative_revision_count` 最大 2；`devils_advocate_block_count` 最大 1。

### 已知不一致

1. `narrative_builder` trace `state_keys` 写 `research_narratives`（复数），实际写 `research_narrative`（单数）
2. `NODE_FIELDS` 中 `innovation_extractor` 未列出 `dataset_candidates`（实际写入）
3. `NODE_FIELDS` 中 `devils_advocate` 未列出 `devils_advocate_block_count`（实际写入）

### 参考项目可用资产

| 源 | 文件 | 复用级别 | Day 3 用途 |
|---|---|---|---|
| academic-research-skills (CC BY-NC) | `claim_verification_protocol.md` | B | claim→source 绑定思想：每个 claim 必须有 `cited source + page/line + verdict`；映射到 innovation point 的 `candidate_ids + evidence_snippets` |
| academic-research-skills (CC BY-NC) | `integrity_review_protocol.md` | B | 2.5/4.5 两阶段 quality gate 思想：pre-review 30% 抽样 + final 100% 全检；映射到 binding validator 的 `sample_check` + `full_check` |
| Draftpaper_loop (NC) | `stale_sync.py` | B | artifact hash drift → mark stale 思想：上游 evidence 变化 → derived narrative/work_package 标记 `stale`；不自动静默改写 |
| Draftpaper_loop (NC) | `quality_gate.py` | B | quality gate 检查清单思想：required files + stage readiness + manuscript hygiene；映射到 binding validator 的检查项 |
| AutoResearchClaw (MIT) | `contracts.py` | B | Re4.1 已借鉴 StageContract；Day 3 补充 reads/writes 声明给新 schema |

> **许可证行动**：Day 3 不复制外部代码。所有 schema 和 validator 为 PaperAgent 独立编写，
> 仅借鉴 claim-source binding 和 stale/quality gate 思想。

---

## 1. 本轮目标

### 核心交付

1. **InnovationPoint schema**：`candidate_ids`、`evidence_snippets`、`novelty/feasibility/evidence_score`
2. **NarrativeRevision schema**：`revision_reason`、`parent_revision_id`、`diff`
3. **WorkPackage schema**：`objective`、`method`、`deliverable`、`effort`、`risk`、`prerequisite_ids`
4. **Binding validator**：候选论文、baseline、parallel、dataset、工作包之间逻辑一致
5. **Devil's advocate**：输出针对 evidence ID 的 critique
6. **依赖 DAG**：工作包间 `prerequisite_ids` 依赖关系
7. **叙事约束编辑**：用户编辑叙事约束后触发一轮再生成
8. **3 个历史 case 离线契约回归**

### 验收标准

- 每项创新点有至少一条可展开证据
- 无 orphan work package
- 叙事修订可查看前后差异
- 缺证据时标记 `needs_evidence`，不进入最终结论

### 不做

- 不修改 graph 拓扑（节点顺序不变）
- 不修改前端（React 前端展示在 Day 7 整合）
- 不实现完整论文编辑器
- 不实现 ACP / RAG（后续 Day）

> **强制规则**：每个 Phase 完成后必须跑 `pytest --collect-only` 确认零 error；
> 全部 Phase 完成后必须跑一个端到端 case 验证产物完整性和正确性（见 Phase 7）。

---

## 2. Phase 设计

### Phase 1：Pydantic Schema 扩展 — 1.5h

#### Fix 1.1: 新建 `schemas/evidence_schema.py`

**文件**：`apps/api/app/services/agents/graph/schemas/evidence_schema.py`（新建）

```python
"""Re4.3: Evidence-bound schemas for innovation, narrative, and work packages.

These Pydantic v2 models formalize the LLM output contracts that were
previously loose dicts. They enable:
  - Binding validators (Phase 2)
  - Devil's advocate evidence-level critique (Phase 4)
  - Stale marking on upstream changes (Phase 5)
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any


class EvidenceSnippet(BaseModel):
    """A snippet of evidence from a specific candidate paper."""
    candidate_id: str = Field(description="ID of the paper/repo this evidence comes from")
    snippet: str = Field(description="Verbatim or near-verbatim excerpt from the source")
    location: str | None = Field(default=None, description="Section/page/paragraph locator")
    verdict: str = Field(default="pending", description="pending | verified | rejected")


class InnovationPoint(BaseModel):
    """Innovation point with mandatory evidence binding.

    Re4.3 upgrade: candidate_ids + evidence_snippets + scores.
    Backward compatible: old fields (description, baseline_used, stitched_modules)
    remain; new fields are optional but validator requires >=1 candidate_id.
    """
    description: str
    baseline_used: str | None = None
    stitched_modules: list[str] = Field(default_factory=list)
    stitching_plan: str | None = None
    estimated_difficulty: str | None = None
    evidence_ref: str | None = None  # legacy: paper title string

    # Re4.3 new fields
    candidate_ids: list[str] = Field(
        default_factory=list,
        description="IDs of verified papers this innovation is derived from"
    )
    evidence_snippets: list[EvidenceSnippet] = Field(default_factory=list)
    novelty_score: float | None = Field(default=None, ge=0, le=10)
    feasibility_score: float | None = Field(default=None, ge=0, le=10)
    evidence_score: float | None = Field(default=None, ge=0, le=10)
    status: str = Field(default="pending", description="pending | verified | needs_evidence | rejected")

    def has_evidence(self) -> bool:
        return bool(self.candidate_ids) or bool(self.evidence_snippets)


class StitchingPlan(BaseModel):
    """Structured stitching plan for innovation points."""
    baseline_model: str | None = None
    module_b: str | None = None
    module_c: str | None = None
    stitching_steps: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)


class NarrativeRevision(BaseModel):
    """One revision of the research narrative.

    Re4.3: replaces silent overwrite with append-only revision history.
    """
    revision_id: str = Field(description="Unique ID, e.g. 'rev-0', 'rev-1'")
    parent_revision_id: str | None = Field(default=None, description="Previous revision ID, None for initial")
    three_problems: list[dict[str, Any]] = Field(default_factory=list)
    nick_model_name: str | None = None
    narrative_summary: str | None = None
    chapter_outline: dict[str, Any] | None = None
    abstract_draft: str | None = None
    revision_reason: str | None = Field(default=None, description="Why this revision was made")
    revision_source: str = Field(
        default="initial",
        description="initial | devils_advocate | user_edit | evidence_gap"
    )
    diff: dict[str, Any] | None = Field(
        default=None,
        description="Diff against parent: {added: [...], removed: [...], changed: [...]}"
    )


class WorkPackage(BaseModel):
    """Structured research work package with dependency tracking.

    Re4.3 upgrade: objective/method/deliverable/effort/risk/prerequisite_ids.
    Backward compatible: old fields (title, research_question, baseline, etc.) remain.
    """
    title: str
    research_question: str | None = None
    baseline: str | None = None
    improved_module_source: str | None = None
    data_source: str | None = None
    experiment_metrics: str | None = None
    risk: str | None = None
    estimated_workload: str | None = None

    # Re4.3 new fields
    objective: str | None = Field(default=None, description="What this package aims to achieve")
    method: str | None = Field(default=None, description="How to achieve the objective")
    deliverable: str | None = Field(default=None, description="Expected output/artifact")
    effort: str | None = Field(default=None, description="Low|Medium|High estimated effort")
    prerequisite_ids: list[str] = Field(
        default_factory=list,
        description="IDs of other work packages that must complete first"
    )
    bound_candidate_ids: list[str] = Field(
        default_factory=list,
        description="IDs of verified papers/repos/datasets this package depends on"
    )
    status: str = Field(default="pending", description="pending | ready | blocked | stale")

    @property
    def package_id(self) -> str:
        """Deterministic ID from title for prerequisite_ids referencing."""
        import re
        slug = re.sub(r"[^a-z0-9]+", "-", self.title.lower()).strip("-")
        return f"wp-{slug[:30]}"


class BindingValidationResult(BaseModel):
    """Result of binding validation across innovation/narrative/work_package."""
    valid: bool
    issues: list[dict[str, Any]] = Field(default_factory=list)
    orphan_packages: list[str] = Field(default_factory=list)
    needs_evidence_items: list[str] = Field(default_factory=list)
    stale_items: list[str] = Field(default_factory=list)
```

#### Fix 1.2: ResearchState 追加字段

**文件**：`apps/api/app/services/agents/graph/state.py`

追加：
```python
    # === Re4.3 new fields ===
    narrative_revisions: list[dict[str, Any]]  # append-only revision history
    binding_validation: dict[str, Any]        # last validation result
```

> 注意：`research_narrative`（单数 dict）保留——存储当前/latest revision；
> `narrative_revisions`（复数 list）为 append-only 历史。不删除旧字段。

#### Fix 1.3: StageContract 补充

**文件**：`apps/api/app/services/agents/graph/stage_contract.py`

在 `CONTRACTS` 中更新已有节点的 writes：

```python
"innovation_extractor": StageContract(
    node_name="innovation_extractor",
    reads=("topic", "topic_atoms", "baseline_candidates", "parallel_candidates"),
    writes=("innovation_points", "stitching_plan", "dataset_candidates", "trace_events"),
    fallback_source="_heuristic",
    error_code="E43_INNOVATION_FAIL",
    dod="Each innovation_point has >=1 candidate_id or marked needs_evidence",
    version="1.1",  # Re4.3: schema upgraded
),
"narrative_builder": StageContract(
    node_name="narrative_builder",
    reads=("topic", "innovation_points", "feasibility_report"),
    writes=("research_narrative", "narrative_revisions", "narrative_revision_count", "trace_events"),
    fallback_source="_heuristic",
    error_code="E43_NARRATIVE_FAIL",
    dod="Narrative revision appended to history with revision_id and parent_revision_id",
    version="1.1",
),
"work_package_brainstorm": StageContract(
    node_name="work_package",
    reads=("topic", "topic_atoms", "baseline_candidates", "parallel_candidates",
           "dataset_candidates", "repo_candidates", "user_constraints"),
    writes=("work_packages", "evidence_audit", "trace_events", "errors"),
    fallback_source="evidence_gap_repair",
    error_code="E43_WORK_PACKAGE_FAIL",
    dod="Each work_package has objective+method+deliverable or marked evidence_gap",
    version="1.1",
),
```

#### Fix 1.4: 测试

**文件**：`apps/api/tests/test_re43_schema.py`（新建）

```python
"""Re4.3: Evidence-bound schema tests."""
import pytest
from apps.api.app.services.agents.graph.schemas.evidence_schema import (
    InnovationPoint, EvidenceSnippet, NarrativeRevision, WorkPackage,
    BindingValidationResult, StitchingPlan,
)

class TestInnovationPoint:
    def test_has_evidence_with_candidate_ids(self):
        ip = InnovationPoint(description="test", candidate_ids=["p1"])
        assert ip.has_evidence()

    def test_has_evidence_without_candidates(self):
        ip = InnovationPoint(description="test")
        assert not ip.has_evidence()

    def test_needs_evidence_status(self):
        ip = InnovationPoint(description="test", candidate_ids=[])
        assert not ip.has_evidence()
        # Validator should mark this as needs_evidence

    def test_scores_in_range(self):
        ip = InnovationPoint(description="test", novelty_score=8.5,
                             feasibility_score=7.0, evidence_score=6.0)
        assert 0 <= ip.novelty_score <= 10

    def test_backward_compatible_with_legacy_fields(self):
        ip = InnovationPoint(description="test", baseline_used="YOLOv8",
                             stitched_modules=["attention"], evidence_ref="YOLOv8 paper")
        assert ip.baseline_used == "YOLOv8"
        assert ip.evidence_ref == "YOLOv8 paper"

class TestNarrativeRevision:
    def test_initial_revision(self):
        rev = NarrativeRevision(revision_id="rev-0", narrative_summary="initial")
        assert rev.parent_revision_id is None
        assert rev.revision_source == "initial"

    def test_devils_advocate_revision(self):
        rev = NarrativeRevision(
            revision_id="rev-1", parent_revision_id="rev-0",
            revision_reason="D2 evidence insufficient",
            revision_source="devils_advocate"
        )
        assert rev.parent_revision_id == "rev-0"

class TestWorkPackage:
    def test_package_id_deterministic(self):
        wp = WorkPackage(title="复现 YOLOv8 基线")
        assert wp.package_id.startswith("wp-")

    def test_prerequisite_ids(self):
        wp1 = WorkPackage(title="A")
        wp2 = WorkPackage(title="B", prerequisite_ids=[wp1.package_id])
        assert wp1.package_id in wp2.prerequisite_ids

    def test_backward_compatible(self):
        wp = WorkPackage(title="test", baseline="YOLOv8",
                         improved_module_source="attention", data_source="NEU-DET")
        assert wp.baseline == "YOLOv8"
```

---

### Phase 2：Binding Validator — 1.5h

#### Fix 2.1: 新建 `validators/binding_validator.py`

**文件**：`apps/api/app/services/agents/graph/validators/binding_validator.py`（新建）

**设计**（借鉴 academic-research-skills `claim_verification_protocol.md` E1-E3 思想
 + Draftpaper `quality_gate.py` required-files/stage-readiness 检查，B 级）：

```python
"""Re4.3: Binding validator — ensures logical consistency across evidence chain.

Checks:
  1. Innovation points reference real candidate IDs
  2. Work packages reference real baseline/parallel/dataset
  3. No orphan work packages (prerequisite_ids must resolve)
  4. Narrative references existing innovation points
  5. Stale marking: upstream evidence changed → derived items marked stale

Inspired by:
  - academic-research-skills claim_verification_protocol.md (claim→source binding)
  - Draftpaper stale_sync.py (artifact drift → stale marking)
"""
from __future__ import annotations

from typing import Any

from apps.api.app.services.agents.graph.schemas.evidence_schema import (
    InnovationPoint, WorkPackage, BindingValidationResult,
)


def _build_evidence_index(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Build an index of all evidence by ID/title for quick lookup."""
    index: dict[str, dict[str, Any]] = {}
    for key in ("verified_papers", "baseline_candidates", "parallel_candidates",
                "dataset_candidates", "repo_candidates"):
        for item in (state.get(key) or []):
            for id_key in ("paper_id", "doi", "arxiv_id", "full_name", "name", "title"):
                val = item.get(id_key)
                if val:
                    index[str(val).lower()] = item
    return index


def validate_innovations(
    innovations: list[dict[str, Any]],
    evidence_index: dict[str, dict[str, Any]],
) -> tuple[list[InnovationPoint], list[dict[str, Any]]]:
    """Validate that each innovation point references real evidence.

    Returns (validated_points, issues).
    Points without evidence are marked status='needs_evidence'.
    """
    issues: list[dict[str, Any]] = []
    validated: list[InnovationPoint] = []

    for i, raw in enumerate(innovations):
        ip = InnovationPoint(**{k: v for k, v in raw.items()
                                if k in InnovationPoint.model_fields})

        if not ip.candidate_ids:
            # Try to derive from legacy evidence_ref
            ref = (ip.evidence_ref or "").lower()
            if ref and ref in evidence_index:
                ip.candidate_ids = [ref]
            else:
                # Try baseline_used
                baseline = (ip.baseline_used or "").lower()
                if baseline and baseline in evidence_index:
                    ip.candidate_ids = [baseline]

        if not ip.has_evidence():
            ip.status = "needs_evidence"
            issues.append({
                "type": "innovation_no_evidence",
                "item_index": i,
                "description": ip.description[:100],
                "message": f"Innovation point #{i+1} has no candidate_id binding",
            })

        # Verify candidate_ids exist in evidence
        for cid in ip.candidate_ids:
            if cid.lower() not in evidence_index:
                ip.status = "needs_evidence"
                issues.append({
                    "type": "innovation_dangling_ref",
                    "item_index": i,
                    "candidate_id": cid,
                    "message": f"Innovation point #{i+1} references unknown candidate: {cid}",
                })

        validated.append(ip)

    return validated, issues


def validate_work_packages(
    packages: list[dict[str, Any]],
    evidence_index: dict[str, dict[str, Any]],
    package_ids: set[str] | None = None,
) -> tuple[list[WorkPackage], list[dict[str, Any]], list[str]]:
    """Validate work packages: evidence binding + prerequisite resolution.

    Returns (validated_packages, issues, orphan_ids).
    """
    issues: list[dict[str, Any]] = []
    validated: list[WorkPackage] = []
    orphan_ids: list[str] = []

    all_package_ids = set()
    for raw in packages:
        wp = WorkPackage(**{k: v for k, v in raw.items()
                            if k in WorkPackage.model_fields})
        all_package_ids.add(wp.package_id)

    for i, raw in enumerate(packages):
        wp = WorkPackage(**{k: v for k, v in raw.items()
                            if k in WorkPackage.model_fields})

        # Check evidence references
        for ref_key in ("baseline", "improved_module_source", "data_source"):
            ref_val = getattr(wp, ref_key, None)
            if ref_val and ref_val.lower() not in evidence_index:
                issues.append({
                    "type": "work_package_dangling_ref",
                    "item_index": i,
                    "field": ref_key,
                    "value": ref_val,
                    "message": f"Work package #{i+1} {ref_key} not in evidence: {ref_val}",
                })

        # Check prerequisite_ids resolve
        for prereq_id in wp.prerequisite_ids:
            if prereq_id not in all_package_ids:
                orphan_ids.append(prereq_id)
                issues.append({
                    "type": "work_package_orphan_prerequisite",
                    "item_index": i,
                    "prerequisite_id": prereq_id,
                    "message": f"Work package #{i+1} prerequisite not found: {prereq_id}",
                })

        validated.append(wp)

    return validated, issues, orphan_ids


def validate_narrative(
    narrative: dict[str, Any],
    innovations: list[InnovationPoint],
) -> list[dict[str, Any]]:
    """Validate that narrative references existing innovation points."""
    issues: list[dict[str, Any]] = []
    three_problems = narrative.get("three_problems") or []

    for i, problem in enumerate(three_problems):
        from_paper = (problem.get("from_paper") or "").lower()
        if from_paper:
            # Check if from_paper matches any innovation's candidate
            found = False
            for ip in innovations:
                if from_paper in [c.lower() for c in ip.candidate_ids]:
                    found = True
                    break
            if not found:
                issues.append({
                    "type": "narrative_dangling_ref",
                    "problem_index": i,
                    "from_paper": from_paper,
                    "message": f"Narrative problem #{i+1} references unknown paper: {from_paper}",
                })

    return issues


def mark_stale_derived_items(
    state: dict[str, Any],
    changed_evidence_ids: set[str],
) -> list[str]:
    """Mark derived items as stale when upstream evidence changes.

    Inspired by Draftpaper stale_sync.py artifact drift detection (B level).
    """
    stale_items: list[str] = []

    # If verified_papers changed, innovation_points and work_packages are stale
    innovations = state.get("innovation_points") or []
    for i, ip in enumerate(innovations):
        candidate_ids = ip.get("candidate_ids") or []
        if any(cid.lower() in changed_evidence_ids for cid in candidate_ids):
            ip["status"] = "stale"
            stale_items.append(f"innovation_{i}")

    packages = state.get("work_packages") or []
    for i, wp in enumerate(packages):
        bound_ids = wp.get("bound_candidate_ids") or []
        if any(cid.lower() in changed_evidence_ids for cid in bound_ids):
            wp["status"] = "stale"
            stale_items.append(f"work_package_{i}")

    return stale_items


def run_full_validation(state: dict[str, Any]) -> BindingValidationResult:
    """Run all binding validations and return aggregated result."""
    evidence_index = _build_evidence_index(state)

    innovations, inn_issues = validate_innovations(
        state.get("innovation_points") or [], evidence_index)
    packages, wp_issues, orphan_ids = validate_work_packages(
        state.get("work_packages") or [], evidence_index)
    nar_issues = validate_narrative(
        state.get("research_narratives") or {}, innovations)

    all_issues = inn_issues + wp_issues + nar_issues
    needs_evidence = [f"innovation_{i['item_index']}"
                       for i in inn_issues if i["type"] == "innovation_no_evidence"]

    return BindingValidationResult(
        valid=len(all_issues) == 0,
        issues=all_issues,
        orphan_packages=orphan_ids,
        needs_evidence_items=needs_evidence,
        stale_items=[],
    )
```

#### Fix 2.2: 接入 low_bar_review 节点

**文件**：`apps/api/app/services/agents/graph/nodes/content.py`

在 `low_bar_review_node` 中追加 binding validation：

```python
from apps.api.app.services.agents.graph.validators.binding_validator import run_full_validation

def low_bar_review_node(state: ResearchState) -> dict[str, Any]:
    # ... existing rule-based checks ...

    # Re4.3: binding validation
    binding_result = run_full_validation(state)
    if not binding_result.valid:
        issues.extend([f"binding: {i['message']}" for i in binding_result.issues])

    review = {"status": "pass" if not issues else "blocked",
              "issues": issues, "n_packages_reviewed": len(packages),
              "n_packages_after_review": len(kept),
              "binding_validation": binding_result.model_dump()}

    # ... return patch ...
```

#### Fix 2.3: 测试

**文件**：`apps/api/tests/test_re43_binding_validator.py`（新建）

```python
"""Re4.3: Binding validator tests."""

class TestBindingValidator:
    def test_innovation_with_valid_candidate_id(self):
        """Innovation referencing a real paper should pass."""
        # Setup evidence index with "yolov8"
        # Validate innovation with candidate_ids=["yolov8"]
        # Assert: no issues, status != needs_evidence

    def test_innovation_without_evidence_marked_needs_evidence(self):
        """Innovation with no candidate_ids should be marked needs_evidence."""

    def test_work_package_with_dangling_baseline(self):
        """Work package referencing non-existent baseline should produce issue."""

    def test_orphan_prerequisite_detected(self):
        """Work package with prerequisite_ids pointing to non-existent package."""

    def test_narrative_dangling_ref_detected(self):
        """Narrative referencing unknown paper should produce issue."""

    def test_stale_marking_on_evidence_change(self):
        """When evidence changes, derived items should be marked stale."""

    def test_full_validation_aggregates_all(self):
        """run_full_validation should aggregate innovation + work_package + narrative issues."""
```

---

### Phase 3：创新点 prompt 升级 — 1h

#### Fix 3.1: innovation_extractor prompt 升级

**文件**：`apps/api/app/services/agents/prompts/innovation_extractor.py`

在 USER_TEMPLATE 的输出 JSON 中追加 Re4.3 字段：

```python
# 在 innovation_points 的每个 item 中追加：
#   "candidate_ids": ["论文ID或标题"],    # 必填：此创新点引用了哪些已验证论文
#   "evidence_snippets": [{"candidate_id":"论文ID","snippet":"原文摘录","location":"Section 3.2"}],
#   "novelty_score": 0-10,
#   "feasibility_score": 0-10,
#   "evidence_score": 0-10
```

**关键约束**（prompt 中强调）：
```
重要约束：
1. 每个 innovation_point 的 candidate_ids 必须引用上面 Baseline 或 Parallel 论文列表中的论文
2. 如果无法确定具体论文，设 candidate_ids=[] 并省略 evidence_snippets
3. evidence_snippets 中的 snippet 必须是论文摘要或标题的近原文摘录，不可编造
4. novelty_score: 创新点的新颖程度 (0=纯复现, 10=全新方法)
5. feasibility_score: 可行性 (0=极难, 10=可直接复现)
6. evidence_score: 证据强度 (0=无证据, 10=有多篇论文+数据集支持)
```

同时在 `build()` 函数的 `slim()` 中追加 `paper_id`/`doi`/`arxiv_id` 字段，让 LLM 能引用：

```python
def slim(items):
    return [{"id": i.get("paper_id") or i.get("doi") or i.get("arxiv_id") or i.get("title", ""),
             "title": i.get("title", ""),
             "abstract": (i.get("abstract") or i.get("snippet") or "")[:300],
             "year": i.get("year", ""),
             "venue": i.get("venue", i.get("source", ""))}
            for i in items[:5]]
```

#### Fix 3.2: innovation_extractor node 追加 validator 调用

**文件**：`apps/api/app/services/agents/graph/nodes/innovation_extractor.py`

在 LLM 返回后、返回 state patch 前，调用 binding validator：

```python
from apps.api.app.services.agents.graph.validators.binding_validator import (
    validate_innovations, _build_evidence_index,
)

# ... after getting result_inn from LLM ...
evidence_index = _build_evidence_index(state)
validated_inns, inn_issues = validate_innovations(result_inn, evidence_index)
# Convert back to dicts for state
result_inn = [ip.model_dump() for ip in validated_inns]
```

#### Fix 3.3: heuristic fallback 也输出新字段

```python
def _heuristic(state):
    baselines = state.get("baseline_candidates") or []
    parallels = state.get("parallel_candidates") or []
    b_title = (baselines[0].get("title", "") if baselines else "未知baseline")
    b_id = (baselines[0].get("paper_id") or baselines[0].get("doi") or b_title) if baselines else ""
    p_title = (parallels[0].get("title", "") if parallels else "未知parallel")
    p_id = (parallels[0].get("paper_id") or parallels[0].get("doi") or p_title) if parallels else ""
    return {
        "innovation_points": [{
            "description": f"在{b_title}基础上借鉴{p_title}的模块",
            "baseline_used": b_title,
            "stitched_modules": [p_title],
            "stitching_plan": "待LLM生成",
            "estimated_difficulty": "中",
            "evidence_ref": b_title,
            "candidate_ids": [b_id] if b_id else [],
            "evidence_snippets": [],
            "novelty_score": 5.0,
            "feasibility_score": 5.0,
            "evidence_score": 5.0 if b_id else 0.0,
            "status": "pending" if b_id else "needs_evidence",
        }],
        # ... stitching_plan unchanged ...
    }
```

---

### Phase 4：叙事修订历史 + Devil's Advocate 证据级 Critique — 1.5h

#### Fix 4.1: narrative_builder 追加修订历史

**文件**：`apps/api/app/services/agents/graph/nodes/narrative_builder.py`

```python
def narrative_builder_node(state: ResearchState) -> dict[str, Any]:
    # ... existing LLM call ...

    current_count = state.get("narrative_revision_count", 0)
    revision_id = f"rev-{current_count}"
    parent_id = f"rev-{current_count - 1}" if current_count > 0 else None

    # Build revision record
    revision = {
        "revision_id": revision_id,
        "parent_revision_id": parent_id,
        **result,
        "revision_reason": state.get("_narrative_revision_reason") or "initial",
        "revision_source": state.get("_narrative_revision_source") or "initial",
    }

    # Compute diff against previous (if exists)
    revisions = state.get("narrative_revisions") or []
    if revisions:
        prev = revisions[-1]
        revision["diff"] = _compute_diff(prev, result)
    else:
        revision["diff"] = None

    revisions_out = list(revisions) + [revision]

    trace = _emit(...)
    return {"research_narrative": result,
            "narrative_revisions": revisions_out,
            "narrative_revision_count": current_count + 1,
            "trace_events": [trace]}


def _compute_diff(prev: dict, curr: dict) -> dict[str, Any]:
    """Compute simple diff between two narrative revisions."""
    added, removed, changed = [], [], []
    for key in ("nick_model_name", "narrative_summary", "abstract_draft"):
        old_val = prev.get(key, "")
        new_val = curr.get(key, "")
        if old_val != new_val:
            changed.append({"field": key, "old": old_val[:100], "new": new_val[:100]})

    old_problems = prev.get("three_problems") or []
    new_problems = curr.get("three_problems") or []
    if len(new_problems) > len(old_problems):
        added.append({"field": "three_problems", "count": len(new_problems) - len(old_problems)})
    elif len(new_problems) < len(old_problems):
        removed.append({"field": "three_problems", "count": len(old_problems) - len(new_problems)})

    return {"added": added, "removed": removed, "changed": changed}
```

#### Fix 4.2: devils_advocate prompt 升级

**文件**：`apps/api/app/services/agents/prompts/devils_advocate_graph.py`

在 USER_TEMPLATE 中追加 evidence-level critique 要求：

```python
# 在输出 JSON 中追加：
#   "evidence_critiques": [
#     {
#       "target_type": "innovation" | "narrative" | "work_package",
#       "target_id": "innovation_0" | "wp-xxx" | "rev-0",
#       "issue": "具体问题描述",
#       "evidence_id": "引用的论文ID",
#       "severity": "critical" | "major" | "minor",
#       "suggested_fix": "具体修改建议"
#     }
#   ]
```

**关键约束**（prompt 中强调）：
```
重要约束：
1. 每个 evidence_critique 必须指向具体的 target_id（innovation_序号 / wp-包名 / rev-版本号）
2. 不允许泛泛评价（如"创新点不足"），必须指出具体哪条创新点有什么问题
3. evidence_id 必须是实际存在的论文 ID
4. suggested_fix 必须是可操作的修改建议
```

#### Fix 4.3: devils_advocate node 传递 critique 到叙事修订

**文件**：`apps/api/app/services/agents/graph/nodes/devils_advocate_node.py`

当 verdict 为 MINOR_REVISION 时，将 evidence_critiques 传递给 narrative_builder：

```python
# 在返回的 patch 中追加（当 MINOR_REVISION 时）
if result.get("overall_verdict") == "MINOR_REVISION":
    critiques = result.get("evidence_critiques") or []
    # 存入 state 供 narrative_builder 读取
    return {"review_report": result,
            "devils_advocate_block_count": block_count,
            "_narrative_revision_reason": "; ".join(
                c.get("issue", "") for c in critiques if c.get("target_type") == "narrative"
            ) or "MINOR_REVISION",
            "_narrative_revision_source": "devils_advocate",
            "trace_events": [trace]}
```

#### Fix 4.4: 测试

**文件**：`apps/api/tests/test_re43_narrative_revision.py`（新建）

```python
"""Re4.3: Narrative revision history tests."""

class TestNarrativeRevision:
    def test_initial_revision_has_no_parent(self):
        """First revision should have parent_revision_id=None."""

    def test_second_revision_links_to_first(self):
        """Second revision should have parent_revision_id=rev-0."""

    def test_diff_computed_on_revision(self):
        """When narrative changes, diff should show what changed."""

    def test_revision_count_increments(self):
        """narrative_revision_count should increment per revision."""

    def test_devils_advocate_critique_passed_to_narrative(self):
        """When MINOR_REVISION, critique reason should reach narrative_builder."""
```

---

### Phase 5：工作包 schema 升级 + 依赖 DAG — 1h

#### Fix 5.1: work_package prompt 升级

**文件**：`apps/api/app/services/agents/prompts/re11_work_package.py`

在 USER_TEMPLATE 的 work_packages 输出中追加：

```python
# 每个 work_package 追加：
#   "objective": "此工作包要达到什么目标"
#   "method": "用什么方法实现"
#   "deliverable": "预期产出（代码/模型/实验报告）"
#   "effort": "Low|Medium|High"
#   "prerequisite_ids": ["wp-其他工作包的title-slug"],  # 依赖的其他工作包
#   "bound_candidate_ids": ["论文ID"],  # 绑定的已验证论文
```

#### Fix 5.2: 依赖 DAG 构建

**文件**：`apps/api/app/services/agents/graph/validators/dependency_dag.py`（新建）

```python
"""Re4.3: Dependency DAG for work packages.

Builds a directed acyclic graph from prerequisite_ids and validates:
  1. No cycles
  2. All prerequisites exist
  3. Topological order is valid
"""
from __future__ import annotations

from typing import Any
from collections import defaultdict, deque


def build_dag(packages: list[dict[str, Any]]) -> dict[str, Any]:
    """Build dependency DAG from work packages.

    Returns:
      {
        "nodes": [{"id": "wp-xxx", "title": "...", "effort": "Medium"}],
        "edges": [{"from": "wp-a", "to": "wp-b"}],  # a must complete before b
        "topo_order": ["wp-a", "wp-b", "wp-c"],
        "has_cycle": False,
        "milestones": [{"id": "ms-1", "packages": ["wp-a", "wp-b"], "label": "Phase 1"}],
      }
    """
    # Build adjacency list
    id_to_pkg = {}
    for pkg in packages:
        # Use WorkPackage.package_id logic
        import re
        title = pkg.get("title", "")
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        pkg_id = f"wp-{slug[:30]}"
        pkg["package_id"] = pkg_id
        id_to_pkg[pkg_id] = pkg

    edges: list[dict[str, str]] = []
    adj: dict[str, list[str]] = defaultdict(list)
    in_degree: dict[str, int] = {pid: 0 for pid in id_to_pkg}

    for pkg_id, pkg in id_to_pkg.items():
        for prereq in (pkg.get("prerequisite_ids") or []):
            if prereq in id_to_pkg:
                edges.append({"from": prereq, "to": pkg_id})
                adj[prereq].append(pkg_id)
                in_degree[pkg_id] += 1

    # Topological sort (Kahn's algorithm)
    queue = deque([pid for pid, deg in in_degree.items() if deg == 0])
    topo_order: list[str] = []
    while queue:
        node = queue.popleft()
        topo_order.append(node)
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    has_cycle = len(topo_order) != len(id_to_pkg)

    # Build milestones (group by topological layer)
    milestones = _build_milestones(id_to_pkg, adj, in_degree)

    return {
        "nodes": [{"id": pid, "title": pkg.get("title", ""),
                    "effort": pkg.get("effort", "Unknown")}
                   for pid, pkg in id_to_pkg.items()],
        "edges": edges,
        "topo_order": topo_order,
        "has_cycle": has_cycle,
        "milestones": milestones,
    }


def _build_milestones(
    id_to_pkg: dict[str, dict],
    adj: dict[str, list[str]],
    in_degree: dict[str, int],
) -> list[dict[str, Any]]:
    """Group packages into milestone layers (parallel-executable sets)."""
    if not id_to_pkg:
        return []

    milestones: list[dict[str, Any]] = []
    remaining = set(id_to_pkg.keys())
    layer = 0

    while remaining:
        # Find all packages with no unmet dependencies
        ready = [pid for pid in remaining
                 if all(dep not in remaining for dep in (id_to_pkg[pid].get("prerequisite_ids") or [])
                        if dep in id_to_pkg)]
        if not ready:
            # Cycle detected — put remaining in last milestone
            ready = list(remaining)

        milestones.append({
            "id": f"ms-{layer + 1}",
            "packages": sorted(ready),
            "label": f"阶段 {layer + 1}",
        })
        remaining -= set(ready)
        layer += 1

    return milestones
```

#### Fix 5.3: low_bar_review 追加 DAG 检查

在 `low_bar_review_node` 中追加 DAG 构建：

```python
from apps.api.app.services.agents.graph.validators.dependency_dag import build_dag

# ... in low_bar_review_node ...
dag = build_dag(packages)
if dag["has_cycle"]:
    issues.append("work package dependency cycle detected")
```

#### Fix 5.4: API 端点新增 DAG 返回

**文件**：`apps/api/app/api/v1/research.py`

追加端点：

```python
@router.get("/{case_id}/work-packages")
def get_work_packages(case_id: str) -> dict[str, Any]:
    """Get work packages with dependency DAG."""
    _validate_case_id(case_id)
    state = _load_state(case_id)
    packages = state.get("work_packages") or []
    from apps.api.app.services.agents.graph.validators.dependency_dag import build_dag
    dag = build_dag(packages)
    return {"case_id": case_id, "work_packages": packages, "dag": dag, "n": len(packages)}
```

#### Fix 5.5: 测试

**文件**：`apps/api/tests/test_re43_dependency_dag.py`（新建）

```python
"""Re4.3: Dependency DAG tests."""

class TestDependencyDAG:
    def test_no_dependencies_single_layer(self):
        """Packages without prerequisites → single milestone."""

    def test_linear_dependency(self):
        """A→B→C chain → 3 milestones."""

    def test_parallel_packages_same_layer(self):
        """Two independent packages → same milestone."""

    def test_cycle_detected(self):
        """Circular dependency → has_cycle=True."""

    def test_milestone_label_generation(self):
        """Milestones labeled 阶段 1, 阶段 2, ..."""
```

---

### Phase 6：历史 case 离线契约回归 — 1h

#### Fix 6.1: 选择 3 个历史 case

从 `tmp_re13_eval/` 中选择 3 个不同领域的已完成 case：

```bash
# 列出已完成 case
ls tmp_re13_eval/ | head -20
```

选择标准：
- 1 个工科（如 YOLO/钢材缺陷）
- 1 个医学/合规（如 医学问答可信度）
- 1 个其他领域（如 建筑工程/能源）

#### Fix 6.2: 契约回归测试

**文件**：`apps/api/tests/test_re43_contract_regression.py`（新建）

```python
"""Re4.3: Offline contract regression for 3 historical cases.

Validates that schema upgrades don't break existing case data:
  1. InnovationPoint schema accepts old innovation_points dicts
  2. WorkPackage schema accepts old work_packages dicts
  3. Binding validator runs without crash on old data
  4. DAG builder runs without crash on old data
  5. All old fields are preserved (backward compatible)
"""
import json
from pathlib import Path
import pytest

EVAL_DIR = Path("tmp_re13_eval")

# 3 historical cases (will be configured based on actual available cases)
HISTORICAL_CASES = [
    "re41-verify-001",   # YOLO (Re4.1 verified)
    "04d365f121bc",       # Re4.2 verified case
    # + 1 more from existing cases
]


class TestContractRegression:
    @pytest.mark.parametrize("case_id", HISTORICAL_CASES)
    def test_state_json_loads(self, case_id):
        """state.json must be loadable."""
        path = EVAL_DIR / case_id / "state.json"
        if not path.exists():
            pytest.skip(f"Case {case_id} not found")
        state = json.loads(path.read_text(encoding="utf-8"))
        assert "topic" in state

    @pytest.mark.parametrize("case_id", HISTORICAL_CASES)
    def test_innovation_points_backward_compatible(self, case_id):
        """Old innovation_points dicts must be accepted by InnovationPoint schema."""
        path = EVAL_DIR / case_id / "state.json"
        if not path.exists():
            pytest.skip(f"Case {case_id} not found")
        state = json.loads(path.read_text(encoding="utf-8"))
        innovations = state.get("innovation_points") or []
        for raw in innovations:
            # Should not raise
            ip = InnovationPoint(**{k: v for k, v in raw.items()
                                    if k in InnovationPoint.model_fields})
            assert ip.description  # at least description must exist

    @pytest.mark.parametrize("case_id", HISTORICAL_CASES)
    def test_work_packages_backward_compatible(self, case_id):
        """Old work_packages dicts must be accepted by WorkPackage schema."""
        path = EVAL_DIR / case_id / "state.json"
        if not path.exists():
            pytest.skip(f"Case {case_id} not found")
        state = json.loads(path.read_text(encoding="utf-8"))
        packages = state.get("work_packages") or []
        for raw in packages:
            wp = WorkPackage(**{k: v for k, v in raw.items()
                                if k in WorkPackage.model_fields})
            assert wp.title

    @pytest.mark.parametrize("case_id", HISTORICAL_CASES)
    def test_binding_validator_runs_on_old_data(self, case_id):
        """Binding validator must not crash on old case data."""
        path = EVAL_DIR / case_id / "state.json"
        if not path.exists():
            pytest.skip(f"Case {case_id} not found")
        state = json.loads(path.read_text(encoding="utf-8"))
        result = run_full_validation(state)
        # May have issues (old data lacks candidate_ids) but must not crash
        assert isinstance(result, BindingValidationResult)

    @pytest.mark.parametrize("case_id", HISTORICAL_CASES)
    def test_dag_builder_runs_on_old_data(self, case_id):
        """DAG builder must not crash on old case data."""
        path = EVAL_DIR / case_id / "state.json"
        if not path.exists():
            pytest.skip(f"Case {case_id} not found")
        state = json.loads(path.read_text(encoding="utf-8"))
        packages = state.get("work_packages") or []
        dag = build_dag(packages)
        assert "nodes" in dag
        assert "edges" in dag
```

---

### Phase 7：验收与端到端验证 — 1h

#### Step 1: 单元测试

```bash
cd G:\PaperAgent
.venv\Scripts\python.exe -m pytest apps/api/tests/test_re43_schema.py -v
.venv\Scripts\python.exe -m pytest apps/api/tests/test_re43_binding_validator.py -v
.venv\Scripts\python.exe -m pytest apps/api/tests/test_re43_narrative_revision.py -v
.venv\Scripts\python.exe -m pytest apps/api/tests/test_re43_dependency_dag.py -v
# 预期：全部 PASS
```

#### Step 2: 契约回归

```bash
.venv\Scripts\python.exe -m pytest apps/api/tests/test_re43_contract_regression.py -v
# 预期：全部 PASS 或 SKIP（case 不存在时）
```

#### Step 3: pytest 收集不退化

```bash
.venv\Scripts\python.exe -m pytest --collect-only -q 2>&1 | Select-String "error|collected"
# 预期：0 errors，collected 数 ≥ 426（新增 Re4.3 测试）
```

#### Step 4: ruff 无新增

```bash
.venv\Scripts\python.exe -m ruff check apps/api/app --statistics
# 预期：≤ 18 errors（无新增）
```

#### Step 5: 端到端 Case 验证（强制）

> **规则**：全部 Phase 完成后必须跑一个端到端 case，证明 schema 升级未破坏完整流程。

**前置条件**：后端 18181 运行中，`.env` 有效 `DEEPSEEK_API_KEY`。

```bash
# 1. 提交一个 case
curl -X POST http://127.0.0.1:18181/api/v1/research/ `
  -H "Content-Type: application/json" `
  -d '{"topic": "基于YOLO的钢材表面缺陷检测", "case_id": "re43-verify-001"}'

# 2. 等待完成（~3-4 分钟）

# 3. 验证产物
curl http://127.0.0.1:18181/api/v1/research/re43-verify-001/state > state_re43.json
curl http://127.0.0.1:18181/api/v1/research/re43-verify-001/work-packages > wp_re43.json
```

**产物完整性检查清单**：

| 检查项 | 通过标准 |
|---|---|
| state.json | 包含 `innovation_points`、`work_packages`、`research_narrative`、`narrative_revisions`、`binding_validation` |
| innovation_points | 每个 item 包含 `candidate_ids`（可为空但字段存在）；有 `status` 字段 |
| work_packages | 每个 item 包含 `objective`/`method`/`deliverable`/`effort`/`prerequisite_ids`/`bound_candidate_ids`（可为空但字段存在） |
| narrative_revisions | ≥ 1 个 revision；每个有 `revision_id`、`parent_revision_id`、`revision_source` |
| work-packages API | 返回包含 `dag` 字段，有 `nodes`/`edges`/`topo_order`/`milestones` |
| binding_validation | `low_bar_review` 中包含 `binding_validation` 字段 |
| trace.json | innovation_extractor 和 narrative_builder trace 事件正常 |

**数据正确性自检清单**：

| 维度 | 验证方法 | 通过标准 |
|---|---|---|
| 创新点证据绑定 | 检查 innovation_points 中 `candidate_ids` 非空的比例 | ≥ 1 个有 candidate_ids（LLM 成功时） |
| 需证据标记 | `needs_evidence` 状态的 innovation 不进入最终推荐 | final_recommendation 中不引用 needs_evidence 项 |
| 无孤儿工作包 | DAG 中 `topo_order` 包含所有 packages | 无遗漏 |
| 叙事修订历史 | narrative_revisions 长度 = narrative_revision_count | 一致 |
| 修订 diff | 第 2+ 轮修订有 diff 字段 | diff 非空（有 changed/added/removed） |
| 向后兼容 | 旧 case 的 state.json 可被新 schema 加载 | 契约回归测试全部 PASS |

> **自我检验**：验收者必须对照上述清单逐项检查实际产物，
> 确认每项通过后再标记 Phase 7 完成。任何一项不通过则回到对应 Phase 修复。

---

## 3. 执行顺序与依赖

```
Phase 1 (Schema 扩展) ─── 无依赖，立即可做
    │
    ├── Phase 2 (Binding Validator) ─── 依赖 Phase 1 的 schema
    │
    ├── Phase 3 (Innovation prompt 升级) ─── 依赖 Phase 1 schema + Phase 2 validator
    │
    ├── Phase 4 (叙事修订 + DA critique) ─── 依赖 Phase 1 NarrativeRevision schema
    │       ├── Fix 4.1 (narrative_builder) ─── 依赖 Phase 1
    │       ├── Fix 4.2 (DA prompt) ─── 无依赖
    │       └── Fix 4.3 (DA node) ─── 依赖 4.1 + 4.2
    │
    ├── Phase 5 (WorkPackage + DAG) ─── 依赖 Phase 1 WorkPackage schema
    │       ├── Fix 5.1 (prompt) ─── 无依赖
    │       ├── Fix 5.2 (DAG builder) ─── 依赖 Phase 1
    │       └── Fix 5.3 (low_bar_review) ─── 依赖 5.2 + Phase 2
    │
    ├── Phase 6 (历史 case 回归) ─── 依赖 Phase 1-5 全部完成
    │
    └── Phase 7 (验收 + 端到端) ─── 依赖全部完成

可并行：
- Phase 3 (innovation prompt) 和 Phase 4 (narrative + DA) 可同时开发
- Phase 5 (work_package + DAG) 可与 Phase 4 并行
- Phase 6 测试用例可在 Phase 2-5 开发时同步编写
```

---

## 4. 风险与预案

| 风险 | 触发信号 | 预案 |
|---|---|---|
| LLM 不输出新 schema 字段 | innovation_points 中 candidate_ids 为空 | prompt 中强制约束 + heuristic fallback 补充默认值 + validator 标记 needs_evidence |
| Pydantic schema 向后不兼容 | 旧 case state.json 加载失败 | 所有新字段 `default=None` / `default_factory=list`；只接受已知字段 |
| binding validator 过于严格 | 所有旧 case 都 BLOCK | 区分 `error`（必须修）和 `warning`（标记但不阻塞）；needs_evidence 不阻塞流程 |
| DAG 检测到循环 | has_cycle=True | 不阻塞流程，在 issues 中记录；前端展示循环警告 |
| devils_advocate critique 不指向 evidence ID | evidence_critiques 为空或泛泛 | prompt 约束 + 空 critique 时 fallback 到维度评分 |
| 修订历史膨胀 | narrative_revisions 过大 | 限制最大 5 个 revision（实际 max 2+1 initial = 3） |
| historical case 数据格式不一致 | 契约回归 test 失败 | 跳过缺失字段的验证；只验证 schema 兼容性，不验证数据质量 |

---

## 5. 完成标准

- [ ] `evidence_schema.py` 定义 InnovationPoint / NarrativeRevision / WorkPackage / BindingValidationResult
- [ ] InnovationPoint 包含 `candidate_ids`、`evidence_snippets`、`novelty/feasibility/evidence_score`、`status`
- [ ] NarrativeRevision 包含 `revision_id`、`parent_revision_id`、`revision_reason`、`diff`
- [ ] WorkPackage 包含 `objective`、`method`、`deliverable`、`effort`、`prerequisite_ids`、`bound_candidate_ids`
- [ ] binding_validator 验证 innovation → candidate_id、work_package → evidence、narrative → innovation
- [ ] validator 将无证据的创新点标记为 `needs_evidence`
- [ ] stale marking：上游 evidence 变化 → derived items 标记 `stale`
- [ ] devils_advocate 输出 `evidence_critiques` 指向具体 target_id
- [ ] MINOR_REVISION 时 critique reason 传递给 narrative_builder
- [ ] narrative_builder 追加 revision 到 `narrative_revisions` 历史
- [ ] 修订 diff 记录 added/removed/changed
- [ ] DAG builder 输出 nodes/edges/topo_order/milestones，检测循环
- [ ] low_bar_review 包含 binding_validation 结果
- [ ] API `/work-packages` 返回 DAG
- [ ] 3 个历史 case 契约回归全部 PASS
- [ ] `pytest --collect-only` 零 error
- [ ] `ruff check apps/api/app` ≤ 18 errors（无新增）
- [ ] **端到端 case 跑通**：新 schema 字段在产物中存在
- [ ] **数据正确性自检**：创新点有证据绑定、无孤儿工作包、修订可追溯

---

## 6. 提交清单

| 文件 | 操作 |
|---|---|
| `apps/api/app/services/agents/graph/schemas/__init__.py` | 新建 |
| `apps/api/app/services/agents/graph/schemas/evidence_schema.py` | 新建 |
| `apps/api/app/services/agents/graph/validators/__init__.py` | 新建 |
| `apps/api/app/services/agents/graph/validators/binding_validator.py` | 新建 |
| `apps/api/app/services/agents/graph/validators/dependency_dag.py` | 新建 |
| `apps/api/app/services/agents/graph/state.py` | 追加 `narrative_revisions`、`binding_validation` |
| `apps/api/app/services/agents/graph/stage_contract.py` | 更新 3 个节点 contract |
| `apps/api/app/services/agents/graph/nodes/innovation_extractor.py` | 修改：validator 调用 + heuristic 补字段 |
| `apps/api/app/services/agents/graph/nodes/narrative_builder.py` | 修改：revision history + diff |
| `apps/api/app/services/agents/graph/nodes/devils_advocate_node.py` | 修改：evidence_critiques 传递 |
| `apps/api/app/services/agents/graph/nodes/content.py` | 修改：low_bar_review 追加 binding + DAG |
| `apps/api/app/services/agents/prompts/innovation_extractor.py` | 修改：prompt 追加新字段约束 |
| `apps/api/app/services/agents/prompts/devils_advocate_graph.py` | 修改：prompt 追加 evidence_critiques |
| `apps/api/app/services/agents/prompts/re11_work_package.py` | 修改：prompt 追加新字段 |
| `apps/api/app/api/v1/research.py` | 追加 `/work-packages` 端点 |
| `apps/api/tests/test_re43_schema.py` | 新建 |
| `apps/api/tests/test_re43_binding_validator.py` | 新建 |
| `apps/api/tests/test_re43_narrative_revision.py` | 新建 |
| `apps/api/tests/test_re43_dependency_dag.py` | 新建 |
| `apps/api/tests/test_re43_contract_regression.py` | 新建 |
| `CHANGELOG.md` | 追加 Re4.3 条目 |

---

## 7. CHANGELOG 预备

```markdown
## [0.4.0-dev] - 2026-07-10 (Re4.3)

### Added
- `schemas/evidence_schema.py`: Pydantic v2 models for InnovationPoint (candidate_ids, evidence_snippets, scores),
  NarrativeRevision (revision_id, parent_revision_id, diff), WorkPackage (objective, method, deliverable, prerequisite_ids)
- `validators/binding_validator.py`: 证据链一致性验证器
  - innovation → candidate_id 绑定检查
  - work_package → evidence 绑定检查
  - narrative → innovation 引用检查
  - stale marking（上游 evidence 变化 → derived items 标记 stale）
- `validators/dependency_dag.py`: 工作包依赖 DAG 构建
  - 拓扑排序 + 循环检测 + 里程碑分层
- API endpoint `GET /{case_id}/work-packages`: 返回工作包 + DAG
- 5 个新测试文件：schema、binding validator、narrative revision、DAG、契约回归

### Changed
- `innovation_extractor.py`: prompt 追加 candidate_ids/evidence_snippets/scores 约束；validator 调用
- `narrative_builder.py`: 追加 revision history + diff 计算
- `devils_advocate_node.py`: prompt 追加 evidence_critiques；MINOR_REVISION 时传递 critique
- `content.py` (low_bar_review): 追加 binding validation + DAG 构建
- `stage_contract.py`: 3 个节点 contract 版本升级到 1.1
- `state.py`: 追加 narrative_revisions, binding_validation 字段
- `re11_work_package.py` prompt: 追加 objective/method/deliverable/effort/prerequisite_ids

### Verified
- 端到端 case 验证：新 schema 字段在 state/trace/work-packages 产物中存在
- 3 个历史 case 契约回归全部 PASS（向后兼容）
- 创新点有证据绑定、无孤儿工作包、叙事修订可追溯
```
