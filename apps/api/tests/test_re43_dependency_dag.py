"""Re4.3: Dependency DAG tests."""
from __future__ import annotations

from apps.api.app.services.agents.graph.validators.dependency_dag import build_dag


class TestDependencyDAG:
    def test_no_dependencies_single_layer(self) -> None:
        """Packages without prerequisites → single milestone."""
        packages = [
            {"title": "Package A"},
            {"title": "Package B"},
        ]
        dag = build_dag(packages)
        assert len(dag["milestones"]) == 1
        assert len(dag["milestones"][0]["packages"]) == 2
        assert dag["has_cycle"] is False

    def test_linear_dependency(self) -> None:
        """A→B→C chain → 3 milestones."""
        packages = [
            {"title": "A"},
            {"title": "B", "prerequisite_ids": ["wp-a"]},
            {"title": "C", "prerequisite_ids": ["wp-b"]},
        ]
        dag = build_dag(packages)
        assert len(dag["milestones"]) == 3
        assert dag["milestones"][0]["packages"] == ["wp-a"]
        assert dag["milestones"][1]["packages"] == ["wp-b"]
        assert dag["milestones"][2]["packages"] == ["wp-c"]
        assert dag["has_cycle"] is False

    def test_parallel_packages_same_layer(self) -> None:
        """Two independent packages → same milestone."""
        packages = [
            {"title": "Independent A"},
            {"title": "Independent B"},
        ]
        dag = build_dag(packages)
        assert len(dag["milestones"]) == 1
        assert len(dag["milestones"][0]["packages"]) == 2

    def test_cycle_detected(self) -> None:
        """Circular dependency → has_cycle=True."""
        packages = [
            {"title": "A", "prerequisite_ids": ["wp-b"]},
            {"title": "B", "prerequisite_ids": ["wp-a"]},
        ]
        dag = build_dag(packages)
        assert dag["has_cycle"] is True

    def test_milestone_label_generation(self) -> None:
        """Milestones labeled 阶段 1, 阶段 2, ..."""
        packages = [
            {"title": "Base"},
            {"title": "Dep", "prerequisite_ids": ["wp-base"]},
        ]
        dag = build_dag(packages)
        assert dag["milestones"][0]["label"] == "阶段 1"
        assert dag["milestones"][1]["label"] == "阶段 2"

    def test_empty_packages(self) -> None:
        """Empty package list → empty DAG."""
        dag = build_dag([])
        assert dag["nodes"] == []
        assert dag["edges"] == []
        assert dag["milestones"] == []
        assert dag["has_cycle"] is False

    def test_edges_correct(self) -> None:
        """Edges should reflect prerequisite relationships."""
        packages = [
            {"title": "A"},
            {"title": "B", "prerequisite_ids": ["wp-a"]},
        ]
        dag = build_dag(packages)
        assert len(dag["edges"]) == 1
        assert dag["edges"][0]["from"] == "wp-a"
        assert dag["edges"][0]["to"] == "wp-b"

    def test_topo_order_valid(self) -> None:
        """Topological order should have prerequisites before dependents."""
        packages = [
            {"title": "A"},
            {"title": "B", "prerequisite_ids": ["wp-a"]},
            {"title": "C", "prerequisite_ids": ["wp-a", "wp-b"]},
        ]
        dag = build_dag(packages)
        order = dag["topo_order"]
        assert order.index("wp-a") < order.index("wp-b")
        assert order.index("wp-b") < order.index("wp-c")
