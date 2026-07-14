"""Quick WP0 baseline validation."""
import json

with open("artifacts/re8_2/baseline/vit_dr_before.json") as f:
    d = json.load(f)

print("=== Gate Results ===")
for g in ("gate_seed_audit_gate", "gate_tailor_gate", "gate_final_review_gate"):
    info = d.get(g, {})
    print(f"{g}:")
    print(f"  verdict={info.get('verdict')}, generated_by={info.get('generated_by')}, round_idx={info.get('round_idx')}")
    if info.get("all_rounds"):
        for r in info["all_rounds"]:
            print(f"  [{r['round_idx']}] {r['verdict']} ({r['generated_by']})")
    print()

print(f"fused_verdict={d.get('fused_verdict')}")
print(f"quality_pass={d.get('quality_pass')}")
print(f"repair_cycles={d.get('repair_cycles_detected')}")
