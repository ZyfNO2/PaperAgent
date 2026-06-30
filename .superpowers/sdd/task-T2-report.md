# Task T2 Report: research_topic_parser.py

## Status: DONE

## What was implemented
Created `apps/api/app/services/research_topic_parser.py` with:

**Public API (2 functions):**
- `parse_topic_rule_based(raw_topic: str) -> dict` — deterministic rule-based parser; no LLM calls.
- `validate_and_repair_llm_output(llm_output: dict, raw_topic: str) -> dict` — validates LLM topic_understand output, repairs common issues, marks `llm_output_repaired` and `domain_route_conflict` flags.

**Domain dictionaries (`DOMAIN_DICTS`):**
9 domains: vision_3d, vision_2d, nlp_llm, signal_timeseries, robotics_control, remote_sensing, medical_ai, energy_power, civil_infra. Each has zh+en `keywords` and canonical `methods` lists (COLMAP/MVSNet/PointNet++/VoteNet/PointRCNN/OpenPCDet/3DGS/DUSt3R/NeRF/FoundationStereo for vision_3d; YOLO/Faster R-CNN/Mask R-CNN/ViT/U-Net/ResNet for vision_2d; BERT/RoBERTa/LLM/LoRA/RAG/ChatGPT/GPT for nlp_llm; LSTM/GRU/FFT for signal; ROS/PID/MPC for robotics).

**Parser internals:**
- `_detect_domain`: score each domain by keyword hits; highest wins; confidence = min(0.95, 0.4 + 0.15*n_hits).
- `_extract_object_terms`: strips leading `基于X的` prefix, removes trailing task verbs, NEVER returns the whole sentence.
- `_build_query_atoms`: maps Chinese task terms to English (检测→detection, 缺陷检测→defect detection, 情感分析→sentiment analysis, etc.), dedupes preserving order.
- `_needs_clarification`: asks for object specifics when object is generic (数据/样本/图像).
- Negative domain enforcement: vision_3d → exclude YOLO/U-Net/BERT; vision_2d → exclude 3DGS/DUSt3R/COLMAP/NeRF; nlp_llm → exclude YOLO/U-Net/PointNet/COLMAP/ResNet.

**Repair logic (`validate_and_repair_llm_output`):**
1. Fill missing schema fields from rule-based parse.
2. If `object_terms == raw_topic`, re-extract from rule-based.
3. If LLM `domain_route` conflicts with method keyword hints (e.g. LLM said vision_2d but methods contain COLMAP), override domain and refresh negative_domains.
4. If domain_route=unknown but rule-based has confidence ≥0.5, use rule-based.
5. Mark `llm_output_repaired=True` and `domain_route_conflict=True` as needed.

## Test approach
Embedded `__main__` self-check (assert-based, no pytest required). All 4 checks passed:
- T1: "基于三维成像的损伤智能检测" → vision_3d, object_terms ≠ whole sentence
- T2: "基于YOLO的钢材表面缺陷检测" → vision_2d, negative_domains ⊇ {3DGS, DUSt3R, COLMAP}, method_terms ⊇ {YOLO}
- T3: "基于大语言模型的中文舆情情感分析" → nlp_llm, negative_domains ⊇ {YOLO, U-Net, PointNet, COLMAP}
- Repair: LLM returns object_terms == raw_topic → repair splits it

Run: `cd apps/api && python -m app.services.research_topic_parser`

## Concerns
None. Module is self-contained, no LLM dependency, pure deterministic logic. Downstream caller `research_planner_agent.py` (T5) can import and merge parse output with LLM topic_understand output via `validate_and_repair_llm_output`.