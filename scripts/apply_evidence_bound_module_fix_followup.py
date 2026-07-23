from __future__ import annotations

import re
import runpy
import subprocess
import tempfile
import traceback
from pathlib import Path

_PATCH_SOURCE_COMMIT = "0533bf3d7e717064f998a63545c40131cf98f01c"
_PATCH_PATH = "scripts/apply_evidence_bound_module_fix_followup.py"
_FAILURE_LOG = Path(".github/evidence-bound-module-followup-failure.log")
_LITERATURE_ADAPTER = Path("src/paperagent/literature/adapter.py")


def _run(*args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=check, text=True, capture_output=False)


def _replace_exact(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if text.count(old) != 1:
        raise RuntimeError(f"{label} shape changed")
    path.write_text(text.replace(old, new), encoding="utf-8")


def _prepatch_literature_relation() -> None:
    old = '''        for paper in selected:
            relation = (
                "declared_identity"
                if required_title is not None
                and _exact_title_match(paper.canonical_title, required_title)
                else (
                    "parallel_via_dataset"
                    if paper.paper_id in relation_paper_ids
                    else (
                        "baseline_role_query"
                        if _query_candidate_role(query.query) == "baseline"
                        else (
                            "comparator_role_query"
                            if _query_candidate_role(query.query) == "comparator"
                            else "direct_query"
                        )
                    )
                )
            )
'''
    new = '''        query_role = _query_candidate_role(query.query)
        for paper in selected:
            exact_declared_identity = required_title is not None and _exact_title_match(
                paper.canonical_title, required_title
            )
            relation = (
                "module_role_query"
                if exact_declared_identity and query_role == "module"
                else (
                    "declared_identity"
                    if exact_declared_identity
                    else (
                        "module_linked_by_focused_retrieval"
                        if paper.paper_id in relation_paper_ids and query_role == "module"
                        else (
                            "parallel_via_dataset"
                            if paper.paper_id in relation_paper_ids
                            else (
                                "baseline_role_query"
                                if query_role == "baseline"
                                else (
                                    "comparator_role_query"
                                    if query_role == "comparator"
                                    else (
                                        "module_role_query"
                                        if query_role == "module"
                                        else "direct_query"
                                    )
                                )
                            )
                        )
                    )
                )
            )
'''
    _replace_exact(_LITERATURE_ADAPTER, old, new, "literature relation")


def _prepatch_literature_metadata() -> None:
    old = '''                **(
                    {"baseline_candidate": "declared"}
                    if relation == "declared_identity"
                    else (
                        {"baseline_candidate": "inferred"}
                        if relation in {"parallel_via_dataset", "baseline_role_query"}
                        else (
                            {"comparator_candidate": "inferred"}
                            if relation == "comparator_role_query"
                            else {}
                        )
                    )
                ),
'''
    new = '''                **(
                    {"baseline_candidate": "declared"}
                    if relation == "declared_identity"
                    else (
                        {"baseline_candidate": "inferred"}
                        if relation in {"parallel_via_dataset", "baseline_role_query"}
                        else (
                            {"comparator_candidate": "inferred"}
                            if relation == "comparator_role_query"
                            else (
                                {"module_candidate": "inferred"}
                                if relation
                                in {
                                    "module_role_query",
                                    "parallel_method_query",
                                    "module_linked_by_focused_retrieval",
                                }
                                else {}
                            )
                        )
                    )
                ),
'''
    _replace_exact(_LITERATURE_ADAPTER, old, new, "literature module metadata")


def _drop_replace_call(payload: str, needle: str) -> str:
    needle_index = payload.find(needle)
    if needle_index < 0:
        raise RuntimeError(f"original patch needle was not found: {needle[:40]!r}")
    start = payload.rfind("    replace_once(\n", 0, needle_index)
    if start < 0:
        raise RuntimeError("original replace_once start was not found")
    next_replace = payload.find("\n    replace_once(\n", needle_index + 1)
    next_function = payload.find("\n\n\ndef patch_planning() -> None:\n", needle_index + 1)
    boundaries = [value for value in (next_replace, next_function) if value >= 0]
    if not boundaries:
        raise RuntimeError("original replace_once end was not found")
    end = min(boundaries)
    return payload[:start] + payload[end + (1 if end == next_replace else 0) :]


def _harden_original_payload(payload: str) -> str:
    payload, removed = re.subn(
        r"(?m)^\s*patch_module_compatibility\(\)\s*$",
        "",
        payload,
        count=1,
    )
    if removed != 1:
        raise RuntimeError("original module compatibility call was not found")
    payload = _drop_replace_call(
        payload,
        '''                    for paper in selected:
                        relation = (
''',
    )
    payload = _drop_replace_call(
        payload,
        '''                                {"comparator_candidate": "inferred"}
                                if relation == "comparator_role_query"
                                else {}
''',
    )

    old_helper = '''def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if new in text:
        print(f"already patched: {path}")
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one exact match, found {count}")
    file.write_text(text.replace(old, new), encoding="utf-8")
    print(f"patched: {path}")
'''
    new_helper = '''def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if new in text:
        print(f"already patched: {path}")
        return
    count = text.count(old)
    if count != 1:
        if path == "tests/methodology/test_method_design_draft.py" and count > 1:
            file.write_text(text.replace(old, new, 1), encoding="utf-8")
            print(f"patched first guarded occurrence: {path}")
            return
        raise RuntimeError(f"{path}: expected one exact match, found {count}")
    file.write_text(text.replace(old, new), encoding="utf-8")
    print(f"patched: {path}")
'''
    if old_helper not in payload:
        raise RuntimeError("original patch helper shape changed")
    return payload.replace(old_helper, new_helper)


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
    _prepatch_literature_relation()
    _prepatch_literature_metadata()
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
