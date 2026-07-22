from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

from paperagent.claw_academic_benchmark import AcademicTailoringRunTrace

SCRIPT = Path(__file__).parents[2] / "scripts" / "score_academic_tailoring_retrieval_v2.py"
SPEC = importlib.util.spec_from_file_location("retrieval_scorer_v2_test", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
scorer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scorer)

BERT = "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding"
BEIT = "BEiT: BERT Pre-Training of Image Transformers"
LORA = "LoRA: Low-Rank Adaptation of Large Language Models"


def _case() -> dict[str, Any]:
    return {
        "case_id": "atr-v1-003-nlp-bert-lora-clinc",
        "case_type": "baseline_plus_parallel_paper",
        "domain": "nlp",
        "public_input": {
            "supplied_materials": [
                {"title": BERT, "declared_role": "baseline"},
                {"title": LORA, "declared_role": "parallel_module_source"},
            ]
        },
        "gold": {
            "expected_assets": [
                {"kind": "paper", "title": BERT, "role": "baseline"},
                {"kind": "paper", "title": LORA, "role": "module source"},
            ],
            "baseline_decision": {"canonical": "BERT-base classifier with a linear intent head"},
        },
    }


def _item(evidence_id: str, title: str) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "source_type": "paper",
        "title": title,
        "locator": f"arxiv:{evidence_id}",
        "summary": f"Verified primary paper: {title}",
        "metadata": {"relation": "declared_identity"},
    }


def _state() -> dict[str, Any]:
    items = [_item("ev-bert", BERT), _item("ev-beit", BEIT), _item("ev-lora", LORA)]
    return {
        "evidence": {
            "items": items,
            "accepted_ids": [item["evidence_id"] for item in items],
        }
    }


def _review(
    evidence_id: str,
    role: str,
    *,
    role_compatible: bool = True,
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "source_type": "paper",
        "identity_verified": True,
        "relevance_reviewed": True,
        "relevance_passed": True,
        "accepted": True,
        "role": role,
        "core_evidence": True,
        "role_compatible": role_compatible,
    }


def _module(evidence_id: str) -> dict[str, Any]:
    return {
        "module_id": "lora-qv",
        "evidence_id": evidence_id,
        "original_role": "low-rank parameter-efficient transformer adaptation",
        "proposed_role": "low-rank updates on BERT query and value projections",
        "input_semantics": "BERT self-attention hidden states before query/value projection",
        "output_semantics": "adapted query and value vectors with frozen base weights",
        "input_shape": "batch x tokens x hidden_size",
        "output_shape": "batch x tokens x hidden_size",
        "optimization_interaction": "optimize only rank matrices A/B and intent head",
        "compute_cost": "rank-8 trainable adapters",
        "failure_mode": "low rank underfits rare intents or destabilizes OOS calibration",
        "implementation_switch": "method.enable_lora_qv",
        "role_compatible": True,
    }


def _experiment(experiment_id: str, arm_type: str, *, generic: bool = False) -> dict[str, Any]:
    if generic:
        dataset = "unresolved task-matched data source"
        split = "preserve the documented split"
        preprocessing = "match input construction"
        tuning_budget = "match epochs or steps"
    else:
        dataset = "CLINC150/OOS-Eval release used by the frozen baseline"
        split = "fixed per-intent 10-shot seeds with a disjoint OOS evaluation split"
        preprocessing = "BERT-base-uncased tokenizer, casing preserved, max length 64"
        tuning_budget = "20 epochs and the same optimizer grid for every arm"
    return {
        "experiment_id": experiment_id,
        "arm_type": arm_type,
        "included_modules": ["lora-qv"] if arm_type != "baseline" else [],
        "dataset": dataset,
        "split": split,
        "preprocessing": preprocessing,
        "tuning_budget": tuning_budget,
        "metrics": ["macro-F1", "OOS recall", "trainable parameters"],
        "seeds": [1, 2, 3],
        "uncertainty_reporting": "mean, standard deviation, and paired seed deltas",
        "resource_measures": ["latency", "peak memory"],
        "stopping_criteria": "stop if OOS recall degrades by more than two points",
    }


def _trace(
    *,
    baseline_id: str,
    baseline_name: str,
    module_id: str,
    module_role: str,
    decision: str = "REVISE",
    generic_experiments: bool = False,
) -> AcademicTailoringRunTrace:
    return AcademicTailoringRunTrace.model_validate(
        {
            "case_id": "atr-v1-003-nlp-bert-lora-clinc",
            "fact_partitions": {
                "verified": ["paper identities verified"],
                "inferred": ["compatibility remains conditional"],
                "proposed": ["LoRA query/value pilot"],
                "unknown": [],
            },
            "retrieval_roles": ["baseline", "parallel_method"],
            "evidence_reviews": [
                _review("ev-bert", "baseline" if baseline_id == "ev-bert" else "other"),
                _review("ev-beit", "baseline" if baseline_id == "ev-beit" else "other"),
                _review("ev-lora", module_role),
            ],
            "clarification_questions": [],
            "resolved_unknowns": [],
            "baseline": {
                "name": baseline_name,
                "source_evidence_id": baseline_id,
                "version_or_commit": "frozen checkpoint and implementation commit",
                "dataset": "CLINC150/OOS-Eval",
                "split": "fixed per-intent 10-shot seeds; independent OOS split",
                "metrics": ["macro-F1", "OOS recall"],
                "environment": "locked Python and framework versions",
                "seed_policy": "1, 2, 3",
            },
            "hypothesis": {
                "condition": "ten examples per intent with separate OOS evaluation",
                "limitation": "full fine-tuning overfits and damages OOS calibration",
                "mechanism": "low-rank updates constrain the adaptation subspace",
                "intervention": "LoRA rank matrices on BERT query/value projections",
                "target_metric": "macro-F1",
                "guardrail": "OOS recall and latency must remain within predefined bounds",
            },
            "modules": [_module(module_id)],
            "stitch_order": ["bert", "lora-qv", "intent-head"],
            "experiments": [
                _experiment("e0", "baseline", generic=generic_experiments),
                _experiment("e1", "single_module", generic=generic_experiments),
            ],
            "decision": decision,
            "pilot_recommended": decision == "REVISE",
            "next_actions": ["freeze the exact implementation and sampler"],
            "stop_conditions": [
                "baseline cannot be reproduced under the frozen protocol",
                "gain disappears under the matched tuning budget",
            ],
            "stronger_baselines_considered": True,
            "negative_results_visible": True,
        }
    )


def _score(trace: AcademicTailoringRunTrace) -> dict[str, Any]:
    return scorer._score_case(
        _case(),
        _state(),
        trace,
        prompt_leakage=False,
        minimum_score=80,
    )


def test_correct_bert_elsewhere_does_not_rescue_beit_baseline() -> None:
    result = _score(
        _trace(
            baseline_id="ev-beit",
            baseline_name=BEIT,
            module_id="ev-lora",
            module_role="parallel_method",
        )
    )

    assert "wrong_paper_identity" in result["hard_failures"]
    assert result["dimensions"]["baseline_selection"] == 0
    assert result["matched_assets"]["papers"] == [1, 2]
    assert result["status"] == "failed"


def test_baseline_evidence_cannot_double_as_module_provenance() -> None:
    result = _score(
        _trace(
            baseline_id="ev-bert",
            baseline_name=BERT,
            module_id="ev-bert",
            module_role="parallel_method",
        )
    )

    assert "baseline_reused_as_module_evidence" in result["hard_failures"]
    assert result["dimensions"]["module_provenance_and_role"] == 0
    assert result["dimensions"]["semantic_and_interface_compatibility"] == 0


def test_module_requires_parallel_method_review_role() -> None:
    result = _score(
        _trace(
            baseline_id="ev-bert",
            baseline_name=BERT,
            module_id="ev-lora",
            module_role="other",
        )
    )

    assert "module_evidence_role_mismatch" in result["hard_failures"]
    assert "module_compatibility_not_independently_verified" in result["hard_failures"]
    assert result["matched_assets"]["papers"] == [1, 2]


def test_correct_bert_lora_roles_receive_role_specific_credit() -> None:
    result = _score(
        _trace(
            baseline_id="ev-bert",
            baseline_name=BERT,
            module_id="ev-lora",
            module_role="parallel_method",
        )
    )

    assert "wrong_paper_identity" not in result["hard_failures"]
    assert "module_evidence_role_mismatch" not in result["hard_failures"]
    assert "module_compatibility_not_independently_verified" not in result["hard_failures"]
    assert result["matched_assets"]["papers"] == [2, 2]
    assert result["dimensions"]["baseline_selection"] == 15
    assert result["dimensions"]["module_provenance_and_role"] == 10
    assert result["dimensions"]["semantic_and_interface_compatibility"] == 15
    assert result["scoring_policy"] == "role_bound_semantic_v2"


def test_go_is_rejected_when_experiment_contract_is_generic() -> None:
    result = _score(
        _trace(
            baseline_id="ev-bert",
            baseline_name=BERT,
            module_id="ev-lora",
            module_role="parallel_method",
            decision="GO",
            generic_experiments=True,
        )
    )

    assert result["scoring_audit"]["task_specific_experiment_count"] == 0
    assert "unsupported_go_decision" in result["hard_failures"]
    assert result["status"] == "failed"
