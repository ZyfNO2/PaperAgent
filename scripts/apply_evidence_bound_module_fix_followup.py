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
_PLANNING = Path("src/paperagent/nodes/planning.py")
_TARGET_BRANCH = "fix/evidence-bound-module-contracts-v2"


def _run(*args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=check, text=True, capture_output=False)


def _replace_exact(text: str, old: str, new: str, *, label: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one exact match, found {count}")
    return text.replace(old, new)


def _patch_literature_adapter() -> None:
    text = _LITERATURE_ADAPTER.read_text(encoding="utf-8")

    old_query_regex = """_COMPARATOR_ROLE_QUERY = re.compile(
    r"(?:\\bcomparators?\\b|\\bcomparison\\b|对照|比较|对比)",
    re.IGNORECASE,
)
_DATASET_CONTEXT = re.compile(
"""
    new_query_regex = """_COMPARATOR_ROLE_QUERY = re.compile(
    r"(?:\\bcomparators?\\b|\\bcomparison\\b|对照|比较|对比)",
    re.IGNORECASE,
)
_MODULE_ROLE_QUERY = re.compile(
    r"(?:\\bmodules?\\b|\\bparallel(?: method| paper)?\\b|\\bmechanisms?\\b|"
    r"模块|平行论文|并行方法|机制)",
    re.IGNORECASE,
)
_DATASET_CONTEXT = re.compile(
"""
    text = _replace_exact(
        text,
        old_query_regex,
        new_query_regex,
        label="literature module query regex",
    )

    old_role_classifier = """def _query_seeks_comparator_role(query: str) -> bool:
    return not _query_seeks_baseline_role(query) and bool(_COMPARATOR_ROLE_QUERY.search(query))


def _query_candidate_role(query: str) -> str | None:
    if _query_seeks_baseline_role(query):
        return "baseline"
    if _query_seeks_comparator_role(query):
        return "comparator"
    return None
"""
    new_role_classifier = """def _query_seeks_comparator_role(query: str) -> bool:
    return not _query_seeks_baseline_role(query) and bool(_COMPARATOR_ROLE_QUERY.search(query))


def _query_seeks_module_role(query: str) -> bool:
    return not _query_seeks_baseline_role(query) and bool(_MODULE_ROLE_QUERY.search(query))


def _query_candidate_role(query: str) -> str | None:
    if _query_seeks_baseline_role(query):
        return "baseline"
    if _query_seeks_comparator_role(query):
        return "comparator"
    if _query_seeks_module_role(query):
        return "module"
    return None
"""
    text = _replace_exact(
        text,
        old_role_classifier,
        new_role_classifier,
        label="literature query role classifier",
    )

    old_relation_block = """        candidates: list[SearchCandidate] = []
        for paper in selected:
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
"""
    relation_block = """        candidates: list[SearchCandidate] = []
        query_role = _query_candidate_role(query.query)
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
"""
    text = _replace_exact(
        text,
        old_relation_block,
        relation_block,
        label="literature candidate relation block",
    )

    old_metadata = """                **(
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
"""
    new_metadata = """                **(
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
"""
    text = _replace_exact(
        text,
        old_metadata,
        new_metadata,
        label="literature module candidate metadata",
    )
    _LITERATURE_ADAPTER.write_text(text, encoding="utf-8")
    print(f"patched by function boundary: {_LITERATURE_ADAPTER}")


def _patch_planning() -> None:
    text = _PLANNING.read_text(encoding="utf-8")
    text = _replace_exact(
        text,
        "from __future__ import annotations\n\nfrom langchain_core.runnables import RunnableConfig\n",
        "from __future__ import annotations\n\nimport re\n\nfrom langchain_core.runnables import RunnableConfig\n",
        label="planning re import",
    )

    old_title_helper = """def _query_contains_material_title(query: SearchQuery, title: str) -> bool:
    normalized_title = " ".join(title.replace('"', " ").split()).casefold()
    normalized_query = " ".join(query.query.replace('"', " ").split()).casefold()
    return bool(normalized_title and normalized_title in normalized_query)
"""
    new_title_helper = """def _query_contains_material_title(query: SearchQuery, title: str) -> bool:
    normalized_title = " ".join(title.replace('"', " ").split()).casefold()
    normalized_query = " ".join(query.query.replace('"', " ").split()).casefold()
    return bool(normalized_title and normalized_title in normalized_query)


def _material_query_role_hint(reference: str) -> str:
    match = re.search(r"\\[declared role:(?P<role>[^\\]]+)\\]", reference, re.IGNORECASE)
    if match is None:
        return ""
    role = match.group("role").casefold()
    if any(token in role for token in ("parallel", "module", "mechanism", "平行", "模块")):
        return " parallel method module"
    if "baseline" in role or "基线" in role:
        return " baseline"
    if any(token in role for token in ("comparison", "comparator", "对比", "比较")):
        return " comparator comparison"
    return ""
"""
    text = _replace_exact(
        text,
        old_title_helper,
        new_title_helper,
        label="planning material role helper",
    )

    text = _replace_exact(
        text,
        """        exact_title = identity.title.replace('"', " ").strip()
        identity_gaps.append(
""",
        """        exact_title = identity.title.replace('"', " ").strip()
        role_hint = _material_query_role_hint(identity.reference)
        identity_gaps.append(
""",
        label="planning material role hint assignment",
    )
    text = _replace_exact(
        text,
        "                query=f'\"{exact_title}\"',\n",
        "                query=f'\"{exact_title}\"{role_hint}',\n",
        label="planning exact-title role query",
    )
    text = _replace_exact(
        text,
        "                query=f'\"{exact_title}\" official implementation code repository',\n",
        """                query=(
                    f'\"{exact_title}\" official implementation code repository'
                    f'{_material_query_role_hint(identity.reference)}'
                ),
""",
        label="planning repository role query",
    )
    _PLANNING.write_text(text, encoding="utf-8")
    print(f"patched by function boundary: {_PLANNING}")


def _harden_original_payload(payload: str) -> str:
    for call in (
        "patch_module_compatibility",
        "patch_literature_adapter",
        "patch_planning",
        "patch_method_design",
    ):
        payload, removed = re.subn(
            rf"(?m)^\s*{call}\(\)\s*$",
            "",
            payload,
            count=1,
        )
        if removed != 1:
            raise RuntimeError(f"original {call} call was not found")

    old_helper = """def replace_once(path: str, old: str, new: str) -> None:
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
"""
    new_helper = """def replace_once(path: str, old: str, new: str) -> None:
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
"""
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
    _run("git", "push", "origin", f"HEAD:{_TARGET_BRANCH}")


def main() -> None:
    original: Path | None = None
    try:
        runpy.run_path("scripts/prepatch_method_design.py", run_name="__main__")
        _patch_literature_adapter()
        _patch_planning()
        original = _materialize_original()
        runpy.run_path(str(original), run_name="__main__")
    except BaseException:
        rendered = traceback.format_exc()
        _persist_failure(rendered)
        raise
    finally:
        if original is not None:
            original.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
