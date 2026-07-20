from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    "tests/e2e/test_graph_e2e_blocked.py",
    "tests/e2e/test_graph_e2e_bounded_failure.py",
    "tests/e2e/test_graph_e2e_happy_path.py",
    "tests/e2e/test_graph_e2e_malformed.py",
    "tests/e2e/test_graph_e2e_method_repair.py",
    "tests/e2e/test_graph_e2e_retrieval_retry.py",
    "tests/e2e/test_graph_e2e_timeout.py",
    "tests/graph/test_full_graph.py",
)

pattern = re.compile(r'^(?P<indent>\s*)"intake_node",\n', re.MULTILINE)
for relative in TARGETS:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise RuntimeError(f"expected one intake sequence entry in {relative}, found {len(matches)}")
    match = matches[0]
    indent = match.group("indent")
    replacement = f'{indent}"intake_node",\n{indent}"readiness_preflight_node",\n'
    path.write_text(pattern.sub(replacement, text, count=1), encoding="utf-8")

print("readiness preflight node sequence contracts applied")
