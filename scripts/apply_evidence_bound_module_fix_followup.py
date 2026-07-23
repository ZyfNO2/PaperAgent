from __future__ import annotations

import runpy
import subprocess
import tempfile
import traceback
from pathlib import Path

_PATCH_SOURCE_COMMIT = "0533bf3d7e717064f998a63545c40131cf98f01c"
_PATCH_PATH = "scripts/apply_evidence_bound_module_fix_followup.py"
_FAILURE_LOG = Path(".github/evidence-bound-module-followup-failure.log")


def _run(*args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=check, text=True, capture_output=False)


def _harden_original_payload(payload: str) -> str:
    # module_compatibility.py is already committed directly; do not re-patch it.
    payload = payload.replace("    patch_module_compatibility()\n", "")

    old_test_target = '''            '''\n                    "input_semantics": "a shallow detector feature map containing fine spatial cues",\n                    "output_semantics": "a shape-compatible enhanced feature map for the baseline head",\n                    "predicted_effect": "improve small-object recall and AP_small",\n            '''\n'''
    unique_test_target = '''            '''\n                    "module_proposed_role": "single causal small-object feature intervention",\n                    "input_semantics": "a shallow detector feature map containing fine spatial cues",\n                    "output_semantics": "a shape-compatible enhanced feature map for the baseline head",\n                    "predicted_effect": "improve small-object recall and AP_small",\n            '''\n'''
    old_test_replacement = '''            '''\n                    "input_semantics": "a shallow detector feature map containing fine spatial cues",\n                    "output_semantics": "a shape-compatible enhanced feature map for the baseline head",\n                    "input_shape": "[B, C3, H/8, W/8] shallow detector feature map",\n                    "output_shape": "[B, C3, H/8, W/8] enhanced feature map",\n                    "insertion_point": "between the stride-8 backbone feature and the first neck fusion block",\n                    "normalization_contract": "apply the source module normalization before neck fusion",\n                    "masking_contract": "preserve detector target-validity masks without adding padding masks",\n                    "gradient_path": "detection losses backpropagate through neck fusion into this module",\n                    "trainable_parameters": "feature-fusion convolution and channel-gating parameters",\n                    "frozen_parameters": "none during the matched end-to-end detector pilot",\n                    "loss_terms": ["classification loss", "box regression loss"],\n                    "loss_weighting": "use the frozen baseline classification and box-loss weights",\n                    "predicted_effect": "improve small-object recall and AP_small",\n            '''\n'''
    unique_test_replacement = '''            '''\n                    "module_proposed_role": "single causal small-object feature intervention",\n                    "input_semantics": "a shallow detector feature map containing fine spatial cues",\n                    "output_semantics": "a shape-compatible enhanced feature map for the baseline head",\n                    "input_shape": "[B, C3, H/8, W/8] shallow detector feature map",\n                    "output_shape": "[B, C3, H/8, W/8] enhanced feature map",\n                    "insertion_point": "between the stride-8 backbone feature and the first neck fusion block",\n                    "normalization_contract": "apply the source module normalization before neck fusion",\n                    "masking_contract": "preserve detector target-validity masks without adding padding masks",\n                    "gradient_path": "detection losses backpropagate through neck fusion into this module",\n                    "trainable_parameters": "feature-fusion convolution and channel-gating parameters",\n                    "frozen_parameters": "none during the matched end-to-end detector pilot",\n                    "loss_terms": ["classification loss", "box regression loss"],\n                    "loss_weighting": "use the frozen baseline classification and box-loss weights",\n                    "predicted_effect": "improve small-object recall and AP_small",\n            '''\n'''
    payload = payload.replace(old_test_target, unique_test_target)
    payload = payload.replace(old_test_replacement, unique_test_replacement)

    old_metadata_target = '''        '            "relation": "parallel_via_dataset",\\n            "rank_score": "0.90",\\n',\n'''
    unique_metadata_target = '''        '            "baseline_candidate": "inferred",\\n            "relation": "parallel_via_dataset",\\n            "rank_score": "0.90",\\n',\n'''
    old_metadata_replacement = '''        '            "relation": "module_role_query",\\n            "module_candidate": "inferred",\\n            "rank_score": "0.90",\\n            "relevance_score": "0.90",\\n',\n'''
    unique_metadata_replacement = '''        '            "baseline_candidate": "inferred",\\n            "relation": "module_role_query",\\n            "module_candidate": "inferred",\\n            "rank_score": "0.90",\\n            "relevance_score": "0.90",\\n',\n'''
    payload = payload.replace(old_metadata_target, unique_metadata_target)
    payload = payload.replace(old_metadata_replacement, unique_metadata_replacement)
    return payload


def _materialize_original() -> Path:
    payload = subprocess.check_output(
        ["git", "show", f"{_PATCH_SOURCE_COMMIT}:{_PATCH_PATH}"],
        text=True,
    )
    payload = _harden_original_payload(payload)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        prefix="paperagent-module-patch-",
        delete=False,
        encoding="utf-8",
    )
    with handle:
        handle.write(payload)
    return Path(handle.name)


def _persist_failure(rendered: str) -> None:
    print(rendered)
    _run("git", "reset", "--hard", "HEAD")
    _FAILURE_LOG.write_text(rendered, encoding="utf-8")
    _run("git", "config", "user.name", "github-actions[bot]")
    _run(
        "git",
        "config",
        "user.email",
        "41898282+github-actions[bot]@users.noreply.github.com",
    )
    _run("git", "add", str(_FAILURE_LOG))
    _run("git", "commit", "-m", "chore(ci): record module follow-up patch failure")
    _run("git", "push", "origin", "HEAD:fix/evidence-bound-module-contracts")


def main() -> None:
    original = _materialize_original()
    try:
        runpy.run_path(str(original), run_name="__main__")
    except BaseException:
        rendered = traceback.format_exc()
        _persist_failure(rendered)
        raise
    finally:
        original.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
