from __future__ import annotations

from pathlib import Path


ADAPTER = Path("src/paperagent/literature/adapter.py")


def main() -> int:
    source = ADAPTER.read_text(encoding="utf-8")
    bad = 'strip(".,;:()[]{}"\'")'
    good = 'strip(".,;:()[]{}")'
    count = source.count(bad)
    if count == 0 and good not in source:
        raise RuntimeError("missing generated dataset strip literal")
    source = source.replace(bad, good)
    ADAPTER.write_text(source, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
