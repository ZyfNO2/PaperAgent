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


def _prepatch_literature_metadata() -> None:
    text = _LITERATURE_ADAPTER.read_text(encoding="utf-8")
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
    if new in text:
        return
    if text.count(old) != 1:
        raise RuntimeError("literature adapter module metadata shape changed")
    _LITERATURE_ADAPTER.write_text(text.replace(old, new), encoding="utf-8")


def _drop_original_literature_metadata_patch(payload: str) -> str:
    start_marker = '''    replace_once(
        "src/paperagent/literature/adapter.py",
        block(
            '''\n                                {"comparator_candidate": "inferred"}
'''
    end_marker = '''    )


def patch_planning() -> None:
'''
    start = payload.find(start_marker)
    end = payload.find(end_marker, start)
    if start < 0 or end < 0:
        raise RuntimeError("original literature metadata patch block was not found")
    return payload[:start] + payload[end + len("    )\n\n\n") :]


def _harden_original_payload(payload: str) -> str:
    payload, removed = re.subn(
        r"(?m)^\s*patch_module_compatibility\(\)\s*$",
        "",
        payload,
        count=1,
    )
    if removed != 1:
        raise RuntimeError("original module compatibility call was not found")
    payload = _drop_original_literature_metadata_patch(payload)

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
