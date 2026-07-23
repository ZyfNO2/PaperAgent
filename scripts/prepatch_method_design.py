from __future__ import annotations

import base64
import runpy
import tempfile
import zlib
from pathlib import Path

PAYLOAD = Path("scripts/prepatch_method_design.payload")


def main() -> None:
    source = zlib.decompress(base64.b64decode(PAYLOAD.read_text(encoding="utf-8").strip()))
    handle = tempfile.NamedTemporaryFile(
        mode="wb",
        suffix=".py",
        prefix="paperagent-method-design-prepatch-",
        delete=False,
    )
    path = Path(handle.name)
    try:
        with handle:
            handle.write(source)
        runpy.run_path(str(path), run_name="__main__")
    finally:
        path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
