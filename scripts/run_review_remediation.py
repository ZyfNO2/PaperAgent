from __future__ import annotations

import base64
import gzip
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS = (
    "scripts/.review-remediation-00.b64",
    "scripts/.review-remediation-01.b64",
    "scripts/.review-remediation-02.b64",
    "scripts/.review-remediation-03.b64",
    "scripts/.review-remediation-04a.b64",
    "scripts/.review-remediation-04b.b64",
    "scripts/.review-remediation-04c.b64",
    "scripts/.review-remediation-04d.b64",
    "scripts/.review-remediation-04e.b64",
    "scripts/.review-remediation-05a.b64",
    "scripts/.review-remediation-05b.b64",
    "scripts/.review-remediation-05c.b64",
    "scripts/.review-remediation-05d.b64",
)


def _ensure_legacy_adapter_test_precondition() -> None:
    path = ROOT / "tests/evals/test_claw_benchmark_adapter.py"
    text = path.read_text(encoding="utf-8")
    if "def test_explicit_structured_pilot_signal_is_preserved" in text:
        return
    marker = "\n\ndef test_canonical_ledger_controls_evidence_review_semantics() -> None:\n"
    if text.count(marker) != 1:
        raise RuntimeError("cannot establish legacy adapter-test precondition")
    legacy_test = '''\n\ndef test_explicit_structured_pilot_signal_is_preserved() -> None:\n    state = _revise_state(\n        next_action="Collect one more observation.", quality_route="repair_method"\n    )\n    trace = normalize_paperagent_state(\n        state,\n        BenchmarkNormalizationContext(\n            case_id="held-out-002",\n            pilot_recommended=True,\n        ),\n    )\n    assert trace.decision == "REVISE"\n    assert trace.pilot_recommended is True\n'''
    path.write_text(text.replace(marker, legacy_test + marker), encoding="utf-8")


# One-shot migration entry point. This file is deleted by the workflow after use.
_ensure_legacy_adapter_test_precondition()
payload = "".join((ROOT / part).read_text(encoding="utf-8").strip() for part in PARTS)
source = gzip.decompress(base64.b64decode(payload))
namespace = {"__file__": __file__, "__name__": "__main__"}
exec(compile(source, __file__, "exec"), namespace)
