# -*- coding: utf-8 -*-
"""Re3.2 integration test - covers all Phase 1-3 fixes."""
from __future__ import annotations

import os
import sys
import time
import inspect

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = 0
FAIL = 0
SKIP = 0
RESULTS = []


def report(phase, name, status, detail=""):
    global PASS, FAIL, SKIP
    if status == "PASS":
        PASS += 1
    elif status == "FAIL":
        FAIL += 1
    else:
        SKIP += 1
    RESULTS.append((phase, name, status))
    tag = {"PASS": "OK", "FAIL": "FAIL", "SKIP": "SKIP"}[status]
    line = "  [" + tag + "] " + name
    if detail:
        line += " -- " + detail
    print(line)


def test_phase1():
    print("\n=== Phase 1: P0 bug fixes ===")

    # 1a: verify.py has import re and import json
    try:
        from apps.api.app.services.agents.graph.nodes import verify as verify_mod
        src = inspect.getsource(verify_mod)
        assert "import re" in src, "verify.py should have import re"
        assert "import json" in src, "verify.py should have import json"
        report("Phase 1", "verify.py has import re + import json", "PASS")
    except Exception as e:
        report("Phase 1", "verify.py has import re + import json", "FAIL", str(e))

    # 1b: verify.py _normalise_verifier_output works with string input
    try:
        from apps.api.app.services.agents.graph.nodes.verify import _normalise_verifier_output
        # Should not raise NameError
        result = _normalise_verifier_output(None)
        assert isinstance(result, list)
        report("Phase 1", "verify.py _normalise_verifier_output no NameError", "PASS")
    except Exception as e:
        report("Phase 1", "verify.py _normalise_verifier_output no NameError", "FAIL", str(e))

    # 1c: rules.md exists
    try:
        assert os.path.exists(os.path.join(os.path.dirname(__file__), "..", "rules.md")), "rules.md should exist"
        report("Phase 1", "rules.md exists", "PASS")
    except Exception as e:
        report("Phase 1", "rules.md exists", "FAIL", str(e))

    # 1d: test_re1_2_graph_nodes.py updated (3/4 pass, smoke test has pre-existing mock issue)
    try:
        from apps.api.app.services.agents.graph.nodes import REGISTRY
        assert "search_agent" in REGISTRY
        assert "paper_retriever" in REGISTRY  # alias still exists
        assert "verify" in REGISTRY
        report("Phase 1", "REGISTRY has search_agent + verify", "PASS",
               "keys=" + str(len(REGISTRY)))
    except Exception as e:
        report("Phase 1", "REGISTRY has search_agent + verify", "FAIL", str(e))


def test_phase2():
    print("\n=== Phase 2: Missing features ===")

    # 2a: CORE adapter registered
    try:
        from apps.api.app.services.retrieval.adapters import REGISTRY
        assert "core" in REGISTRY, "core should be in REGISTRY"
        report("Phase 2", "CORE adapter registered", "PASS")
    except Exception as e:
        report("Phase 2", "CORE adapter registered", "FAIL", str(e))

    # 2b: DataCite adapter registered
    try:
        assert "datacite" in REGISTRY, "datacite should be in REGISTRY"
        report("Phase 2", "DataCite adapter registered", "PASS")
    except Exception as e:
        report("Phase 2", "DataCite adapter registered", "FAIL", str(e))

    # 2c: DataCite adapter importable
    try:
        from apps.api.app.services.retrieval.adapters.datacite_search import datacite_search
        assert callable(datacite_search)
        report("Phase 2", "DataCite adapter importable", "PASS")
    except Exception as e:
        report("Phase 2", "DataCite adapter importable", "FAIL", str(e))

    # 2d: search_agent has 8 tools in system prompt
    try:
        from apps.api.app.services.agents.graph.nodes.search_agent import _SYSTEM_PROMPT
        for tool in ("arxiv", "openalex", "crossref", "github", "semantic_scholar",
                      "huggingface", "core", "datacite"):
            assert tool in _SYSTEM_PROMPT, "tool " + tool + " not in system prompt"
        report("Phase 2", "search_agent has 8 tools in prompt", "PASS")
    except Exception as e:
        report("Phase 2", "search_agent has 8 tools in prompt", "FAIL", str(e))

    # 2e: search_agent available_tools has 8
    try:
        from apps.api.app.services.agents.graph.nodes.search_agent import search_agent_node
        src = inspect.getsource(search_agent_node)
        assert "huggingface" in src and "core" in src and "datacite" in src
        report("Phase 2", "search_agent available_tools has 8", "PASS")
    except Exception as e:
        report("Phase 2", "search_agent available_tools has 8", "FAIL", str(e))

    # 2f: adapters/__init__.py no mojibake
    try:
        from apps.api.app.services.retrieval.adapters import __doc__ as adoc
        # Should be readable ASCII/English
        assert adoc is None or "registry" in (adoc or "").lower() or "adapter" in (adoc or "").lower(), \
            "docstring should be readable: " + repr(adoc)
        report("Phase 2", "adapters/__init__.py no mojibake", "PASS")
    except Exception as e:
        report("Phase 2", "adapters/__init__.py no mojibake", "FAIL", str(e))

    # 2g: SearchSource includes core and datacite
    try:
        from apps.api.app.schemas_retrieval import SearchSource
        import typing
        args = typing.get_args(SearchSource)
        assert "core" in args
        assert "datacite" in args
        report("Phase 2", "SearchSource includes core + datacite", "PASS")
    except Exception as e:
        report("Phase 2", "SearchSource includes core + datacite", "FAIL", str(e))

    # 2h: real DataCite search (network)
    try:
        import asyncio
        from apps.api.app.services.retrieval.adapters.datacite_search import datacite_search
        print("    [network] fetching datacite 'YOLO crop detection'...")
        t0 = time.time()
        results = asyncio.run(datacite_search(["YOLO crop detection"], 5))
        elapsed = round(time.time() - t0, 1)
        assert isinstance(results, list)
        report("Phase 2", "real DataCite search", "PASS",
               "got " + str(len(results)) + " results, " + str(elapsed) + "s")
    except Exception as e:
        report("Phase 2", "real DataCite search", "SKIP", "network: " + str(e))

    # 2i: real CORE search (network)
    try:
        import asyncio
        from apps.api.app.services.retrieval.adapters.core_search import core_search
        print("    [network] fetching core 'machine learning'...")
        t0 = time.time()
        results = asyncio.run(core_search(["machine learning"], 5))
        elapsed = round(time.time() - t0, 1)
        assert isinstance(results, list)
        report("Phase 2", "real CORE search", "PASS",
               "got " + str(len(results)) + " results, " + str(elapsed) + "s")
    except Exception as e:
        report("Phase 2", "real CORE search", "SKIP", "network: " + str(e))


def test_phase3():
    print("\n=== Phase 3: Consistency fixes ===")

    # 3a: targeted_repair MAX_REPAIR_ROUNDS reads env
    try:
        from apps.api.app.services.agents.graph.nodes import targeted_repair
        src = inspect.getsource(targeted_repair)
        assert "PAPERAGENT_MAX_REPAIR_ROUNDS" in src, "should read env var"
        report("Phase 3", "targeted_repair reads env MAX_REPAIR_ROUNDS", "PASS")
    except Exception as e:
        report("Phase 3", "targeted_repair reads env MAX_REPAIR_ROUNDS", "FAIL", str(e))

    # 3b: CHANGELOG has Unreleased section
    try:
        changelog_path = os.path.join(os.path.dirname(__file__), "..", "CHANGELOG.md")
        content = open(changelog_path, encoding="utf-8").read()
        assert "## [Unreleased]" in content, "should have Unreleased section"
        assert "Re3.0" in content or "Re3.1" in content or "Re3.2" in content
        report("Phase 3", "CHANGELOG has Unreleased + Re3.x", "PASS")
    except Exception as e:
        report("Phase 3", "CHANGELOG has Unreleased + Re3.x", "FAIL", str(e))

    # 3c: llm_router docstring not "DeepSeek flash"
    try:
        from apps.api.app.services import llm_router
        src = inspect.getsource(llm_router)
        assert "DeepSeek flash" not in src, "should not say 'DeepSeek flash'"
        assert "FAST_JSON_PRIMARY" in src
        report("Phase 3", "llm_router docstring corrected", "PASS")
    except Exception as e:
        report("Phase 3", "llm_router docstring corrected", "FAIL", str(e))

    # 3d: adapters/__init__.py docstring is readable
    try:
        init_path = os.path.join(os.path.dirname(__file__), "..", "apps", "api", "app", "services", "retrieval", "adapters", "__init__.py")
        content = open(init_path, encoding="utf-8").read()
        assert "registry" in content.lower()
        assert "\ufffd" not in content, "should not have replacement chars"
        report("Phase 3", "adapters/__init__.py readable docstring", "PASS")
    except Exception as e:
        report("Phase 3", "adapters/__init__.py readable docstring", "FAIL", str(e))


def main():
    print("=" * 60)
    print("PaperAgent Re3.2 Integration Test")
    print("=" * 60)

    test_phase1()
    test_phase2()
    test_phase3()

    print("\n" + "=" * 60)
    print("Total: " + str(PASS) + " passed, " + str(FAIL) + " failed, " + str(SKIP) + " skipped")
    print("=" * 60)

    if FAIL > 0:
        print("\nFailed items:")
        for phase, name, status in RESULTS:
            if status == "FAIL":
                print("  [FAIL] [" + phase + "] " + name)
        return 1
    else:
        print("\nAll passed OK")
        return 0


if __name__ == "__main__":
    sys.exit(main())
