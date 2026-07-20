from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(relative: str, old: str, new: str) -> None:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"expected one follow-up replacement in {relative}")
    path.write_text(text.replace(old, new), encoding="utf-8")


# License has its own compatibility check; absence is a warning, not a duplicate
# baseline-card completeness error.
replace_once(
    "src/paperagent/academic_methodology.py",
    '''        baseline.source_evidence_id,
        baseline.license,
        baseline.dataset,
''',
    '''        baseline.source_evidence_id,
        baseline.dataset,
''',
)

print("decision-policy follow-up applied")
