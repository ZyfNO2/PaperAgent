"""Re4.1: StageContract v1 tests."""
from __future__ import annotations

from apps.api.app.services.agents.graph.stage_contract import (
    CONTRACTS,
    StageContract,
    get_contract,
)


class TestStageContract:
    def test_contract_registry_has_core_nodes(self) -> None:
        """Registry must have contracts for all core nodes."""
        required = [
            "intake",
            "topic_parser",
            "search_planner",
            "search_agent",
            "quality_filter",
            "verify",
            "citation_expander",
        ]
        for node in required:
            assert node in CONTRACTS, f"Missing contract for {node}"

    def test_reads_present_before_writes(self) -> None:
        """A node's writes should not appear in its own reads (no circular)."""
        for name, contract in CONTRACTS.items():
            overlap = set(contract.reads) & set(contract.writes)
            assert not overlap, f"{name}: reads and writes overlap: {overlap}"

    def test_validate_state_missing_keys(self) -> None:
        """validate_state returns missing keys."""
        c = CONTRACTS["topic_parser"]
        missing = c.validate_state({})
        assert "topic" in missing

    def test_validate_state_all_present(self) -> None:
        """validate_state returns empty list when all reads present."""
        c = CONTRACTS["topic_parser"]
        missing = c.validate_state({"topic": "test"})
        assert missing == []

    def test_every_contract_has_error_code(self) -> None:
        """Every contract must have a non-empty error_code."""
        for name, c in CONTRACTS.items():
            assert c.error_code, f"{name}: missing error_code"

    def test_every_contract_has_dod(self) -> None:
        """Every contract must have a non-empty dod."""
        for name, c in CONTRACTS.items():
            assert c.dod, f"{name}: missing dod"

    def test_get_contract_returns_contract(self) -> None:
        """get_contract returns the StageContract for known nodes."""
        c = get_contract("intake")
        assert c is not None
        assert c.node_name == "intake"

    def test_get_contract_returns_none_for_unknown(self) -> None:
        """get_contract returns None for unknown nodes."""
        assert get_contract("nonexistent_node") is None

    def test_contract_version_is_string(self) -> None:
        """All contracts have a string version."""
        for name, c in CONTRACTS.items():
            assert isinstance(c.version, str)
            assert c.version  # non-empty

    def test_contract_is_pydantic_model(self) -> None:
        """StageContract is a Pydantic BaseModel."""
        c = StageContract(
            node_name="test",
            reads=("a",),
            writes=("b",),
            error_code="E_TEST",
        )
        assert isinstance(c, StageContract)
        assert c.node_name == "test"
        assert c.reads == ("a",)
        assert c.writes == ("b",)
        assert c.version == "1.0"
        assert c.optional_reads == ()
        assert c.fallback_source is None
