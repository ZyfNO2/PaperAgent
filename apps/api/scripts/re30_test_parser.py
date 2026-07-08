"""Test topic_parser only — check for domain bias in parsed atoms.

Usage:
    python apps/api/scripts/re30_test_parser.py
"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
os.environ.setdefault('FAST_JSON_PRIMARY', 'deepseek')
os.environ.setdefault('PAPERAGENT_SKIP_SEARCH_PLANNER', 'true')

# Test topics — various crack/defect domains to check for bias
TEST_TOPICS = [
    # Crack topics — should NOT all route to civil_infra/concrete
    ("T1-WOOD",  "基于yolo的木材裂缝识别",          "wood crack → vision_2d, NOT civil_infra"),
    ("T2-STEEL", "基于深度学习的钢材表面缺陷检测研究", "steel defect → vision_2d, NOT civil_infra"),
    ("T3-PCB",   "基于深度学习的pcb焊点缺陷检测",    "PCB solder defect → vision_2d, NOT civil_infra"),
    # Control cases
    ("T4-CROP",  "基于yolo的农作物识别",            "crop → vision_2d"),
    ("T5-INSUL", "基于YOLOv5的绝缘子检测与缺陷识别", "insulator → vision_2d"),
    ("T6-ROAD",  "基于深度学习的道路裂缝检测研究",    "road crack → civil_infra (correct)"),
    ("T7-MED",   "基于大语言模型的医学问答可信度评估", "medical → nlp_llm"),
    ("T8-SLAM",  "基于深度学习的视觉SLAM语义地图的研究","SLAM → vision_3d"),
]


def run_topic_parser(topic: str) -> dict:
    """Run only the topic_parser node, return its output."""
    from apps.api.app.services.agents.graph.nodes.topic_parser import topic_parser_node

    state = {
        "case_id": "test-parser",
        "topic": topic,
        "user_constraints": {"topic_zh": topic},
        "trace_events": [],
        "errors": [],
        "provider_profile": "fast_json",
    }
    result = topic_parser_node(state)
    return result


def analyze_result(case_id: str, topic: str, expectation: str, result: dict) -> dict:
    """Check if the parsed atoms are biased."""
    atoms = result.get("topic_atoms", {})
    method = atoms.get("method", [])
    obj = atoms.get("object", [])
    task = atoms.get("task", [])
    domain = atoms.get("domain", "unknown")
    
    # Collect all English text from atoms for bias check
    all_text = " ".join([
        " ".join(str(m) for m in method),
        " ".join(str(o) for o in obj),
        " ".join(str(t) for t in task),
    ]).lower()
    
    # Also check query_atoms_en if present
    query_en = atoms.get("query_atoms_en", [])
    if query_en:
        all_text += " " + " ".join(query_en).lower()
    
    # Check for bias indicators
    bias_indicators = {
        "concrete": "concrete" in all_text,
        "building": "building" in all_text,
        "civil": "civil" in all_text or domain == "civil_infra",
        "pavement": "pavement" in all_text,
        "bridge": "bridge" in all_text,
    }
    
    # Check if topic itself mentions these (legitimate)
    topic_lower = topic.lower()
    topic_has_concrete = "混凝土" in topic or "concrete" in topic_lower
    topic_has_building = "建筑" in topic or "building" in topic_lower
    topic_has_road = "道路" in topic or "road" in topic_lower
    topic_has_bridge = "桥梁" in topic or "bridge" in topic_lower
    
    # Bias = detected but NOT in topic
    biased = False
    bias_detail = []
    for word, detected in bias_indicators.items():
        if detected:
            in_topic = (word == "concrete" and topic_has_concrete) or \
                       (word == "building" and topic_has_building) or \
                       (word == "civil" and (topic_has_concrete or topic_has_building or topic_has_road or topic_has_bridge)) or \
                       (word == "pavement" and topic_has_road) or \
                       (word == "bridge" and topic_has_bridge)
            if not in_topic:
                biased = True
                bias_detail.append(f'{word}="{detected}" (NOT in topic)')
    
    return {
        "case_id": case_id,
        "topic": topic,
        "expectation": expectation,
        "domain": domain,
        "method": method,
        "object": obj,
        "task": task,
        "query_atoms_en": query_en,
        "biased": biased,
        "bias_detail": bias_detail,
        "pass": not biased,
    }


def main():
    print("=" * 70)
    print("Topic Parser Bias Test")
    print("=" * 70)
    print()
    
    all_pass = True
    for case_id, topic, expectation in TEST_TOPICS:
        print(f"[{case_id}] {topic}")
        print(f"  Expect: {expectation}")
        
        t0 = time.time()
        try:
            result = run_topic_parser(topic)
            elapsed = round(time.time() - t0, 1)
            
            analysis = analyze_result(case_id, topic, expectation, result)
            
            status = "PASS" if analysis["pass"] else "BIAS!"
            if not analysis["pass"]:
                all_pass = False
            
            print(f"  Domain: {analysis['domain']}")
            print(f"  Method: {analysis['method']}")
            print(f"  Object: {analysis['object']}")
            print(f"  Task:   {analysis['task']}")
            if analysis['query_atoms_en']:
                print(f"  Query:  {analysis['query_atoms_en']}")
            if analysis['bias_detail']:
                print(f"  BIAS:   {analysis['bias_detail']}")
            print(f"  [{status}] ({elapsed}s)")
            
        except Exception as exc:
            elapsed = round(time.time() - t0, 1)
            print(f"  ERROR: {type(exc).__name__}: {str(exc)[:200]}")
            print(f"  [FAIL] ({elapsed}s)")
            all_pass = False
        
        print()
    
    print("=" * 70)
    print(f"Overall: {'ALL PASS - No bias detected' if all_pass else 'BIAS DETECTED - review above'}")
    print("=" * 70)


if __name__ == "__main__":
    main()
