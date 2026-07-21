from __future__ import annotations

from pathlib import Path


METHOD = Path("src/paperagent/method_design_draft.py")


def main() -> int:
    source = METHOD.read_text(encoding="utf-8")
    old = (
        '                        f"review source {primary.stable_identifier}; '
        'implementation baseline unresolved"\n'
    )
    new = (
        '                        (\n'
        '                            f"review source {primary.stable_identifier}; "\n'
        '                            "implementation baseline unresolved"\n'
        '                        )\n'
    )
    if old in source:
        source = source.replace(old, new, 1)
    elif new not in source:
        raise RuntimeError("missing inferred baseline review wrapping target")
    METHOD.write_text(source, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
