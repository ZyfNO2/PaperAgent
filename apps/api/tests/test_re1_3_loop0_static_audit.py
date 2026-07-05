"""Loop 0: Static audit — verify Re1.3 structural requirements.

Checks that all new files exist, nodes are registered, state has new fields,
no hardcoded blacklist, no citation_tracker import, etc.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def test_quality_filter_node_exists():
    p = REPO_ROOT / "apps/api/app/services/agents/graph/nodes/quality_filter.py"
    assert p.exists(), "quality_filter.py not found"


def test_citation_expander_node_exists():
    p = REPO_ROOT / "apps/api/app/services/agents/graph/nodes/citation_expander.py"
    assert p.exists(), "citation_expander.py not found"


def test_quality_filter_prompt_exists():
    p = REPO_ROOT / "apps/api/app/services/agents/prompts/re13_quality_filter.py"
    assert p.exists(), "re13_quality_filter.py not found"


def test_citation_expander_prompt_exists():
    p = REPO_ROOT / "apps/api/app/services/agents/prompts/re13_citation_expander.py"
    assert p.exists(), "re13_citation_expander.py not found"


def test_frontend_exists():
    p = REPO_ROOT / "apps/web/index.html"
    assert p.exists(), "index.html not found"


def test_nodes_registered():
    from apps.api.app.services.agents.graph import nodes as graph_nodes
    assert "quality_filter" in graph_nodes.REGISTRY
    assert "citation_expander" in graph_nodes.REGISTRY


def test_state_has_new_fields():
    from apps.api.app.services.agents.graph.state import ResearchState
    hints = ResearchState.__annotations__
    assert "seed_papers" in hints
    assert "expanded_papers" in hints
    assert "filter_results" in hints
    assert "citation_expansion_done" in hints
    assert "surveys_found" in hints
    assert "repos_found" in hints


def test_no_hardcoded_blacklist():
    """rg for _BLACKLIST or _BLACK_LIST in .py files returns 0."""
    import subprocess
    result = subprocess.run(
        ["rg", "_BLACKLIST|_BLACK_LIST", "--type", "py", "--count"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    # rg returns 1 when no matches found
    assert result.returncode == 1 or not result.stdout.strip(), \
        f"Found hardcoded blacklist:\n{result.stdout}"


def test_no_citation_tracker_import():
    """citation_tracker.py should NOT be imported in graph nodes."""
    nodes_dir = REPO_ROOT / "apps/api/app/services/agents/graph"
    for py in nodes_dir.rglob("*.py"):
        content = py.read_text(encoding="utf-8")
        assert "citation_tracker" not in content, \
            f"citation_tracker found in {py}"


def test_s2_functions_imported_in_citation_expander():
    p = REPO_ROOT / "apps/api/app/services/agents/graph/nodes/citation_expander.py"
    content = p.read_text(encoding="utf-8")
    assert "semantic_scholar_citations" in content
    assert "semantic_scholar_references" in content


def test_sse_endpoint_exists():
    p = REPO_ROOT / "apps/api/app/api/v1/research.py"
    content = p.read_text(encoding="utf-8")
    assert "stream" in content.lower()
    assert "StreamingResponse" in content


def test_expanded_endpoint_exists():
    p = REPO_ROOT / "apps/api/app/api/v1/research.py"
    content = p.read_text(encoding="utf-8")
    assert "expanded" in content.lower()


def test_no_manual_seeds_endpoint():
    p = REPO_ROOT / "apps/api/app/api/v1/research.py"
    content = p.read_text(encoding="utf-8")
    assert "seeds" not in content.lower(), "Manual seeds endpoint should not exist"


def test_static_mount_exists():
    p = REPO_ROOT / "apps/api/app/main.py"
    content = p.read_text(encoding="utf-8")
    assert "StaticFiles" in content
    assert "web" in content


def test_select_seeds_function_exists():
    p = REPO_ROOT / "apps/api/app/services/agents/graph/nodes/citation_expander.py"
    content = p.read_text(encoding="utf-8")
    assert "_select_seeds" in content


def test_env_not_tracked():
    env_path = REPO_ROOT / ".env"
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in gitignore or not env_path.exists()


def test_frontend_no_external_deps():
    p = REPO_ROOT / "apps/web/index.html"
    content = p.read_text(encoding="utf-8")
    assert "<script src=\"http" not in content, "External script dependency found"
    assert "<link" not in content or "href=\"http" not in content, "External link dependency found"


def test_frontend_uses_eventsource():
    p = REPO_ROOT / "apps/web/index.html"
    content = p.read_text(encoding="utf-8")
    assert "EventSource" in content


def test_frontend_has_polling_fallback():
    p = REPO_ROOT / "apps/web/index.html"
    content = p.read_text(encoding="utf-8")
    assert "setInterval" in content or "setTimeout" in content
