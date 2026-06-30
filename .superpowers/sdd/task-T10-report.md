# T10 Report: S63 backend tests for topic-driven retrieval

**Status:** PASSED — 13/13 tests green in 0.25s.

## Coverage

| Test | Verifies |
|------|----------|
| `test_3d_imaging_topic_keyword_atoms` | vision_3d domain routing + risk/object term parsing |
| `test_object_terms_not_whole_sentence` | object_terms never equals raw_topic (3 topics) |
| `test_yolo_steel_topic_routes_to_vision_2d` | vision_2d routing + YOLO method + 3D exclusion |
| `test_nlp_llm_topic_routes_correctly` | nlp_llm routing + sentiment task + vision exclusion |
| `test_3d_imaging_query_pack_has_18_plus_queries` | ≥18 queries + 3DGS + DUSt3R present |
| `test_yolo_query_pack_excludes_3d_methods` | YOLO pack lacks 3DGS/DUSt3R/COLMAP/NeRF |
| `test_topic_change_changes_query_pack` | 3D ≠ YOLO ≠ NLP query packs (repo_queries diff) |
| `test_3d_imaging_datasets_include_3d_ad` | DATASET_CATALOG vision_3d has MVTec 3D-AD or Real3D-AD |
| `test_vision_2d_datasets_include_neu_det` | vision_2d has NEU-DET |
| `test_nlp_llm_datasets_include_chnsenti` | nlp_llm has ChnSentiCorp |
| `test_3d_imaging_baselines_include_classic_and_emerging` | COLMAP + PointNet++/OpenPCDet + 3DGS/DUSt3R |
| `test_yolo_steel_topic_does_not_leak_3dgs` | vision_2d baselines lack 3DGS/DUSt3R/FoundationStereo |
| `test_nlp_llm_topic_generates_text_route` | nlp_llm baselines have BERT/RoBERTa, lack YOLOv8/PointNet++ |

## Key invariants asserted

1. **Cross-domain isolation**: vision_3d topic → 3DGS/DUSt3R/COLMAP **in pack**, YOLO/PointNet **excluded**.
   vision_2d topic → YOLO **in pack**, 3DGS/DUSt3R/FoundationStereo **excluded**.
   nlp_llm topic → BERT/RoBERTa **in baselines**, YOLO/PointNet/COLMAP **excluded**.

2. **Negative-domain enforcement**: `negative_domains` populated per topic (3D/YOLO/NLP each get a
   hard-coded exclusion list in the parser — see `research_topic_parser.py:317-322`).

3. **object_terms != raw_topic**: the parser strips `基于X的` prefix and walks back through task
   verbs (检测/分析/诊断), so the object head is always shorter than the raw sentence.

4. **Query pack ≥18**: `rule_fill_query_pack` for 3D already generates ~22 queries across 6 buckets
   (paper/dataset/repo/baseline/classic_tool/emerging_method); no `ensure_minimum_queries` needed
   in fallback path for 3D topic.

## Adjustments from the spec template

- Replaced `result["detected_domain"]` with `result["domain_route"]` (actual field name in the parser).
- The spec's `test_3d_imaging_query_pack_has_18_plus_queries` asserted only "no fixed YOLO"; I
  additionally asserted 3DGS + DUSt3R presence (positive-domain coverage). Defense-in-depth.
- Split the original 8-case spec into 13 tests so each invariant is named and isolated.

## Files touched

- `apps/api/tests/test_session63_topic_driven_retrieval.py` (new, 13 tests)

## Run command

```bash
cd apps/api && python -m pytest tests/test_session63_topic_driven_retrieval.py -v
```

→ 13 passed in 0.25s.
