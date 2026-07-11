"""Quick smoke test for graph contract registration."""
from __future__ import annotations

from apps.api.app.services.router.register_graph_contracts import register_graph_contracts
from apps.api.app.services.router.contracts import get_contract_registry


def test_register_graph_contracts_idempotent():
    register_graph_contracts()
    register_graph_contracts()  # idempotent
    reg = get_contract_registry()
    assert reg.get_by_id("topic-parse/v1") is not None
    assert reg.get_by_id("search-plan/v1") is not None
    assert reg.get_by_id("verification-batch/v1") is not None
    assert reg.get_by_id("novelty-review/v1") is not None
    assert reg.get_by_id("falsifiability-batch/v1") is not None
    assert reg.get_by_id("claim-judge/v1") is not None
    assert reg.get_by_id("novelty-draft/v1") is not None
