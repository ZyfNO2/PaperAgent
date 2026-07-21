from __future__ import annotations

from pathlib import Path


ADAPTER_PATH = Path("src/paperagent/literature/adapter.py")


def main() -> int:
    source = ADAPTER_PATH.read_text(encoding="utf-8")
    old = "from collections.abc import Iterable\nfrom hashlib import sha256\nimport re\n"
    new = "import re\nfrom collections.abc import Iterable\nfrom hashlib import sha256\n"
    if old in source:
        source = source.replace(old, new, 1)
    elif new not in source:
        raise RuntimeError("adapter import block not found")
    ADAPTER_PATH.write_text(source, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
