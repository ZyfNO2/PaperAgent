from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(relative: str, old: str, new: str) -> None:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"expected exactly one replacement in {relative}, found {count}: {old[:120]!r}"
        )
    path.write_text(text.replace(old, new), encoding="utf-8")


replace_once(
    "scripts/scan_production.py",
    """def scan_production(
""",
    """def _pilot_source_findings(production_root: Path) -> list[dict[str, object]]:
    path = production_root / "src/paperagent/claw_benchmark_normalizer.py"
    if not path.exists():
        return [{"code": "PILOT_NORMALIZER_FILE_MISSING", "path": str(path)}]
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    target: ast.FunctionDef | ast.AsyncFunctionDef | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == (
            "normalize_paperagent_state"
        ):
            target = node
            break
    relative = str(path.relative_to(production_root))
    if target is None:
        return [{"code": "PILOT_NORMALIZER_FUNCTION_MISSING", "path": relative}]

    assignments = []
    for node in ast.walk(target):
        if not isinstance(node, ast.Assign):
            continue
        if any(
            isinstance(assigned, ast.Name) and assigned.id == "pilot_recommended"
            for assigned in node.targets
        ):
            assignments.append(node.value)
    expected = ast.parse(
        "bool(outcome is not None and outcome.pilot_recommended)",
        mode="eval",
    ).body
    assignment_verified = bool(
        len(assignments) == 1
        and ast.dump(assignments[0], include_attributes=False)
        == ast.dump(expected, include_attributes=False)
    )

    update_verified = False
    for node in ast.walk(target):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values, strict=True):
            if (
                isinstance(key, ast.Constant)
                and key.value == "pilot_recommended"
                and isinstance(value, ast.Name)
                and value.id == "pilot_recommended"
            ):
                update_verified = True
                break
        if update_verified:
            break

    if assignment_verified and update_verified:
        return []
    return [
        {
            "code": "PILOT_RECOMMENDATION_SOURCE_UNVERIFIED",
            "path": relative,
            "assignment_verified": assignment_verified,
            "trace_update_verified": update_verified,
        }
    ]


def scan_production(
""",
)
replace_once(
    "scripts/scan_production.py",
    """    findings = _runtime_signature_findings(root)
    file_hashes: dict[str, str] = {}
""",
    """    findings = [
        *_runtime_signature_findings(root),
        *_pilot_source_findings(root),
    ]
    pilot_recommendation_source_verified = not any(
        str(item.get("code", "")).startswith("PILOT_") for item in findings
    )
    file_hashes: dict[str, str] = {}
""",
)
replace_once(
    "scripts/scan_production.py",
    """        "schema": "paperagent.academic-holdout.production-scan.v2",
""",
    """        "schema": "paperagent.academic-holdout.production-scan.v3",
""",
)
replace_once(
    "scripts/scan_production.py",
    """        "private_ngram_count": len(forbidden_ngrams),
        "passed": not findings,
""",
    """        "private_ngram_count": len(forbidden_ngrams),
        "pilot_recommendation_source_verified": pilot_recommendation_source_verified,
        "passed": not findings,
""",
)

replace_once(
    "scripts/run_private_holdout.py",
    """    adapter_created_pilot_count = 0 if production_scan.get("passed") is True else 1
""",
    """    adapter_created_pilot_count = (
        0 if production_scan.get("pilot_recommendation_source_verified") is True else 1
    )
""",
)

replace_once(
    "tests/test_scan_production.py",
    """        path.write_text(
            "from __future__ import annotations\\n\\n"
            f"async def execute_benchmark_input({signature}):\\n"
            "    return benchmark_input\\n",
            encoding="utf-8",
        )
        return temporary, root
""",
    """        path.write_text(
            "from __future__ import annotations\\n\\n"
            f"async def execute_benchmark_input({signature}):\\n"
            "    return benchmark_input\\n",
            encoding="utf-8",
        )
        normalizer = root / "src/paperagent/claw_benchmark_normalizer.py"
        normalizer.write_text(
            "def normalize_paperagent_state(state, context):\\n"
            "    outcome = state.get('final_outcome')\\n"
            "    pilot_recommended = bool(outcome is not None and outcome.pilot_recommended)\\n"
            "    trace = legacy(state, context)\\n"
            "    return trace.model_copy(update={'pilot_recommended': pilot_recommended})\\n",
            encoding="utf-8",
        )
        return temporary, root
""",
)
replace_once(
    "tests/test_scan_production.py",
    """        self.assertEqual(report["scanned_file_count"], 1)
""",
    """        self.assertEqual(report["scanned_file_count"], 2)
        self.assertTrue(report["pilot_recommendation_source_verified"])
""",
)
replace_once(
    "tests/test_scan_production.py",
    """    def test_missing_executor_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = scan_production(Path(directory))
        self.assertFalse(report["passed"])
        self.assertEqual(report["findings"][0]["code"], "RUNTIME_FILE_MISSING")


if __name__ == "__main__":
""",
    """    def test_pilot_value_not_sourced_from_final_outcome_fails(self) -> None:
        temporary, root = self._production_tree(
            "*, benchmark_input, llm, search, max_llm_calls, task_id"
        )
        self.addCleanup(temporary.cleanup)
        normalizer = root / "src/paperagent/claw_benchmark_normalizer.py"
        normalizer.write_text(
            "def normalize_paperagent_state(state, context):\\n"
            "    pilot_recommended = True\\n"
            "    trace = legacy(state, context)\\n"
            "    return trace.model_copy(update={'pilot_recommended': pilot_recommended})\\n",
            encoding="utf-8",
        )

        report = scan_production(root)

        self.assertFalse(report["passed"])
        self.assertFalse(report["pilot_recommendation_source_verified"])
        findings = [
            item
            for item in report["findings"]
            if item["code"] == "PILOT_RECOMMENDATION_SOURCE_UNVERIFIED"
        ]
        self.assertEqual(len(findings), 1)

    def test_missing_executor_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = scan_production(Path(directory))
        self.assertFalse(report["passed"])
        codes = {item["code"] for item in report["findings"]}
        self.assertIn("RUNTIME_FILE_MISSING", codes)
        self.assertIn("PILOT_NORMALIZER_FILE_MISSING", codes)
        self.assertFalse(report["pilot_recommendation_source_verified"])


if __name__ == "__main__":
""",
)

print("pilot source scan invariant applied")
