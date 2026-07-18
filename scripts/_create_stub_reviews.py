"""Create stub reviewer scores to test the scoring pipeline.
Real Gate L requires human experts - this validates the mechanics only."""
import json
from pathlib import Path

MAPPING = Path("build/gate-l-v2-final/blinded-review-package.mapping.json")
REVIEW_A = Path("build/gate-l-v2-final/review-a-stub.json")
REVIEW_B = Path("build/gate-l-v2-final/review-b-stub.json")

RUBRIC = {
    "scientific_correctness": 25,
    "claim_evidence_alignment": 25,
    "methodological_rigor": 20,
    "calibration_and_limits": 15,
    "actionability": 15,
}

def main():
    mapping = json.loads(MAPPING.read_text(encoding="utf-8"))
    arms = mapping["arms"]

    # Stub: both reviewers give identical mid-range scores
    # Real Gate L requires independent human experts
    def make_review(arm_ids):
        return {
            "reviewer_id": "stub-reviewer",
            "blinded": True,
            "cases": [
                {
                    "arm_id": arm_id,
                    "decision": "REVISE",
                    "critical_defect": False,
                    "scores": {
                        "scientific_correctness": 20,
                        "claim_evidence_alignment": 20,
                        "methodological_rigor": 16,
                        "calibration_and_limits": 12,
                        "actionability": 12,
                    },
                }
                for arm_id in arm_ids
            ],
        }

    arm_ids = [a["arm_id"] for a in arms]
    REVIEW_A.write_text(json.dumps(make_review(arm_ids), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    REVIEW_B.write_text(json.dumps(make_review(arm_ids), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Stub reviews written: {REVIEW_A}, {REVIEW_B}")

if __name__ == "__main__":
    main()
