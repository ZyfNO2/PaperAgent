from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from paperagent.errors import NodeError
from paperagent.method_design_draft import MethodDesignDraft, build_method_proposal
from paperagent.method_evidence import accepted_evidence_ledger, bind_method_evidence
from paperagent.nodes._shared import call_structured
from paperagent.runtime import get_services
from paperagent.schemas import MethodProposal
from paperagent.state import PaperAgentState, StatePatch

NODE = "method_design_node"

_MODULE_CONTRACT_REQUIREMENTS = (
    "Use one independently retrieved accepted module-lane paper that is distinct "
    "from the baseline.",
    "Bind the module name and original role to the selected paper title, summary, "
    "or verified metadata.",
    "State the exact baseline insertion point; do not use generic phrases such as "
    "selected representation stage.",
    "Specify input and output semantics and explicit tensor ranks/shapes, or an "
    "explicit projection path.",
    "Specify normalization and masking behavior for the target task rather than "
    "inheriting unspecified defaults.",
    "Specify gradient path, trainable parameters, frozen parameters, loss terms, "
    "and numeric loss weighting separately.",
    "Defer the module design when any required interface contract is unsupported "
    "by accepted evidence.",
)


async def method_design_node(state: PaperAgentState, config: RunnableConfig) -> StatePatch:
    plan = state.get("plan")
    synthesis = state.get("synthesis")
    evidence = state.get("evidence")
    if plan is None or synthesis is None or evidence is None:
        raise ValueError("plan, synthesis and evidence are required")
    accepted_ids = set(evidence.accepted_ids)

    def bind(method: MethodProposal) -> MethodProposal:
        try:
            return bind_method_evidence(method, evidence, synthesis)
        except ValueError as exc:
            raise NodeError(
                code="SEMANTIC_EVIDENCE_PROVENANCE_MISMATCH",
                message=str(exc),
                node=NODE,
            ) from exc

    def canonicalize(draft: MethodDesignDraft) -> MethodProposal:
        try:
            method = build_method_proposal(state, draft)
        except ValueError as exc:
            message = str(exc)
            code = (
                "MODULE_DESIGN_DEFERRED"
                if message.startswith("module_design_deferred:")
                else "METHOD_CANONICALIZATION_FAILED"
            )
            raise NodeError(code=code, message=message, node=NODE) from exc
        return bind(method)

    def validate(method: MethodProposal) -> None:
        canonical_evidence_ids = {item.evidence_id for item in method.methodology_plan.evidence}
        unknown = (set(method.evidence_ids) | canonical_evidence_ids) - accepted_ids
        if unknown:
            raise NodeError(
                code="SEMANTIC_UNKNOWN_EVIDENCE_ID",
                message=f"method referenced unknown evidence IDs: {sorted(unknown)}",
                node=NODE,
            )

    request = state.get("request")
    quality = state.get("quality")
    user_payload = {
        "user_request": request.question if request is not None else None,
        "problem_statement": plan.problem_statement,
        "scope": plan.scope,
        "verified_findings": [
            claim.model_dump(mode="json") for claim in synthesis.verified_findings
        ],
        "gap_assessments": [
            assessment.model_dump(mode="json") for assessment in synthesis.gap_assessments
        ],
        "accepted_evidence_ledger": accepted_evidence_ledger(evidence),
        "module_contract_requirements": list(_MODULE_CONTRACT_REQUIREMENTS),
        "constraints": request.required_constraints if request is not None else [],
        "risks": plan.risks,
        "clarification_question": plan.clarification_question,
        "repair_reason": quality.reason_codes if quality is not None else None,
    }

    services = get_services(config)
    if getattr(services.llm, "provider_name", None) == "fake_llm":
        patch, result = await call_structured(
            state=state,
            config=config,
            node=NODE,
            task="method_design",
            schema=MethodProposal,
            user_payload=user_payload,
            transform=bind,
            semantic_validate=validate,
        )
    else:
        patch, result = await call_structured(
            state=state,
            config=config,
            node=NODE,
            task="method_design",
            schema=MethodDesignDraft,
            user_payload=user_payload,
            transform=canonicalize,
            semantic_validate=validate,
        )

    if result is not None:
        patch["method"] = result
        patch["methodology_audit"] = None
    return patch
