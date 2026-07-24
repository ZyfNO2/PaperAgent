"""E2E: retrieval retry loop through the HTTP task contract.

The first ``evidence_synthesis`` call reports ``gap-support`` as ``partial``
(not ``supported``). ``quality_gate`` must detect the weak gap and route to
``repair_retrieval``. The second retrieval subgraph pass finds no new queries
to run (all query_ids are already in ``completed_query_ids``), so it only
re-confirms the existing coverage. The second ``evidence_synthesis`` call
(``call_index=1``) reports ``gap-support`` as ``supported``, so ``quality_gate``
returns ``pass`` and the graph proceeds to a completed report.

This proves the repair_retrieval loop is honoured end-to-end, including the
re-entry into the retrieval subgraph and the second synthesis/method pass.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from helpers import FixtureKey, assert_completed_nodes, build_services, load_llm_raw

EXPECTED_RETRIEVAL_RETRY_NODES = [
    "intake_node",
    "readiness_preflight_node",
    "planning_node",
    # First retrieval pass (round 0 -> 1): search returns candidates.
    "prepare_search_node",
    "search_tool_node",
    "verify_evidence_node",
    "evidence_synthesis_node",
    "method_design_node",
    "methodology_audit_node",
    "quality_gate_node",
    # Second retrieval pass (round 1 -> 2): no new queries to run, but the
    # subgraph still re-executes prepare_search/search_tool/verify_evidence.
    "prepare_search_node",
    "search_tool_node",
    "verify_evidence_node",
    "evidence_synthesis_node",
    "method_design_node",
    "methodology_audit_node",
    "quality_gate_node",
    "report_node",
    "persist_node",
]


def _retrieval_retry_services() -> Any:
    fixtures = {
        FixtureKey(task="planning", scenario="happy_path", call_index=0): load_llm_raw(
            "planning", "happy_path", 0
        ),
        # call_0 reports gap-support=partial; call_1 reports gap-support=supported.
        FixtureKey(
            task="evidence_synthesis", scenario="repair_retrieval", call_index=0
        ): load_llm_raw("evidence_synthesis", "repair_retrieval", 0),
        FixtureKey(
            task="evidence_synthesis", scenario="repair_retrieval", call_index=1
        ): load_llm_raw("evidence_synthesis", "repair_retrieval", 1),
        # Both method_design calls return a valid proposal (no method repair).
        FixtureKey(task="method_design", scenario="repair_retrieval", call_index=0): load_llm_raw(
            "method_design", "repair_retrieval", 0
        ),
        FixtureKey(task="method_design", scenario="repair_retrieval", call_index=1): load_llm_raw(
            "method_design", "repair_retrieval", 1
        ),
        FixtureKey(task="report", scenario="happy_path", call_index=0): load_llm_raw(
            "report", "happy_path", 0
        ),
    }
    return build_services(llm_fixtures=fixtures, prefix="retrieval_retry")


def test_e2e__retrieval_retry_loop__reaches_pass_after_one_repair_via_http(
    graph_app_factory, submit_task, wait_for_terminal
) -> None:
    client: TestClient = graph_app_factory(
        services=_retrieval_retry_services(),
        configurable={
            "scenarios": {
                "planning": "happy_path",
                "evidence_synthesis": "repair_retrieval",
                "method_design": "repair_retrieval",
                "report": "happy_path",
            }
        },
    )
    with client:
        task_id = submit_task(client, key="retrieval-retry-e2e")
        task = wait_for_terminal(client, task_id, timeout=20.0)

        assert task["status"] == "succeeded"
        result: dict[str, Any] = task["result"]

        assert result["execution"]["status"] == "completed"
        # repair_retrieval does not increment repair_count (only repair_method does).
        assert result["execution"]["repair_count"] == 0
        assert result["quality"]["verdict"] == "pass"
        assert result["report"]["status"] == "completed"
        # Two retrieval rounds must have executed.
        assert result["retrieval"]["round"] == 2

        assert_completed_nodes(result, EXPECTED_RETRIEVAL_RETRY_NODES)

        # The trace must record both quality_gate decisions in order.
        gate_routes = [
            event.get("route")
            for event in result.get("trace", [])
            if event.get("event_type") == "route.decided"
            and event.get("node") == "quality_gate_node"
        ]
        assert gate_routes == ["repair_retrieval", "pass"], gate_routes
