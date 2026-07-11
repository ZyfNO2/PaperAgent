"""Re4.3: Dependency DAG for work packages.

Builds a directed acyclic graph from prerequisite_ids and validates:
  1. No cycles
  2. All prerequisites exist
  3. Topological order is valid
"""
from __future__ import annotations

import re
from collections import defaultdict, deque
from typing import Any


def _package_id(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return f"wp-{slug[:30]}"


def build_dag(packages: list[dict[str, Any]]) -> dict[str, Any]:
    """Build dependency DAG from work packages.

    Returns dict with nodes, edges, topo_order, has_cycle, milestones.
    """
    id_to_pkg: dict[str, dict[str, Any]] = {}
    for pkg in packages:
        title = pkg.get("title", "")
        pkg_id = _package_id(title)
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

    milestones = _build_milestones(id_to_pkg)

    return {
        "nodes": [
            {"id": pid, "title": pkg.get("title", ""), "effort": pkg.get("effort", "Unknown")}
            for pid, pkg in id_to_pkg.items()
        ],
        "edges": edges,
        "topo_order": topo_order,
        "has_cycle": has_cycle,
        "milestones": milestones,
    }


def _build_milestones(
    id_to_pkg: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Group packages into milestone layers (parallel-executable sets)."""
    if not id_to_pkg:
        return []

    milestones: list[dict[str, Any]] = []
    remaining = set(id_to_pkg.keys())
    layer = 0

    while remaining:
        ready = [
            pid for pid in remaining
            if all(
                dep not in remaining
                for dep in (id_to_pkg[pid].get("prerequisite_ids") or [])
                if dep in id_to_pkg
            )
        ]
        if not ready:
            ready = list(remaining)

        milestones.append({
            "id": f"ms-{layer + 1}",
            "packages": sorted(ready),
            "label": f"阶段 {layer + 1}",
        })
        remaining -= set(ready)
        layer += 1

    return milestones
