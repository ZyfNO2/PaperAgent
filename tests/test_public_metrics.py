from __future__ import annotations

import unittest

from scripts.run_public_dev import _metamorphic_consistency, _report_digest


class PublicProtocolMetricTests(unittest.TestCase):
    def test_consistent_pair_passes(self) -> None:
        cases = [
            {"case_id": "a", "metadata": {"metamorphic_group": "group-1"}},
            {"case_id": "b", "metadata": {"metamorphic_group": "group-1"}},
        ]
        traces = [
            {"case_id": "a", "decision": "REVISE"},
            {"case_id": "b", "decision": "REVISE"},
        ]
        self.assertEqual(_metamorphic_consistency(cases, traces), (1.0, 1))

    def test_inconsistent_pair_fails(self) -> None:
        cases = [
            {"case_id": "a", "metadata": {"metamorphic_group": "group-1"}},
            {"case_id": "b", "metadata": {"metamorphic_group": "group-1"}},
        ]
        traces = [
            {"case_id": "a", "decision": "REVISE"},
            {"case_id": "b", "decision": "NO_GO"},
        ]
        self.assertEqual(_metamorphic_consistency(cases, traces), (0.0, 1))

    def test_singletons_do_not_create_a_comparable_group(self) -> None:
        cases = [
            {"case_id": "a", "metadata": {"metamorphic_group": "group-1"}},
            {"case_id": "b", "metadata": {"metamorphic_group": None}},
        ]
        traces = [
            {"case_id": "a", "decision": "REVISE"},
            {"case_id": "b", "decision": "GO"},
        ]
        self.assertEqual(_metamorphic_consistency(cases, traces), (None, 0))

    def test_report_digest_ignores_prior_digest_field(self) -> None:
        report = {"decision_accuracy": 0.8, "report_digest": "old"}
        first = _report_digest(report)
        report["report_digest"] = "different-old-value"
        self.assertEqual(_report_digest(report), first)
        self.assertEqual(len(first), 64)


if __name__ == "__main__":
    unittest.main()
