from __future__ import annotations

from pathlib import Path

PATCH = Path("scripts/apply_comparator_identity_binding_v1.py")


def main() -> int:
    source = PATCH.read_text(encoding="utf-8")
    source = source.replace(
        'f"{title}\\n{summary}"',
        'f"{title}\\\\n{summary}"',
        1,
    )
    PATCH.write_text(source, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
