from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "src/paperagent/claw_benchmark_adapter.py"
ADAPTER_TESTS = ROOT / "tests/evals/test_claw_benchmark_adapter.py"
PLANNING_TESTS = ROOT / "tests/nodes/test_planning_nonblocking.py"
ANOMALY_TESTS = ROOT / "tests/literature/test_time_series_anomaly_precision.py"

_METHOD_EVIDENCE_ROLES = '''def _method_evidence_roles(state: PaperAgentState) -> dict[str, EvidenceRole]:
    method = state.get("method")
    if method is None:
        return {}
    plan = method.methodology_plan
    roles: dict[str, EvidenceRole] = {}
    if plan.baseline.source_evidence_id:
        roles[plan.baseline.source_evidence_id] = "baseline"
    for module in plan.modules:
        if module.evidence_id:
            roles[module.evidence_id] = "parallel_method"
    for experiment in plan.experiments:
        if not experiment.source_evidence_id:
            continue
        if experiment.arm_type is ExperimentArmType.STRONG_COMPARISON:
            roles[experiment.source_evidence_id] = "strong_comparison"
        elif experiment.arm_type is ExperimentArmType.NEGATIVE_CONTROL:
            roles[experiment.source_evidence_id] = "risk"
    return roles


'''


def patch_adapter() -> None:
    text = ADAPTER.read_text(encoding="utf-8")

    if "def _method_evidence_roles(" not in text:
        marker = "_SUPPLIED_REF = re.compile(\n"
        if marker not in text:
            raise RuntimeError("supplied-material marker not found")
        text = text.replace(marker, _METHOD_EVIDENCE_ROLES + marker, 1)

    old = '''    bundle = state.get("evidence")
    if bundle is None:
        return ()
'''
    new = '''    bundle = state.get("evidence")
    if bundle is None:
        return _supplied_material_reviews(state, existing_count=0)
'''
    if old in text:
        text = text.replace(old, new, 1)
    elif new not in text:
        raise RuntimeError("evidence bundle fallback block not found")

    ADAPTER.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    adapter_tests = ADAPTER_TESTS.read_text(encoding="utf-8")
    adapter_tests = adapter_tests.replace(
        'question="我上传了 MobileNetV3 论文，想用于轻量化植物病害识别"',
        'question="我上传了 MobileNetV3 论文, 想用于轻量化植物病害识别"',
    )
    ADAPTER_TESTS.write_text(adapter_tests, encoding="utf-8")

    planning_tests = PLANNING_TESTS.read_text(encoding="utf-8")
    planning_tests = planning_tests.replace(
        'clarification_question="Which behavior types and deployment limits should constrain the pilot?",',
        'clarification_question=(\n'
        '            "Which behavior types and deployment limits should constrain the pilot?"\n'
        '        ),',
    )
    PLANNING_TESTS.write_text(planning_tests, encoding="utf-8")

    anomaly_tests = ANOMALY_TESTS.read_text(encoding="utf-8")
    anomaly_tests = anomaly_tests.replace(
        "def test_time_series_anomaly_candidate_guard(\n"
        "    query: str, candidate: str, expected: bool\n"
        ") -> None:",
        "def test_time_series_anomaly_candidate_guard(\n"
        "    query: str, candidate: str, expected: bool\n"
        ") -> None:",
    )
    anomaly_tests = anomaly_tests.replace(
        "小样本时间序列异常检测，以 Anomaly Transformer 为基线",
        "小样本时间序列异常检测, 以 Anomaly Transformer 为基线",
    )
    ANOMALY_TESTS.write_text(anomaly_tests, encoding="utf-8")


def main() -> None:
    patch_adapter()
    patch_tests()


if __name__ == "__main__":
    main()
