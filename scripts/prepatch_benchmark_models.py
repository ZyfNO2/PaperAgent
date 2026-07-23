from __future__ import annotations

from pathlib import Path

PATH = Path("src/paperagent/claw_academic_benchmark.py")


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    new = (
        "    role_compatible: bool | None = None\n"
        "    compatibility_reasons: tuple[str, ...] = ()\n\n\n"
        "class ExperimentTrace"
    )
    if new in text:
        return
    old = "    role_compatible: bool | None = None\n\n\nclass ExperimentTrace"
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"benchmark ModuleTrace boundary: expected one exact match, found {count}"
        )
    PATH.write_text(text.replace(old, new), encoding="utf-8")


if __name__ == "__main__":
    main()
