from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


SOURCE = Path(__file__).with_name("clouddev_patch_case_015_multibehavior.py")


def _load_patch_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("case015_patch", SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load patch module: {SOURCE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _indent(value: str, spaces: int) -> str:
    if spaces == 0:
        return value
    prefix = " " * spaces
    return "".join(prefix + line if line.strip() else line for line in value.splitlines(keepends=True))


def _resolve(text: str, value: str, *, label: str, path: Path) -> tuple[str, int]:
    for spaces in (0, 4, 8, 12):
        candidate = _indent(value, spaces)
        count = text.count(candidate)
        if count == 1:
            return candidate, spaces
    raise RuntimeError(f"{path}: expected one {label} at indentation 0/4/8/12")


def main() -> None:
    patch = _load_patch_module()

    def replace_once(path: Path, old: str, new: str) -> None:
        old_value = patch._clean(old)
        new_value = patch._clean(new)
        text = path.read_text(encoding="utf-8")
        for spaces in (0, 4, 8, 12):
            if _indent(new_value, spaces) in text:
                return
        resolved_old, spaces = _resolve(text, old_value, label="anchor", path=path)
        resolved_new = _indent(new_value, spaces)
        path.write_text(text.replace(resolved_old, resolved_new, 1), encoding="utf-8")

    def insert_after(path: Path, anchor: str, addition: str) -> None:
        anchor_value = patch._clean(anchor)
        addition_value = patch._clean(addition)
        text = path.read_text(encoding="utf-8")
        for spaces in (0, 4, 8, 12):
            if _indent(addition_value, spaces).strip() in text:
                return
        resolved_anchor, spaces = _resolve(text, anchor_value, label="insertion anchor", path=path)
        resolved_addition = _indent(addition_value, spaces)
        path.write_text(
            text.replace(resolved_anchor, resolved_anchor + resolved_addition, 1),
            encoding="utf-8",
        )

    patch.replace_once = replace_once
    patch.insert_after = insert_after
    patch.main()


if __name__ == "__main__":
    main()
