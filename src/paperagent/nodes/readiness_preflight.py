from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from paperagent.nodes._shared import execution_with
from paperagent.outcome import derive_final_outcome
from paperagent.runtime import get_services
from paperagent.schemas import QualityDecision
from paperagent.scientific_readiness import derive_scientific_readiness
from paperagent.state import PaperAgentState, StatePatch
from paperagent.telemetry import make_event

NODE = "readiness_preflight_node"


async def readiness_preflight_node(
    state: PaperAgentState,
    config: RunnableConfig,
) -> StatePatch:
    """Classify explicit readiness declarations before planning or retrieval.

    The preflight records only what the user explicitly declared. It does not
    manufacture external evidence, numeric results, or publication claims.
    """

    request = state.get("request")
    if request is None:
        raise ValueError("request is required for readiness preflight")

    services = get_services(config)
    signals = derive_scientific_readiness(request.question)
    execution = execution_with(state, node=NODE)
    trace = [
        make_event(
            services,
            state,
            node=NODE,
            event_type="node.started",
            status="started",
        )
    ]
    patch: StatePatch = {
        "scientific_readiness": signals,
        "execution": execution,
    }

    quality: QualityDecision | None = None
    if signals.explicit_evaluation_protocol_invalid:
        quality = QualityDecision(
            verdict="blocked",
            reason_codes=["Q_EXPLICIT_EVALUATION_PROTOCOL_INVALID"],
        )
    elif signals.declared_ready:
        quality = QualityDecision(
            verdict="pass",
            reason_codes=["Q_USER_DECLARED_READINESS_COMPLETE"],
        )

    if quality is not None:
        resolved_state: PaperAgentState = {
            **state,
            "scientific_readiness": signals,
            "quality": quality,
            "execution": execution,
        }
        final_outcome = derive_final_outcome(resolved_state)
        patch["quality"] = quality
        patch["final_outcome"] = final_outcome
        trace.append(
            make_event(
                services,
                resolved_state,
                node=NODE,
                event_type="route.decided",
                status="decided",
                route=quality.verdict,
                output_payload={
                    "scientific_readiness": signals,
                    "quality": quality,
                    "final_outcome": final_outcome,
                },
            )
        )
    else:
        trace.append(
            make_event(
                services,
                state,
                node=NODE,
                event_type="node.completed",
                status="completed",
                output_payload=signals,
            )
        )

    patch["trace"] = trace
    return patch


def readiness_preflight_route(state: PaperAgentState) -> str:
    signals = state.get("scientific_readiness")
    if signals is None:
        raise ValueError("scientific readiness is required for preflight routing")
    if signals.explicit_evaluation_protocol_invalid or signals.declared_ready:
        return "terminal"
    return "continue"


__all__ = ["readiness_preflight_node", "readiness_preflight_route"]
