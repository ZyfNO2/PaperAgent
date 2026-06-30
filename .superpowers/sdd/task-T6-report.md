# Task T6 Report — 3D Support Integration

## Scope
Integrate 3D vision (点云 / RGB-D / 三维重建 / PointNet etc.) into `apps/api/app/services/one_topic.py` so 3D topics no longer get mis-routed to YOLO/U-Net and are not silently dropped.

## Changes Applied (6/6)

| # | Change | Location | Status |
|---|--------|----------|--------|
| 1 | Removed fixed `"ultralytics yolov8 defect detection"` query | `build_search_plan()` eng_en | done |
| 2 | Added 7 3D entries to `_OBJECT_HINTS` (三维成像/三维重建/点云/RGB-D/深度/stereo) | dict def | done |
| 3 | Added 7 3D method entries to `_METHOD_HINTS` (PointNet++/PointRCNN/VoteNet/3DGS/DUSt3R/COLMAP/MVSNet) | dict def | done |
| 4 | Added `_is_3d_topic()` helper (15 indicators: 三维/点云/rgb-d/3d/depth/stereo/colmap/mvsnet/pointnet/votenet/3dgs/dust3r/sfm/mvs/slam/lidar/激光) | module level | done |
| 5 | Added 4 3D datasets to `_heuristic_datasets()` (MVTec 3D-AD / Real3D-AD / ModelNet40 / ScanNet) | function head | done |
| 6 | Added 7 3D baselines to `_heuristic_baselines()` (COLMAP / MVSNet / PointNet++ / VoteNet / OpenPCDet / 3DGS / DUSt3R) | function head, short-circuit before YOLO check | done |

## Smoke Test Result

```
detect OK
3D datasets: ['DS3D01', 'DS3D02', 'DS3D03', 'DS3D04']
3D baselines: ['BL3D01', 'BL3D02', 'BL3D03', 'BL3D04', 'BL3D05', 'BL3D06', 'BL3D07']
non-3D path OK
all checks passed
```

Verified:
- 3D topic detection triggers on 三维重建/点云/RGB-D/PointNet
- 3D topic produces 4 datasets + 7 baselines
- Non-3D topic (YOLO+钢材) still falls through to YOLO path unchanged

## Notes
- YOLO query removal: `eng_en` now uses only the method+object+github template. 3D-specific engineering queries can be added later if needed.
- `_is_3d_topic()` is intentionally a simple substring scan (case-insensitive). Acceptable ceiling: O(n) per topic, fine for the single-call pipeline.
- 3D paths are checked before YOLO/Transformer/BERT branches in `_heuristic_baselines()` — early return prevents any collision.

## Files Modified
- `apps/api/app/services/one_topic.py` (6 hunks)