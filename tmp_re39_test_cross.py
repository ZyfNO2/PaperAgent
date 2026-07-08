"""Test cross-node dataset scan."""
from apps.api.app.services.agents.graph.nodes.innovation_extractor import _cross_node_dataset_scan

existing = []
inn = [{"description": "We use NEU-DET and KITTI for evaluation", "stitching_plan": ""}]
plan = {"baseline_model": "YOLO", "stitching_steps": []}

new = _cross_node_dataset_scan(inn, plan, existing)
print(f"Found {len(new)} datasets")
for d in new:
    print(f"  name={d['name']} source={d['source']}")
assert len(new) == 2, f"Expected 2, got {len(new)}"
assert new[0]["source"] == "cross_node:innovation_extractor"
print("OK: cross-node dataset scan works")
