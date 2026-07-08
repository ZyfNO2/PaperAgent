"""Quick dataset coverage check."""
import json, os

EVAL_DIRS = ["tmp_re13_eval", "tmp_re34_eval", "tmp_re35_eval", "tmp_re36_eval", "tmp_re38_eval"]

def find_state(case_id):
    for d in EVAL_DIRS:
        p = os.path.join(d, case_id, "state.json")
        if os.path.exists(p):
            return p
    return None

cases = [
    "V-YOLO-33", "V-SLAM-33", "V-MED-33",
    "R34-002", "R34-033", "R34-038", "R34-046", "R34-066", "R34-092",
    "R35-033", "R35-046",
    "R36-003", "R36-007", "R36-015", "R36-021", "R36-052",
    "R36-060", "R36-074", "R36-079", "R36-084", "R36-091", "R36-094", "R36-100",
    "R38-005", "R38-008", "R38-011", "R38-023",
    "R38-014", "R38-075", "R38-076", "R38-083",
    "R38-047", "R38-050", "R38-067",
    "R38-026", "R38-037", "R38-027",
    "R38-006", "R38-004",
]

total = 0
has_dc = 0
has_rc = 0

for cid in cases:
    sp = find_state(cid)
    if not sp:
        continue
    s = json.load(open(sp, encoding="utf-8"))
    dc = len(s.get("dataset_candidates", []))
    rc = len(s.get("repo_candidates", []))
    total += 1
    if dc > 0:
        has_dc += 1
    if rc > 0:
        has_rc += 1
    print(f"{cid:15s}: dc={dc:2d} rc={rc:2d}")

print(f"\nDataset coverage: {has_dc}/{total} = {has_dc/total*100:.0f}%")
print(f"Repo coverage:    {has_rc}/{total} = {has_rc/total*100:.0f}%")
