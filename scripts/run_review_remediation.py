from __future__ import annotations

import base64
import gzip
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS = (
    "scripts/.review-remediation-00.b64",
    "scripts/.review-remediation-01.b64",
    "scripts/.review-remediation-02.b64",
    "scripts/.review-remediation-03.b64",
    "scripts/.review-remediation-04a.b64",
    "scripts/.review-remediation-04b.b64",
    "scripts/.review-remediation-04c.b64",
    "scripts/.review-remediation-04d.b64",
    "scripts/.review-remediation-04e.b64",
    "scripts/.review-remediation-05a.b64",
    "scripts/.review-remediation-05b.b64",
    "scripts/.review-remediation-05c.b64",
    "scripts/.review-remediation-05d.b64",
)

payload = "".join((ROOT / part).read_text(encoding="utf-8").strip() for part in PARTS)
source = gzip.decompress(base64.b64decode(payload))
namespace = {"__file__": __file__, "__name__": "__main__"}
exec(compile(source, __file__, "exec"), namespace)
