"""Test heuristic translation for R39-GAS scenario."""
from apps.api.app.services.agents.graph.nodes.topic_parser import (
    _heuristic_translate,
    _has_chinese,
    _force_translate_keywords,
)

# Test 1: the actual R39-GAS failure case
test_cases = [
    ("瓦斯突出危险性预测", "gas outburst risk prediction"),
    ("煤与瓦斯突出危险性预测", "coal gas outburst risk prediction"),
    ("建筑工程施工安全预警", "construction safety warning"),
    ("卷积神经网络", "convolutional neural network"),
]

print("=== Heuristic translation tests ===")
for cn, expected in test_cases:
    result = _heuristic_translate(cn)
    has_cn = _has_chinese(result)
    print(f"  '{cn}' -> '{result}' (has_chinese={has_cn})")

# Test 2: Full _force_translate_keywords with the R39-GAS atoms
print("\n=== _force_translate_keywords (no LLM needed — heuristic only) ===")
atoms = {
    "method": ["瓦斯突出危险性预测"],
    "object": [],
    "task": [],
    "scenario": [],
    "domain": ["unknown"],
}
result = _force_translate_keywords(atoms)
for key in ("method", "object", "task", "domain"):
    vals = result.get(key, [])
    has_cn = any(_has_chinese(v) for v in vals)
    print(f"  {key}: {vals} (has_chinese={has_cn})")

# Assert no Chinese in output
all_vals = result.get("method", []) + result.get("object", []) + result.get("task", [])
for v in all_vals:
    assert not _has_chinese(v), f"Still has Chinese: {v}"
print("\nOK: all keywords translated to English")
