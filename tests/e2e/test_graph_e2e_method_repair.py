"""E2E: method_design repair loop through the HTTP task contract.

The first ``method_design`` call returns a deliberately weak proposal (no
threshold in hypothesis, empty ablations, empty stop_conditions). ``quality_gate``
must detect the missing fields and route to ``repair_method``. The second
``method_design`` call (same scenario, ``call_index=1``) returns a fixed proposal
that satisfies every quality check, so ``quality_gate`` returns ``pass`` and the
graph proceeds to a completed report. This proves the repair_method loop is
honoured end-to-end, not only at the graph level.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from helpers import FixtureKey, assert_completed_nodes, build_services, load_llm_raw

EXPECTED_METHOD_REPAIR_NODES = [
    "intake_node",
    "planning_node",
    "prepare_search_node",
    "search_tool_node",
    "verify_evidence_node",
    "evidence_synthesis_node",
    "method_design_node",
    "quality_gate_node",
    # Second method_design call after quality_gate returned repair_method.
    "method_design_node",
    "quality_gate_node",
    "report_node",
    "persist_node",
]


def _method_repair_services() -> Any:
    fixtures = {
        FixtureKey(task="planning", scenario="happy_path", call_index=0): load_llm_raw(
            "planning", "happy_path", 0
        ),
        FixtureKey(task="evidence_synthesis", scenario="happy_path", call_index=0): load_llm_raw(
            "evidence_synthesis", "happy_path", 0
        ),
        # call_index=0 is deliberately weak; call_index=1 is the fixed proposal.
        FixtureKey(
            task="method_design", scenario="gate_repair_method", call_index=0
        ): load_llm_raw("method_design", "gate_repair_method", 0),
        FixtureKey(
            task="method_design", scenario="gate_repair_method", call_index=1
        ): load_llm_raw("method_design", "gate_repair_method", 1),
        FixtureKey(task="report", scenario="happy_path", call_index=0): load_llm_raw(
            "report", "happy_path", 0
        ),
    }
    return build_services(llm_fixtures=fixtures, prefix="method_repair")


def test_e2e__method_repair_loop__reaches_pass_after_one_repair_via_http(
    graph_app_factory, submit_task, wait_for_terminal
) -> None:
    client: TestClient = graph_app_factory(
        services=_method_repair_services(),
        configurable={
            "scenarios": {
                "planning": "happy_path",
                "evidence_synthesis": "happy_path",
                "method_design": "gate_repair_method",
                "report": "happy_path",
            }
        },
    )
    with client:
        task_id = submit_task(client, key="method-repair-e2e")
        task = wait_for_terminal(client, task_id)

        assert task["status"] == "succeeded"
        result: dict[str, Any] = task["result"]

        assert result["execution"]["status"] == "completed"
        assert result["execution"]["repair_count"] == 1
        # repair_target is cleared once quality_gate returns "pass" (the final
        # QualityDecision carries no repair_target), so we only assert that one
        # repair happened, not the final target field.
        assert result["quality"]["verdict"] == "pass"
        assert result["report"]["status"] == "completed"

        assert_completed_nodes(result, EXPECTED_METHOD_REPAIR_NODES)

        # The trace must record both quality_gate decisions: repair_method then pass.
        gate_routes = [
            event.get("route")
            for event in result.get("trace", [])
            if event.get("event_type") == "route.decided" and event.get("node") == "quality_gate_node"
        ]
        assert gate_routes == ["repair_method", "pass"], gate_routes
