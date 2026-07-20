from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(relative: str, old: str, new: str) -> None:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"expected exactly one replacement in {relative}, found {count}: {old[:120]!r}"
        )
    path.write_text(text.replace(old, new), encoding="utf-8")


replace_once(
    "src/paperagent/scientific_readiness.py",
    """from dataclasses import dataclass


@dataclass(frozen=True)
class ScientificReadinessSignals:
    baseline_readiness_confirmed: bool = False
    evaluation_protocol_validated: bool = False
    comparison_readiness_confirmed: bool = False
    module_validation_confirmed: bool = False
    failure_policy_confirmed: bool = False
    explicit_evaluation_protocol_invalid: bool = False
""",
    """from typing import Literal

from paperagent.schemas.base import FrozenModel


class ScientificReadinessSignals(FrozenModel):
    basis: Literal["user_declaration"] = "user_declaration"
    independently_verified: Literal[False] = False
    baseline_readiness_confirmed: bool = False
    evaluation_protocol_validated: bool = False
    comparison_readiness_confirmed: bool = False
    module_validation_confirmed: bool = False
    failure_policy_confirmed: bool = False
    explicit_evaluation_protocol_invalid: bool = False

    @property
    def declared_ready(self) -> bool:
        return bool(
            self.baseline_readiness_confirmed
            and self.evaluation_protocol_validated
            and self.comparison_readiness_confirmed
            and self.module_validation_confirmed
            and self.failure_policy_confirmed
            and not self.explicit_evaluation_protocol_invalid
        )
""",
)

replace_once(
    "src/paperagent/state.py",
    """from paperagent.academic_methodology import MethodAuditReport
from paperagent.schemas import (
""",
    """from paperagent.academic_methodology import MethodAuditReport
from paperagent.scientific_readiness import ScientificReadinessSignals
from paperagent.schemas import (
""",
)
replace_once(
    "src/paperagent/state.py",
    """class PaperAgentState(TypedDict, total=False):
    run: RunContext
    request: ResearchRequest
    plan: ResearchPlan | None
""",
    """class PaperAgentState(TypedDict, total=False):
    run: RunContext
    request: ResearchRequest
    scientific_readiness: ScientificReadinessSignals | None
    plan: ResearchPlan | None
""",
)
replace_once(
    "src/paperagent/state.py",
    """class StatePatch(TypedDict, total=False):
    run: RunContext
    request: ResearchRequest
    plan: ResearchPlan | None
""",
    """class StatePatch(TypedDict, total=False):
    run: RunContext
    request: ResearchRequest
    scientific_readiness: ScientificReadinessSignals | None
    plan: ResearchPlan | None
""",
)

replace_once(
    "src/paperagent/graph.py",
    """from paperagent.nodes.quality_gate import quality_gate_node, quality_route
from paperagent.nodes.report import report_node
""",
    """from paperagent.nodes.quality_gate import quality_gate_node, quality_route
from paperagent.nodes.readiness_preflight import (
    readiness_preflight_node,
    readiness_preflight_route,
)
from paperagent.nodes.report import report_node
""",
)
replace_once(
    "src/paperagent/graph.py",
    """    builder.add_node("intake_node", intake_node)
    builder.add_node("planning_node", planning_node)
""",
    """    builder.add_node("intake_node", intake_node)
    builder.add_node("readiness_preflight_node", readiness_preflight_node)
    builder.add_node("planning_node", planning_node)
""",
)
replace_once(
    "src/paperagent/graph.py",
    """    builder.add_edge(START, "intake_node")
    builder.add_edge("intake_node", "planning_node")
    builder.add_conditional_edges(
        "planning_node",
""",
    """    builder.add_edge(START, "intake_node")
    builder.add_edge("intake_node", "readiness_preflight_node")
    builder.add_conditional_edges(
        "readiness_preflight_node",
        readiness_preflight_route,
        {
            "continue": "planning_node",
            "terminal": "report_node",
        },
    )
    builder.add_conditional_edges(
        "planning_node",
""",
)

replace_once(
    "src/paperagent/outcome.py",
    """    quality = state.get("quality")
    plan = state.get("plan")
    audit = state.get("methodology_audit")
    reason_codes = list(quality.reason_codes) if quality is not None else []
""",
    """    quality = state.get("quality")
    plan = state.get("plan")
    audit = state.get("methodology_audit")
    readiness = state.get("scientific_readiness")
    reason_codes = list(quality.reason_codes) if quality is not None else []
""",
)
replace_once(
    "src/paperagent/outcome.py",
    """    if plan is None or plan.status == "blocked":
        reason = (plan.block_reason if plan is not None else None) or "PLAN_NOT_AVAILABLE"
""",
    """    if readiness is not None and readiness.explicit_evaluation_protocol_invalid:
        reason = "Q_EXPLICIT_EVALUATION_PROTOCOL_INVALID"
        return _outcome(
            state,
            execution_status="succeeded",
            scientific_verdict="NO_GO",
            report_status="completed",
            reason_codes=reason_codes or [reason],
            blocker_code=reason,
            recommended_next_actions=[],
        )
    if (
        readiness is not None
        and readiness.declared_ready
        and quality is not None
        and quality.verdict == "pass"
    ):
        return _outcome(
            state,
            execution_status="succeeded",
            scientific_verdict="GO",
            report_status="completed",
            reason_codes=reason_codes,
            blocker_code=None,
            recommended_next_actions=[],
        )
    if plan is None or plan.status == "blocked":
        reason = (plan.block_reason if plan is not None else None) or "PLAN_NOT_AVAILABLE"
""",
)
replace_once(
    "src/paperagent/outcome.py",
    """    quality = state.get("quality")
    audit = state.get("methodology_audit")

    if evidence is not None and ledger is not None:
""",
    """    quality = state.get("quality")
    audit = state.get("methodology_audit")
    readiness = state.get("scientific_readiness")
    readiness_terminal = bool(
        readiness is not None
        and (readiness.explicit_evaluation_protocol_invalid or readiness.declared_ready)
    )

    if evidence is not None and ledger is not None:
""",
)
replace_once(
    "src/paperagent/outcome.py",
    """            outcome is not None and outcome.scientific_verdict == "NOT_EVALUATED",
            "Evaluated scientific outcomes require an evidence ledger.",
""",
    """            bool(
                outcome is not None
                and (
                    outcome.scientific_verdict == "NOT_EVALUATED"
                    or readiness_terminal
                )
            ),
            (
                "Evaluated scientific outcomes require an evidence ledger unless the "
                "decision is explicitly limited to a user-declaration readiness preflight."
            ),
""",
)
replace_once(
    "src/paperagent/outcome.py",
    """            audit is not None and audit.verdict is AuditVerdict.NO_GO,
            "Scientific NO_GO must come from the canonical methodology audit.",
""",
    """            bool(
                (audit is not None and audit.verdict is AuditVerdict.NO_GO)
                or (
                    readiness is not None
                    and readiness.explicit_evaluation_protocol_invalid
                )
            ),
            (
                "Scientific NO_GO must come from the canonical methodology audit or an "
                "explicitly declared invalid evaluation protocol."
            ),
""",
)
replace_once(
    "src/paperagent/outcome.py",
    """    quality_route_nodes = {"quality_gate_node", "evidence_quality_gate_node"}
""",
    """    quality_route_nodes = {
        "quality_gate_node",
        "evidence_quality_gate_node",
        "readiness_preflight_node",
    }
""",
)

replace_once(
    "src/paperagent/claw_academic_benchmark.py",
    """from paperagent.schemas.base import FrozenModel
""",
    """from paperagent.scientific_readiness import ScientificReadinessSignals
from paperagent.schemas.base import FrozenModel
""",
)
replace_once(
    "src/paperagent/claw_academic_benchmark.py",
    """    asked_user_to_design_method: bool = False
    baseline: BaselineTrace | None = None
""",
    """    asked_user_to_design_method: bool = False
    scientific_readiness: ScientificReadinessSignals | None = None
    baseline: BaselineTrace | None = None
""",
)
replace_once(
    "src/paperagent/claw_benchmark_adapter.py",
    """        asked_user_to_design_method=context.asked_user_to_design_method,
        baseline=_baseline_trace(state),
""",
    """        asked_user_to_design_method=context.asked_user_to_design_method,
        scientific_readiness=state.get("scientific_readiness"),
        baseline=_baseline_trace(state),
""",
)

replace_once(
    "tests/methodology/test_scientific_readiness.py",
    """    assert signals.failure_policy_confirmed is True
    assert signals.explicit_evaluation_protocol_invalid is False
""",
    """    assert signals.failure_policy_confirmed is True
    assert signals.explicit_evaluation_protocol_invalid is False
    assert signals.declared_ready is True
    assert signals.basis == "user_declaration"
    assert signals.independently_verified is False
""",
)

print("readiness preflight integration applied")
