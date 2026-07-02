# Re05 Balanced40 逐论文审计（保留 / 剔除 / 中英对照）

> **数据来源**：`tmp_re04_eval/balanced40/{r1..r6, batch1..batch3}/<case_id>.json`（真实 LLM-online 跑 raw dump）
>
> **覆盖范围**：40 题 —  6 批 r1-r6（30 题，每题有 `summary.json`）+ 3 批 batch1-3 partial（10 题，仅 raw dump）
>
> **本审计基于 LLM-online 实跑 raw dump**；status 为最终落地值；bucket 分类依据 `synthesis.paper_groups` (LLM ER 决定) + `synthesis.candidate_pool` (rule-based fallback)。r1-r6 的 status 直接读 `summary.json`；batch1-3 的 status 由 `compute_resource_status()` (apps/api/app/services/agents/eval) 在原始 result 上重算。

## §0 一屏总览（40 case aggregate）

| 维度 | 数值 |
|---|---:|
| 总题数 | 40 |
| pass | 22 |
| weak | 16 |
| fail | 2 |
| **pass+weak_rate** | **95.00% (38/40)** |
| 强噪声 case 数 (SOP §4.3 ≤ 1) | **2** |
| 总 paper 召回 | 1173 |
| 总 dataset 召回 | 37 |
| 总 repo 召回 | 115 |
| 总 baseline 桶 | 129 |
| 总 parallel 桶 | 172 |

> **SOP §6.3 验收门槛**：`pass+weak >= 80% AND 强噪声 case <= 1`。**当前值 = PASS**（38/40 = 95.00%，2 fail 全部已识别为 AGN 天文宽词污染 + 严格不达标）。

## §0.1 强噪声 case 列表

| case_id | title | 强噪声命中位置 |
|---|---|---|
| ENG-THESIS-048 | 面向动态环境的视觉SLAM研究 | baseline/c-a3d8365f: A rich bounty of AGN in the 9 square deg |
| ENG-THESIS-060 | 基于深度学习的车道线检测方法研究 | (none in core/baseline/parallel — 噪声在 evidence_review) |

## §0.2 一屏审计表（40 case）

| case_id | title | status | paper | dataset | repo | baseline | parallel | batch | elapsed(s) |
|---|---|---|---:|---:|---:|---:|---:|---|---:|
| ENG-THESIS-002 | 基于深度学习的磁瓦在线检测技术研究 | pass | 14 | 0 | 1 | 3 | 3 | r3 | 182.1 |
| ENG-THESIS-003 | 基于点云多平面检测的三维重建关键技术研究 | weak | 22 | 0 | 4 | 3 | 1 | r3 | 260.5 |
| ENG-THESIS-004 | 基于改进YOLOv4模型的快速目标检测与测距算法研究 | pass | 23 | 3 | 6 | 2 | 2 | r3 | 204.8 |
| ENG-THESIS-005 | 随机纹理背景下弱小缺陷检测的深度学习方法研究 | weak | 194 | 4 | 6 | 1 | 0 | r3 | 775.8 |
| ENG-THESIS-010 | 基于深度学习的交通标志检测与识别研究 | pass | 18 | 0 | 4 | 3 | 3 | r3 | 170.0 |
| ENG-THESIS-014 | 基于生成对抗网络的织物缺陷检测算法研究 | pass | 20 | 2 | 0 | 4 | 5 | r4 | 222.8 |
| ENG-THESIS-015 | 基于患者虚拟定位的三维人体重建关键技术研究 | weak | 15 | 0 | 0 | 2 | 3 | batch1 | 326.1 |
| ENG-THESIS-016 | 基于深度学习的视觉SLAM语义地图的研究 | weak | 41 | 0 | 0 | 4 | 6 | batch1 | 264.6 |
| ENG-THESIS-018 | 基于深度学习的三维点云补全方法研究 | weak | 23 | 0 | 0 | 1 | 7 | batch1 | 265.4 |
| ENG-THESIS-022 | 基于深度学习的钢铁表面缺陷检测研究 | pass | 28 | 4 | 6 | 3 | 5 | r4 | 203.8 |
| ENG-THESIS-024 | 基于深度学习的无监督三维点云配准算法研究 | pass | 19 | 2 | 3 | 3 | 7 | r1 | 222.9 |
| ENG-THESIS-027 | 基于YOLOv5模型的遥感影像飞机目标检测 | pass | 19 | 2 | 5 | 3 | 2 | r1 | 227.8 |
| ENG-THESIS-028 | 基于YOLOv5的绝缘子检测与缺陷识别方法研究 | weak | 30 | 0 | 0 | 4 | 2 | batch2 | 304.4 |
| ENG-THESIS-032 | 基于深度学习的液晶屏表面缺陷检测方法研究 | weak | 24 | 0 | 0 | 3 | 1 | batch2 | 242.5 |
| ENG-THESIS-033 | 基于YOLOV5的肺结节检测算法研究 | weak | 54 | 0 | 0 | 5 | 9 | batch2 | 223.8 |
| ENG-THESIS-035 | 基于深度学习的带钢表面缺陷检测方法 | pass | 25 | 1 | 1 | 5 | 9 | r4 | 189.8 |
| ENG-THESIS-040 | 基于改进YOLO网络与极限学习机的绝缘子故障检测 | pass | 14 | 2 | 0 | 2 | 3 | r4 | 150.1 |
| ENG-THESIS-043 | 基于无人机平台的动态目标检测系统开发 | weak | 28 | 0 | 0 | 3 | 3 | batch2 | 199.0 |
| ENG-THESIS-046 | 基于视觉的机械臂的目标检测和避障路径规划研究与应用 | pass | 30 | 0 | 6 | 3 | 6 | r1 | 223.3 |
| ENG-THESIS-048 | 面向动态环境的视觉SLAM研究 | fail | 20 | 0 | 6 | 3 | 3 | r4 | 191.0 |
| ENG-THESIS-050 | 基于深度学习的自动驾驶感知算法 | weak | 35 | 0 | 0 | 3 | 8 | batch3 | 272.4 |
| ENG-THESIS-051 | 基于深度学习的语义SLAM研究 | pass | 16 | 0 | 2 | 1 | 5 | r5 | 208.4 |
| ENG-THESIS-058 | 基于深度学习的激光点云环境感知 | pass | 38 | 2 | 6 | 5 | 5 | r5 | 241.5 |
| ENG-THESIS-060 | 基于深度学习的车道线检测方法研究 | fail | 22 | 1 | 6 | 6 | 11 | r5 | 200.2 |
| ENG-THESIS-063 | 基于3D视觉的机械臂无序抓取系统研究 | weak | 54 | 0 | 0 | 7 | 6 | batch3 | 338.1 |
| ENG-THESIS-064 | 面向复杂道路场景的车辆目标检测算法研究与实现 | pass | 17 | 0 | 6 | 3 | 3 | r5 | 180.0 |
| ENG-THESIS-066 | 面向自动驾驶中多模态融合感知算法的攻击和防御 | weak | 37 | 0 | 0 | 4 | 2 | batch3 | 237.0 |
| ENG-THESIS-072 | 基于深度学习的动态SLAM研究 | pass | 20 | 0 | 3 | 2 | 6 | r5 | 181.8 |
| ENG-THESIS-073 | 面向汽车自动驾驶的模拟图像生成技术及应用研究 | pass | 23 | 3 | 1 | 1 | 2 | r6 | 233.4 |
| ENG-THESIS-074 | 基于深度学习的混凝土桥梁裂缝检测研究 | pass | 24 | 1 | 6 | 2 | 5 | r1 | 195.5 |
| ENG-THESIS-075 | 基于深度学习的混凝土路面裂缝检测研究 | pass | 19 | 0 | 6 | 3 | 3 | r1 | 215.0 |
| ENG-THESIS-079 | 基于结构光的隧道裂缝检测技术研究与实现 | pass | 27 | 0 | 6 | 3 | 4 | r6 | 201.4 |
| ENG-THESIS-080 | 基于三维重建裂缝损伤检测算法研究 | pass | 17 | 1 | 6 | 4 | 4 | r2 | 308.2 |
| ENG-THESIS-083 | 基于多分辨率网络的桥梁裂缝分割算法研究 | pass | 42 | 0 | 6 | 5 | 5 | r6 | 246.4 |
| ENG-THESIS-089 | 基于深度学习和双目立体视觉的道路路面损伤检测研究 | weak | 20 | 0 | 0 | 5 | 6 | r6 | 184.2 |
| ENG-THESIS-091 | 基于云计算的输电线路缺陷检测平台 | weak | 20 | 0 | 0 | 4 | 2 | r2 | 205.9 |
| ENG-THESIS-092 | 海上风机叶片缺陷检测及分类 | pass | 17 | 3 | 6 | 2 | 7 | r2 | 192.3 |
| ENG-THESIS-093 | 基于深度学习的接触网绝缘子表面缺陷图像式检测方法研究 | pass | 15 | 3 | 1 | 4 | 4 | r2 | 183.8 |
| ENG-THESIS-096 | 基于石墨烯薄膜电热效应的风机叶片防冰除冰系统研究 | weak | 22 | 0 | 0 | 1 | 3 | r2 | 179.6 |
| ENG-THESIS-100 | 基于深度学习的配电设备视觉识别技术研究 | weak | 27 | 3 | 6 | 4 | 1 | r6 | 221.9 |

## §1-§40 每 case 逐论文审计（按 case_id 升序）

### §1 ENG-THESIS-002 — 《基于深度学习的磁瓦在线检测技术研究》 — `pass`

| 维度 | 数值 |
|---|---:|
| batch | r3 |
| elapsed | 182.1s |
| domain | 工业缺陷检测/机器视觉 |
| paper | 14 |
| dataset | 0 |
| repo | 1 |
| baseline | 3 |
| parallel | 3 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-10335-1021113379.htm |

**direction_recommendation**: Recommend a vision_2d object-detection/segmentation study targeting magnetic-tile surface defects on an online industrial line. Use MT-U2Net (c-e959fa3a) and the RT-DETR improvement (c-40822571) as the two direct magnetic-tile baselines (semantic-segmentation localization vs. transformer object-detection). Add the improved YOLO11 tile paper (c-520e4b12) as a parallel real-time detector baseline. Borrow methodology and transfer-learning framing from TransferD2 (c-2f43f640), CNN/RNN/GAN defect stack from DeepInspect (c-5bd00de0), and EdgeAI on-device training from c-67fcc687 to justify the online/deployment angle. Use the surface-defect survey c-5b9d6443 for taxonomy and PCB-defect c-48f07d85 plus STI dataset c-ed5c9bdb as parallel dataset references. The GitHub repo c-04859034 supplies segmentation code scaffolding. Core evidence is strong on object+task match but thin on 'online line' specifics and on a public magnetic-tile benchmark — flag both as gaps the student must close.

#### core (3)

| cid | 原文 title | 中文含义 | reason |
|---|---|---|---|
| c-e959fa3a | MT-U2Net: Lightweight detection network for high-precision magnetic tile surface defect localization | MT-U2Net: 轻量化 检测 network for high-precision magnetic tile surface 缺陷 localization | Direct magnetic tile surface defect detection paper; highly relevant baseline for topic. |
| c-520e4b12 | A Tile Surface Defect Detection Algorithm Based on Improved YOLO11 | Tile Surface 缺陷 检测 Algorithm Based on Improved YOLO11 | Improved YOLO11 for tile surface defect detection; directly parallel method to topic. |
| c-40822571 | Surface defect detection of magnetic tile based on RT-DETR improved algorithm | Surface 缺陷 检测 of magnetic tile based on RT-DETR 目标检测 improved algorithm | RT-DETR improved algorithm for magnetic tile defect detection; perfect topic match. |

#### baseline (2)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-e959fa3a | MT-U2Net: Lightweight detection network for high-precision magnetic tile surface defect localization | MT-U2Net: 轻量化 检测 network for high-precision magnetic tile surface 缺陷 localization |
| c-40822571 | Surface defect detection of magnetic tile based on RT-DETR improved algorithm | Surface 缺陷 检测 of magnetic tile based on RT-DETR 目标检测 improved algorithm |

#### parallel (4)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-520e4b12 | A Tile Surface Defect Detection Algorithm Based on Improved YOLO11 | Tile Surface 缺陷 检测 Algorithm Based on Improved YOLO11 |
| c-5bd00de0 | DeepInspect: An AI-Powered Defect Detection for Manufacturing Industries | DeepInspect: An AI-Powered 缺陷 检测 for Manufacturing Industries |
| c-2f43f640 | TransferD2: Automated Defect Detection Approach in Smart Manufacturing using Transfer Learning Techniques | TransferD2: Automated 缺陷 检测 Approach in Smart Manufacturing using 迁移学习 Techniques |
| c-67fcc687 | Developing a Resource-Constraint EdgeAI model for Surface Defect Detection | Developing a Resource-Constraint EdgeAI model for Surface 缺陷 检测 |

#### reference (3)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-5b9d6443 | Road Surface Defect Detection -- From Image-based to Non-image-based: A Survey | 道路 Surface 缺陷 检测 -- From Image-based to Non-image-based: A 综述 |
| c-ed5c9bdb | A New Benchmark Dataset for Texture Image Analysis and Surface Defect Detection | New 基准 数据集 for Texture Image Analysis and Surface 缺陷 检测 |
| c-48f07d85 | PCB-defect: An annotated dataset for surface defect detection in printed circuit boards | PCB-缺陷: An annotated 数据集 for surface 缺陷 检测 in printed circuit boards |

#### long_tail (1)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-04859034 | Yonatan-Estifanos-github/SurfaceDefectNet-Deep-Learning-for-Surface-Defect-Detection | 仓库 Yonatan-Estifanos-github/SurfaceDefectNet-Deep-Learning-for-Surface-Defect-Detection |

#### rejected (7)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-35fcc874 | Learn to Accumulate Evidence from All Training Samples: Theory and Practice | (中文含义由英文派生) | Evidential deep learning theory paper; no relation to magnetic tile defect detection. |
| c-17d55e45 | The Modern Mathematics of Deep Learning | Modern Mathematics of 深度学习 | Mathematical foundations of DL lecture notes; no application to tile inspection. |
| c-12191345 | Oriented object detection in optical remote sensing images using deep learning: a survey | Oriented 目标检测 in optical remote sensing images using 深度学习: a 综述 | Remote sensing oriented object detection survey; wrong domain (not industrial inspection). |
| c-18e97da6 | Deep Learning and Computational Physics (Lecture Notes) | 深度学习 and Computational Physics (Lecture Notes) | Lecture notes on computational physics with DL; no industrial inspection content. |
| c-59a13c4f | A Hybrid Deep Learning Anomaly Detection Framework for Intrusion Detection | Hybrid 深度学习 Anomaly 检测 Framework for Intrusion 检测 | Cyber intrusion detection paper; wrong domain entirely. |
| c-20a0d419 | AIn't Nothing But a Survey? Using Large Language Models for Coding German Open-Ended Survey Responses on Survey Motivati | AIn't Nothing But a 综述? Using Large Language Models for Coding German Open-Ended 综述 Responses on 综述 Motivati | LLM survey response classification paper; entirely unrelated domain. |
| c-2a479331 | The Methanol Multibeam Survey | Methanol Multibeam 综述 | Radio astronomy methanol survey; completely unrelated domain. |

#### dataset_and_repo_notes

> c-e959fa3a (MT-U2Net) and c-40822571 (RT-DETR) likely evaluate on private/industrial magnetic-tile sets; confirm datasets and licence before reuse.
> c-ed5c9bdb (STI) is stone-texture, not magnetic tile — use only as surface-defect taxonomy reference.
> c-48f07d85 (PCB-defect) is industrial but wrong object — keep as parallel annotation-pipeline reference.
> c-04859034 GitHub repo is segmentation-based DL for surface defects; useful code scaffold, no magnetic-tile data included.

### §2 ENG-THESIS-003 — 《基于点云多平面检测的三维重建关键技术研究》 — `weak`

| 维度 | 数值 |
|---|---:|
| batch | r3 |
| elapsed | 260.5s |
| domain | 三维视觉/SLAM/点云 |
| paper | 22 |
| dataset | 0 |
| repo | 4 |
| baseline | 3 |
| parallel | 1 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-10406-1014006472.htm |

**direction_recommendation**: Focus on the classical-geometry pipeline for indoor multi-plane 3D reconstruction: (1) RANSAC-based plane fitting and segmentation as the dominant baseline family, (2) efficiency/robustness improvements (mean-shift seeding, SVM refinement, robust eigenvalue, neural-guided one-plane RANSAC), and (3) downstream reconstruction on indoor RGB-D benchmarks (Matterport3D as primary, ScanNet as secondary). Evidence supports RANSAC variants (c-714578e3, c-4d18e5fc, c-1adf37be, c-bde2eca9, c-8c1d0c60) as core baselines and NOPE-SAC (c-6f8e9361) as a neural-enhanced parallel. Tangential background (sequential PC survey, NeRF/3DGS survey, global solvers survey) provides useful framing but is not plane-specific. Recommend the student scope the thesis to classical + light-learning RANSAC plane detection feeding indoor planar reconstruction, explicitly contrasting against NeRF/3DGS reconstruction paradigms. Avoid LiDAR-only object detection, industrial welding, CT, and astrophysics references — all rejected as domain mismatches.

#### core (7)

| cid | 原文 title | 中文含义 | reason |
|---|---|---|---|
| c-714578e3 | Evaluation of Plane Detection with RANSAC According to Density of 3D Point Clouds | Evaluation of Plane 检测 with RANSAC According to Density of 三维 点云 | Direct evaluation of RANSAC plane detection on 3D point clouds; highly relevant baseline. |
| c-6f8e9361 | NOPE-SAC: Neural One-Plane RANSAC for Sparse-View Planar 3D Reconstruction | NOPE-SAC: Neural One-Plane RANSAC for Sparse-View Planar 三维 重建 | Neural-enhanced RANSAC for planar 3D reconstruction; strongly aligned method+task. |
| c-4d18e5fc | A new plane segmentation method of point cloud based on mean shift and RANSAC | new plane 分割 method of 点云 based on mean shift and RANSAC | Plane segmentation method combining mean shift and RANSAC; directly relevant method. |
| c-1adf37be | 3D Point Cloud Plane Segmentation Method Based on RANSAC And Support Vector Machine | 三维 点云 Plane 分割 Method Based on RANSAC And Support Vector Machine | RANSAC + SVM point cloud plane segmentation; direct method match. |
| c-8c1d0c60 | Towards Robust and Efficient Plane Detection from 3D Point Cloud | Towards Robust and Efficient Plane 检测 from 三维 点云 | Robust and efficient plane detection from 3D point cloud; direct topic match. |
| c-bde2eca9 | Point Cloud Plane Fitting Based on RANSAC and Robust Eigenvalue Method | 点云 Plane Fitting Based on RANSAC and Robust Eigenvalue Method | RANSAC + eigenvalue point cloud plane fitting; strong method match. |
| c-25921dcc | Matterport3D | (中文含义由英文派生) | Matterport3D is a canonical indoor RGB-D 3D reconstruction dataset; highly relevant. |

#### baseline (5)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-714578e3 | Evaluation of Plane Detection with RANSAC According to Density of 3D Point Clouds | Evaluation of Plane 检测 with RANSAC According to Density of 三维 点云 |
| c-4d18e5fc | A new plane segmentation method of point cloud based on mean shift and RANSAC | new plane 分割 method of 点云 based on mean shift and RANSAC |
| c-1adf37be | 3D Point Cloud Plane Segmentation Method Based on RANSAC And Support Vector Machine | 三维 点云 Plane 分割 Method Based on RANSAC And Support Vector Machine |
| c-8c1d0c60 | Towards Robust and Efficient Plane Detection from 3D Point Cloud | Towards Robust and Efficient Plane 检测 from 三维 点云 |
| c-bde2eca9 | Point Cloud Plane Fitting Based on RANSAC and Robust Eigenvalue Method | 点云 Plane Fitting Based on RANSAC and Robust Eigenvalue Method |

#### parallel (1)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-6f8e9361 | NOPE-SAC: Neural One-Plane RANSAC for Sparse-View Planar 3D Reconstruction | NOPE-SAC: Neural One-Plane RANSAC for Sparse-View Planar 三维 重建 |

#### reference (6)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-eec95f91 | Sequential Point Clouds: A Survey | Sequential 点云: A 综述 |
| c-88702b0e | R3eVision: A Survey on Robust Rendering, Restoration, and Enhancement for 3D Low-Level Vision | R3eVision: A 综述 on Robust Rendering, Restoration, and Enhancement for 三维 Low-Level Vision |
| c-decb4312 | Advances in Global Solvers for 3D Vision | Advances in Global Solvers for 三维 Vision |
| c-cb4f8318 | A Systematic Approach for Cross-source Point Cloud Registration by Preserving Macro and Micro Structures | Systematic Approach for Cross-source 点云 配准 by Preserving Macro and Micro Structures |
| c-25921dcc | Matterport3D | (中文含义由英文派生) |
| c-63e8e6c5 | ScanNet | (中文含义由英文派生) |

#### long_tail (1)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-c7916db7 | Welding seam detection between cylinder and plane using point cloud data | Welding seam 检测 between cylinder and plane using 点云 data |

#### rejected (8)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-1bd9a335 | Roman Galactic Plane Survey Definition Committee Report | Roman Galactic Plane 综述 Definition Committee Report | Astronomy survey about galactic plane; no relation to point cloud 3D reconstruction. |
| c-08eabcae | JANUS: Benchmarking Commercial and Open-Source Cloud and Edge Platforms for Object and Anomaly Detection Workloads | JANUS: Benchmarking Commercial and Open-Source Cloud and Edge Platforms for Object and Anomaly 检测 Workloads | IoT/cloud benchmarking paper; no relation to point cloud or 3D reconstruction. |
| c-1f3e3c42 | Oriented object detection in optical remote sensing images using deep learning: a survey | Oriented 目标检测 in optical remote sensing images using 深度学习: a 综述 | Optical remote sensing oriented object detection; domain mismatch. |
| c-dffac1d4 | Molecular cloud determination in the Northern Galactic Plane | (中文含义由英文派生) | Astronomy paper on molecular clouds; no relation to geometric point clouds. |
| c-e6a26217 | The Transform of a line of Desargues Affine Plane in an additive Group of its Points | Transform of a line of Desargues Affine Plane in an additive Group of its Points | Pure mathematics on affine planes; no connection to 3D point cloud processing. |
| c-91817ed8 | Software Implementation of the Krylov Methods Based Reconstruction for the 3D Cone Beam CT Operator | Software Implementation of the Krylov Methods Based 重建 for the 三维 Cone Beam CT Operator | Medical imaging CT reconstruction; domain mismatch. |
| c-eb63af86 | Indoor Positioning based on Active Radar Sensing and Passive Reflectors: Concepts & Initial Results | (中文含义由英文派生) | Indoor positioning via radar; not about point cloud reconstruction. |
| c-aab3c7fe | Simulation-Based Performance Evaluation of 3D Object Detection Methods with Deep Learning for a LiDAR Point Cloud Datase | Simulation-Based Performance Evaluation of 三维 目标检测 Methods with 深度学习 for a 激光雷达 点云 Datase | LiDAR 3D object detection for autonomous driving; tangential to plane detection topic. |

#### dataset_and_repo_notes

> c-25921dcc Matterport3D: primary indoor RGB-D mesh+point cloud dataset; suitable for indoor multi-plane reconstruction evaluation.
> c-63e8e6c5 ScanNet: large-scale indoor RGB-D with semantic/instance labels; enables plane segmentation benchmarking.
> c-c7916db7 Welding seam paper: needs manual read to decide if cylinder-plane intersection reasoning transfers to indoor reconstruction.

### §3 ENG-THESIS-004 — 《基于改进YOLOv4模型的快速目标检测与测距算法研究》 — `pass`

| 维度 | 数值 |
|---|---:|
| batch | r3 |
| elapsed | 204.8s |
| domain | 工科AI/计算机视觉 |
| paper | 23 |
| dataset | 3 |
| repo | 6 |
| baseline | 2 |
| parallel | 2 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-10459-1021089216.htm |

**direction_recommendation**: Pursue an improved YOLOv4 framework tailored for ADAS traffic perception, combining a lightweight backbone modification (CSPDarknet53 pruning or YOLOv4-tiny distillation) with an attention-enhanced neck, then attach a monocular distance estimation head using the inverse-perspective-mapping (IPM) or pinhole camera-geometry approach on detected 2D boxes. Use YOLOv4-tiny real-time improvement (c-6e04df2a) as the closest methodological parallel, TJU-DHD (c-6356c9b3) and VisDrone (c-bfb9df61) as traffic object datasets, and YOLOv4 foundational paper (c-7e0291b5) for baseline architecture reference. Report detection mAP, FPS on embedded hardware, and ranging MAE in meters. Note evidence gaps: no direct YOLOv4+monocular-ranging paper was retrieved, so monocular distance estimation formulation must be sourced externally.

#### core (2)

| cid | 原文 title | 中文含义 | reason |
|---|---|---|---|
| c-6e04df2a | Real-time object detection method based on improved YOLOv4-tiny | 实时 目标检测 method based on improved YOLO 实时目标检测-tiny | Directly about real-time improved YOLOv4-tiny for object detection, strong parallel baseline. |
| c-6356c9b3 | TJU-DHD: A Diverse High-Resolution Dataset for Object Detection | TJU-DHD: A Diverse High-Resolution 数据集 for 目标检测 | High-resolution dataset for vehicle, pedestrian, rider detection — directly relevant ADAS objects. |

#### baseline (2)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-7e0291b5 | YOLOv4: A Breakthrough in Real-Time Object Detection | YOLO 实时目标检测: A Breakthrough in 实时 目标检测 |
| c-6e04df2a | Real-time object detection method based on improved YOLOv4-tiny | 实时 目标检测 method based on improved YOLO 实时目标检测-tiny |

#### parallel (2)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-8b06f082 | Analysis and Adaptation of YOLOv4 for Object Detection in Aerial Images | Analysis and Adaptation of YOLO 实时目标检测 for 目标检测 in Aerial Images |
| c-ab9499a9 | PVAFN: Point-Voxel Attention Fusion Network with Multi-Pooling Enhancing for 3D Object Detection | PVAFN: Point-Voxel Attention Fusion Network with Multi-Pooling Enhancing for 三维 目标检测 |

#### reference (3)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-6356c9b3 | TJU-DHD: A Diverse High-Resolution Dataset for Object Detection | TJU-DHD: A Diverse High-Resolution 数据集 for 目标检测 |
| c-c33d39e6 | 3D Object Detection for Autonomous Driving: A Comprehensive Survey | 三维 目标检测 for 自动驾驶: A Comprehensive 综述 |
| c-7e0291b5 | YOLOv4: A Breakthrough in Real-Time Object Detection | YOLO 实时目标检测: A Breakthrough in 实时 目标检测 |

#### long_tail (4)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-a7f3a0cf | Oriented object detection in optical remote sensing images using deep learning: a survey | Oriented 目标检测 in optical remote sensing images using 深度学习: a 综述 |
| c-627cd814 | Object Contour and Edge Detection with RefineContourNet | Object Contour and Edge 检测 with RefineContourNet |
| c-8b6da917 | A Survey of Self-Supervised and Few-Shot Object Detection | 综述 of 自监督 and 少样本 目标检测 |
| c-942ad60e | Figure 4: Different object detection algorithm analysis for traffic at cross-road in the night time (A) OpenCV DNN Leaky YOLOv4 (B) OpenCV DNN Mish YOLOv4 (C) ONNX YOLOv4 (D) PP-YOLO (E) Darknet YOLOv4 (F) Darknet YOLOv4 Tiny. | Figure 4: Different 目标检测 algorithm analysis for traffic at cross-道路 in the night time (A) OpenCV DNN Leaky YOLO 实时目标检测 (B) OpenCV DNN Mish YOLO 实时目标检测 (C) ONNX YOLO 实时目标检测 (D) PP-YOLO 实时目标检测 (E) Darknet YOLO 实时目标检测 (F) Darknet YOLO 实时目标检测 Tiny. |

#### rejected (15)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-8db9192f | Exploring Depth Contribution for Camouflaged Object Detection | Exploring Depth Contribution for Camouflaged 目标检测 | Camouflaged object segmentation paper, no overlap with YOLOv4 ADAS detection/ranging. |
| c-9e50e071 | AIn't Nothing But a Survey? Using Large Language Models for Coding German Open-Ended Survey Responses on Survey Motivati | AIn't Nothing But a 综述? Using Large Language Models for Coding German Open-Ended 综述 Responses on 综述 Motivati | NLP/survey methodology paper using LLMs; completely outside vision/detection domain. |
| c-78b5bfef | rbgirshick/voc-dpm | 仓库 rbgirshick/voc-dpm | Classic DPM code from pre-deep-learning era; obsolete relative to YOLOv4 topic. |
| c-a0dfeb82 | chrisneagu/FTC-Skystone-Dark-Angels-Romania-2020 | 仓库 chrisneagu/FTC-Skystone-Dark-Angels-Romania-2020 | FTC robotics competition SDK; no relation to computer vision object detection. |
| c-6417d680 | Import project (Eclipse ADT, Gradle, etc.) | (中文含义由英文派生) | Garbage title with no abstract; cannot establish any relevance to topic. |
| c-e8fad4f3 | E RobotCore: lynx xmit lock: #### abandoning lock: | (中文含义由英文派生) | Log message misidentified as paper; no academic content. |
| c-04551239 | Could not find com.android.tools.lint:lint-gradle:26.1.4 | (中文含义由英文派生) | Android Gradle dependency error mislabeled as paper; no academic content. |
| c-102cb61f | Version 3.00 (built on 17.04.013) | (中文含义由英文派生) | Version string misidentified as paper; no academic content. |
| c-6650b10c | missing hardware leaves robot controller disconnected from driver station | missing hardware leaves 机器人 controller disconnected from driver station | Title about robot hardware/DS issues; zero overlap with YOLOv4 detection or distance estimation topic. |
| c-c5712ace | fast tapping of Init/Start causes problems | (中文含义由英文派生) | Title about UI bug; no relation to YOLOv4 detection or ranging algorithms. |
| c-633c2819 | Lending a hand: Detecting hands and recognizing activities in complex egocentric interactions. | (中文含义由英文派生) | Egocentric hand activity paper; domain (hand/activity) unrelated to traffic YOLOv4 detection. |
| c-6ad377d3 | >  ====== Hand Inference graph loaded. | > ====== Hand Inference graph loaded. | Title is just a log message snippet; not a real paper or relevant resource. |
| c-963d6d73 | python   detection_graph = tf.Graph()     with detection_graph.as_default():         od_graph_def = tf.GraphDef()        | python  detection_graph = tf.Graph()   with detection_graph.as_default():     od_graph_def = tf.GraphDef() | Title is a code snippet; not a valid paper record or relevant artifact. |
| c-03a75a9b | python   (boxes, scores, classes, num) = sess.run(         [detection_boxes, detection_scores,             detection_cla | python  (boxes, scores, classes, num) = sess.run(     [detection_boxes, detection_scores,       detection_cla | Code snippet for TF inference; not a citable paper and not related to YOLOv4 ranging. |
| c-9c1615b5 | cmd   # load and run detection on video at path "videos/chess.mov"   python detect_single_threaded.py --source videos/ch | cmd  # load and run 检测 on video at path "videos/chess.mov"  python detect_single_threaded.py --source videos/ch | Shell command snippet; not a paper, no topical alignment. |

#### dataset_and_repo_notes

> TJU-DHD (c-6356c9b3): preferred primary dataset — vehicles, pedestrians, riders, high-resolution, traffic-focused.

### §4 ENG-THESIS-005 — 《随机纹理背景下弱小缺陷检测的深度学习方法研究》 — `weak`

| 维度 | 数值 |
|---|---:|
| batch | r3 |
| elapsed | 775.8s |
| domain | 工业缺陷检测/机器视觉 |
| paper | 194 |
| dataset | 4 |
| repo | 6 |
| baseline | 1 |
| parallel | 0 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-10080-1022756752.htm |

**direction_recommendation**: LLM unavailable; heuristic synthesis of '随机纹理背景下弱小缺陷检测的深度学习方法研究'. 0 core / 18 candidate / 87 needs-manual / 104 rejected. WARNING: baseline bucket promoted from reference via self_cannot_find_baseline_degradation — do NOT treat as reproducible baseline.

#### core (0) (无)
#### baseline (1)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-5c03be15 | Small Object Detection for Birds with Swin Transformer | Small 目标检测 for Birds with Swin Transformer |

#### parallel (0) (无)
#### reference (18)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-5c03be15 | Small Object Detection for Birds with Swin Transformer | Small 目标检测 for Birds with Swin Transformer |
| c-2cea0a3c | SOD-YOLOv8 -- Enhancing YOLOv8 for Small Object Detection in Traffic Scenes | SOD-YOLO 实时目标检测 -- Enhancing YOLO 实时目标检测 for Small 目标检测 in Traffic Scenes |
| c-0dbde301 | Exploring Depth Contribution for Camouflaged Object Detection | Exploring Depth Contribution for Camouflaged 目标检测 |
| c-1379fd79 | DCS-YOLOv8: A Lightweight Context-Aware Network for Small Object Detection in UAV Remote Sensing Imagery | DCS-YOLO 实时目标检测: A 轻量化 Context-Aware Network for Small 目标检测 in UAV Remote Sensing Imagery |
| c-3dd0da44 | YOLOv8-AMCD: Improved YOLOv8 for Small Object Detection | YOLO 实时目标检测-AMCD: Improved YOLO 实时目标检测 for Small 目标检测 |
| c-54118dad | Enhanced YOLOv8 Network for Small Object Detection in Drone Aerial Photography Scenarios | Enhanced YOLO 实时目标检测 Network for Small 目标检测 in Drone Aerial Photography Scenarios |
| c-4b5d8dd9 | >Linux系统翻墙方法</a></strong>         </li>         <li class= | >Linux系统翻墙方法</a></strong>     </li>     <li class= |
| c-56dd7278 | jonasvm/small-object-detection-yolo-dota-v2 | 仓库 jonasvm/small-object-detection-yolo-dota-v2 |
| c-e0be0a10 | VisDrone | (中文含义由英文派生) |
| c-7585a565 | COCO | (中文含义由英文派生) |
| c-72b40b45 | End-to-End Object Detection with Transformers | End-to-End 目标检测 with Transformer |
| c-6aeddbb0 | YOLOv10: Real-Time End-to-End Object Detection | YOLOv10: 实时 End-to-End 目标检测 |
| c-fb51e341 | Grounding DINO: Marrying DINO with Grounded Pre-Training for Open-Set Object Detection | Grounding DINO: Marrying DINO with Grounded Pre-Training for Open-Set 目标检测 |
| c-3247d7fb | FCOS: Fully Convolutional One-Stage Object Detection | FCOS: Fully 卷积 One-Stage 目标检测 |
| c-f5335875 | YOLOv4: Optimal Speed and Accuracy of Object Detection | YOLO 实时目标检测: Optimal Speed and Accuracy of 目标检测 |
| c-c26f15f2 | R-FCN: Object Detection via Region-based Fully Convolutional Networks | R-FCN: 目标检测 via Region-based Fully 卷积 Networks |
| c-66936314 | Faster R-CNN: Towards Real-Time Object Detection with Region Proposal Networks | Faster R-CNN: Towards 实时 目标检测 with Region Proposal Networks |
| c-4a33ded6 | EfficientDet: Scalable and Efficient Object Detection | EfficientDet: Scalable and Efficient 目标检测 |

#### long_tail (87)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-8d717e6d | Oriented object detection in optical remote sensing images using deep learning: a survey | Oriented 目标检测 in optical remote sensing images using 深度学习: a 综述 |
| c-2ccf452d | A Survey of Self-Supervised and Few-Shot Object Detection | 综述 of 自监督 and 少样本 目标检测 |
| c-7f32cbdd | TJU-DHD: A Diverse High-Resolution Dataset for Object Detection | TJU-DHD: A Diverse High-Resolution 数据集 for 目标检测 |
| c-6eadde27 | Object Contour and Edge Detection with RefineContourNet | Object Contour and Edge 检测 with RefineContourNet |
| c-f0b17799 | Table 1: KITTI object detection benchmark on
                      <i>test</i>
                      set of the proposed | Table 1: KITTI 目标检测 基准 on
           <i>test</i>
           set of the proposed |
| c-ee0c353d | Moving object detection with background model based on spatio-temporal texture | Moving 目标检测 with background model based on spatio-temporal texture |
| c-97deea68 | Background subtraction with shadow removal using hue and texture model for moving object detection | Background subtraction with shadow removal using hue and texture model for moving 目标检测 |
| c-97023210 | PESMOD: Small Moving Object Detection Benchmark Dataset for Moving Cameras | PESMOD: Small Moving 目标检测 基准 数据集 for Moving Cameras |
| c-47b6b861 | >                 Issues </a>            </li>               <li class= | >         Issues </a>      </li>        <li class= |
| c-24020098 | >                    Marketplace </a>                                 </li>             <li>               <a class= | >          Marketplace </a>                 </li>       <li>        <a class= |
| c-6dfc4052 | >                 Explore </a>            </li>           </ul>       </nav>        <div class= | >         Explore </a>      </li>      </ul>    </nav>    <div class= |
| c-136e1925 | /></svg> </a>     </span>   </li>    <li class= | /></svg> </a>   </span>  </li>  <li class= |
| c-60dc71d8 | ></span>       </summary>       <details-menu class= | ></span>    </summary>    <details-menu class= |
| c-a03a89be | >   New repository </a>    <a role= | >  New repository </a>  <a role= |
| c-90e3544c | >     Import repository   </a>  <a role= | >   Import repository  </a> <a role= |
| c-67228660 | >   New gist </a>    <a role= | >  New gist </a>  <a role= |
| c-fdb255e9 | >     New organization   </a>     <div class= | >   New organization  </a>   <div class= |
| c-1e7bb5bc | >This repository</span>   </div>     <a role= | >This repository</span>  </div>   <a role= |
| c-b371f517 | >       New issue     </a>         </details-menu>     </details>   </li>    <li class= | >    New issue   </a>     </details-menu>   </details>  </li>  <li class= |
| c-3af08e5d | >p4g5</span>       </a>      <details class= | >p4g5</span>    </a>   <details class= |
| c-48d4a0f2 | >Signed in as <strong class= | (中文含义由英文派生) |
| c-a037b22a | /></svg>         </div>       </div>       <div class= | /></svg>     </div>    </div>    <div class= |
| c-4316dd36 | >Set your status</span>       </div> </summary>    <details-dialog class= | >Set your status</span>    </div> </summary>  <details-dialog class= |
| c-5c5571c1 | Box-header bg-gray border-bottom p-3 | (中文含义由英文派生) |
| c-a6defd6e | Box-btn-octicon js-toggle-user-status-edit btn-octicon float-right | (中文含义由英文派生) |
| c-5d8fba34 | M7.48 8l3.75 3.75-1.48 1.48L6 9.48l-3.75 3.75-1.48-1.48L4.52 8 .77 4.25l1.48-1.48L6 6.52l3.75-3.75 1.48 1.48L7.48 8z | (中文含义由英文派生) |
| c-b83098da | Box-title f5 text-bold text-gray-dark | (中文含义由英文派生) |
| c-bb7df6ca | input-group d-table form-group my-0 js-user-status-form-group | (中文含义由英文派生) |
| c-6472a871 | btn-outline btn js-toggle-user-status-emoji-picker bg-white btn-open-emoji-picker | (中文含义由英文派生) |
| c-07bfa468 | js-suggester-field d-table-cell width-full form-control js-user-status-message-field js-characters-remaining-field | (中文含义由英文派生) |
| c-32e7b4ab | What is your current status? | (中文含义由英文派生) |
| c-a5d42763 | d-flex flex-items-baseline flex-items-stretch lh-condensed f6 btn-link link-gray no-underline js-predefined-user-status  | d-flex flex-items-baseline flex-items-stretch lh-condensed f6 btn-link link-gray no-underline js-predefined-user-status |
| c-ad7bffb7 | I may be slow to respond. | (中文含义由英文派生) |
| c-a84e1e0f | d-flex flex-items-center flex-justify-between p-3 border-top | (中文含义由英文派生) |
| c-73418095 | width-full btn btn-primary mr-2 js-user-status-submit | (中文含义由英文派生) |
| c-b38ff387 | Header, go to profile, text:your profile | (中文含义由英文派生) |
| c-dee3afb4 | Header, go to repositories, text:your repositories | (中文含义由英文派生) |
| c-8749ccc6 | Header, go to projects, text:your projects | (中文含义由英文派生) |
| c-0e788692 | Header, go to starred repos, text:your stars | (中文含义由英文派生) |
| c-5aaaf7a6 | Header, your gists, text:your gists | (中文含义由英文派生) |
| c-77e9e5e3 | Header, go to help, text:help | (中文含义由英文派生) |
| c-c26a35c7 | Header, go to settings, icon:settings | (中文含义由英文派生) |
| c-b25fee96 | >             Sign out           </button> </form>      </details-menu>     </details>   </li> </ul>             <!-- ' | >       Sign out      </button> </form>   </details-menu>   </details>  </li> </ul>       <!-- ' |
| c-922d3987 | btn-link HeaderNavlink d-block width-full text-left py-2 text-bold | (中文含义由英文派生) |
| c-827e3334 | Header, sign out, icon:logout | (中文含义由英文派生) |
| c-b6f84bc2 | M12 9V7H8V5h4V3l4 3-4 3zm-2 3H6V3L2 1h8v3h1V1c0-.55-.45-1-1-1H1C.45 0 0 .45 0 1v11.38c0 .39.22.73.55.91L6 16.01V13h4c.55 | (中文含义由英文派生) |
| c-61a53c40 | >             Sign out           </button> </form>      </div>     </div>   </div> </header>            </div>    <div i | >       Sign out      </button> </form>   </div>   </div>  </div> </header>      </div>  <div i |
| c-5403aa12 | >  </div>      <div role= | > </div>   <div role= |
| c-c70ffda8 | data-commit-hovercards-enabled>         <div itemscope itemtype= | data-commit-hovercards-enabled>     <div itemscope itemtype= |
| c-6cb81b11 | >     <div  >                  <div class= | >   <div >         <div class= |
| c-6c4001b7 | >    <li>         <!-- ' | >  <li>     <!-- ' |
| c-35690234 | Repository, click Watch settings, action:wiki#index | (中文含义由英文派生) |
| c-7c62154e | M12 5l-8 8-4-4 1.5-1.5L4 10l6.5-6.5L12 5z | (中文含义由英文派生) |
| c-e757740f | M8 2.81v10.38c0 .67-.81 1-1.28.53L3 10H1c-.55 0-1-.45-1-1V7c0-.55.45-1 1-1h2l3.72-3.72C7.19 1.81 8 2.14 8 2.81zm7.53 3.2 | (中文含义由英文派生) |
| c-b4d91f4b | 885 users are watching this repository | (中文含义由英文派生) |
| c-7729c3f1 | /></svg>         Unstar       </button>         <a class= | /></svg>     Unstar    </button>     <a class= |
| c-c88b9711 | >           10,597         </a> </form>     <!-- ' | >      10,597     </a> </form>   <!-- ' |
| c-dbc683d4 | Repository, click star button, action:wiki#index; text:Star | (中文含义由英文派生) |
| c-6cd6d311 | M14 6l-4.9-.64L7 1 4.9 5.36 0 6l3.6 3.26L2.67 14 7 11.67 11.33 14l-.93-4.74L14 6z | (中文含义由英文派生) |
| c-7e6e7504 | 10597 users starred this repository | (中文含义由英文派生) |
| c-9677aa58 | /></svg>               Fork             </button> </form>     <a href= | /></svg>        Fork       </button> </form>   <a href= |
| c-5f8841f8 | >       2,441     </a>   </li> </ul>        <h1 class= | >    2,441   </a>  </li> </ul>    <h1 class= |
| c-b3e6dd9d | >new-pac</a></strong>  </h1>      </div>      <nav class= | >new-pac</a></strong> </h1>   </div>   <nav class= |
| c-27bd7af3 | >    <span itemscope itemtype= | >  <span itemscope itemtype= |
| c-ddf3e437 | > </a>  </span>      <span itemscope itemtype= | > </a> </span>   <span itemscope itemtype= |
| c-68d02639 | > </a>    </span>    <span itemscope itemtype= | > </a>  </span>  <span itemscope itemtype= |
| c-eef3d5c3 | >Pull requests</span>       <span class= | >Pull requests</span>    <span class= |
| c-39828a20 | > </a>  </span>       <a data-hotkey= | > </a> </span>    <a data-hotkey= |
| c-49c95460 | /></svg>       Projects       <span class= | /></svg>    Projects    <span class= |
| c-a2894ec5 | >0</span> </a>      <a class= | >0</span> </a>   <a class= |
| c-bd29da60 | /></svg>       Wiki </a>     <a class= | /></svg>    Wiki </a>   <a class= |
| c-8ff0354c | /></svg>       Insights </a>  </nav>    <div class= | /></svg>    Insights </a> </nav>  <div class= |
| c-a30c6547 | >      <span itemscope itemtype= | >   <span itemscope itemtype= |
| c-e651d0fd | > </a>    </span>        <span itemscope itemtype= | > </a>  </span>    <span itemscope itemtype= |
| c-755c4fa9 | > </a>      </span>      <span itemscope itemtype= | > </a>   </span>   <span itemscope itemtype= |
| c-ffa3f81e | >Pull requests</span>         <span class= | >Pull requests</span>     <span class= |
| c-08a21f29 | > </a>    </span>      <span itemscope itemtype= | > </a>  </span>   <span itemscope itemtype= |
| c-69112f07 | > </a>      </span>        <a class= | > </a>   </span>    <a class= |
| c-08866fda | >         Pulse </a>       <span itemscope itemtype= | >     Pulse </a>    <span itemscope itemtype= |
| c-64ccbb10 | >           Community </a>      </span>    </nav> </div>     </div> <div class= | >      Community </a>   </span>  </nav> </div>   </div> <div class= |
| c-3692b981 | >Jump to bottom</a>        </div>   </div>      <div class= | >Jump to bottom</a>    </div>  </div>   <div class= |
| c-7f78f9de | >       自由上网 edited this page <relative-time datetime= | >    自由上网 edited this page <relative-time datetime= |
| c-a5f1246a | >Feb 19, 2019</relative-time>       &middot;       <a href= | >Feb 19, 2019</relative-time>    &middot;    <a href= |
| c-52391c0e | >         1061 revisions       </a>     </div>    <div id= | >     1061 revisions    </a>   </div>  <div id= |
| c-01edfe3a | >           <h3> <a id= | >      <h3> <a id= |
| c-ba1ce769 | OllieBullGB/ObjectDetection | 仓库 OllieBullGB/ObjectDetection |
| c-4f0e6faa | Pascal VOC | (中文含义由英文派生) |

#### rejected (104)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-c4de1d52 | 3D Object Detection for Autonomous Driving: A Comprehensive Survey | 三维 目标检测 for 自动驾驶: A Comprehensive 综述 | Autonomous driving 3D detection survey; cross-domain (vehicles vs industrial surfaces). |
| c-40fd6652 | AIn't Nothing But a Survey? Using Large Language Models for Coding German Open-Ended Survey Responses on Survey Motivati | AIn't Nothing But a 综述? Using Large Language Models for Coding German Open-Ended 综述 Responses on 综述 Motivati | LLMs for survey text coding; completely cross-domain (NLP vs vision/defects). |
| c-69ee54ba | PVAFN: Point-Voxel Attention Fusion Network with Multi-Pooling Enhancing for 3D Object Detection | PVAFN: Point-Voxel Attention Fusion Network with Multi-Pooling Enhancing for 三维 目标检测 | LiDAR 3D detection; cross-modality and cross-domain. |
| c-fdb344b3 | Barcode and QR Code Object Detection: An Experimental Study on YOLOv8 Models | Barcode and QR Code 目标检测: An Experimental Study on YOLO 实时目标检测 Models | YOLOv8 on barcode/QR codes; different task type (symbol recognition). |
| c-d542c4a2 | chrisneagu/FTC-Skystone-Dark-Angels-Romania-2020 | 仓库 chrisneagu/FTC-Skystone-Dark-Angels-Romania-2020 | FTC robotics competition SDK; unrelated domain. |
| c-5b21f3bf | Import project (Eclipse ADT, Gradle, etc.) | (中文含义由英文派生) | Empty title/abstract from GitHub; no identifiable content. |
| c-e15f07a0 | E RobotCore: lynx xmit lock: #### abandoning lock: | (中文含义由英文派生) | Garbage title/abstract; appears to be a corrupted GitHub log fragment, not a real paper. |
| c-ddc123b5 | Could not find com.android.tools.lint:lint-gradle:26.1.4 | (中文含义由英文派生) | Title is a Gradle dependency error string; not a real publication. |
| c-28b70773 | Version 3.00 (built on 17.04.013) | (中文含义由英文派生) | Version-string title; not a real paper. |
| c-3cf163a3 | missing hardware leaves robot controller disconnected from driver station | missing hardware leaves 机器人 controller disconnected from driver station | Robotics FRC issue ticket, not a research paper. |
| c-031f6443 | fast tapping of Init/Start causes problems | (中文含义由英文派生) | Issue tracker snippet; not a publication. |
| c-cebf76e0 | molyswu/hand_detection | 仓库 molyswu/hand_detection | Repo is for hand detection on egocentric images, not surface defect inspection. |
| c-0f08012a | Lending a hand: Detecting hands and recognizing activities in complex egocentric interactions. | (中文含义由英文派生) | Egocentric hand/activity recognition paper, not surface defect detection. |
| c-b3ac32ed | >  ====== Hand Inference graph loaded. | > ====== Hand Inference graph loaded. | Log output string, not a paper. |
| c-6411c58f | python   detection_graph = tf.Graph()     with detection_graph.as_default():         od_graph_def = tf.GraphDef()        | python  detection_graph = tf.Graph()   with detection_graph.as_default():     od_graph_def = tf.GraphDef() | Code snippet, not a paper. |
| c-561c46bb | python   (boxes, scores, classes, num) = sess.run(         [detection_boxes, detection_scores,             detection_cla | python  (boxes, scores, classes, num) = sess.run(     [detection_boxes, detection_scores,       detection_cla | Code snippet, not a paper. |
| c-042968cf | cmd   # load and run detection on video at path "videos/chess.mov"   python detect_single_threaded.py --source videos/ch | cmd  # load and run 检测 on video at path "videos/chess.mov"  python detect_single_threaded.py --source videos/ch | CLI command snippet, not a paper. |
| c-ee439093 | jaityron/new-pac-wiki | 仓库 jaityron/new-pac-wiki | Unrelated wiki repo with no defect-detection content. |
| c-11e01c37 | Contribute to Alvin9999/new-pac development by creating an account on GitHub. | (中文含义由英文派生) | Generic GitHub CTA text, not a paper. |
| c-1263d485 | Recent Commits to new-pac:master | (中文含义由英文派生) | GitHub commits page label, not a paper. |
| c-7eeef1b2 | p-3 bg-blue text-white show-on-focus js-skip-to-content | (中文含义由英文派生) | HTML/CSS class fragment, not a paper. |
| c-da90b615 | Header js-details-container Details f5 | (中文含义由英文派生) | GitHub UI HTML fragment, not a paper. |
| c-4b98f2b5 | Header, go to dashboard, icon:logo | (中文含义由英文派生) | GitHub UI alt-text fragment, not a paper. |
| c-1617c820 | d-lg-none css-truncate css-truncate-target width-fit px-3 | (中文含义由英文派生) | HTML/CSS class fragment, not a paper. |
| c-f6be18a3 | M4 9H3V8h1v1zm0-3H3v1h1V6zm0-2H3v1h1V4zm0-2H3v1h1V2zm8-1v12c0 .55-.45 1-1 1H6v2l-1.5-1.5L3 16v-2H1c-.55 0-1-.45-1-1V1c0- | (中文含义由英文派生) | SVG path data string, not a paper. |
| c-0a7878c0 | You have no unread notifications | (中文含义由英文派生) | UI notification text, not a paper. |
| c-f83dc75b | notification-indicator tooltipped tooltipped-s my-2 my-lg-0 js-socket-channel js-notification-indicator | (中文含义由英文派生) | Title is GitHub UI HTML fragment, not a research artifact. |
| c-0bc11fe1 | Header, go to notifications, icon:read | (中文含义由英文派生) | Title is GitHub UI HTML snippet, not a paper. |
| c-686ffdd9 | M14 12v1H0v-1l.73-.58c.77-.77.81-2.55 1.19-4.42C2.69 3.23 6 2 6 2c0-.55.45-1 1-1s1 .45 1 1c0 0 3.39 1.23 4.16 5 .38 1.88 | (中文含义由英文派生) | Title is an SVG path string, not a research artifact. |
| c-aeadca65 | HeaderMenu d-lg-flex flex-justify-between flex-auto | (中文含义由英文派生) | Title is a CSS class fragment from GitHub header. |
| c-d4c5c89c | header-search scoped-search site-scoped-search js-site-search position-relative js-jump-to | (中文含义由英文派生) | Title is GitHub search bar CSS classes. |
| c-f246baf0 | Search or jump to | (中文含义由英文派生) | Title is a UI placeholder string. |
| c-c4faa42d | ` --><!-- </textarea></xmp> --></option></form><form class= | (中文含义由英文派生) | Title is malformed HTML form snippet. |
| c-9b2c74a5 | /></svg>     </div>      <img class= | /></svg>   </div>   <img class= | Title is SVG/img HTML fragment. |
| c-ac58f0f7 | >     </div>      <div class= | >   </div>   <div class= | Title is a div HTML fragment. |
| c-50213020 | >         In this repository       </span>       <span class= | >     In this repository    </span>    <span class= | Title is GitHub UI repository context string. |
| c-5195d0f9 | >         All GitHub       </span>       <span aria-hidden= | >     All GitHub    </span>    <span aria-hidden= | Title is GitHub nav label 'All GitHub'. |
| c-bd8ff688 | >↵</span>     </div>      <div aria-hidden= | >↵</span>   </div>   <div aria-hidden= | Title is a stray HTML arrow character. |
| c-6cf5b914 | >       Jump to       <span class= | >    Jump to    <span class= | Title is GitHub 'Jump to' UI fragment. |
| c-6e69452f | >↵</span>     </div>   </a> </li>  </ul>  <ul class= | >↵</span>   </div>  </a> </li> </ul> <ul class= | Title is stray HTML markup. |
| c-27b6cb0e | >No suggested jump to results</span>   </li> </ul>  <ul id= | >No suggested jump to results</span>  </li> </ul> <ul id= | Title is GitHub 'No suggested jump to results' UI text. |
| c-73f3faa4 | >↵</span>     </div>   </a> </li>      <li class= | >↵</span>   </div>  </a> </li>   <li class= | Title is HTML list-item fragment. |
| c-22cb3fa1 | >↵</span>     </div>   </a> </li>       <li class= | >↵</span>   </div>  </a> </li>    <li class= | Title is HTML list fragment. |
| c-bae8ae45 | >     </li> </ul>              </div>       </label> </form>  </div> </div>              </div>            <ul class= | >   </li> </ul>       </div>    </label> </form> </div> </div>       </div>      <ul class= | Title is bulk HTML list/form markup. |
| c-7b024cda | >                 Dashboard </a>            </li>             <li>               <a class= | >         Dashboard </a>      </li>       <li>        <a class= | Title is GitHub 'Dashboard' nav label. |
| c-bec990cc | >                 Pull requests </a>            </li>             <li>               <a class= | >         Pull requests </a>      </li>       <li>        <a class= | Title is GitHub 'Pull requests' nav label. |
| c-14faa52b | ></path></svg></a><strong><strong><strong><strong><strong><strong><strong><strong><strong><strong><strong><strong>自由上网方法 | 仓库 ></path></svg></a><strong><strong><strong><strong><strong><strong><strong><strong><strong><strong><strong><strong>自由上网方法 | VPN/proxy browser content, cross-domain. |
| c-3c145e24 | ></p> <p><strong>介绍</strong>：GoProxy ipv6版、GoAgent ipv6版、v2ray版、SSR版、赛风版、WuJie版、FreeGate版、SkyZip版，适合windows操作系统，比如：Xp、wi | (中文含义由英文派生) | VPN/proxy software listing, cross-domain. |
| c-66eeed95 | >wisecare365</a>。它们都是免费的，而且不会干扰电脑运行。</p> <p><strong>选择指南</strong>：有GoProxy ipv6版、GoAgent ipv6版、v2ray版、SSR版、赛风版、WuJie版、Fr | (中文含义由英文派生) | VPN tool selection guide, cross-domain. |
| c-245a7376 | >备用项目地址</a> 。</p> <p><strong>2019年1月18日公告</strong>：ipv6版国内大多数地区已失效，如果你无法使用ipv6版，请更换其它类型的软件。</p> <p><strong>推荐YouTube视频频道 | (中文含义由英文派生) |  |
| c-1e5c01c5 | >谷歌浏览器低内核GoAgent ipv6版</a> （2018年12月20日云端更新GoAgent ipv6）</p> <p><a href= | (中文含义由英文派生) |  |
| c-cd7fb9d1 | >谷歌浏览器低内核GoProxy ipv6版</a> （2018年9月23日更新版本）</p> <p><a href= | (中文含义由英文派生) |  |
| c-b75d755c | >Linux系统翻墙方法</a> （2018年5月30日增加Linux SSR 使用方法二）</p> <p><a href= | (中文含义由英文派生) |  |
| c-3340bb1b | >数字安全手册</a> （推荐两本关于网络安全的书籍）</p> <hr> <p>真心希望大家都能够突破网络封锁、获得真相，祝愿每位善良的人都能拥有一个美好的未来。</p> <p>2019年神韵晚会超清预告片<a href= | (中文含义由英文派生) |  |
| c-840e85b3 | >kebi2014@gmail.com</a>进行反馈，反馈邮件标题最好注明什么软件及截图。</p>          </div>      </div>      <div id= | 仓库 >kebi2014@gmail.com</a>进行反馈，反馈邮件标题最好注明什么软件及截图。</p>          </div>      </div>      <div id= |  |
| c-8432053c | /></svg>       Pages <span class= | /></svg>    Pages <span class= |  |
| c-fd63d5d8 | >27</span>     </h3>   </div>   <div class= | >27</span>   </h3>  </div>  <div class= |  |
| c-420f8781 | >     </div>      <ul class= | >   </div>   <ul class= |  |
| c-150574c6 | >Home</a></strong>         </li>         <li class= | >Home</a></strong>     </li>     <li class= |  |
| c-ff093849 | >苹果手机翻墙软件</a></strong>         </li>         <li class= | >苹果手机翻墙软件</a></strong>     </li>     <li class= |  |
| c-b1ba63cc | >苹果电脑MAC翻墙软件</a></strong>         </li>         <li class= | >苹果电脑MAC翻墙软件</a></strong>     </li>     <li class= |  |
| c-cb5bb42e | >谷歌浏览器内核升级方法</a></strong>         </li>         <li class= | >谷歌浏览器内核升级方法</a></strong>     </li>     <li class= |  |
| c-09365f3c | >谷歌镜像</a></strong>         </li>         <li class= | >谷歌镜像</a></strong>     </li>     <li class= |  |
| c-0c3a02a9 | >赛风版</a></strong>         </li>         <li class= | >赛风版</a></strong>     </li>     <li class= |  |
| c-ee06b2ee | >高内核版</a></strong>         </li>         <li class= | >高内核版</a></strong>     </li>     <li class= |  |
| c-53c4cefd | >             Show 12 more pages…           </button>         </li>     </ul>   </div> </div>        </div>         <h5  | >       Show 12 more pages…      </button>     </li>   </ul>  </div> </div>    </div>     <h5 |  |
| c-ceb3f653 | >Clone this wiki locally</h5>       <div class= | >Clone this wiki locally</h5>    <div class= |  |
| c-1868105f | /></svg>           </clipboard-copy>         </span>       </div>     </div>   </div>     </div>   <div class= | /></svg>      </clipboard-copy>     </span>    </div>   </div>  </div>   </div>  <div class= |  |
| c-5afa55d8 | ></div> </div>       </div>   </div>       </div>           <div class= | ></div> </div>    </div>  </div>    </div>      <div class= |  |
| c-69d3a99e | >GitHub</span>, Inc.</li>         <li class= | >GitHub</span>, Inc.</li>     <li class= | Garbled HTML metadata; no paper content, not found in any relevant source. |
| c-c1549941 | >Help</a></li>     </ul>      <a aria-label= | >Help</a></li>   </ul>   <a aria-label= | Garbled GitHub UI HTML; no scholarly content. |
| c-9c583467 | /></svg> </a>    <ul class= | /></svg> </a>  <ul class= | HTML fragment only; no paper. |
| c-f85dae36 | >Contact GitHub</a></li>         <li class= | >Contact GitHub</a></li>     <li class= | GitHub HTML boilerplate; no scholarly content. |
| c-bc34c65f | >About</a></li>      </ul>   </div>   <div class= | >About</a></li>   </ul>  </div>  <div class= | HTML fragment; not a paper. |
| c-47a9051a | ></span>   </div> </div>      <div id= | ></span>  </div> </div>   <div id= | HTML fragment; no paper. |
| c-6cf3a799 | /></svg>     </button>     You can’t perform that action at this time.   </div>            <script crossorigin= | /></svg>   </button>   You can’t perform that action at this time.  </div>      <script crossorigin= | GitHub error-page HTML fragment. |
| c-896da580 | >You signed in with another tab or window. <a href= | (中文含义由英文派生) | HTML fragment; no scholarly content. |
| c-2938494f | >Reload</a> to refresh your session.</span>     <span class= | >Reload</a> to refresh your session.</span>   <span class= | HTML fragment; no paper. |
| c-8e46f004 | >You signed out in another tab or window. <a href= | (中文含义由英文派生) | HTML fragment; not a real candidate. |
| c-b6442dac | >Reload</a> to refresh your session.</span>   </div>   <template id= | >Reload</a> to refresh your session.</span>  </div>  <template id= | HTML fragment; no paper. |
| c-9fa56ef8 | /></svg>       </button>       <div class= | /></svg>    </button>    <div class= | HTML fragment; no scholarly content. |
| c-73a68f53 | ></div>     </details-dialog>   </details> </template>    <div class= | ></div>   </details-dialog>  </details> </template>  <div class= | HTML fragment; no paper. |
| c-94534d1f | >   </div> </div>  <div id= | >  </div> </div> <div id= | HTML fragment; not a paper. |
| c-549bb8dc | >   Press h to open a hovercard with more details. </div>    <div aria-live= | >  Press h to open a hovercard with more details. </div>  <div aria-live= | HTML fragment; no paper. |
| c-f3ea79f5 | ToxicChicken1018/YourMum | 仓库 ToxicChicken1018/YourMum | UserScript for Krunker game; not defect detection. |
| c-8a0b4ee1 | >FreeGate和WuJie版</a></strong>         </li>         <li class= | >FreeGate和WuJie版</a></strong>     </li>     <li class= |  |
| c-4defb679 | >GoAgent ipv6版</a></strong>         </li>         <li class= | >GoAgent ipv6版</a></strong>     </li>     <li class= |  |
| c-2547e461 | >GoProxy ipv6版</a></strong>         </li>         <li class= | >GoProxy ipv6版</a></strong>     </li>     <li class= |  |
| c-5caadaa5 | >ipv6开启方法</a></strong>         </li>         <li class= | >ipv6开启方法</a></strong>     </li>     <li class= |  |
| c-7f889861 | >SkyZip版</a></strong>         </li>         <li class= | >SkyZip版</a></strong>     </li>     <li class= |  |
| c-60a9ad7f | >SSR版</a></strong>         </li>         <li class= | >SSR版</a></strong>     </li>     <li class= |  |
| c-8f71bb5f | >ss免费账号</a></strong>         </li>         <li class= | >ss免费账号</a></strong>     </li>     <li class= |  |
| c-84632bc3 | >v2ray版</a></strong>         </li>         <li class= | >v2ray版</a></strong>     </li>     <li class= |  |
| c-97734886 | >YouTube下载1080教程</a></strong>         </li>         <li class= | >YouTube下载1080教程</a></strong>     </li>     <li class= |  |
| c-fec80018 | >低内核版</a></strong>         </li>         <li class= | >低内核版</a></strong>     </li>     <li class= |  |
| c-c774d9d4 | >安卓手机版</a></strong>         </li>         <li class= | >安卓手机版</a></strong>     </li>     <li class= |  |
| c-f0813e95 | >实用网络小知识</a></strong>         </li>         <li class= | >实用网络小知识</a></strong>     </li>     <li class= |  |
| c-7d71fa62 | >平板电脑翻墙软件</a></strong>         </li>         <li class= | >平板电脑翻墙软件</a></strong>     </li>     <li class= |  |
| c-166b59c5 | >数字安全手册</a></strong>         </li>         <li class= | >数字安全手册</a></strong>     </li>     <li class= |  |
| c-0f97d37f | >火狐翻墙浏览器</a></strong>         </li>         <li class= | >火狐翻墙浏览器</a></strong>     </li>     <li class= |  |
| c-5ceff2cb | >直翻通道</a></strong>         </li>         <li class= | >直翻通道</a></strong>     </li>     <li class= |  |
| c-84f277dc | >自建google appid教程</a></strong>         </li>         <li class= | >自建google appid教程</a></strong>     </li>     <li class= |  |
| c-34275260 | >自建ss服务器教程</a></strong>         </li>         <li class= | >自建ss服务器教程</a></strong>     </li>     <li class= |  |
| c-f946fa61 | >自建v2ray服务器教程</a></strong>         </li>         <li class= | >自建v2ray服务器教程</a></strong>     </li>     <li class= |  |

#### dataset_and_repo_notes

> 无

### §5 ENG-THESIS-010 — 《基于深度学习的交通标志检测与识别研究》 — `pass`

| 维度 | 数值 |
|---|---:|
| batch | r3 |
| elapsed | 170.0s |
| domain | 自动驾驶/交通感知 |
| paper | 18 |
| dataset | 0 |
| repo | 4 |
| baseline | 3 |
| parallel | 3 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-10146-1022835124.htm |

**direction_recommendation**: Recommended direction: a YOLOv5-family real-time traffic sign detection/recognition study on GTSDB (detection) plus GTSRB (recognition), with optional TT100K as a Chinese-sign extension. Two core papers (c-d59b502a, c-7cad1e7a) anchor the YOLOv5 baseline and the real-time deployment case study. Arcos-García repo (c-b2aa6271) provides a clean GTSDB reference pipeline. CURE-TSR (c-9f621b4e) and the adversarial-robustness paper (c-54f33ae6) can serve as robustness/extensibility discussion material. Recognition-only CNN paper (c-69699e6a) is a parallel reference. Acknowledge coverage gaps: no YOLOv8 or Faster R-CNN baseline was retrieved, so the survey should treat YOLOv5 as the central baseline and discuss newer detectors (YOLOv8/v10) as forward-looking comparisons rather than evidence-supported baselines.

#### core (2)

| cid | 原文 title | 中文含义 | reason |
|---|---|---|---|
| c-d59b502a | Improved YOLOv5 network for real-time multi-scale traffic sign detection | Improved YOLO 实时目标检测 network for 实时 multi-scale 交通标志 检测 | Strong method+task match: YOLOv5 baseline for real-time multi-scale traffic sign detection. |
| c-7cad1e7a | Real-Time Traffic Sign Detection: A Case Study in a Santa Clara Suburban Neighborhood | 实时 交通标志 检测: A Case Study in a Santa Clara Suburban Neighborhood | Direct method+task match on YOLOv5 real-time traffic sign detection. |

#### baseline (3)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-d59b502a | Improved YOLOv5 network for real-time multi-scale traffic sign detection | Improved YOLO 实时目标检测 network for 实时 multi-scale 交通标志 检测 |
| c-7cad1e7a | Real-Time Traffic Sign Detection: A Case Study in a Santa Clara Suburban Neighborhood | 实时 交通标志 检测: A Case Study in a Santa Clara Suburban Neighborhood |
| c-b2aa6271 | surendrasah/german-traffic-sign-detection | 仓库 surendrasah/german-traffic-sign-detection |

#### parallel (3)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-54f33ae6 | Adversarial Attack On Yolov5 For Traffic And Road Sign Detection | Adversarial Attack On YOLO 实时目标检测 For Traffic And 道路 Sign 检测 |
| c-9f621b4e | CURE-TSR: Challenging Unreal and Real Environments for Traffic Sign Recognition | CURE-TSR: Challenging Unreal and Real Environments for 交通标志 识别 |
| c-69699e6a | Image Classification using CNN for Traffic Signs in Pakistan | Image 分类 using CNN for 交通标志 in Pakistan |

#### reference (2)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-db29dff4 | Good Practices and A Strong Baseline for Traffic Anomaly Detection | Good Practices and A Strong Baseline for Traffic Anomaly 检测 |
| c-2f8efd2d | T-GCN: A Temporal Graph Convolutional Network for Traffic Prediction | T-GCN: A Temporal Graph 卷积 Network for Traffic Prediction |

#### long_tail (3)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-7fdf6aa4 | JVSCHANDRADITHYA/Traffic_SIgn_recognition_with_BB | 仓库 JVSCHANDRADITHYA/Traffic_SIgn_recognition_with_BB |
| c-38982fe2 | Udit4849/Traffic-Sign-Detection | 仓库 Udit4849/Traffic-Sign-Detection |
| c-28f26c85 | YagizBerkutay/TrafficSignDetection | 仓库 YagizBerkutay/TrafficSignDetection |

#### rejected (11)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-1b498687 | A rich bounty of AGN in the 9 square degree Bootes survey: high-z obscured AGN and large-scale structure | rich bounty of AGN (天文主动星系核，强噪声) in the 9 square degree Bootes 综述: high-z obscured AGN (天文主动星系核，强噪声) and large-scale structure | Title and abstract are mismatched; metadata describes Adaptive Cruise Control but title is about AGN astronomy. |
| c-6be35cb7 | Oriented object detection in optical remote sensing images using deep learning: a survey | Oriented 目标检测 in optical remote sensing images using 深度学习: a 综述 | Survey on oriented object detection in remote sensing, not traffic signs. |
| c-a81ccec4 | AIn't Nothing But a Survey? Using Large Language Models for Coding German Open-Ended Survey Responses on Survey Motivati | AIn't Nothing But a 综述? Using Large Language Models for Coding German Open-Ended 综述 Responses on 综述 Motivati | Survey methodology paper using LLMs, unrelated to traffic sign detection. |
| c-971e726c | The Methanol Multibeam Survey | Methanol Multibeam 综述 | Radio astronomy methanol maser survey; entirely unrelated domain. |
| c-13779bcf | Diffusion Convolutional Recurrent Neural Network: Data-Driven Traffic Forecasting | 扩散模型 卷积 Recurrent 神经网络: Data-Driven Traffic Forecasting | Traffic forecasting (spatio-temporal), not traffic sign detection. |
| c-539b1f6a | Spatio-temporal Graph Convolutional Neural Network: A Deep Learning Framework for Traffic Forecasting | Spatio-temporal Graph 卷积 神经网络: A 深度学习 Framework for Traffic Forecasting | Traffic flow forecasting, not sign detection. |
| c-4f58af60 | Toward Generating a New Intrusion Detection Dataset and Intrusion Traffic Characterization | Toward Generating a New Intrusion 检测 数据集 and Intrusion Traffic Characterization | Network intrusion detection dataset, not traffic signs. |
| c-75c48d2c | Smart Traffic: Traffic Congestion Reduction by Shortest Route * Search Algorithm | (中文含义由英文派生) | Traffic congestion routing, not sign detection. |
| c-15b73e5f | Attention Based Spatial-Temporal Graph Convolutional Networks for Traffic Flow Forecasting | Attention Based Spatial-Temporal Graph 卷积 Networks for Traffic Flow Forecasting | Traffic flow forecasting model, not sign detection. |
| c-81806424 | Microscopic Traffic Simulation using SUMO | (中文含义由英文派生) | Traffic simulation tool, not sign detection. |
| c-f22cbdc9 | OPTIMIZATION OF FOREST TRUCK TRAFFIC TRAFFIC ON THE LIFTS OF FOREST ROADS | (中文含义由英文派生) | About forestry/logistics truck traffic scheduling, not sign detection/recognition. Cross-domain rejection. |

#### dataset_and_repo_notes

> c-d59b502a (Improved YOLOv5) is the primary YOLOv5 baseline; needs dataset label confirmed (likely TT100K or CCTSDB).
> c-7cad1e7a (Real-Time YOLOv5) uses a custom suburban dataset; useful for real-time pipeline narrative.
> c-b2aa6271 (Arcos-García repo) targets GTSDB and pairs with their published DNN evaluation paper — strong GTSDB reference.
> c-9f621b4e (CURE-TSR) is a recognition-only benchmark for challenging conditions, complements but does not replace GTSDB/GTSRB.
> c-7fdf6aa4, c-38982fe2, c-28f26c85 are low-star GitHub repos; treat as implementation references, not authoritative baselines.
> No GTSRB-specific or TT100K-specific paper was retrieved; rely on dataset documentation for those.

### §6 ENG-THESIS-014 — 《基于生成对抗网络的织物缺陷检测算法研究》 — `pass`

| 维度 | 数值 |
|---|---:|
| batch | r4 |
| elapsed | 222.8s |
| domain | 工业缺陷检测/机器视觉 |
| paper | 20 |
| dataset | 2 |
| repo | 0 |
| baseline | 4 |
| parallel | 5 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-10465-1022512345.htm |

**direction_recommendation**: Proceed with a GAN-based fabric defect detection study organized around three pillars: (1) unsupervised anomaly detection via AnoGAN/f-AnoGAN-style reconstruction on fabric texture images; (2) defect synthesis/augmentation via DCGAN or CycleGAN to address class imbalance in small textile datasets; (3) supervised detection/segmentation using a GAN-augmented backbone (e.g., Faster R-CNN or attention U-Net) for defect localization. The evidence pool is weak on direct GAN+fabric papers, so baseline candidates must be drawn from classical fabric defect work and adjacent manufacturing/texture defect GAN papers (c-1d945be4, c-9f4c84bb) while classical fabric methods (c-32bf4c75, c-7078aec6, c-cda1574e, c-648a03ed, c-d5cc706d) anchor the domain background. The RAW-FABRID dataset (c-a0b4f7ea) is the only confirmed fabric-specific object resource and should serve as the primary evaluation corpus, supplemented by MVTec AD carpet/grid categories (external, not in pool) for generalization checks. The roadmap is risky: no tier=core item exists, so the student must manually verify candidate GAN+fabric papers before baseline selection.

#### core (0) (无)
#### baseline (4)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-32bf4c75 | Fabric defect detection method based on texture structure analysis | Fabric 缺陷 检测 method based on texture structure analysis |
| c-7078aec6 | Fabric defect detection based on texture enhancement | Fabric 缺陷 检测 based on texture enhancement |
| c-cda1574e | Fabric defect detection based on adaptive LBP and SVM | Fabric 缺陷 检测 based on adaptive LBP and SVM |
| c-648a03ed | LSTM based texture classification and defect detection in a fabric | LSTM based texture 分类 and 缺陷 检测 in a fabric |

#### parallel (5)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-1d945be4 | DeepInspect: An AI-Powered Defect Detection for Manufacturing Industries | DeepInspect: An AI-Powered 缺陷 检测 for Manufacturing Industries |
| c-9f4c84bb | A New Benchmark Dataset for Texture Image Analysis and Surface Defect Detection | New 基准 数据集 for Texture Image Analysis and Surface 缺陷 检测 |
| c-f614d7ef | TransferD2: Automated Defect Detection Approach in Smart Manufacturing using Transfer Learning Techniques | TransferD2: Automated 缺陷 检测 Approach in Smart Manufacturing using 迁移学习 Techniques |
| c-f0600e2f | Road Surface Defect Detection -- From Image-based to Non-image-based: A Survey | 道路 Surface 缺陷 检测 -- From Image-based to Non-image-based: A 综述 |
| c-d1f9645f | Texture-based Fabric Defect Detection Method | Texture-based Fabric 缺陷 检测 Method |

#### reference (1)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-d5cc706d | Automated Fabric Defect Inspection: A Survey of Classifiers | Automated Fabric 缺陷 Inspection: A 综述 of Classifiers |

#### long_tail (2)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-a0b4f7ea | A Dataset of Raw Fabric Grayscale Images for Defect Detection | 数据集 of Raw Fabric Grayscale Images for 缺陷 检测 |
| c-d7122b60 | DCSFPSS assisted morphological approach for grey twill fabric defect detection and defect area measurement for fabric grading | DCSFPSS assisted morphological approach for grey twill fabric 缺陷 检测 and 缺陷 area measurement for fabric grading |

#### rejected (10)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-355ec514 | DogLayout: Denoising Diffusion GAN for Discrete and Continuous Layout Generation | DogLayout: Denoising 扩散模型 GAN for Discrete and Continuous Layout Generation | Layout generation paper, not defect detection; domain mismatch. |
| c-bf282ea0 | SCPAT-GAN: Structural Constrained and Pathology Aware Convolutional Transformer-GAN for Virtual Histology Staining of Hu | SCPAT-GAN: Structural Constrained and Pathology Aware 卷积 Transformer-GAN for Virtual Histology Staining of Hu | Medical imaging (OCT histology), cross-domain; rejected. |
| c-1b2a67c6 | Sequential Attention GAN for Interactive Image Editing | (中文含义由英文派生) | Interactive image editing paper, not defect detection. |
| c-7ab7d499 | Data-Efficient GAN Training Beyond (Just) Augmentations: A Lottery Ticket Perspective | (中文含义由英文派生) | GAN training methodology paper, no defect detection. |
| c-1c827030 | Recurrent Topic-Transition GAN for Visual Paragraph Generation | (中文含义由英文派生) | Visual paragraph generation, unrelated domain. |
| c-f7921a15 | Oriented object detection in optical remote sensing images using deep learning: a survey | Oriented 目标检测 in optical remote sensing images using 深度学习: a 综述 | Remote sensing oriented object detection survey; cross-domain. |
| c-5b75d402 | AIn't Nothing But a Survey? Using Large Language Models for Coding German Open-Ended Survey Responses on Survey Motivati | AIn't Nothing But a 综述? Using Large Language Models for Coding German Open-Ended 综述 Responses on 综述 Motivati | NLP survey coding paper; no overlap with vision/defect detection. |
| c-fb418d32 | The Methanol Multibeam Survey | Methanol Multibeam 综述 | Astronomy methanol maser survey; no relation to fabric/GAN topic. |
| c-85d1e682 | COCO | (中文含义由英文派生) | COCO is a general object detection dataset, not a fabric/textile defect dataset; cross-domain mismatch. |
| c-4313df1f | ImageNet | (中文含义由英文派生) | ImageNet is a general image classification dataset, not a fabric/textile defect dataset; cross-domain mismatch. |

#### dataset_and_repo_notes

> c-a0b4f7ea (RAW-FABRID): 709 grayscale fabric images, line-scan camera; primary dataset; verify public access and license.
> No fabric-specific GAN repo found; rely on standard AnoGAN/DCGAN/CycleGAN implementations (external).
> MVTec AD carpet/grid categories are external (not in pool); use as generalization check.

### §7 ENG-THESIS-015 — 《基于患者虚拟定位的三维人体重建关键技术研究》 — `weak`

| 维度 | 数值 |
|---|---:|
| batch | batch1 |
| elapsed | 326.1s |
| domain | 医学/人体三维视觉 |
| paper | 15 |
| dataset | 0 |
| repo | 0 |
| baseline | 2 |
| parallel | 3 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-10731-1021713041.htm |

**direction_recommendation**: 检索得到的证据极其稀疏且主题偏离严重。最贴近的主题是 c-1d3d2775（3D 人体网格/姿态/形状从单目图像恢复综述），可作为核心技术基础；c-226b38c6（前馈 3D 重建与视图合成）和 c-510ae629（NeRF/3DGS 鲁棒渲染）提供 3D 重建底层方法支撑；c-c60ce0a6（3D 视觉全局求解器）为姿态/配准提供几何优化背景。注意：原始主题“基于患者虚拟定位的三维人体重建”带有明显医学/放射治疗定位语境，但现有证据中几乎没有任何临床定位（CT 模拟、放射治疗摆位、虚拟定位）或患者特异性重建内容；检索结果主要是一般性计算机视觉方向的 3D 人体重建与 3D 视觉综述。强烈建议在进入下一步前由人类研究者澄清“患者虚拟定位”的具体临床场景与系统边界。

#### core (1)

| cid | 原文 title | 中文含义 | reason |
|---|---|---|---|
| c-1d3d2775 | Recovering 3D Human Mesh from Monocular Images: A Survey | Recovering 三维 Human Mesh from Monocular Images: A 综述 | Directly surveys 3D human body reconstruction from images, the most topically aligned source. |

#### baseline (2)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-1d3d2775 | Recovering 3D Human Mesh from Monocular Images: A Survey | Recovering 三维 Human Mesh from Monocular Images: A 综述 |
| c-226b38c6 | Advances in Feed-Forward 3D Reconstruction and View Synthesis: A Survey | Advances in Feed-Forward 三维 重建 and View Synthesis: A 综述 |

#### parallel (3)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-510ae629 | R3eVision: A Survey on Robust Rendering, Restoration, and Enhancement for 3D Low-Level Vision | R3eVision: A 综述 on Robust Rendering, Restoration, and Enhancement for 三维 Low-Level Vision |
| c-c60ce0a6 | Advances in Global Solvers for 3D Vision | Advances in Global Solvers for 三维 Vision |
| c-4b86c255 | GPT-4V(ision) is a Human-Aligned Evaluator for Text-to-3D Generation | GPT-4V(ision) is a Human-Aligned Evaluator for Text-to-三维 Generation |

#### reference (0) (无)
#### long_tail (1)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-aa382f03 | Research on Personnel Location Technology in Key Areas Based on ZigBee | (中文含义由英文派生) |

#### rejected (11)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-b616e6a7 | VLP: A Survey on Vision-Language Pre-training | VLP: A 综述 on Vision-Language Pre-training | Vision-language pre-training is cross-domain relative to 3D human body reconstruction. |
| c-f56e6c3b | The Evolution of First Person Vision Methods: A Survey | Evolution of First Person Vision Methods: A 综述 | First-person vision survey is unrelated to 3D human body reconstruction. |
| c-a4d21937 | Vision Mamba: A Comprehensive Survey and Taxonomy | Vision Mamba: A Comprehensive 综述 and Taxonomy | Vision Mamba survey focuses on state-space models; unrelated to 3D human reconstruction. |
| c-e9e7e897 | A rich bounty of AGN in the 9 square degree Bootes survey: high-z obscured AGN and large-scale structure | rich bounty of AGN (天文主动星系核，强噪声) in the 9 square degree Bootes 综述: high-z obscured AGN (天文主动星系核，强噪声) and large-scale structure | Astronomy paper on AGN galaxies; completely cross-domain. |
| c-8bfb8892 | GPT-4V(ision) is a Generalist Web Agent, if Grounded | (中文含义由英文派生) | GPT-4V web agent paper; unrelated to 3D human body reconstruction. |
| c-8976c6b5 | The Dawn of LMMs: Preliminary Explorations with GPT-4V(ision) | Dawn of LMMs: Preliminary Explorations with GPT-4V(ision) | GPT-4V exploratory paper; unrelated to 3D human body reconstruction. |
| c-4a7d71ad | GPT-4V(ision) System Card | (中文含义由英文派生) | GPT-4V system card; unrelated to 3D human reconstruction. |
| c-7b4706ce | Death-ision: the link between cellular resilience and cancer resistance to treatments | (中文含义由英文派生) | Biology/cancer paper mistakenly parsed as vision-related; fully cross-domain. |
| c-b4ec7948 | Unveiling the clinical incapabilities: a benchmarking study of GPT-4V(ision) for ophthalmic multimodal image analysis | (中文含义由英文派生) | Ophthalmic image analysis benchmarking; not 3D human body reconstruction. |
| c-000b0a98 | GPT-4V(ision) as A Social Media Analysis Engine | (中文含义由英文派生) | Social media analysis paper; unrelated to 3D reconstruction. |
| c-c7709815 | Holistic Analysis of Hallucination in GPT-4V(ision): Bias and Interference Challenges | (中文含义由英文派生) | GPT-4V hallucination study; unrelated to 3D human reconstruction. |

#### dataset_and_repo_notes

> No medical imaging dataset (e.g., TCIA, DeepLesion) or radiotherapy positioning dataset surfaced from the queries — must be sourced manually by the student.
> No 3D human body reconstruction codebase (e.g., SMPL/SMPL-X, HMR, PIFu, ICON) appeared in the evidence pool — student must search GitHub independently.
> No CT/CBCT-derived patient 3D reconstruction dataset or pipeline was retrieved; clinical positioning workflows remain uncovered.

### §8 ENG-THESIS-016 — 《基于深度学习的视觉SLAM语义地图的研究》 — `weak`

| 维度 | 数值 |
|---|---:|
| batch | batch1 |
| elapsed | 264.6s |
| domain | 三维视觉/SLAM/点云 |
| paper | 41 |
| dataset | 0 |
| repo | 0 |
| baseline | 4 |
| parallel | 6 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-10336-1022019365.htm |

**direction_recommendation**: Anchor the survey on the canonical semantic-visual-SLAM baseline DS-SLAM (SegNet+ORB-SLAM2 in dynamic scenes) and contrast it with two 2025-era directions: (a) semantic filtering plus adaptive robust kernels for unknown dynamic objects (VAR-SLAM) and (b) open-source dynamic SLAM frameworks that jointly model moving-object trajectories (DynoSAM). Use DBLD-SLAM to cover the deep-feature branch and the Overview of Visual SLAM survey as the spine for the traditional→deep-learning narrative. Treat MLP-SLAM, PL-VINS, ViSTA-SLAM, and OKVIS2-X as parallel SLAM-front-end/geometry references. Flag three items (c-124e3d23 metadata mismatch, c-197487aa LIFT-SLAM stub, c-68b1d797 path-planning student project) for manual confirmation before citing. Strong-evidence mapping and explicit deep-semantic baselines are well-covered; NeRF/implicit-semantic mapping and dataset/benchmark coverage are thin and should be the next-retrieval gap.

#### core (6)

| cid | 原文 title | 中文含义 | reason |
|---|---|---|---|
| c-052845f3 | VAR-SLAM: Visual Adaptive and Robust SLAM for Dynamic Environments | VAR-SLAM: Visual Adaptive and Robust SLAM for 动态 Environments | Adaptive semantic-aware visual SLAM for dynamic scenes; directly on-topic. |
| c-574dfd86 | OKVIS2-X: Open Keyframe-based Visual-Inertial SLAM Configurable with Dense Depth or LiDAR, and GNSS | OKVIS2-X: Open Keyframe-based 视觉惯性 SLAM Configurable with Dense Depth or 激光雷达, and GNSS | State-of-the-art multi-sensor SLAM with dense mapping; relevant core reference. |
| c-9a6aaeab | DynoSAM: Open-Source Smoothing and Mapping Framework for Dynamic SLAM | DynoSAM: Open-Source Smoothing and Mapping Framework for 动态 SLAM | Dynamic SLAM framework explicitly addressing semantic understanding; core match. |
| c-06ecb20b | DS-SLAM: A Semantic Visual SLAM towards Dynamic Environments | DS-SLAM: A 语义 Visual SLAM towards 动态 Environments | DS-SLAM is a canonical semantic visual SLAM baseline for dynamic scenes. |
| c-d4e24945 | DBLD-SLAM: A Deep-Learning Visual SLAM System Based on Deep Binary Local Descriptor | (中文含义由英文派生) | Deep-learning based visual SLAM using learned binary descriptors; core match. |
| c-8fbe00bf | Overview of Visual SLAM Technology: From Traditional to Deep Learning Methods | Overview of Visual SLAM Technology: From Traditional to 深度学习 Methods | Survey of visual SLAM from traditional to deep learning methods; ideal background survey. |

#### baseline (4)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-06ecb20b | DS-SLAM: A Semantic Visual SLAM towards Dynamic Environments | DS-SLAM: A 语义 Visual SLAM towards 动态 Environments |
| c-d4e24945 | DBLD-SLAM: A Deep-Learning Visual SLAM System Based on Deep Binary Local Descriptor | (中文含义由英文派生) |
| c-052845f3 | VAR-SLAM: Visual Adaptive and Robust SLAM for Dynamic Environments | VAR-SLAM: Visual Adaptive and Robust SLAM for 动态 Environments |
| c-9a6aaeab | DynoSAM: Open-Source Smoothing and Mapping Framework for Dynamic SLAM | DynoSAM: Open-Source Smoothing and Mapping Framework for 动态 SLAM |

#### parallel (6)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-574dfd86 | OKVIS2-X: Open Keyframe-based Visual-Inertial SLAM Configurable with Dense Depth or LiDAR, and GNSS | OKVIS2-X: Open Keyframe-based 视觉惯性 SLAM Configurable with Dense Depth or 激光雷达, and GNSS |
| c-c9e504dc | PL-VINS: Real-Time Monocular Visual-Inertial SLAM with Point and Line Features | PL-VINS: 实时 Monocular 视觉惯性 SLAM with Point and Line Features |
| c-d7b6839b | ViSTA-SLAM: Visual SLAM with Symmetric Two-view Association | (中文含义由英文派生) |
| c-047f5743 | MLP-SLAM: Multilayer Perceptron-Based Simultaneous Localization and Mapping | (中文含义由英文派生) |
| c-3a6c481f | Self-supervised Learning of Contextualized Local Visual Embeddings | 自监督 Learning of Contextualized Local Visual Embeddings |
| c-cd8db1f9 | Renderable Neural Radiance Map for Visual Navigation‬ | (中文含义由英文派生) |

#### reference (4)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-8fbe00bf | Overview of Visual SLAM Technology: From Traditional to Deep Learning Methods | Overview of Visual SLAM Technology: From Traditional to 深度学习 Methods |
| c-4a5345d4 | 14 Lectures on Visual SLAM: from Theory to Practice | (中文含义由英文派生) |
| c-e3a00498 | lznhello/slambook-en | 仓库 lznhello/slambook-en |
| c-7cf2ced8 | A multitask deep learning model for real-time deployment in embedded systems | 多任务 深度学习 model for 实时 deployment in 嵌入式 systems |

#### long_tail (8)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-51a1fea9 | rllab-snu/RNR-Map | 仓库 rllab-snu/RNR-Map |
| c-5f39b232 | Rich-King395/ORB-SLAM3-with-dense-pointcloud-reconstruction | 仓库 Rich-King395/ORB-SLAM3-with-dense-pointcloud-reconstruction |
| c-e9de8699 | sta105/VIORB | 仓库 sta105/VIORB |
| c-4db34ea6 | maazmb/LEP-Hybrid-Visual-Odometry | 仓库 maazmb/LEP-Hybrid-Visual-Odometry |
| c-5b222255 | mlab-upenn/ISP2021-visual_slam | 仓库 mlab-upenn/ISP2021-visual_slam |
| c-124e3d23 | A rich bounty of AGN in the 9 square degree Bootes survey: high-z obscured AGN and large-scale structure | rich bounty of AGN (天文主动星系核，强噪声) in the 9 square degree Bootes 综述: high-z obscured AGN (天文主动星系核，强噪声) and large-scale structure |
| c-197487aa | LIFT-SLAM | (中文含义由英文派生) |
| c-68b1d797 | Robot Path Planning based on Visual SLAM | 机器人 Path Planning based on Visual SLAM |

#### rejected (6)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-7f510f66 | Learn to Accumulate Evidence from All Training Samples: Theory and Practice | (中文含义由英文派生) | Evidential deep learning theory paper; no SLAM or semantic mapping content. |
| c-c0fa93e7 | The Modern Mathematics of Deep Learning | Modern Mathematics of 深度学习 | Mathematical foundations of deep learning; no application to SLAM. |
| c-2961148d | Deep Learning and Computational Physics (Lecture Notes) | 深度学习 and Computational Physics (Lecture Notes) | Lecture notes on deep learning + computational physics; not robotics. |
| c-f78f4464 | Monodense Deep Neural Model for Determining Item Price Elasticity | (中文含义由英文派生) | Price elasticity/economics paper; no robotics content. |
| c-092aa3d7 | Deep learning observables in computational fluid dynamics | 深度学习 observables in computational fluid 动态 | Computational fluid dynamics paper; cross-domain. |
| c-2466f868 | DILIE: Deep Internal Learning for Image Enhancement | (中文含义由英文派生) | Image enhancement paper; no SLAM relevance. |

#### dataset_and_repo_notes

> c-06ecb20b DS-SLAM supplies SegNet+ORB-SLAM2 reference pipeline plus TUM/RGB-D benchmark usage.
> c-5f39b232 is an ORB-SLAM3 ROS dense-pointcloud fork useful as code skeleton, but lacks semantic layer.
> c-e9de8699 VIORB provides Visual-Inertial ORB-SLAM reference but no DL/semantic module.
> c-51a1fea9 RNR-Map is a NeRF-based repo usable only for implicit-map discussion, not semantic SLAM.
> c-e3a00498 and c-4a5345d4 are foundational visual SLAM theory sources, not DL-semantic.
> No dedicated RGB-D or driving semantic-SLAM dataset was returned by retrievers — gap to flag.

### §9 ENG-THESIS-018 — 《基于深度学习的三维点云补全方法研究》 — `weak`

| 维度 | 数值 |
|---|---:|
| batch | batch1 |
| elapsed | 265.4s |
| domain | 三维视觉/SLAM/点云 |
| paper | 23 |
| dataset | 0 |
| repo | 0 |
| baseline | 1 |
| parallel | 7 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-10284-1022418660.htm |

**direction_recommendation**: This literature survey targets deep-learning methods for 3D point cloud completion. After evidence filtering, only one core baseline (PCN) and four parallel completion networks (cascaded refinement, consistency loss, DC-PCN, DCSE-PCN, DFG-PCN) survived in the candidate pool. Listed method anchors PoinTr, GRNet, SnowflakeNet returned no evidence and must be backfilled in Re03 via dedicated retrieval. PCN dataset and ShapeNet are the primary datasets; KITTI is a secondary real-scan benchmark. The repo point-cloud-completion-survey provides a working bibliography anchor; the bulk of returned github results are Cmder shell noise and were rejected. Proceed with a taxonomy organized as (i) encoder-decoder / coarse-to-fine, (ii) Transformer/GAN-based, (iii) graph/quantization-based, with PCN as anchor baseline and CD/SA-CD as loss-function reference. Re-run targeted searches for PoinTr/GRNet/SnowflakeNet and a dedicated survey before drafting.

#### core (4)

| cid | 原文 title | 中文含义 | reason |
|---|---|---|---|
| c-817651f3 | PCN: Point Completion Network | (中文含义由英文派生) | Foundational PCN paper explicitly listed in topic method terms; canonical baseline for completion. |
| c-556bf35c | keneniwt/Point-Cloud-Completion-Survey | 仓库 keneniwt/Point-Cloud-Completion-Survey | GitHub survey repo explicitly titled Point-Cloud-Completion-Survey; directly matches topic. |
| c-9a376778 | PCN | (中文含义由英文派生) | PCN dataset is the canonical benchmark for point cloud completion; listed in topic object_terms. |
| c-e80a53d8 | ShapeNet | (中文含义由英文派生) | ShapeNet is the primary 3D shape repository and synthetic training data source for completion methods. |

#### baseline (1)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-817651f3 | PCN: Point Completion Network | (中文含义由英文派生) |

#### parallel (7)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-470051d7 | Enhancing Performance of Point Cloud Completion Networks with Consistency Loss | Enhancing Performance of 点云 Completion Networks with Consistency Loss |
| c-089b8a42 | Cascaded Refinement Network for Point Cloud Completion with Self-supervision | Cascaded Refinement Network for 点云 Completion with Self-supervision |
| c-da01f67f | DC-PCN: Point Cloud Completion Network with Dual-Codebook Guided Quantization | DC-PCN: 点云 Completion Network with Dual-Codebook Guided Quantization |
| c-7468f29f | DCSE-PCN: A Coarse-to-Fine Point Completion Network with Details Compensation and Structure Enhancement | (中文含义由英文派生) |
| c-7049e7df | DFG-PCN: Point Cloud Completion With Degree-Flexible Point Graph | DFG-PCN: 点云 Completion With Degree-Flexible Point Graph |
| c-1eebfe0c | Multimodal Shape Completion via IMLE | (中文含义由英文派生) |
| c-04c49e47 | Structural-Adaptive Contrastive Chamfer Distance for Robust Point Cloud Completion | Structural-Adaptive 对比学习 Chamfer Distance for Robust 点云 Completion |

#### reference (4)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-556bf35c | keneniwt/Point-Cloud-Completion-Survey | 仓库 keneniwt/Point-Cloud-Completion-Survey |
| c-9a376778 | PCN | (中文含义由英文派生) |
| c-e80a53d8 | ShapeNet | (中文含义由英文派生) |
| c-5cde6c91 | KITTI | (中文含义由英文派生) |

#### long_tail (4)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-6cc8fc86 | Sequential Point Clouds: A Survey | Sequential 点云: A 综述 |
| c-77abd689 | R3eVision: A Survey on Robust Rendering, Restoration, and Enhancement for 3D Low-Level Vision | R3eVision: A 综述 on Robust Rendering, Restoration, and Enhancement for 三维 Low-Level Vision |
| c-d77579d1 | Advances in Global Solvers for 3D Vision | Advances in Global Solvers for 三维 Vision |
| c-7ce2a4fb | NBV-SC: Next Best View Planning based on Shape Completion for Fruit Mapping and Reconstruction | NBV-SC: Next Best View Planning based on Shape Completion for Fruit Mapping and 重建 |

#### rejected (20)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-343bb79e | A Systematic Approach for Cross-source Point Cloud Registration by Preserving Macro and Micro Structures | Systematic Approach for Cross-source 点云 配准 by Preserving Macro and Micro Structures | Cross-source point cloud registration paper, not about completion; rejected as cross-task content. |
| c-240fd55d | L-PCN: A Point Cloud Accelerator Exploiting Spatial Locality through Octree-based Islandization | L-PCN: A 点云 Accelerator Exploiting Spatial Locality through Octree-based Islandization | Hardware accelerator paper for Point Cloud Networks (classification/segmentation), not completion. |
| c-4b9407f6 | Ch-Jad/CH-JaDi-Rajput1 | 仓库 Ch-Jad/CH-JaDi-Rajput1 | Cmder shell-config repository, completely unrelated to 3D point cloud completion research. |
| c-b2de0239 | c:\users\[CH JaDi Rajput]\cmder_config      ├───bin      ├───config      │   └───profile.d      └───opt | c:\users\[CH JaDi Rajput]\cmder_config   ├───bin   ├───config   │  └───profile.d   └───opt | Title is a filesystem path string from Cmder config; not a research artifact. |
| c-cae57cf9 | cd $CMDER_ROOT/vendor git clone https://github.com/karlin/mintty-colors-solarized.git cd mintty-colors-solarized/ echo s | (中文含义由英文派生) | Title is a shell snippet for mintty color installation; not a research artifact. |
| c-ef02be81 | 1. {cmd::Cmder as Admin} | (中文含义由英文派生) | Title is a Cmder command; unrelated to research. |
| c-51313796 | cmd /s /k ""%ConEmuDir%\..\init.bat" [ADD ARGS HERE]" | (中文含义由英文派生) | ConEmu/Cmder init batch invocation; unrelated shell content. |
| c-4256b9c7 | [new-alias | set-alias] alias command | (中文含义由英文派生) | PowerShell alias snippet from Cmder docs; not research. |
| c-e0bc116e | cmd /c "[path_to_external_env]\bin\bash --login -i" -new_console | (中文含义由英文派生) | Title is a Cmder shell command string; no relation to point cloud completion. |
| c-07089702 | # CMDER_ROOT=${USERPROFILE}/cmder  # This is not required if launched from Cmder. | # CMDER_ROOT=${USERPROFILE}/cmder # This is not required if launched from Cmder. | Cmder shell config text; no connection to 3D point cloud research. |
| c-4076ecf4 | batch    cmd.exe /k ""%ConEmuDir%\..\init.bat" /startnotepad" | batch  cmd.exe /k ""%ConEmuDir%\..\init.bat" /startnotepad" | ConEmu batch command fragment; unrelated to point cloud completion. |
| c-4150ead4 | batch    %ccall% "/startNotepad" "start" "notepad.exe" | batch  %ccall% "/startNotepad" "start" "notepad.exe" | ConEmu task batch code; unrelated content. |
| c-ea8b8312 | To see detailed usage of | (中文含义由英文派生) | Incomplete usage description fragment; unrelated content. |
| c-f8c9d8e2 | , you are running a newer version of Cmder, follow the below process:  1. Exit all Cmder sessions and relaunch | , you are running a newer version of Cmder, follow the below process: 1. Exit all Cmder sessions and relaunch | Cmder upgrade instruction text; no research content. |
| c-5214ced8 | , this backs up your existing | (中文含义由英文派生) | Backup instruction text; unrelated. |
| c-56ca52e3 | contains any custom settings you have made using the 'Setup Tasks' settings dialog.  2. Exit all Cmder sessions and back | contains any custom settings you have made using the 'Setup Tasks' settings dialog. 2. Exit all Cmder sessions and back | Cmder settings backup note; unrelated. |
| c-c6fa681a | .     * Editing files under | .   * Editing files under | Fragmented Cmder config note; unrelated. |
| c-cfd31007 | is not recommended since you will need to re-apply these changes after any upgrade.  All user customizations should go i | is not recommended since you will need to re-apply these changes after any upgrade. All user customizations should go i | Cmder upgrade advice text; unrelated. |
| c-84925032 | folder.  3.  Delete the | folder. 3. Delete the | Cmder upgrade instruction fragment; unrelated. |
| c-3b5fac71 | folder. 4.  Extract the new | folder. 4. Extract the new | Cmder extraction instruction fragment; unrelated. |

#### dataset_and_repo_notes

> c-9a376778 PCN dataset: canonical 28974-train/800-val benchmark over 8 categories; primary eval for c-817651f3 PCN and derivatives (c-da01f67f, c-7468f29f, c-7049e7df).
> c-e80a53d8 ShapeNet: source of clean CAD models; partial inputs synthesized via back-projection; paired with PCN dataset splits.
> c-5cde6c91 KITTI: real outdoor LiDAR scans used for cross-domain / real-world completion evaluation; not standard training set.
> c-556bf35c keneniwt/Point-Cloud-Completion-Survey: MIT-licensed GitHub bibliography; low-confidence evidence layer, manually verify completeness before citing.

### §10 ENG-THESIS-022 — 《基于深度学习的钢铁表面缺陷检测研究》 — `pass`

| 维度 | 数值 |
|---|---:|
| batch | r4 |
| elapsed | 203.8s |
| domain | 工业缺陷检测/机器视觉 |
| paper | 28 |
| dataset | 4 |
| repo | 6 |
| baseline | 3 |
| parallel | 5 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-10561-1021892121.htm |

**direction_recommendation**: Focus the survey on YOLO-family deep-learning detectors for steel surface defect detection, benchmarked primarily on NEU-DET/GC10-DET/severstal-style strip-steel datasets. The retrieval surfaced two strong on-topic core papers (c-156dbb1a enhanced zero-shot YOLOv10 for tiny steel defects; c-e91b01a5 YOLO-GVMamba state-space YOLO for steel defects) that should anchor the parallel-method group. Use c-b50bf6ad DAMO-YOLO as a generic YOLO baseline reference. Treat c-430fa090 (poisoning attacks on steel defect detectors) as an adversarial-robustness parallel thread. Treat c-46c528b8 YOLO-World and c-28b3d7e8 YOLO-IOD as transferable modules (open-vocabulary / incremental learning) for evolving defect categories. c-ba4d55ff (MS-YOLO edge deployment) and c-e66f04bb (D-YOLO adverse weather) inform deployment-robustness discussion. All other arxiv candidates are cross-domain background only. No steel-specific dataset (NEU-DET, GC10-DET) was retrieved — manual confirmation of dataset availability is required before Re03.

#### core (2)

| cid | 原文 title | 中文含义 | reason |
|---|---|---|---|
| c-156dbb1a | Enhanced Zero-Shot YOLOv10 for Multi-Class Tiny-Object Detection of Steel Surface Defects | Enhanced Zero-Shot YOLOv10 for Multi-Class Tiny-目标检测 of Steel Surface 缺陷 | Direct YOLOv10 method paper on steel surface tiny defect detection. |
| c-e91b01a5 | YOLO-GVMamba: An Efficient Steel Surface Defect Object Detection Method Based on State Space Model | YOLO 实时目标检测-GVMamba: An Efficient Steel Surface 缺陷 目标检测 Method Based on State Space Model | Steel-surface-defect YOLO method (SSM-based), directly on-topic. |

#### baseline (3)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-156dbb1a | Enhanced Zero-Shot YOLOv10 for Multi-Class Tiny-Object Detection of Steel Surface Defects | Enhanced Zero-Shot YOLOv10 for Multi-Class Tiny-目标检测 of Steel Surface 缺陷 |
| c-e91b01a5 | YOLO-GVMamba: An Efficient Steel Surface Defect Object Detection Method Based on State Space Model | YOLO 实时目标检测-GVMamba: An Efficient Steel Surface 缺陷 目标检测 Method Based on State Space Model |
| c-b50bf6ad | DAMO-YOLO : A Report on Real-Time Object Detection Design | DAMO-YOLO 实时目标检测 : A Report on 实时 目标检测 Design |

#### parallel (5)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-430fa090 | Poisoning Object Detection Models for Surface Defect Inspection in Steel Manufacturing | Poisoning 目标检测 Models for Surface 缺陷 Inspection in Steel Manufacturing |
| c-46c528b8 | YOLO-World: Real-Time Open-Vocabulary Object Detection | YOLO 实时目标检测-World: 实时 Open-Vocabulary 目标检测 |
| c-28b3d7e8 | YOLO-IOD: Towards Real Time Incremental Object Detection | YOLO 实时目标检测-IOD: Towards 实时 Incremental 目标检测 |
| c-ba4d55ff | MS-YOLO: Infrared Object Detection for Edge Deployment via MobileNetV4 and SlideLoss | MS-YOLO 实时目标检测: Infrared 目标检测 for Edge Deployment via MobileNetV4 and SlideLoss |
| c-e66f04bb | D-YOLO a robust framework for object detection in adverse weather conditions | D-YOLO 实时目标检测 a robust framework for 目标检测 in adverse weather conditions |

#### reference (8)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-698b7d95 | Oriented object detection in optical remote sensing images using deep learning: a survey | Oriented 目标检测 in optical remote sensing images using 深度学习: a 综述 |
| c-11565550 | A Survey of Self-Supervised and Few-Shot Object Detection | 综述 of 自监督 and 少样本 目标检测 |
| c-eb4ad0df | 3D Object Detection for Autonomous Driving: A Comprehensive Survey | 三维 目标检测 for 自动驾驶: A Comprehensive 综述 |
| c-a6ef4c35 | SPMamba-YOLO: An Underwater Object Detection Network Based on Multi-Scale Feature Enhancement and Global Context Modeling | SPMamba-YOLO 实时目标检测: An Underwater 目标检测 Network Based on Multi-Scale Feature Enhancement and Global Context Modeling |
| c-b5bba4c9 | PVAFN: Point-Voxel Attention Fusion Network with Multi-Pooling Enhancing for 3D Object Detection | PVAFN: Point-Voxel Attention Fusion Network with Multi-Pooling Enhancing for 三维 目标检测 |
| c-daf5d513 | Exploring Depth Contribution for Camouflaged Object Detection | Exploring Depth Contribution for Camouflaged 目标检测 |
| c-7444c9b1 | Object Contour and Edge Detection with RefineContourNet | Object Contour and Edge 检测 with RefineContourNet |
| c-fd8a7a2d | YOLO-CL: Galaxy cluster detection in the SDSS with deep machine learning | YOLO 实时目标检测-CL: Galaxy cluster 检测 in the SDSS with deep machine learning |

#### long_tail (4)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-750de2d0 | amusi/awesome-object-detection | 仓库 amusi/awesome-object-detection |
| c-398abb91 | Smorodov/Deep-learning-object-detection-links. | 仓库 Smorodov/Deep-learning-object-detection-links. |
| c-be1fecfe | Alpaca-zip/ultralytics_ros | 仓库 Alpaca-zip/ultralytics_ros |
| c-0915ea3e | rbgirshick/voc-dpm | 仓库 rbgirshick/voc-dpm |

#### rejected (18)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-19c3a81b | AIn't Nothing But a Survey? Using Large Language Models for Coding German Open-Ended Survey Responses on Survey Motivati | AIn't Nothing But a 综述? Using Large Language Models for Coding German Open-Ended 综述 Responses on 综述 Motivati | NLP/LLM survey on German open-ended survey responses, cross-domain. |
| c-9df0d6bd | chrisneagu/FTC-Skystone-Dark-Angels-Romania-2020 | 仓库 chrisneagu/FTC-Skystone-Dark-Angels-Romania-2020 | FTC robotics SDK repository; completely unrelated to steel defect detection. |
| c-8deabd54 | Import project (Eclipse ADT, Gradle, etc.) | (中文含义由英文派生) | Garbled Android/Eclipse import error message, not a real paper. |
| c-3fce980f | E RobotCore: lynx xmit lock: #### abandoning lock: | (中文含义由英文派生) | FTC robot log message, not a research paper. |
| c-84506b20 | Could not find com.android.tools.lint:lint-gradle:26.1.4 | (中文含义由英文派生) | Gradle dependency error string, not a real paper. |
| c-eb05a9a8 | Version 3.00 (built on 17.04.013) | (中文含义由英文派生) | Version string artifact, not a research paper. |
| c-f8fa2c35 | missing hardware leaves robot controller disconnected from driver station | missing hardware leaves 机器人 controller disconnected from driver station | FTC robotics issue title, not a research paper. |
| c-b1b13263 | fast tapping of Init/Start causes problems | (中文含义由英文派生) | FTC robotics bug report, not a paper. |
| c-ab4970e0 | molyswu/hand_detection | 仓库 molyswu/hand_detection | Hand detection repo, not steel defect domain. |
| c-c4e62460 | Lending a hand: Detecting hands and recognizing activities in complex egocentric interactions. | (中文含义由英文派生) | Hand activity recognition paper, wrong domain. |
| c-46b07819 | >  ====== Hand Inference graph loaded. | > ====== Hand Inference graph loaded. | Code log line, not a paper. |
| c-a4ac4cf7 | python   detection_graph = tf.Graph()     with detection_graph.as_default():         od_graph_def = tf.GraphDef()        | python  detection_graph = tf.Graph()   with detection_graph.as_default():     od_graph_def = tf.GraphDef() | Code snippet, not a paper. |
| c-afe4e187 | python   (boxes, scores, classes, num) = sess.run(         [detection_boxes, detection_scores,             detection_cla | python  (boxes, scores, classes, num) = sess.run(     [detection_boxes, detection_scores,       detection_cla | Code snippet, not a paper. |
| c-dd9787d5 | cmd   # load and run detection on video at path "videos/chess.mov"   python detect_single_threaded.py --source videos/ch | cmd  # load and run 检测 on video at path "videos/chess.mov"  python detect_single_threaded.py --source videos/ch | Command-line snippet, not a paper. |
| c-375b5e2d | Cityscapes | (中文含义由英文派生) | Urban street scenes dataset, wrong domain. |
| c-d60c92fb | COCO | (中文含义由英文派生) | General COCO dataset, not steel-specific. |
| c-3fde03a1 | Pascal VOC | (中文含义由英文派生) | General VOC dataset, wrong domain. |
| c-87949821 | DOTA | (中文含义由英文派生) | Aerial imagery dataset, wrong domain. |

#### dataset_and_repo_notes

> NEU-DET, GC10-DET, and Severstal steel-defect datasets were NOT returned by any adapter — manual verification required.
> c-156dbb1a and c-e91b01a5 both evaluate on steel surface defect datasets but exact dataset names not in retrieved metadata.
> c-750de2d0 (amusi/awesome-object-detection) is the best general entry-point repo for discovery but is not steel-specific.
> c-be1fecfe (YOLOv8 ROS wrapper) is the most relevant deployment-oriented repo for industrial line integration.

### §11 ENG-THESIS-024 — 《基于深度学习的无监督三维点云配准算法研究》 — `pass`

| 维度 | 数值 |
|---|---:|
| batch | r1 |
| elapsed | 222.9s |
| domain | 三维视觉/SLAM/点云 |
| paper | 19 |
| dataset | 2 |
| repo | 3 |
| baseline | 3 |
| parallel | 7 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-10614-1021747888.htm |

**direction_recommendation**: Topic: deep learning based unsupervised 3D point cloud registration. Evidence coverage is thin and partly off-target. Only one paper (c-23fc8dab, multi-scale + unsupervised transfer learning, 3DV 2021) is a direct unsupervised-deep match. DCP (c-e9e4b8d7, 2019) is the canonical supervised baseline. A broad deep-learning-for-point-cloud survey (c-48631d21, 2019) anchors background. ModelNet40 and ScanNet are the standard evaluation datasets. Other candidates are either supervised-only parallel work (c-c61d07ac, c-ba5c109c, c-89fd7b7e, c-810a25a3, c-33b54bdb, c-7ad54da6, c-471f8b2e) or domain-mismatched and rejected (forestry, medical surface, RL, tracking, adversarial). Recommended direction: anchor a taxonomy on (i) unsupervised/self-supervised correspondence learning (contrastive, cycle-consistency, Chamfer/EMD-based losses), (ii) learned end-to-end registration without pose labels (transfer/curriculum), and (iii) Transformer/GNN backbones with unsupervised losses; benchmark on ModelNet40 and indoor RGB-D scenes (ScanNet/ScanObjectNN) against DCP family. Gaps: very few unsupervised-deep papers were retrieved; needs_manual queries should target ICP-Net, PointNetLK, PREDATOR, RPM-Ne

#### core (3)

| cid | 原文 title | 中文含义 | reason |
|---|---|---|---|
| c-48631d21 | Deep Learning for 3D Point Clouds: A Survey | 深度学习 for 三维 点云: A 综述 | Foundational survey on deep learning for 3D point clouds; broad reference. |
| c-e9e4b8d7 | Deep Closest Point: Learning Representations for Point Cloud Registration | Deep Closest Point: Learning Representations for 点云 配准 | DCP is the canonical deep learning baseline for point cloud registration. |
| c-23fc8dab | 3D Point Cloud Registration with Multi-Scale Architecture and Unsupervised Transfer Learning | 三维 点云 配准 with Multi-Scale Architecture and 无监督 迁移学习 | Unsupervised transfer learning for point cloud registration; direct topic match. |

#### baseline (3)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-e9e4b8d7 | Deep Closest Point: Learning Representations for Point Cloud Registration | Deep Closest Point: Learning Representations for 点云 配准 |
| c-23fc8dab | 3D Point Cloud Registration with Multi-Scale Architecture and Unsupervised Transfer Learning | 三维 点云 配准 with Multi-Scale Architecture and 无监督 迁移学习 |
| c-48631d21 | Deep Learning for 3D Point Clouds: A Survey | 深度学习 for 三维 点云: A 综述 |

#### parallel (7)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-c61d07ac | Deep Models with Fusion Strategies for MVP Point Cloud Registration | Deep Models with Fusion Strategies for MVP 点云 配准 |
| c-ba5c109c | Geometry-to-Image Synthesis-Driven Generative Point Cloud Registration | Geometry-to-Image Synthesis-Driven Generative 点云 配准 |
| c-89fd7b7e | Improving Deep Learning Point Cloud Registration with Semantic Labels | Improving 深度学习 点云 配准 with 语义 Labels |
| c-810a25a3 | An efficient point cloud registration method based on deep learning framework | efficient 点云 配准 method based on 深度学习 framework |
| c-33b54bdb | Deep Learning Registration Algorithm for Point Cloud Data and BIM Information Modeling Technology | 深度学习 配准 Algorithm for 点云 Data and BIM Information Modeling Technology |
| c-471f8b2e | Crane-YU/rethink_rotation | 仓库 Crane-YU/rethink_rotation |
| c-7ad54da6 | jundaozhilian/DeepVCP-PyTorch | 仓库 jundaozhilian/DeepVCP-PyTorch |

#### reference (6)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-e28bab79 | A Systematic Approach for Cross-source Point Cloud Registration by Preserving Macro and Micro Structures | Systematic Approach for Cross-source 点云 配准 by Preserving Macro and Micro Structures |
| c-0e870ab7 | Benchmark of multi-view Terrestrial Laser Scanning Point Cloud data registration algorithms | 基准 of 多视图 Terrestrial Laser Scanning 点云 data 配准 algorithms |
| c-3e035541 | ScanNet | (中文含义由英文派生) |
| c-fb27e1e5 | ModelNet40 | (中文含义由英文派生) |
| c-5fad4f45 | Advances in Global Solvers for 3D Vision | Advances in Global Solvers for 三维 Vision |
| c-93d19613 | R3eVision: A Survey on Robust Rendering, Restoration, and Enhancement for 3D Low-Level Vision | R3eVision: A 综述 on Robust Rendering, Restoration, and Enhancement for 三维 Low-Level Vision |

#### long_tail (0) (无)
#### rejected (8)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-54876add | Automatic marker-free registration based on similar tetrahedras for single-tree point clouds | Automatic marker-free 配准 based on similar tetrahedras for single-tree 点云 | Forestry domain marker-free registration; no deep learning; cross-domain for this topic. |
| c-e40394dc | Cortical surface registration using unsupervised learning | Cortical surface 配准 using 无监督 learning | Medical cortical surface registration, not 3D point cloud domain. |
| c-d42f0a1d | A Tutorial about Random Neural Networks in Supervised Learning | Tutorial about Random 神经网络 in 有监督 Learning | Random neural networks tutorial; no 3D/point cloud relevance. |
| c-d56f89e1 | URLB: Unsupervised Reinforcement Learning Benchmark | URLB: 无监督 Reinforcement Learning 基准 | Reinforcement learning benchmark; no connection to point cloud registration. |
| c-a42632e3 | Unsupervised Deep Representation Learning for Real-Time Tracking | 无监督 Deep Representation Learning for 实时 跟踪 | Visual tracking paper; no point cloud registration relevance. |
| c-e1d5318c | ShapeAdv: Generating Shape-Aware Adversarial 3D Point Clouds | ShapeAdv: Generating Shape-Aware Adversarial 三维 点云 | Adversarial perturbation paper on point clouds; no registration task. |
| c-c9f1b2de | Novel Approaches for Point Cloud Analysis with Evidential Methods: A Multifaceted Approach to Object Pose Estimation, Po | Novel Approaches for 点云 Analysis with Evidential Methods: A Multifaceted Approach to Object Pose Estimation, Po | Forestry PCR with evidential methods; cross-domain and not unsupervised deep. |
| c-4ef2371b | marecek199/Thesis_3DDataGenerationSegmentationRegistration | 仓库 marecek199/Thesis_3DDataGenerationSegmentationRegistration | Diploma thesis repo focuses on 3D point cloud segmentation for bin-picking, not registration. |

#### dataset_and_repo_notes

> ModelNet40 (c-fb27e1e5) is the canonical shape benchmark for PCR; use clean-pairs variant for unsupervised evaluation.
> ScanNet (c-3e035541) supports indoor RGB-D partial overlap PCR evaluation, complementary to ModelNet40.
> rethink_rotation (c-471f8b2e) provides rotation-invariant PCR code useful as parallel baseline implementation.
> DeepVCP-PyTorch (c-7ad54da6) is a LiDAR PCR reference impl; helpful for outdoor registration comparisons.

### §12 ENG-THESIS-027 — 《基于YOLOv5模型的遥感影像飞机目标检测》 — `pass`

| 维度 | 数值 |
|---|---:|
| batch | r1 |
| elapsed | 227.8s |
| domain | 遥感/无人机目标检测 |
| paper | 19 |
| dataset | 2 |
| repo | 5 |
| baseline | 3 |
| parallel | 2 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-10710-1023420120.htm |

**direction_recommendation**: Recommended direction: an oriented (rotated) bounding-box aircraft detector built on a YOLOv5 backbone, trained and evaluated on the DOTA dataset with a focus on small-aircraft instances. The evidence chain is strong but thin in count: the closest direct match is c-fc6212df (YOLOv5 for oriented detection in RS imagery) and c-a00e5114 (small oriented objects in aerial images), with c-fbafaa77 as the foundational RS-oriented-detection survey. Methodologically, c-dc50530c (HIC-YOLOv5, small-object FPN/attention improvements) supplies a drop-in upgrade path. Scope should remain 2D optical RS aircraft only; reject the LiDAR, autonomous-driving, contour, and camouflaged items. Two outstanding gaps need human clarification: confirm whether the student must literally use YOLOv5 (not YOLOv7/v8) and whether evaluation target is DOTA aircraft-only or full multi-class DOTA. Until those are answered, no re-search is recommended; downstream stages can proceed with the listed baselines and DOTA.

#### core (5)

| cid | 原文 title | 中文含义 | reason |
|---|---|---|---|
| c-fbafaa77 | Oriented object detection in optical remote sensing images using deep learning: a survey | Oriented 目标检测 in optical remote sensing images using 深度学习: a 综述 | Direct survey on oriented object detection in optical RS imagery; foundational reference for the topic. |
| c-a00e5114 | Improving the Detection of Small Oriented Objects in Aerial Images | Improving the 检测 of Small Oriented Objects in Aerial Images | Addresses small oriented object detection in aerial images, matching key task terms. |
| c-dc50530c | HIC-YOLOv5: Improved YOLOv5 For Small Object Detection | HIC-YOLO 实时目标检测: Improved YOLO 实时目标检测 For Small 目标检测 | Improved YOLOv5 specifically for small object detection with FPN enhancements; strong method match. |
| c-fc6212df | Oriented Object Detection in Remote Sensing Image Based on YOLOV5 | Oriented 目标检测 in Remote Sensing Image Based on YOLO 实时目标检测 | Direct match: oriented object detection in RS imagery based on YOLOv5. |
| c-befd471c | DOTA | (中文含义由英文派生) | DOTA is the canonical benchmark for oriented aircraft detection in aerial imagery — strong front-rank dataset. |

#### baseline (3)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-fc6212df | Oriented Object Detection in Remote Sensing Image Based on YOLOV5 | Oriented 目标检测 in Remote Sensing Image Based on YOLO 实时目标检测 |
| c-dc50530c | HIC-YOLOv5: Improved YOLOv5 For Small Object Detection | HIC-YOLO 实时目标检测: Improved YOLO 实时目标检测 For Small 目标检测 |
| c-a00e5114 | Improving the Detection of Small Oriented Objects in Aerial Images | Improving the 检测 of Small Oriented Objects in Aerial Images |

#### parallel (2)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-d9b3b1bc | Object Detection Of Flexible Object With Arbitrary-Oriented Based On Rotation Adaptive YOLOv5 | 目标检测 Of Flexible Object With Arbitrary-Oriented Based On Rotation Adaptive YOLO 实时目标检测 |
| c-98fe1464 | phamminhhanhuet/resnet-orient-detection | 仓库 phamminhhanhuet/resnet-orient-detection |

#### reference (4)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-fbafaa77 | Oriented object detection in optical remote sensing images using deep learning: a survey | Oriented 目标检测 in optical remote sensing images using 深度学习: a 综述 |
| c-befd471c | DOTA | (中文含义由英文派生) |
| c-e447cdba | TJU-DHD: A Diverse High-Resolution Dataset for Object Detection | TJU-DHD: A Diverse High-Resolution 数据集 for 目标检测 |
| c-f6efe7fa | TJU-DHD | (中文含义由英文派生) |

#### long_tail (1)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-afc4af31 | Object Oriented Shadow Detection and Removal from Urban High Resolution RSI | Object Oriented Shadow 检测 and Removal from Urban High Resolution RSI |

#### rejected (16)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-6099a0c3 | Object Contour and Edge Detection with RefineContourNet | Object Contour and Edge 检测 with RefineContourNet | Cross-domain: edge/contour detection paper unrelated to RS oriented detection. |
| c-d41dcc34 | Exploring Depth Contribution for Camouflaged Object Detection | Exploring Depth Contribution for Camouflaged 目标检测 | Cross-domain: camouflaged object segmentation paper unrelated to RS aircraft detection. |
| c-d4b2c4ba | PVAFN: Point-Voxel Attention Fusion Network with Multi-Pooling Enhancing for 3D Object Detection | PVAFN: Point-Voxel Attention Fusion Network with Multi-Pooling Enhancing for 三维 目标检测 | Cross-domain: LiDAR 3D detection paper unrelated to 2D RS aircraft detection. |
| c-f871f411 | A Survey of Self-Supervised and Few-Shot Object Detection | 综述 of 自监督 and 少样本 目标检测 | Cross-domain: self-supervised/few-shot detection survey unrelated to RS YOLOv5 aircraft detection. |
| c-76c13632 | 3D Object Detection for Autonomous Driving: A Comprehensive Survey | 三维 目标检测 for 自动驾驶: A Comprehensive 综述 | Cross-domain: autonomous driving 3D detection survey unrelated to RS aircraft detection. |
| c-698782c7 | AIn't Nothing But a Survey? Using Large Language Models for Coding German Open-Ended Survey Responses on Survey Motivati | AIn't Nothing But a 综述? Using Large Language Models for Coding German Open-Ended 综述 Responses on 综述 Motivati | Cross-domain: LLM survey coding paper unrelated to computer vision/RS detection. |
| c-41c542cb | Aircraft Systems Conceptual Design : An object-oriented approach from &lt;element&gt; to &lt;aircraft&gt; | 飞机 Systems Conceptual Design : An object-oriented approach from &lt;element&gt; to &lt;飞机&gt; | Cross-domain: aircraft conceptual design/AGN astronomy paper, not detection. |
| c-8570bbf2 | Automatic detection of design problems in object-oriented reengineering | Automatic 检测 of design problems in object-oriented reengineering | Cross-domain: software reengineering paper unrelated to RS detection. |
| c-5e60e3cd | swati1024/torrents | 仓库 swati1024/torrents | Cross-domain: unrelated torrent listing repository. |
| c-f21cc66d | Getting started with Spring Framework: covers Spring 5 | (中文含义由英文派生) | Cross-domain: Spring Framework book unrelated to RS detection. |
| c-db2a4523 | J Sharma (Author), Ashish Sarin | (中文含义由英文派生) | Cross-domain: author metadata fragment unrelated to RS detection. |
| c-9083722b | Windows Presentation Foundation Masterclass | (中文含义由英文派生) | Cross-domain: WPF masterclass unrelated to RS detection. |
| c-d66d050a | Programming languages A,B and C | (中文含义由英文派生) | Cross-domain: programming language course unrelated to RS detection. |
| c-20c49df1 | htmlnation/Tanky_Tank | 仓库 htmlnation/Tanky_Tank | A JavaScript tank game; zero overlap with remote sensing aircraft detection. |
| c-cf7e8478 | AndreS2375/TicTacToe | 仓库 AndreS2375/TicTacToe | C++ TicTacToe game repository; completely unrelated to the topic. |
| c-be20c0fb | vignankamarthi/Facial-Recognition-With-Ethical-Analysis | 仓库 vignankamarthi/Facial-Recognition-With-Ethical-Analysis | Facial recognition ethics project; unrelated domain to aerial aircraft detection. |

#### dataset_and_repo_notes

> DOTA (c-befd471c) is the primary benchmark; subset to airplane class and convert to DOTA-style rotated boxes for training c-fc6212df.
> c-98fe1464 is a BBAVectors-oriented-detection notebook (MIT); useful as a non-YOLO oriented-box reference, not as the main repo.
> TJU-DHD (c-e447cdba / c-f6efe7fa duplicate entries) is vehicle/pedestrian oriented; use only as a high-resolution auxiliary, not as primary.
> No aircraft-specific YOLOv5 implementation repo was found in this evidence set; the student should plan to adapt c-fc6212df's described pipeline plus an open YOLOv5 (Ultralytics) base.

### §13 ENG-THESIS-028 — 《基于YOLOv5的绝缘子检测与缺陷识别方法研究》 — `weak`

| 维度 | 数值 |
|---|---:|
| batch | batch2 |
| elapsed | 304.4s |
| domain | 电力/轨交巡检视觉 |
| paper | 30 |
| dataset | 0 |
| repo | 0 |
| baseline | 4 |
| parallel | 2 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-10731-1022697659.htm |

**direction_recommendation**: 检索面严重缺位:crossref/openalex/github/huggingface 全部 empty,仅 arxiv 拿到 4 段结果且全部为'YOLOv5 改进'或'YOLOv5 应用'论文,没有一篇真正命中'绝缘子检测/缺陷识别'。EvidenceReview 中 23 行里 14 行被标为 rejected(天体/凝聚态/LLM 编码等),9 行 candidate 也都是弱相关(YOLOv5 改造手法),真正可作为基线/对比的'绝缘子+YOLOv5'论文为 0;唯一的可用 dataset 候选 VisDrone (c-a59ff8e0) 不含绝缘子类别,只能作为 UAV 域预训练源。结论:不能以当前证据直接构造基于 YOLOv5 的绝缘子检测与缺陷识别研究,核心证据缺失。建议下一阶段补检索:CNKI/万方中文库('基于YOLOv5 绝缘子 缺陷识别')、IEEE Xplore('insulator defect detection deep learning')、GitHub('insulator yolov5')、Roboflow/HuggingFace('insulator dataset')、以及最新 survey 'deep learning based power line inspection'。在补检前不要锁定 baseline,候选 candidate 只能作为方法学旁证(轻量化、注意力、小目标头、压缩)。当前最稳的临时研究骨架是:YOLOv5s/l 基线 + 借鉴 HIC-YOLOv5 (c-87a331f5) 的小目标头与 UTD-YOLOv5 (c-a8b30f2b) 的注意力 + YOLOv5s-GTB (c-5a5ddeb3) 的轻量化路线,在自建/外购绝缘子数据集上做消融,并以 VisDrone 做域适应预训练。

#### core (0) (无)
#### baseline (4)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-87a331f5 | HIC-YOLOv5: Improved YOLOv5 For Small Object Detection | HIC-YOLO 实时目标检测: Improved YOLO 实时目标检测 For Small 目标检测 |
| c-5a5ddeb3 | YOLOv5s-GTB: light-weighted and improved YOLOv5s for bridge crack detection | YOLO 实时目标检测-GTB: light-weighted and improved YOLO 实时目标检测 for bridge 裂缝 检测 |
| c-a8b30f2b | UTD-Yolov5: A Real-time Underwater Targets Detection Method based on Attention Improved YOLOv5 | UTD-YOLO 实时目标检测: A 实时 Underwater Targets 检测 Method based on Attention Improved YOLO 实时目标检测 |
| c-8ff35640 | Model Compression Methods for YOLOv5: A Review | Model Compression Methods for YOLO 实时目标检测: A Review |

#### parallel (2)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-03ca4b06 | Oriented object detection in optical remote sensing images using deep learning: a survey | Oriented 目标检测 in optical remote sensing images using 深度学习: a 综述 |
| c-f8fe4b77 | Fire Detection From Image and Video Using YOLOv5 | Fire 检测 From Image and Video Using YOLO 实时目标检测 |

#### reference (3)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-44529da7 | Adversarial Attack On Yolov5 For Traffic And Road Sign Detection | Adversarial Attack On YOLO 实时目标检测 For Traffic And 道路 Sign 检测 |
| c-77991f8f | YOLOv5 vs. YOLOv8 in Marine Fisheries: Balancing Class Detection and Instance Count | YOLO 实时目标检测 vs. YOLO 实时目标检测 in Marine Fisheries: Balancing Class 检测 and Instance Count |
| c-86e2fc93 | COVID-19 Detection Using CT Image Based On YOLOv5 Network | COVID-19 检测 Using CT Image Based On YOLO 实时目标检测 Network |

#### long_tail (1)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-a59ff8e0 | VisDrone | (中文含义由英文派生) |

#### rejected (13)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-2fb7d713 | Detecting Botnets Through Log Correlation | (中文含义由英文派生) | Cybersecurity log-correlation paper; completely cross-domain with no relation to vision or insulators. |
| c-76aaf3fd | A rich bounty of AGN in the 9 square degree Bootes survey: high-z obscured AGN and large-scale structure | rich bounty of AGN (天文主动星系核，强噪声) in the 9 square degree Bootes 综述: high-z obscured AGN (天文主动星系核，强噪声) and large-scale structure | Astronomy AGN survey paper; entirely cross-domain, no connection to vision or insulators. |
| c-72b72d5a | AIn't Nothing But a Survey? Using Large Language Models for Coding German Open-Ended Survey Responses on Survey Motivati | AIn't Nothing But a 综述? Using Large Language Models for Coding German Open-Ended 综述 Responses on 综述 Motivati | LLM-based survey response coding in social science; cross-domain, unrelated. |
| c-8bf7ed19 | The Methanol Multibeam Survey | Methanol Multibeam 综述 | Radio astronomy methanol survey; cross-domain astrophysics content. |
| c-81f3c71c | IRSF/SIRIUS JHKs near-infrared variable star survey in the Magellanic Clouds | IRSF/SIRIUS JHKs near-infrared variable star 综述 in the Magellanic Clouds | Near-IR variable star survey in Magellanic Clouds; cross-domain astrophysics. |
| c-e458d670 | The SAMI Galaxy Survey: first 1000 galaxies | SAMI Galaxy 综述: first 1000 galaxies | Integral field spectroscopy galaxy survey; cross-domain astrophysics. |
| c-91a1134c | Roman Galactic Plane Survey Definition Committee Report | Roman Galactic Plane 综述 Definition Committee Report | Roman Galactic Plane Survey definition report; cross-domain astrophysics. |
| c-b71c6054 | VLP: A Survey on Vision-Language Pre-training | VLP: A 综述 on Vision-Language Pre-training | Vision-language pre-training survey; cross-domain NLP/CV topic unrelated to insulator detection. |
| c-5be325be | Criticality of the metal-topological insulator transition driven by disorder | Criticality of the metal-topological 绝缘子 transition driven by disorder | Condensed matter physics on metal-topological insulator transition; cross-domain physics. |
| c-18da092c | Tunable Chern insulator with shaken optical lattices | Tunable Chern 绝缘子 with shaken optical lattices | Cold atom physics on Chern insulators in optical lattices; cross-domain physics. |
| c-5e3d529f | Field-induced metal-insulator transition and switching phenomenon in correlated insulators | Field-induced metal-绝缘子 transition and switching phenomenon in correlated 绝缘子 | Condensed matter metal-insulator transition paper; cross-domain physics. |
| c-8da6d304 | Strained topological insulator spin field effect transistor | Strained topological 绝缘子 spin field effect transistor | Topological insulator spin FET device paper; cross-domain device physics. |
| c-cef836bb | Realizing Hopf Insulators in Dipolar Spin Systems | Realizing Hopf 绝缘子 in Dipolar Spin Systems | Physics paper on Hopf insulators in dipolar spin systems; zero overlap with vision-based insulator defect detection. |

#### dataset_and_repo_notes

> VisDrone (c-a59ff8e0) is UAV-view but contains NO insulator classes; usable only as backbone/pretraining domain source, not a target dataset.
> No insulator-specific public dataset was surfaced in this retrieval; a Chinese-language search (CNKI/Wanfang/Roboflow) is required to locate one.
> No GitHub repo for insulator+YOLOv5 was retrieved; repo search returned empty and must be re-run with Chinese keywords.
> VisDrone license and class list should be confirmed before treating it as a pretraining source.

### §14 ENG-THESIS-032 — 《基于深度学习的液晶屏表面缺陷检测方法研究》 — `weak`

| 维度 | 数值 |
|---|---:|
| batch | batch2 |
| elapsed | 242.5s |
| domain | 工业缺陷检测/机器视觉 |
| paper | 24 |
| dataset | 0 |
| repo | 0 |
| baseline | 3 |
| parallel | 1 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-10372-1022628728.htm |

**direction_recommendation**: The current retrieval set lacks any LCD-/Mura-specific evidence: no candidate in the EvidenceReview was confirmed to target LCD panel surface defects, Mura defects, or TFT/OLED/LCD industrial inspection. The most task-relevant candidates are (1) c-79c36d06 — a surface defect benchmark dataset (transferable to LCD as a dataset reference), (2) c-88238e69 — DeepInspect, a generic CNN-based manufacturing defect detection paper, (3) c-53ff3c66 — TransferD2, transfer-learning defect detection, and (4) c-086a457a — the SurfaceDefectNet segmentation repo. Recommended direction: treat the topic as a deep-learning surface defect detection study on LCD panels using CNN/YOLO/Faster R-CNN/U-Net family methods, with Mura/scratch classification + segmentation subtasks, and rely on the generic manufacturing-defect papers plus the surface defect benchmark/repo as indirect baselines pending a second retrieval round targeted at LCD/Mura literature (IEEE Xplore, SID display journals, CNKI/Wanfang for Chinese sources). No item in the current pool should be cited as confirmed LCD evidence.

#### core (0) (无)
#### baseline (3)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-88238e69 | DeepInspect: An AI-Powered Defect Detection for Manufacturing Industries | DeepInspect: An AI-Powered 缺陷 检测 for Manufacturing Industries |
| c-53ff3c66 | TransferD2: Automated Defect Detection Approach in Smart Manufacturing using Transfer Learning Techniques | TransferD2: Automated 缺陷 检测 Approach in Smart Manufacturing using 迁移学习 Techniques |
| c-086a457a | Yonatan-Estifanos-github/SurfaceDefectNet-Deep-Learning-for-Surface-Defect-Detection | 仓库 Yonatan-Estifanos-github/SurfaceDefectNet-Deep-Learning-for-Surface-Defect-Detection |

#### parallel (1)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-79c36d06 | A New Benchmark Dataset for Texture Image Analysis and Surface Defect Detection | New 基准 数据集 for Texture Image Analysis and Surface 缺陷 检测 |

#### reference (5)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-b75d7f4e | Learn to Accumulate Evidence from All Training Samples: Theory and Practice | (中文含义由英文派生) |
| c-f6dee413 | The Modern Mathematics of Deep Learning | Modern Mathematics of 深度学习 |
| c-4f35dc4b | Deep Learning and Computational Physics (Lecture Notes) | 深度学习 and Computational Physics (Lecture Notes) |
| c-2182fa46 | Vision Mamba: A Comprehensive Survey and Taxonomy | Vision Mamba: A Comprehensive 综述 and Taxonomy |
| c-8902aa5c | VLP: A Survey on Vision-Language Pre-training | VLP: A 综述 on Vision-Language Pre-training |

#### long_tail (0) (无)
#### rejected (7)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-dfcf01b4 | Oriented object detection in optical remote sensing images using deep learning: a survey | Oriented 目标检测 in optical remote sensing images using 深度学习: a 综述 | Remote sensing oriented object detection; cross-domain relative to LCD panel defects. |
| c-cc4a4a60 | A Hybrid Deep Learning Anomaly Detection Framework for Intrusion Detection | Hybrid 深度学习 Anomaly 检测 Framework for Intrusion 检测 | Cybersecurity intrusion detection; cross-domain relative to LCD visual inspection. |
| c-72efe044 | The Evolution of First Person Vision Methods: A Survey | Evolution of First Person Vision Methods: A 综述 | First-person vision methods survey; completely different application domain. |
| c-0e1feff9 | A rich bounty of AGN in the 9 square degree Bootes survey: high-z obscured AGN and large-scale structure | rich bounty of AGN (天文主动星系核，强噪声) in the 9 square degree Bootes 综述: high-z obscured AGN (天文主动星系核，强噪声) and large-scale structure | Astronomy AGN survey; completely off-topic domain. |
| c-c0ce31be | AIn't Nothing But a Survey? Using Large Language Models for Coding German Open-Ended Survey Responses on Survey Motivati | AIn't Nothing But a 综述? Using Large Language Models for Coding German Open-Ended 综述 Responses on 综述 Motivati | LLM survey coding paper; NLP domain, not computer vision defect detection. |
| c-cf703472 | Vision-to-Music Generation: A Survey | Vision-to-Music Generation: A 综述 | Vision-to-music generation survey; unrelated multimodal creative task. |
| c-aeb453af | The Methanol Multibeam Survey | Methanol Multibeam 综述 | Astronomy methanol maser survey; completely off-topic. |

#### dataset_and_repo_notes

> c-79c36d06: stone-texture surface defect benchmark; transferable as auxiliary dataset but no LCD/Mura classes.
> c-086a457a: SurfaceDefectNet segmentation repo, 0 stars, low maturity; useful only as code-structure reference, not production baseline.
> No LCD/Mura-specific public dataset was retrieved; recommend MuraTech, Mixed-type Mura defect dataset, or industrial partner data.
> No LCD-panel-specific GitHub repo with reproducible results retrieved.

### §15 ENG-THESIS-033 — 《基于YOLOV5的肺结节检测算法研究》 — `weak`

| 维度 | 数值 |
|---|---:|
| batch | batch2 |
| elapsed | 223.8s |
| domain | 医学/人体三维视觉 |
| paper | 54 |
| dataset | 0 |
| repo | 0 |
| baseline | 5 |
| parallel | 9 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-10674-1022654805.htm |

**direction_recommendation**: Focus the survey on lung nodule detection in CT images using YOLOv5-family one-stage detectors, with LIDC-IDRI and LUNA16 as the canonical evaluation resources. The core evidence set is built around four directly YOLOv5-based lung nodule papers (c-2fd1ed5a, c-04041be4, c-ae8e7a91, c-16c5b4a5) plus the hybrid YOLOv5+ResNet101 paper c-bbdbbb1b, supported by c-e38c6c41 (LIDC-IDRI) and c-5dba436f (LUNA16) as the shared datasets. Use c-57796f15 (YOLOv8) as the immediate architectural successor for comparison, and c-5528fca9, c-efa313e2, c-9ebd7cc5, c-003c3d83, c-949b9f3d, c-e97ef687, c-acbf18e3 as parallel non-YOLO detectors (CNN pyramid, 3D Mask-RCNN, deformable DETR, dual-attention CNN, multi-branch attention, hard-sample focus, reconstruction-aided). Treat c-b37739f6, c-b981042a as rejected (X-ray modality mismatch). Use c-84c85690 as the survey-level AI/lung nodule reference and c-749730db only via manual verification. Recommended scope: compare improved-YOLOv5 variants on LIDC-IDRI/LUNA16 against CNN and transformer baselines, analyzing backbone, neck, feature-fusion, and loss-design improvements for small-nodule sensitivity.

#### core (7)

| cid | 原文 title | 中文含义 | reason |
|---|---|---|---|
| c-2fd1ed5a | Identification of lung nodules CT scan using YOLOv5 based on convolution neural network | Identification of lung nodules CT scan using YOLO 实时目标检测 based on 卷积 神经网络 | Direct match: YOLOv5 + lung nodule CT detection; foundational baseline for the topic. |
| c-bbdbbb1b | A Model for Lung Nodule Detection using a Hybrid Approach by Combining YOLOv5 and ResNet101 Pretrained Artificial Intell | Model for Lung Nodule 检测 using a Hybrid Approach by Combining YOLO 实时目标检测 and ResNet101 Pretrained Artificial Intell | Direct YOLOv5 lung nodule detection with ResNet101 hybrid; highly relevant. |
| c-04041be4 | Based on the Improved YOLOv5 Lung Nodule Detection Method | Based on the Improved YOLO 实时目标检测 Lung Nodule 检测 Method | Direct YOLOv5-based lung nodule detection improvement; highly relevant baseline. |
| c-ae8e7a91 | An improved YOLOv5 network for lung nodule detection | improved YOLO 实时目标检测 network for lung nodule 检测 | Improved YOLOv5 network for lung nodule detection; strong direct match. |
| c-16c5b4a5 | Lung Nodule Detection Algorithm Based on Improved YOLOv5 Network Modeling | Lung Nodule 检测 Algorithm Based on Improved YOLO 实时目标检测 Network Modeling | Improved YOLOv5 lung nodule detection algorithm; highly relevant core match. |
| c-5dba436f | LUNA16 | (中文含义由英文派生) | LUNA16 is a canonical lung nodule detection benchmark derived from LIDC-IDRI, directly relevant to YOLOv5-based nodule detection. |
| c-e38c6c41 | LIDC-IDRI | (中文含义由英文派生) | LIDC-IDRI is the primary lung CT nodule dataset explicitly named in the topic and the source of LUNA16. |

#### baseline (5)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-2fd1ed5a | Identification of lung nodules CT scan using YOLOv5 based on convolution neural network | Identification of lung nodules CT scan using YOLO 实时目标检测 based on 卷积 神经网络 |
| c-04041be4 | Based on the Improved YOLOv5 Lung Nodule Detection Method | Based on the Improved YOLO 实时目标检测 Lung Nodule 检测 Method |
| c-ae8e7a91 | An improved YOLOv5 network for lung nodule detection | improved YOLO 实时目标检测 network for lung nodule 检测 |
| c-16c5b4a5 | Lung Nodule Detection Algorithm Based on Improved YOLOv5 Network Modeling | Lung Nodule 检测 Algorithm Based on Improved YOLO 实时目标检测 Network Modeling |
| c-bbdbbb1b | A Model for Lung Nodule Detection using a Hybrid Approach by Combining YOLOv5 and ResNet101 Pretrained Artificial Intelligence Models | Model for Lung Nodule 检测 using a Hybrid Approach by Combining YOLO 实时目标检测 and ResNet101 Pretrained Artificial Intelligence Models |

#### parallel (9)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-5528fca9 | Integrating Feature and Image Pyramid: A Lung Nodule Detector Learned in Curriculum Fashion | (中文含义由英文派生) |
| c-efa313e2 | Lung-DETR: Deformable Detection Transformer for Sparse Lung Nodule Anomaly Detection | Lung-DETR 目标检测: Deformable 检测 Transformer for Sparse Lung Nodule Anomaly 检测 |
| c-9ebd7cc5 | Lung Nodules Detection and Segmentation Using 3D Mask-RCNN | Lung Nodules 检测 and 分割 Using 三维 Mask-RCNN |
| c-874f81a2 | Lung Nodule-SSM: Self-Supervised Lung Nodule Detection and Classification in Thoracic CT Images | Lung Nodule-SSM: 自监督 Lung Nodule 检测 and 分类 in Thoracic CT Images |
| c-e97ef687 | Improved Focus on Hard Samples for Lung Nodule Detection | Improved Focus on Hard Samples for Lung Nodule 检测 |
| c-003c3d83 | Effective lung nodule detection using deep CNN with dual attention mechanisms | Effective lung nodule 检测 using deep CNN with dual attention mechanisms |
| c-949b9f3d | MANet: Multi-branch attention auxiliary learning for lung nodule detection and segmentation | MANet: Multi-branch attention auxiliary learning for lung nodule 检测 and 分割 |
| c-57796f15 | YOLOv8-Based Framework for Accurate Lung CT Nodule Images Detection | YOLO 实时目标检测-Based Framework for Accurate Lung CT Nodule Images 检测 |
| c-acbf18e3 | Deep Learning Reconstruction Shows Better Lung Nodule Detection for Ultra-Low-Dose Chest CT. | 深度学习 重建 Shows Better Lung Nodule 检测 for Ultra-Low-Dose Chest CT. |

#### reference (10)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-84c85690 | Artificial intelligence: A critical review of applications for lung nodule and lung cancer. | (中文含义由英文派生) |
| c-51107558 | Crowdsourcing Lung Nodules Detection and Annotation | Crowdsourcing Lung Nodules 检测 and Annotation |
| c-1898e32c | - Lung Nodule and Tumor Detection and Segmentation | - Lung Nodule and Tumor 检测 and 分割 |
| c-1d8c346f | A novel computer-aided lung nodule detection system for CT images | novel computer-aided lung nodule 检测 system for CT images |
| c-d643faaf | A Context Based Automated System for Lung Nodule Detection in CT Images | Context Based Automated System for Lung Nodule 检测 in CT Images |
| c-b41919db | Eye-tracking of nodule detection in lung CT volumetric data | Eye-跟踪 of nodule 检测 in lung CT volumetric data |
| c-1a736a6a | Nodule-CLIP: Lung nodule classification based on multi-modal contrastive learning | Nodule-CLIP: Lung nodule 分类 based on multi-modal 对比学习 learning |
| c-e250a61c | CLIP-Lung: Textual Knowledge-Guided Lung Nodule Malignancy Prediction | (中文含义由英文派生) |
| c-79d90054 | DEHA-Net: A Dual-Encoder-Based Hard Attention Network with an Adaptive ROI Mechanism for Lung Nodule Segmentation | DEHA-Net: A Dual-Encoder-Based Hard Attention Network with an Adaptive ROI Mechanism for Lung Nodule 分割 |
| c-f5fdda80 | A Bi-FPN-Based Encoder–Decoder Model for Lung Nodule Image Segmentation | Bi-FPN-Based Encoder–Decoder Model for Lung Nodule Image 分割 |

#### long_tail (2)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-d91a32cb | jiayingliu423/Lung-Nodule-Detection-MICCAI-MLMI2025 | 仓库 jiayingliu423/Lung-Nodule-Detection-MICCAI-MLMI2025 |
| c-749730db | Table 1: Summary of representative lung nodule detection methods in recent studies. | Table 1: Summary of representative lung nodule 检测 methods in recent studies. |

#### rejected (无)

#### dataset_and_repo_notes

> LIDC-IDRI (c-e38c6c41) is the foundational thoracic CT dataset; preprocess via 2D slice extraction and HU windowing for YOLOv5 input.
> LUNA16 (c-5dba436f) is the canonical nodule detection benchmark derived from LIDC-IDRI; recommended primary eval for any YOLOv5 detector.
> c-d91a32cb repo has 0 stars and no listed topics; verify backend repo contents and license before citing as implementation reference.
> c-749730db is only a Crossref table caption; manually fetch the parent peerj-cs.3473 article before drawing any conclusion.

### §16 ENG-THESIS-035 — 《基于深度学习的带钢表面缺陷检测方法》 — `pass`

| 维度 | 数值 |
|---|---:|
| batch | r4 |
| elapsed | 189.8s |
| domain | 工业缺陷检测/机器视觉 |
| paper | 25 |
| dataset | 1 |
| repo | 1 |
| baseline | 5 |
| parallel | 9 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-10702-1021067044.htm |

**direction_recommendation**: Focus the survey on deep-learning object-detection and segmentation methods applied to strip-steel surface defect detection, anchored on the canonical NEU-DET benchmark. Recommend structuring the review around three method families: (1) YOLO-family detectors (YOLOv5s, YOLOv8 variants) which dominate the recent literature; (2) two-stage detectors (Faster R-CNN) used as accuracy baselines; (3) segmentation approaches (U-Net, DeepLab) for pixel-level defect delineation. Position attention mechanisms and FPN as cross-cutting architectural enhancements. Use steel-specific YOLOv8 papers as core baselines, NEU-DET as the shared evaluation ground, and general-purpose detectors (DETR, FCOS, EfficientDet) as parallel architectural references. Current evidence is thin on segmentation-specific strip-steel work and on non-NEU benchmarks (e.g., GC10-DET, Severstal), so the survey should flag those gaps rather than fabricate coverage.

#### core (7)

| cid | 原文 title | 中文含义 | reason |
|---|---|---|---|
| c-5845b5df | Comparative Analysis of Object Detection Algorithms for Surface Defect Detection | Comparative Analysis of 目标检测 Algorithms for Surface 缺陷 检测 | Direct comparison of detectors including YOLOv8 on NEU-DET steel surface defects; strong match. |
| c-8523d6a2 | Steel surface defect detection based on improved YOLOv8 neural network | Steel surface 缺陷 检测 based on improved YOLO 实时目标检测 神经网络 | Directly applies improved YOLOv8 to steel surface defects; strong method+object match. |
| c-94ba25ac | GCE-YOLOv5s Based Surface Defect Detection Algorithm for Strip Steel | GCE-YOLO 实时目标检测 Based Surface 缺陷 检测 Algorithm for Strip Steel | Strip-steel-specific surface defect detection paper; exact object-domain match. |
| c-ea4efe2c | DenseNet network-based surface defect detection algorithm for strip steel | DenseNet network-based surface 缺陷 检测 algorithm for strip steel | DenseNet-based defect detection explicitly for strip steel; strong object+task match. |
| c-1db0e3da | YOLOv8-LSD:A Steel Surface Defect Detection Algorithm Based On YOLOv8 | YOLO 实时目标检测-LSD:A Steel Surface 缺陷 检测 Algorithm Based On YOLO 实时目标检测 | YOLOv8-based steel surface defect detector (LSD variant); direct method+object match. |
| c-b25feaa1 | Improved Steel Surface Defect Detection Algorithm Based on YOLOv8 | Improved Steel Surface 缺陷 检测 Algorithm Based on YOLO 实时目标检测 | IEEE Access paper on improved YOLOv8 for steel surface defects; venue strong, match exact. |
| c-a573f771 | NEU-DET | (中文含义由英文派生) | NEU-DET is the canonical steel-surface-defect object-detection benchmark, directly cited in topic queries. |

#### baseline (5)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-8523d6a2 | Steel surface defect detection based on improved YOLOv8 neural network | Steel surface 缺陷 检测 based on improved YOLO 实时目标检测 神经网络 |
| c-1db0e3da | YOLOv8-LSD:A Steel Surface Defect Detection Algorithm Based On YOLOv8 | YOLO 实时目标检测-LSD:A Steel Surface 缺陷 检测 Algorithm Based On YOLO 实时目标检测 |
| c-b25feaa1 | Improved Steel Surface Defect Detection Algorithm Based on YOLOv8 | Improved Steel Surface 缺陷 检测 Algorithm Based on YOLO 实时目标检测 |
| c-94ba25ac | GCE-YOLOv5s Based Surface Defect Detection Algorithm for Strip Steel | GCE-YOLO 实时目标检测 Based Surface 缺陷 检测 Algorithm for Strip Steel |
| c-ea4efe2c | DenseNet network-based surface defect detection algorithm for strip steel | DenseNet network-based surface 缺陷 检测 algorithm for strip steel |

#### parallel (9)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-5845b5df | Comparative Analysis of Object Detection Algorithms for Surface Defect Detection | Comparative Analysis of 目标检测 Algorithms for Surface 缺陷 检测 |
| c-c196ea7e | Real-Time Industrial Defect Detection on Edge Hardware Using Fine-Tuned YOLOv8: A Systematic Benchmark on the NEU Surface Defect Database and MVTec AD with Automotive & Battery Manufacturing Extensions | 实时 Industrial 缺陷 检测 on Edge Hardware Using Fine-Tuned YOLO 实时目标检测: A Systematic 基准 on the NEU Surface 缺陷 Database and MVTec AD with Automotive & Battery Manufacturing Extensions |
| c-3a8f6ae2 | Deformable DETR: Deformable Transformers for End-to-End Object Detection | Deformable DETR 目标检测: Deformable Transformer for End-to-End 目标检测 |
| c-33032f58 | YOLOv10: Real-Time End-to-End Object Detection | YOLOv10: 实时 End-to-End 目标检测 |
| c-76fba169 | Grounding DINO: Marrying DINO with Grounded Pre-Training for Open-Set Object Detection | Grounding DINO: Marrying DINO with Grounded Pre-Training for Open-Set 目标检测 |
| c-20ce9a1f | FCOS: Fully Convolutional One-Stage Object Detection | FCOS: Fully 卷积 One-Stage 目标检测 |
| c-35189529 | YOLOv4: Optimal Speed and Accuracy of Object Detection | YOLO 实时目标检测: Optimal Speed and Accuracy of 目标检测 |
| c-61148d41 | EfficientDet: Scalable and Efficient Object Detection | EfficientDet: Scalable and Efficient 目标检测 |
| c-111936e4 | End-to-End Object Detection with Transformers | End-to-End 目标检测 with Transformer |

#### reference (5)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-3b412183 | A New Benchmark Dataset for Texture Image Analysis and Surface Defect Detection | New 基准 数据集 for Texture Image Analysis and Surface 缺陷 检测 |
| c-8c3f0d77 | Road Surface Defect Detection -- From Image-based to Non-image-based: A Survey | 道路 Surface 缺陷 检测 -- From Image-based to Non-image-based: A 综述 |
| c-6b08ca92 | Developing a Resource-Constraint EdgeAI model for Surface Defect Detection | Developing a Resource-Constraint EdgeAI model for Surface 缺陷 检测 |
| c-51c5c143 | DeepInspect: An AI-Powered Defect Detection for Manufacturing Industries | DeepInspect: An AI-Powered 缺陷 检测 for Manufacturing Industries |
| c-ad031e66 | TransferD2: Automated Defect Detection Approach in Smart Manufacturing using Transfer Learning Techniques | TransferD2: Automated 缺陷 检测 Approach in Smart Manufacturing using 迁移学习 Techniques |

#### long_tail (1)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-2dda1575 | Yonatan-Estifanos-github/SurfaceDefectNet-Deep-Learning-for-Surface-Defect-Detection | 仓库 Yonatan-Estifanos-github/SurfaceDefectNet-Deep-Learning-for-Surface-Defect-Detection |

#### rejected (5)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-a3e07da1 | Oriented object detection in optical remote sensing images using deep learning: a survey | Oriented 目标检测 in optical remote sensing images using 深度学习: a 综述 | Remote-sensing oriented object detection survey; cross-domain to steel surface defects. |
| c-72ef5f0b | AIn't Nothing But a Survey? Using Large Language Models for Coding German Open-Ended Survey Responses on Survey Motivati | AIn't Nothing But a 综述? Using Large Language Models for Coding German Open-Ended 综述 Responses on 综述 Motivati | LLM-based survey-response coding; completely unrelated to defect detection. |
| c-f62f00da | The Methanol Multibeam Survey | Methanol Multibeam 综述 | Astronomical methanol maser survey; no relation to steel defect detection. |
| c-a6d55a98 | A Refinement of the Spanning Surface Defect in $3$ and $4$ Dimensions | Refinement of the Spanning Surface 缺陷 in $3$ and $4$ Dimensions | Pure mathematics paper on spanning surfaces of knots; homonym 'surface defect' only. |
| c-6a7ede32 | Wildfire Satellite Detection Detection of Lands Damaged by Forest | Wildfire Satellite 检测 检测 of Lands Damaged by Forest | Title indicates wildfire/forest damage satellite imagery, not steel surface defect detection. |

#### dataset_and_repo_notes

> c-a573f771 NEU-DET: canonical 6-class hot-rolled steel strip surface defect benchmark used by nearly all core papers; recommend as primary shared evaluation dataset.
> c-2dda1575 repo: segmentation-based defect detection, no explicit steel/strip label — needs manual README inspection before citing as a strip-steel implementation.

### §17 ENG-THESIS-040 — 《基于改进YOLO网络与极限学习机的绝缘子故障检测》 — `pass`

| 维度 | 数值 |
|---|---:|
| batch | r4 |
| elapsed | 150.1s |
| domain | 电力/轨交巡检视觉 |
| paper | 14 |
| dataset | 2 |
| repo | 0 |
| baseline | 2 |
| parallel | 3 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-10220-1021090626.htm |

**direction_recommendation**: Retrieved evidence does NOT contain any paper, dataset, or repo that directly addresses transmission-line insulator fault detection, improved YOLO on insulators, or ELM-based insulator classification. Of 16 candidate rows, only 2 (oriented-object-detection survey c-227e3a45; YOLO-family variants c-7ac8d9ee, c-41dac2bb, c-f6dbaeba, c-3e4adacf, c-aedda4e0, c-ddd3ad6d) and 2 generic detection datasets (COCO, DOTA) are even tangentially relevant. Core/IE-indexed and citation-expansion searches all returned empty for the true query atoms. Honest recommendation: do NOT claim a literature-validated direction yet. Proceed with (1) targeted re-search on Chinese-language sources (CNKI/Wanfang/IEEE-CN) and IEEE Xplore using the exact query atoms in parsed topic, (2) collect an insulator-specific dataset (e.g. CPLID/InsulatorDefect), (3) only then form a 'improved-YOLO + ELM classifier head' baseline against YOLOv5/v7/v8 detectors. Current evidence supports only methodological scaffolding (improved-YOLO design) and aerial-detection transfer (DOTA), not the topic itself.

#### core (0) (无)
#### baseline (2)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-41dac2bb | DAMO-YOLO : A Report on Real-Time Object Detection Design | DAMO-YOLO 实时目标检测 : A Report on 实时 目标检测 Design |
| c-7ac8d9ee | MS-YOLO: Infrared Object Detection for Edge Deployment via MobileNetV4 and SlideLoss | MS-YOLO 实时目标检测: Infrared 目标检测 for Edge Deployment via MobileNetV4 and SlideLoss |

#### parallel (3)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-f6dbaeba | YOLO-World: Real-Time Open-Vocabulary Object Detection | YOLO 实时目标检测-World: 实时 Open-Vocabulary 目标检测 |
| c-3e4adacf | YOLO-IOD: Towards Real Time Incremental Object Detection | YOLO 实时目标检测-IOD: Towards 实时 Incremental 目标检测 |
| c-aedda4e0 | Poly-YOLO: higher speed, more precise detection and instance segmentation for YOLOv3 | Poly-YOLO 实时目标检测: higher speed, more precise 检测 and instance 分割 for YOLO 实时目标检测 |

#### reference (1)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-227e3a45 | Oriented object detection in optical remote sensing images using deep learning: a survey | Oriented 目标检测 in optical remote sensing images using 深度学习: a 综述 |

#### long_tail (1)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-ddd3ad6d | YOLO-CL: Galaxy cluster detection in the SDSS with deep machine learning | YOLO 实时目标检测-CL: Galaxy cluster 检测 in the SDSS with deep machine learning |

#### rejected (7)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-a0ace20d | Fault Detection in New Wind Turbines with Limited Data by Generative Transfer Learning | Fault 检测 in New Wind Turbines with Limited Data by Generative 迁移学习 | Wind turbine fault detection is a different domain (energy, not power-line insulators). |
| c-700a7312 | A rich bounty of AGN in the 9 square degree Bootes survey: high-z obscured AGN and large-scale structure | rich bounty of AGN (天文主动星系核，强噪声) in the 9 square degree Bootes 综述: high-z obscured AGN (天文主动星系核，强噪声) and large-scale structure | Astrophysics AGN survey paper; completely outside the topic domain. |
| c-0292bcc8 | A Survey of fault models and fault tolerance methods for 2D bus-based multi-core systems and TSV based 3D NOC many-core  | 综述 of fault models and fault tolerance methods for 2D bus-based multi-core systems and TSV based 三维 NOC many-core | Hardware fault tolerance in multi-core systems; entirely different domain. |
| c-14995b77 | AIn't Nothing But a Survey? Using Large Language Models for Coding German Open-Ended Survey Responses on Survey Motivati | AIn't Nothing But a 综述? Using Large Language Models for Coding German Open-Ended 综述 Responses on 综述 Motivati | NLP survey-coding paper; cross-domain content unrelated to insulator vision tasks. |
| c-21535a33 | The Methanol Multibeam Survey | Methanol Multibeam 综述 | Radio-astronomy methanol maser survey; entirely outside scope. |
| c-47387875 | Physics-Informed Real NVP for Satellite Power System Fault Detection | Physics-Informed Real NVP for Satellite Power System Fault 检测 | Satellite power-system fault detection via generative model; wrong domain. |
| c-85a571bd | Beta Residuals: Improving Fault-Tolerant Control for Sensory Faults via Bayesian Inference and Precision Learning | (中文含义由英文派生) | Bayesian fault-tolerant control theory paper; cross-domain. |

#### dataset_and_repo_notes

> No insulator-specific dataset (e.g., CPLID, InsulatorDefect, Chinese Power Line Insulator Dataset) was retrieved; student must add one manually.
> c-1ada8303 COCO is appropriate only for YOLO backbone pretraining; not for insulator evaluation.
> c-ca66f899 DOTA matches aerial/UAV modality; can be used for transfer-learning experiments on small insulator samples.

### §18 ENG-THESIS-043 — 《基于无人机平台的动态目标检测系统开发》 — `weak`

| 维度 | 数值 |
|---|---:|
| batch | batch2 |
| elapsed | 199.0s |
| domain | 遥感/无人机目标检测 |
| paper | 28 |
| dataset | 0 |
| repo | 0 |
| baseline | 3 |
| parallel | 3 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-10335-1018068328.htm |

**direction_recommendation**: Build a UAV-mounted dynamic-target detector by combining a platform-aligned aerial detector backbone with a motion-aware lightweight head. Anchor the system on three tier=core baselines that already match the axes the topic cares about: UAV-Det (c-0e7b4549) for explicit UAV aerial detection, the YOLOv9 UAV small-object improvement (c-ad6b8271) for the YOLO family on drone imagery, and OWRT-DETR (c-2274095e) for real-time transformer detection on UAV aerial video. Add YOLODCC (c-9ba53283) as a parallel method reference because it fuses YOLOv8 with dynamic-confidence / lightweight moving-object design, which is the closest transferable signal for 'dynamic target' on the YOLO side. Treat SOD-YOLOv8 (c-81e21e40) and the underwater dynamic YOLOv8 (c-fc1aaf04) as domain-shifted but method-relevant parallel candidates for small-object / dynamic-environment tricks. Use COCO and TJU-DHD as pretraining or class-coverage supplementary datasets. Defer the oriented-RS survey (c-95090170), self-supervised survey (c-eabea38b), and autonomous-driving survey (c-068f0ff3) to long-tail background. Out-of-scope (rejected) items should not be cited. Open items requiring a human: confirm target drone ha

#### core (4)

| cid | 原文 title | 中文含义 | reason |
|---|---|---|---|
| c-9ba53283 | Yolodcc: Improved Yolov8 Combined with Dynamic Confidence Compensation For Lightweight Moving Object Detection | Yolodcc: Improved YOLO 实时目标检测 Combined with 动态 Confidence Compensation For 轻量化 Moving 目标检测 | YOLOv8 + lightweight + dynamic/moving object detection; strong method/task alignment. |
| c-0e7b4549 | UAV-Det: A Deep Learning-Based Object Detection Algorithm for UAV Aerial Imagery | UAV-Det: A 深度学习-Based 目标检测 Algorithm for UAV Aerial Imagery | Directly named UAV aerial object detection paper; strong platform+task alignment. |
| c-ad6b8271 | YOLOv9 Algorithm Improvement for Small Object Detection in UAV Aerial Imagery | YOLO 实时目标检测 Algorithm Improvement for Small 目标检测 in UAV Aerial Imagery | YOLOv9 improvement explicitly for UAV aerial imagery; direct method+platform match. |
| c-2274095e | Review for "OWRT-DETR: A Novel Real-Time Transformer Network for Small-Object Detection in Open-Water Search and Rescue  | Review for "OWRT-DETR 目标检测: A Novel 实时 Transformer Network for Small-目标检测 in Open-Water Search and Rescue | Real-time transformer for UAV aerial small-object detection; direct multi-axis match. |

#### baseline (3)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-0e7b4549 | UAV-Det: A Deep Learning-Based Object Detection Algorithm for UAV Aerial Imagery | UAV-Det: A 深度学习-Based 目标检测 Algorithm for UAV Aerial Imagery |
| c-ad6b8271 | YOLOv9 Algorithm Improvement for Small Object Detection in UAV Aerial Imagery | YOLO 实时目标检测 Algorithm Improvement for Small 目标检测 in UAV Aerial Imagery |
| c-2274095e | Review for "OWRT-DETR: A Novel Real-Time Transformer Network for Small-Object Detection in Open-Water Search and Rescue From UAV Aerial Imagery" | Review for "OWRT-DETR 目标检测: A Novel 实时 Transformer Network for Small-目标检测 in Open-Water Search and Rescue From UAV Aerial Imagery" |

#### parallel (3)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-9ba53283 | Yolodcc: Improved Yolov8 Combined with Dynamic Confidence Compensation For Lightweight Moving Object Detection | Yolodcc: Improved YOLO 实时目标检测 Combined with 动态 Confidence Compensation For 轻量化 Moving 目标检测 |
| c-81e21e40 | SOD-YOLOv8 -- Enhancing YOLOv8 for Small Object Detection in Traffic Scenes | SOD-YOLO 实时目标检测 -- Enhancing YOLO 实时目标检测 for Small 目标检测 in Traffic Scenes |
| c-fc1aaf04 | Enhanced YOLOv8 for Underwater Object Detection in Dynamic Environment | Enhanced YOLO 实时目标检测 for Underwater 目标检测 in 动态 Environment |

#### reference (6)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-9eb50a78 | TJU-DHD: A Diverse High-Resolution Dataset for Object Detection | TJU-DHD: A Diverse High-Resolution 数据集 for 目标检测 |
| c-d5c96381 | COCO | (中文含义由英文派生) |
| c-0e3905d9 | Pascal VOC | (中文含义由英文派生) |
| c-95090170 | Oriented object detection in optical remote sensing images using deep learning: a survey | Oriented 目标检测 in optical remote sensing images using 深度学习: a 综述 |
| c-eabea38b | A Survey of Self-Supervised and Few-Shot Object Detection | 综述 of 自监督 and 少样本 目标检测 |
| c-068f0ff3 | 3D Object Detection for Autonomous Driving: A Comprehensive Survey | 三维 目标检测 for 自动驾驶: A Comprehensive 综述 |

#### long_tail (0) (无)
#### rejected (6)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-fabb36f0 | Object Contour and Edge Detection with RefineContourNet | Object Contour and Edge 检测 with RefineContourNet | Edge/contour detection on natural images; cross-domain for UAV dynamic detection. |
| c-aee05c04 | Exploring Depth Contribution for Camouflaged Object Detection | Exploring Depth Contribution for Camouflaged 目标检测 | Camouflaged object segmentation paper; cross-domain for UAV detection. |
| c-994c2c10 | PVAFN: Point-Voxel Attention Fusion Network with Multi-Pooling Enhancing for 3D Object Detection | PVAFN: Point-Voxel Attention Fusion Network with Multi-Pooling Enhancing for 三维 目标检测 | LiDAR 3D detection; cross-modality for 2D UAV aerial detection. |
| c-21d442e4 | Barcode and QR Code Object Detection: An Experimental Study on YOLOv8 Models | Barcode and QR Code 目标检测: An Experimental Study on YOLO 实时目标检测 Models | YOLOv8 applied to barcode/QR detection; wrong application domain. |
| c-c4e1703f | AIn't Nothing But a Survey? Using Large Language Models for Coding German Open-Ended Survey Responses on Survey Motivati | AIn't Nothing But a 综述? Using Large Language Models for Coding German Open-Ended 综述 Responses on 综述 Motivati | LLM-based survey response analysis; completely off-domain. |
| c-7b28dab2 | Enhancing Malaysian Medicinal Plant Classification through YOLOv8 Object Detection | Enhancing Malaysian Medicinal Plant 分类 through YOLO 实时目标检测 目标检测 | Plant classification using YOLOv8; wrong domain for UAV detection. |

#### dataset_and_repo_notes

> Use a UAV aerial benchmark (e.g., VisDrone-style data, not in ledger) together with COCO (c-d5c96381) pretraining before fine-tuning on drone imagery.
> TJU-DHD (c-9eb50a78) supplies vehicle/pedestrian/ rider classes useful for transfer, but is not aerial.
> Pascal VOC (c-0e3905d9) is for legacy comparison only; lacks aerial/small-object coverage.
> No GitHub repo was confirmed in this round; code availability must be verified manually for c-0e7b4549, c-ad6b8271, c-2274095e, c-9ba53283.

### §19 ENG-THESIS-046 — 《基于视觉的机械臂的目标检测和避障路径规划研究与应用》 — `pass`

| 维度 | 数值 |
|---|---:|
| batch | r1 |
| elapsed | 223.3s |
| domain | 机器人/机械臂实验系统 |
| paper | 30 |
| dataset | 0 |
| repo | 6 |
| baseline | 3 |
| parallel | 6 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-10212-1022041212.htm |

**direction_recommendation**: The retrieval returned abundant YOLO/detection material but almost nothing for the motion-planning, grasping, visual-servoing, or RGB-D arm half of the topic. Evidence pivots strongly on a vision-only module: real-time YOLO family (YOLOv4 c-41076e3a, YOLOv10 c-cefd0c7e) plus the ROS/ROS2 Ultralytics wrapper (c-f3a8b590) are the only tier=core matches and should anchor the perception baseline. Parallel detectors (DETR c-0254574c, Deformable DETR c-9ed476b1, Grounding DINO c-515b0476, FCOS c-a4d05482, EfficientDet c-a48dfa72) and YOLO variants (MS-YOLO c-ce55ec19, D-YOLO c-85698124, SPMamba-YOLO c-4dd5df61, Mobile-YOLO context) form a method alternative set. The planning/manipulation half must be filled by a second retrieval round focused on RRT*/A*, MoveIt, OMPL, and visual servoing before a final direction can be fixed. Recommendation: split the work into Module A (vision: YOLOv8-ROS + YOLOv4/YOLOv10 baselines) and Module B (planning, currently evidence-poor, needs Re03 retrieval).

#### core (3)

| cid | 原文 title | 中文含义 | reason |
|---|---|---|---|
| c-f3a8b590 | Alpaca-zip/ultralytics_ros | 仓库 Alpaca-zip/ultralytics_ros | YOLOv8 ROS wrapper — directly usable as visual perception module on a robotic arm. |
| c-cefd0c7e | YOLOv10: Real-Time End-to-End Object Detection | YOLOv10: 实时 End-to-End 目标检测 | YOLOv10 directly matches the YOLO method atom and is a leading real-time detector baseline. |
| c-41076e3a | YOLOv4: Optimal Speed and Accuracy of Object Detection | YOLO 实时目标检测: Optimal Speed and Accuracy of 目标检测 | YOLOv4 is a canonical YOLO method reference directly matching the YOLO detection atom. |

#### baseline (3)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-f3a8b590 | Alpaca-zip/ultralytics_ros | 仓库 Alpaca-zip/ultralytics_ros |
| c-cefd0c7e | YOLOv10: Real-Time End-to-End Object Detection | YOLOv10: 实时 End-to-End 目标检测 |
| c-41076e3a | YOLOv4: Optimal Speed and Accuracy of Object Detection | YOLO 实时目标检测: Optimal Speed and Accuracy of 目标检测 |

#### parallel (6)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-9ed476b1 | Deformable DETR: Deformable Transformers for End-to-End Object Detection | Deformable DETR 目标检测: Deformable Transformer for End-to-End 目标检测 |
| c-0254574c | End-to-End Object Detection with Transformers | End-to-End 目标检测 with Transformer |
| c-515b0476 | Grounding DINO: Marrying DINO with Grounded Pre-Training for Open-Set Object Detection | Grounding DINO: Marrying DINO with Grounded Pre-Training for Open-Set 目标检测 |
| c-a4d05482 | FCOS: Fully Convolutional One-Stage Object Detection | FCOS: Fully 卷积 One-Stage 目标检测 |
| c-a48dfa72 | EfficientDet: Scalable and Efficient Object Detection | EfficientDet: Scalable and Efficient 目标检测 |
| c-ce55ec19 | MS-YOLO: Infrared Object Detection for Edge Deployment via MobileNetV4 and SlideLoss | MS-YOLO 实时目标检测: Infrared 目标检测 for Edge Deployment via MobileNetV4 and SlideLoss |

#### reference (3)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-f1ca9bf6 | A Survey of Self-Supervised and Few-Shot Object Detection | 综述 of 自监督 and 少样本 目标检测 |
| c-5a86109b | Lending a hand: Detecting hands and recognizing activities in complex egocentric interactions. | (中文含义由英文派生) |
| c-3d495915 | amusi/awesome-object-detection | 仓库 amusi/awesome-object-detection |

#### long_tail (6)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-85698124 | D-YOLO a robust framework for object detection in adverse weather conditions | D-YOLO 实时目标检测 a robust framework for 目标检测 in adverse weather conditions |
| c-4dd5df61 | SPMamba-YOLO: An Underwater Object Detection Network Based on Multi-Scale Feature Enhancement and Global Context Modeling | SPMamba-YOLO 实时目标检测: An Underwater 目标检测 Network Based on Multi-Scale Feature Enhancement and Global Context Modeling |
| c-f49e0468 | PVAFN: Point-Voxel Attention Fusion Network with Multi-Pooling Enhancing for 3D Object Detection | PVAFN: Point-Voxel Attention Fusion Network with Multi-Pooling Enhancing for 三维 目标检测 |
| c-916c07c3 | molyswu/hand_detection | 仓库 molyswu/hand_detection |
| c-52a3e47b | Smorodov/Deep-learning-object-detection-links. | 仓库 Smorodov/Deep-learning-object-detection-links. |
| c-3e650512 | Wildfire Satellite Detection Detection of Lands Damaged by Forest | Wildfire Satellite 检测 检测 of Lands Damaged by Forest |

#### rejected (17)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-63fe5b58 | Oriented object detection in optical remote sensing images using deep learning: a survey | Oriented 目标检测 in optical remote sensing images using 深度学习: a 综述 | Remote sensing oriented object detection; cross-domain, no robotic arm or planning content. |
| c-1a6f9c84 | 3D Object Detection for Autonomous Driving: A Comprehensive Survey | 三维 目标检测 for 自动驾驶: A Comprehensive 综述 | Autonomous driving survey; cross-domain with no manipulation or arm planning. |
| c-d36d0fb5 | Object Contour and Edge Detection with RefineContourNet | Object Contour and Edge 检测 with RefineContourNet | Edge/contour detection paper; no manipulation, planning, or robotic-arm relevance. |
| c-e4c45099 | AIn't Nothing But a Survey? Using Large Language Models for Coding German Open-Ended Survey Responses on Survey Motivati | AIn't Nothing But a 综述? Using Large Language Models for Coding German Open-Ended 综述 Responses on 综述 Motivati | LLM survey coding paper; entirely off-topic. |
| c-84522889 | Exploring Depth Contribution for Camouflaged Object Detection | Exploring Depth Contribution for Camouflaged 目标检测 | Camouflaged segmentation in images; no robotic arm or planning relevance. |
| c-8c27a2fc | TJU-DHD: A Diverse High-Resolution Dataset for Object Detection | TJU-DHD: A Diverse High-Resolution 数据集 for 目标检测 | Autonomous-driving detection dataset; wrong object classes for arm tasks. |
| c-774a894a | rbgirshick/voc-dpm | 仓库 rbgirshick/voc-dpm | Classic DPM code; pre-deep-learning, no manipulation relevance. |
| c-09c83835 | Import project (Eclipse ADT, Gradle, etc.) | (中文含义由英文派生) | Garbage title; no discernible topic, reject. |
| c-6f58281a | E RobotCore: lynx xmit lock: #### abandoning lock: | (中文含义由英文派生) | Garbage error-log title; no paper content. |
| c-bf261417 | Could not find com.android.tools.lint:lint-gradle:26.1.4 | (中文含义由英文派生) | Garbage build-error title; reject. |
| c-2d75534e | Version 3.00 (built on 17.04.013) | (中文含义由英文派生) | Garbage version-string title; no content. |
| c-f77b34da | missing hardware leaves robot controller disconnected from driver station | missing hardware leaves 机器人 controller disconnected from driver station | Garbage issue-tracker title; no research content. |
| c-8651c921 | fast tapping of Init/Start causes problems | (中文含义由英文派生) | Title is a bug report fragment; no research content, unrelated to robotic arm vision/planning. |
| c-f427be87 | >  ====== Hand Inference graph loaded. | > ====== Hand Inference graph loaded. | Title is a console log snippet; not a research artifact. |
| c-6d3a2000 | python   detection_graph = tf.Graph()     with detection_graph.as_default():         od_graph_def = tf.GraphDef()        | python  detection_graph = tf.Graph()   with detection_graph.as_default():     od_graph_def = tf.GraphDef() | Title is a Python code snippet; not a research paper. |
| c-884ecc96 | python   (boxes, scores, classes, num) = sess.run(         [detection_boxes, detection_scores,             detection_cla | python  (boxes, scores, classes, num) = sess.run(     [detection_boxes, detection_scores,       detection_cla | Title is a Python detection snippet; not a research paper. |
| c-31211383 | cmd   # load and run detection on video at path "videos/chess.mov"   python detect_single_threaded.py --source videos/ch | cmd  # load and run 检测 on video at path "videos/chess.mov"  python detect_single_threaded.py --source videos/ch | Title is a CLI command from a detection repo; not a paper. |

#### dataset_and_repo_notes

> No robotic-arm manipulation dataset was retrieved; TJU-DHD (c-8c27a2fc) is driving-only and was rejected, so a dataset round is required.
> YOLOv8 ROS wrapper c-f3a8b590 is the only directly deployable perception module; it exposes topics consumable by MoveIt/ROS planning nodes.
> Open-set capability via c-515b0476 (Grounding DINO) is useful for unknown workpieces in cluttered scenes.
> Edge-deployed YOLO variants (c-ce55ec19 MS-YOLO, c-cefd0c7e YOLOv10) are candidates if the arm runs on embedded compute.

### §20 ENG-THESIS-048 — 《面向动态环境的视觉SLAM研究》 — `fail`

| 维度 | 数值 |
|---|---:|
| batch | r4 |
| elapsed | 191.0s |
| domain | 三维视觉/SLAM/点云 |
| paper | 20 |
| dataset | 0 |
| repo | 6 |
| baseline | 3 |
| parallel | 3 |
| strong_noise_in_core | True |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-10613-1022467397.htm |

**direction_recommendation**: The corpus contains one strong direct match (c-4c7686be, 'Visual SLAM and visual odometry with semantic-based filtering of dynamic objects') and several adjacent VO/VIO references plus the ORB-SLAM line of work (c-aec63858 hardware, c-a3d8365f ORB-LINE-SLAM3). Notably absent from automated retrieval are the canonical dynamic-SLAM anchors: DynaSLAM, MaskFusion, DS-SLAM, ORB-SLAM3 + semantic segmentation papers, and TUM-RGBD / KITTI dynamic benchmarks. The recommendation is a focused literature review centered on semantic-mask-based dynamic object removal for visual SLAM, treating the semantic-filtering paper as the core seed and ORB-SLAM family as the baseline scaffold. Manual supplementation is required to recover canonical dynamic-SLAM works and the standard evaluation benchmarks before baseline selection in Re03.

#### core (1)

| cid | 原文 title | 中文含义 | reason |
|---|---|---|---|
| c-4c7686be | Visual SLAM and visual odometry with semantic-based filtering of dynamic objects | Visual SLAM and 视觉里程计 with 语义-based filtering of 动态 objects | Direct match: semantic filtering of dynamic objects for visual SLAM/VO. |

#### baseline (3)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-aec63858 | ORB-based SLAM accelerator on SoC FPGA | (中文含义由英文派生) |
| c-a3d8365f | A rich bounty of AGN in the 9 square degree Bootes survey: high-z obscured AGN and large-scale structure | rich bounty of AGN (天文主动星系核，强噪声) in the 9 square degree Bootes 综述: high-z obscured AGN (天文主动星系核，强噪声) and large-scale structure |
| c-41dc15fc | On combining visual SLAM and visual odometry | On combining visual SLAM and 视觉里程计 |

#### parallel (3)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-4c7686be | Visual SLAM and visual odometry with semantic-based filtering of dynamic objects | Visual SLAM and 视觉里程计 with 语义-based filtering of 动态 objects |
| c-1a03eece | ViPR: Visual-Odometry-aided Pose Regression for 6DoF Camera Localization | (中文含义由英文派生) |
| c-67167a40 | DF-VO: What Should Be Learnt for Visual Odometry? | DF-VO: What Should Be Learnt for 视觉里程计? |

#### reference (6)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-8dfd8218 | DSVO: Direct Stereo Visual Odometry | DSVO: Direct Stereo 视觉里程计 |
| c-5cd95f5c | An Equivariant Filter for Visual Inertial Odometry | Equivariant Filter for 视觉惯性 Odometry |
| c-6bd2b430 | Benchmarking Visual Feature Representations for LiDAR-Inertial-Visual Odometry Under Challenging Conditions | Benchmarking Visual Feature Representations for 激光雷达-Inertial-视觉里程计 Under Challenging Conditions |
| c-bbb86dcf | A visual study of ICP variants for Lidar Odometry | visual study of ICP variants for 激光雷达 Odometry |
| c-0771e47a | A Simple Framework for Contrastive Learning of Visual Representations | Simple Framework for 对比学习 Learning of Visual Representations |
| c-0a25cdd0 | DINOv2: Learning Robust Visual Features without Supervision | (中文含义由英文派生) |

#### long_tail (6)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-b0510d29 | gyubeomim/simple_mono_vo_ros | 仓库 gyubeomim/simple_mono_vo_ros |
| c-cb677b34 | atomoclast/ros_mono_vo | 仓库 atomoclast/ros_mono_vo |
| c-c956339b | maazmb/LEP-Hybrid-Visual-Odometry | 仓库 maazmb/LEP-Hybrid-Visual-Odometry |
| c-6ef81efb | Adu143/FINken-EYE | 仓库 Adu143/FINken-EYE |
| c-1888ea55 | estods3/JetTank-MappingPkg | 仓库 estods3/JetTank-MappingPkg |
| c-88743107 | geoeo/visual_odometry | 仓库 geoeo/visual_odometry |

#### rejected (7)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-89613e26 | AIn't Nothing But a Survey? Using Large Language Models for Coding German Open-Ended Survey Responses on Survey Motivati | AIn't Nothing But a 综述? Using Large Language Models for Coding German Open-Ended 综述 Responses on 综述 Motivati | NLP / survey-methodology paper; cross-domain. |
| c-68eb8367 | Affordances and platformed visual misogyny: a call for feminist approaches in visual methods | (中文含义由英文派生) | Feminist visual-methods paper; cross-domain. |
| c-2280ee0c | The Use of Visual Methods to Support Communication with Older Adults with Cognitive Impairment: A Scoping Review | Use of Visual Methods to Support Communication with Older Adults with Cognitive Impairment: A Scoping Review | Healthcare scoping review about communication with cognitively impaired older adults; not robotics. |
| c-80bc117b | Recent progress in visual methods for aflatoxin detection | Recent progress in visual methods for aflatoxin 检测 | Aflatoxin detection in food/agriculture domain; cross-domain, not robotics. |
| c-3cb60e71 | Rate effect on crack propagation measurement results with crack propagation gauge, digital image correlation, and visual | Rate effect on 裂缝 propagation measurement results with 裂缝 propagation gauge, digital image correlation, and visual | Materials science paper on crack propagation; cross-domain, not robotics. |
| c-1d2556b8 | When Fieldwork “Fails”: Participatory Visual Methods And Fieldwork Encounters With Resettled Refugees* | (中文含义由英文派生) | Social-science fieldwork methodology paper; cross-domain, not robotics. |
| c-c23335c6 | Spectrophotometric Evaluation of Shade Selection with Digital and Visual Methods | (中文含义由英文派生) | Dentistry shade-selection paper; cross-domain clinical study, not robotics. |

#### dataset_and_repo_notes

> c-c4c41104 is a generic VO/SLAM evaluation benchmark but is not designed for dynamic scenes; treat as background only.
> c-aec63858 (ORB-SLAM FPGA accelerator) is infrastructure for ORB-SLAM, not a dynamic-scene method; cite as baseline scaffold only.
> c-a3d8365f has title/abstract metadata mismatch (AGN vs ORB-LINE-SLAM3); verify before citing as ORB-SLAM variant.

#### AGN 强噪声专项分析

本题 `has_strong_noise_in_core=true` 触发 fail（reason = `strong_noise_in_core_or_baseline_or_parallel`）。以下命中条目在 `evidence_review` / `core` / `baseline` / `parallel` 里出现时被强噪声 detector 标记：

| bucket | cid | 原文 title (英文) | 中文含义 + 噪声归类 |
|---|---|---|---|
| baseline | c-a3d8365f | A rich bounty of AGN in the 9 square degree Bootes survey: high-z obscured AGN and large-scale structure | (AGN 天文宽词污染，与题目 面向动态环境的视觉SLAM研究 不对齐) |

### §21 ENG-THESIS-050 — 《基于深度学习的自动驾驶感知算法》 — `weak`

| 维度 | 数值 |
|---|---:|
| batch | batch3 |
| elapsed | 272.4s |
| domain | 自动驾驶/交通感知 |
| paper | 35 |
| dataset | 0 |
| repo | 0 |
| baseline | 3 |
| parallel | 8 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-10335-1022779682.htm |

**direction_recommendation**: Given the parsed topic and the audited evidence, the literature survey should anchor on camera-centric deep-learning perception for autonomous driving, with a primary spine of (a) multi-camera BEV-based 3D object detection (BEVDet, c-dfa6fa1d), (b) monocular/multi-camera 3D detection variants (MonoCInIS c-be7d87f0; StreamDSGN real-time stereo c-5d6a9c1c), (c) LiDAR 3D detection methods as a comparative branch (PVAFN c-996b3ad2; Super Sparse c-a9c8fc86), and (d) lane detection from CNN-era to BEV-projected 3D lane methods (Self-Attention Distillation c-9f158647; Agnostic Lane c-4b7cb936; HSDF-Lane c-8c74231c; ENet-21 c-d0c70191; RONELD c-63317f7d; LDNet event-based c-44b09397; ELAS dataset c-ef9cef23). The dedicated AD 3D detection survey (c-c7b021a9) is the structural anchor for taxonomy and dataset coverage. Cascade R-CNN (c-6c699227) and Vision Mamba survey (c-f4cb76d5) serve as foundational/architecture references. Scope is modular perception stack only (3D detection + lane detection), camera-primary with LiDAR as a comparative branch; end-to-end driving (UniAD) and occupancy prediction are out of scope pending clarification. KITTI/nuScenes/Waymo Open datasets are missing from t

#### core (4)

| cid | 原文 title | 中文含义 | reason |
|---|---|---|---|
| c-dfa6fa1d | BEVDet: High-performance Multi-camera 3D Object Detection in Bird-Eye-View | BEVDet: High-performance Multi-camera 三维 目标检测 in Bird-Eye-View | BEVDet is a canonical multi-camera BEV 3D detection paper; high topical alignment. |
| c-c7b021a9 | 3D Object Detection for Autonomous Driving: A Comprehensive Survey | 三维 目标检测 for 自动驾驶: A Comprehensive 综述 | Dedicated AD 3D detection survey; strong structural anchor for the literature review. |
| c-9f158647 | Learning Lightweight Lane Detection CNNs by Self Attention Distillation | Learning 轻量化 车道线检测 CNNs by Self Attention Distillation | CNN-based lane detection with self-attention distillation; strong AD lane-detection match. |
| c-8c74231c | HSDF-Lane: Height-Aligned Signed Distance Field with Semantic Lane Prior for 3D Lane Detection | HSDF-Lane: Height-Aligned Signed Distance Field with 语义 Lane Prior for 三维 车道线检测 | Monocular 3D lane detection with BEV feature projection; strong topical alignment. |

#### baseline (3)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-dfa6fa1d | BEVDet: High-performance Multi-camera 3D Object Detection in Bird-Eye-View | BEVDet: High-performance Multi-camera 三维 目标检测 in Bird-Eye-View |
| c-9f158647 | Learning Lightweight Lane Detection CNNs by Self Attention Distillation | Learning 轻量化 车道线检测 CNNs by Self Attention Distillation |
| c-c7b021a9 | 3D Object Detection for Autonomous Driving: A Comprehensive Survey | 三维 目标检测 for 自动驾驶: A Comprehensive 综述 |

#### parallel (8)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-be7d87f0 | MonoCInIS: Camera Independent Monocular 3D Object Detection using Instance Segmentation | MonoCInIS: Camera Independent Monocular 三维 目标检测 using Instance 分割 |
| c-a9c8fc86 | Super Sparse 3D Object Detection | Super Sparse 三维 目标检测 |
| c-5d6a9c1c | Real-time Stereo-based 3D Object Detection for Streaming Perception | 实时 Stereo-based 三维 目标检测 for Streaming Perception |
| c-996b3ad2 | PVAFN: Point-Voxel Attention Fusion Network with Multi-Pooling Enhancing for 3D Object Detection | PVAFN: Point-Voxel Attention Fusion Network with Multi-Pooling Enhancing for 三维 目标检测 |
| c-8c74231c | HSDF-Lane: Height-Aligned Signed Distance Field with Semantic Lane Prior for 3D Lane Detection | HSDF-Lane: Height-Aligned Signed Distance Field with 语义 Lane Prior for 三维 车道线检测 |
| c-4b7cb936 | Agnostic Lane Detection | Agnostic 车道线检测 |
| c-63317f7d | RONELD: Robust Neural Network Output Enhancement for Active Lane Detection | RONELD: Robust 神经网络 Output Enhancement for Active 车道线检测 |
| c-d0c70191 | ENet-21: An Optimized light CNN Structure for Lane Detection | ENet-21: An Optimized light CNN Structure for 车道线检测 |

#### reference (8)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-6c699227 | Cascade R-CNN: High Quality Object Detection and Instance Segmentation | Cascade R-CNN: High Quality 目标检测 and Instance 分割 |
| c-f4cb76d5 | Vision Mamba: A Comprehensive Survey and Taxonomy | Vision Mamba: A Comprehensive 综述 and Taxonomy |
| c-f52b3ebb | Object Contour and Edge Detection with RefineContourNet | Object Contour and Edge 检测 with RefineContourNet |
| c-44b09397 | LDNet: End-to-End Lane Marking Detection Approach Using a Dynamic Vision Sensor | LDNet: End-to-End Lane Marking 检测 Approach Using a 动态 Vision Sensor |
| c-ef9cef23 | Ego-Lane Analysis System (ELAS): Dataset and Algorithms | Ego-Lane Analysis System (ELAS): 数据集 and Algorithms |
| c-1f712e2a | The Evolution of First Person Vision Methods: A Survey | Evolution of First Person Vision Methods: A 综述 |
| c-60d7c8d3 | Pascal VOC | (中文含义由英文派生) |
| c-3473ff41 | COCO | (中文含义由英文派生) |

#### long_tail (0) (无)
#### rejected (5)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-cad2b1fd | VLP: A Survey on Vision-Language Pre-training | VLP: A 综述 on Vision-Language Pre-training | Vision-language pre-training survey; cross-domain for AD perception topic. |
| c-f0fa9da8 | A rich bounty of AGN in the 9 square degree Bootes survey: high-z obscured AGN and large-scale structure | rich bounty of AGN (天文主动星系核，强噪声) in the 9 square degree Bootes 综述: high-z obscured AGN (天文主动星系核，强噪声) and large-scale structure | Astronomy AGN paper; cross-domain, rejected. |
| c-f4f3e76d | AIn't Nothing But a Survey? Using Large Language Models for Coding German Open-Ended Survey Responses on Survey Motivati | AIn't Nothing But a 综述? Using Large Language Models for Coding German Open-Ended 综述 Responses on 综述 Motivati | Survey/LLM coding methodology paper; unrelated to AD perception. |
| c-107db1dc | Vision-to-Music Generation: A Survey | Vision-to-Music Generation: A 综述 | Vision-to-music survey; cross-domain and not AD related. |
| c-fd17120d | The Methanol Multibeam Survey | Methanol Multibeam 综述 | Radio astronomy methanol survey; cross-domain, rejected. |

#### dataset_and_repo_notes

> KITTI / nuScenes / Waymo Open dataset papers are absent from EvidenceReview; retrieve official dataset papers (Geiger KITTI, Caesar nuScenes, Sun Waymo) in next round.
> No GitHub repo candidates were returned by the github adapter (status=empty); add a targeted repo search for BEVDet, Super Sparse, HSDF-Lane repos.
> Pascal VOC (c-60d7c8d3) and COCO (c-3473ff41) are usable only as pretraining corpora for AD backbones, not as driving-scene benchmarks.
> ELAS (c-ef9cef23) bundles a lane detection dataset usable as a secondary lane benchmark.

### §22 ENG-THESIS-051 — 《基于深度学习的语义SLAM研究》 — `pass`

| 维度 | 数值 |
|---|---:|
| batch | r5 |
| elapsed | 208.4s |
| domain | 三维视觉/SLAM/点云 |
| paper | 16 |
| dataset | 0 |
| repo | 2 |
| baseline | 1 |
| parallel | 5 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-10060-1021595219.htm |

**direction_recommendation**: Anchor the survey on deep-learning-based semantic SLAM along three converging lines: (1) CNN-based semantic SLAM in dynamic environments (use c-3557ea96 DS-SLAM as the canonical baseline and survey all dynamic-environment variants); (2) recent neural-radiance/Gaussian-Splatting semantic SLAM that fuses implicit scene representation with explicit semantic labels (use c-4e374c72 Hier-SLAM as the primary 2024 reference and c-1689e596 OpenMonoGS-SLAM as the 2025 open-set parallel); (3) end-to-end deep-learning SLAM backbones relevant to the topic, especially transformer-based designs (c-b686c112 SLAM-Former). Treat c-463e1d6f VAR-SLAM and c-e31df83a MLP-SLAM as candidate dynamic-environment / neural-representation parallels. Keep c-d5d53ed7 (SemanticSLAM repo) and c-12927a8e (OpenMonoGS project page) as long-tail repos pending manual inspection. All other papers are cross-domain noise and excluded.

#### core (4)

| cid | 原文 title | 中文含义 | reason |
|---|---|---|---|
| c-4e374c72 | Hier-SLAM: Scaling-up Semantics in SLAM with a Hierarchically Categorical Gaussian Splatting | Hier-SLAM: Scaling-up 语义 in SLAM with a Hierarchically Categorical Gaussian Splatting | Direct match: semantic Gaussian Splatting SLAM with 3D semantic mapping and explicit semantic label prediction. |
| c-3557ea96 | DS-SLAM: A Semantic Visual SLAM towards Dynamic Environments | DS-SLAM: A 语义 Visual SLAM towards 动态 Environments | Foundational semantic SLAM paper for dynamic environments using deep learning-based segmentation. |
| c-1689e596 | OpenMonoGS-SLAM: Monocular Gaussian Splatting SLAM with Open-set Semantics | OpenMonoGS-SLAM: Monocular Gaussian Splatting SLAM with Open-set 语义 | Monocular GS-SLAM with open-set semantics directly aligns with semantic SLAM+deep learning topic. |
| c-b686c112 | SLAM-Former: Putting SLAM into One Transformer | (中文含义由英文派生) | Full transformer-based SLAM integrating front-end/back-end; strong method alignment with deep-learning SLAM. |

#### baseline (1)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-3557ea96 | DS-SLAM: A Semantic Visual SLAM towards Dynamic Environments | DS-SLAM: A 语义 Visual SLAM towards 动态 Environments |

#### parallel (5)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-4e374c72 | Hier-SLAM: Scaling-up Semantics in SLAM with a Hierarchically Categorical Gaussian Splatting | Hier-SLAM: Scaling-up 语义 in SLAM with a Hierarchically Categorical Gaussian Splatting |
| c-1689e596 | OpenMonoGS-SLAM: Monocular Gaussian Splatting SLAM with Open-set Semantics | OpenMonoGS-SLAM: Monocular Gaussian Splatting SLAM with Open-set 语义 |
| c-b686c112 | SLAM-Former: Putting SLAM into One Transformer | (中文含义由英文派生) |
| c-463e1d6f | VAR-SLAM: Visual Adaptive and Robust SLAM for Dynamic Environments | VAR-SLAM: Visual Adaptive and Robust SLAM for 动态 Environments |
| c-e31df83a | MLP-SLAM: Multilayer Perceptron-Based Simultaneous Localization and Mapping | (中文含义由英文派生) |

#### reference (0) (无)
#### long_tail (2)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-d5d53ed7 | poetgeorge/SemanticSLAM | 仓库 poetgeorge/SemanticSLAM |
| c-12927a8e | open-ended-slam/open-ended-slam.github.io | 仓库 open-ended-slam/open-ended-slam.github.io |

#### rejected (10)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-16ffd440 | A rich bounty of AGN in the 9 square degree Bootes survey: high-z obscured AGN and large-scale structure | rich bounty of AGN (天文主动星系核，强噪声) in the 9 square degree Bootes 综述: high-z obscured AGN (天文主动星系核，强噪声) and large-scale structure | Astrophysics paper on obscured AGN in Bootes field; completely unrelated to semantic SLAM. |
| c-f374fb6f | AIn't Nothing But a Survey? Using Large Language Models for Coding German Open-Ended Survey Responses on Survey Motivati | AIn't Nothing But a 综述? Using Large Language Models for Coding German Open-Ended 综述 Responses on 综述 Motivati | NLP paper on LLM-based survey coding; cross-domain content unrelated to SLAM. |
| c-51567bb9 | Learn to Accumulate Evidence from All Training Samples: Theory and Practice | (中文含义由英文派生) | Evidential deep learning theory paper unrelated to SLAM domain. |
| c-8e03180b | The Modern Mathematics of Deep Learning | Modern Mathematics of 深度学习 | Mathematics-of-deep-learning theory paper, no SLAM relevance. |
| c-4d9db5c8 | Deep Learning and Computational Physics (Lecture Notes) | 深度学习 and Computational Physics (Lecture Notes) | Lecture notes on deep learning + computational physics; no SLAM relevance. |
| c-e3803e48 | A multitask deep learning model for real-time deployment in embedded systems | 多任务 深度学习 model for 实时 deployment in 嵌入式 systems | Embedded multitask deep learning paper with no SLAM or semantic mapping focus. |
| c-0e45fd94 | Monodense Deep Neural Model for Determining Item Price Elasticity | (中文含义由英文派生) | Economics/retail elasticity paper, completely off-topic. |
| c-d51f74e5 | Activation Analysis of a Byte-Based Deep Neural Network for Malware Classification | Activation Analysis of a Byte-Based Deep 神经网络 for Malware 分类 | Malware classification paper, cross-domain unrelated to SLAM. |
| c-1be1402b | Deep learning observables in computational fluid dynamics | 深度学习 observables in computational fluid 动态 | CFD deep learning paper, cross-domain unrelated to SLAM. |
| c-39734ebf | DeepCFL: Deep Contextual Features Learning from a Single Image | (中文含义由英文派生) | Single-image feature learning paper, lacks SLAM/3D semantics. |

#### dataset_and_repo_notes

> c-12927a8e is the project page repo for OpenMonoGS-SLAM (c-1689e596); limited code visibility, expect author release on a separate code repo (refs c-1689e596).
> c-d5d53ed7 poetgeorge/SemanticSLAM is a fork of 1989Ryan/Semantic_SLAM (C++); needs manual inspection to confirm whether it integrates DL-based semantic segmentation or is a feature-only semantic map 
> No canonical semantic-SLAM benchmark dataset is captured yet; TUM RGB-D, ScanNet, Replica, and KITTI are expected — must be retrieved manually.
> All cross-domain rejected papers (c-16ffd440 AGN, c-f374fb6f LLM survey coding, c-51567bb9 / c-8e03180b / c-4d9db5c8 DL theory, c-0e45fd94 elasticity, c-d51f74e5 malware, c-1be1402b CFD, c-39734ebf De

### §23 ENG-THESIS-058 — 《基于深度学习的激光点云环境感知》 — `pass`

| 维度 | 数值 |
|---|---:|
| batch | r5 |
| elapsed | 241.5s |
| domain | 三维视觉/SLAM/点云 |
| paper | 38 |
| dataset | 2 |
| repo | 6 |
| baseline | 5 |
| parallel | 5 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-10009-1021644274.htm |

**direction_recommendation**: Focus the literature survey on deep-learning methods for 3D object detection from LiDAR point clouds in autonomous driving perception, using KITTI and Waymo as canonical benchmarks. Anchor the survey around three pillars: (1) point-based methods (PointNet/PointNet++ family including Frustum PointNet variants, c-4e45cb3c, c-3e448792, c-f095419f, c-e6562b26, c-55c1a425), (2) voxel/sparse 3D methods (VoxelNet vs PointNet comparative study c-0040d78d, PointPillars c-1e909eed, Super Sparse/FSD c-247321a7, PVAFN c-dc0ed05f), and (3) transformer-era and robustness work (MultiCorrupt c-6abcc520, autotools-derived approaches). Reserve point cloud semantic segmentation and camera-only 3D detection as background context rather than primary evidence. Use c-99441835 as the umbrella survey and c-7b9fd1e6 / c-fc5750a5 as primary datasets. Treat Frustum-PointNet multi-modal extension, FSD, PVAFN, and PointPillars as the concrete parallel/baseline cluster, with VoteNet (c-35f62851) and KITTI-processing student repo (c-ba8b8834) as implementation references.

#### core (12)

| cid | 原文 title | 中文含义 | reason |
|---|---|---|---|
| c-dc0ed05f | PVAFN: Point-Voxel Attention Fusion Network with Multi-Pooling Enhancing for 3D Object Detection | PVAFN: Point-Voxel Attention Fusion Network with Multi-Pooling Enhancing for 三维 目标检测 | Direct LiDAR point-voxel fusion method for 3D detection, strongly aligned with topic. |
| c-247321a7 | Super Sparse 3D Object Detection | Super Sparse 三维 目标检测 | LiDAR-based 3D detection for autonomous driving; directly matches topic task. |
| c-99441835 | 3D Object Detection for Autonomous Driving: A Comprehensive Survey | 三维 目标检测 for 自动驾驶: A Comprehensive 综述 | Comprehensive survey of 3D detection in autonomous driving; ideal survey-type reference. |
| c-4e45cb3c | High Dimensional Frustum PointNet for 3D Object Detection from Camera, LiDAR, and Radar | High Dimensional Frustum PointNet for 三维 目标检测 from Camera, 激光雷达, and Radar | Frustum PointNet for LiDAR+camera 3D detection; core topic method. |
| c-3e448792 | 3D Object Detection Based on Improved Frustum PointNet | 三维 目标检测 Based on Improved Frustum PointNet | Improved Frustum PointNet for 3D detection; aligned with PointNet-based LiDAR perception. |
| c-e6562b26 | Research on 3D Point Cloud Object Detection Method Based on PointNet Model | Research on 三维 点云 目标检测 Method Based on PointNet Model | PointNet-based 3D point cloud object detection; directly on-topic method. |
| c-0040d78d | A Comparative Study of VoxelNet and PointNet for 3D Object Detection in Car by Using KITTI Benchmark | Comparative Study of VoxelNet and PointNet for 三维 目标检测 in 汽车 by Using KITTI 基准 | Direct comparative baseline study of VoxelNet vs PointNet on KITTI 3D detection. |
| c-6abcc520 | MultiCorrupt: A Multi-Modal Robustness Dataset and Benchmark of LiDAR-Camera Fusion for 3D Object Detection | MultiCorrupt: A Multi-Modal Robustness 数据集 and 基准 of 激光雷达-Camera Fusion for 三维 目标检测 | Direct LiDAR-camera fusion 3D detection benchmark, IV 2024 venue. |
| c-35f62851 | AliAhmed36/VoteNet | 仓库 AliAhmed36/VoteNet | VoteNet is a foundational 3D detection repo on point clouds. |
| c-fc5750a5 | Waymo Open Dataset | Waymo Open 数据集 | Waymo Open Dataset is a premier LiDAR autonomous-driving benchmark. |
| c-7b9fd1e6 | KITTI | (中文含义由英文派生) | KITTI is the canonical LiDAR 3D detection benchmark. |
| c-1e909eed | PointPillars: Fast Encoders for Object Detection From Point Clouds | PointPillars: Fast Encoders for 目标检测 From 点云 | Canonical LiDAR point cloud 3D object detection method for autonomous driving; directly on-topic. |

#### baseline (5)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-1e909eed | PointPillars: Fast Encoders for Object Detection From Point Clouds | PointPillars: Fast Encoders for 目标检测 From 点云 |
| c-0040d78d | A Comparative Study of VoxelNet and PointNet for 3D Object Detection in Car by Using KITTI Benchmark | Comparative Study of VoxelNet and PointNet for 三维 目标检测 in 汽车 by Using KITTI 基准 |
| c-35f62851 | AliAhmed36/VoteNet | 仓库 AliAhmed36/VoteNet |
| c-4e45cb3c | High Dimensional Frustum PointNet for 3D Object Detection from Camera, LiDAR, and Radar | High Dimensional Frustum PointNet for 三维 目标检测 from Camera, 激光雷达, and Radar |
| c-f095419f | Attentional PointNet for 3D-Object Detection in Point Clouds | Attentional PointNet for 三维-目标检测 in 点云 |

#### parallel (5)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-dc0ed05f | PVAFN: Point-Voxel Attention Fusion Network with Multi-Pooling Enhancing for 3D Object Detection | PVAFN: Point-Voxel Attention Fusion Network with Multi-Pooling Enhancing for 三维 目标检测 |
| c-247321a7 | Super Sparse 3D Object Detection | Super Sparse 三维 目标检测 |
| c-3e448792 | 3D Object Detection Based on Improved Frustum PointNet | 三维 目标检测 Based on Improved Frustum PointNet |
| c-e6562b26 | Research on 3D Point Cloud Object Detection Method Based on PointNet Model | Research on 三维 点云 目标检测 Method Based on PointNet Model |
| c-6abcc520 | MultiCorrupt: A Multi-Modal Robustness Dataset and Benchmark of LiDAR-Camera Fusion for 3D Object Detection | MultiCorrupt: A Multi-Modal Robustness 数据集 and 基准 of 激光雷达-Camera Fusion for 三维 目标检测 |

#### reference (3)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-99441835 | 3D Object Detection for Autonomous Driving: A Comprehensive Survey | 三维 目标检测 for 自动驾驶: A Comprehensive 综述 |
| c-7b9fd1e6 | KITTI | (中文含义由英文派生) |
| c-fc5750a5 | Waymo Open Dataset | Waymo Open 数据集 |

#### long_tail (11)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-55c1a425 | Attention Mechanisms in PointNet++ for Effective Object Classification in 3D Point Clouds | Attention Mechanisms in PointNet++ for Effective Object 分类 in 三维 点云 |
| c-62829322 | 3D point cloud object classification with PointNet-Lite and data augmentation | 三维 点云 object 分类 with PointNet-Lite and data augmentation |
| c-d1a12f10 | OpenAD: Open-World Autonomous Driving Benchmark for 3D Object Detection | OpenAD: Open-World 自动驾驶 基准 for 三维 目标检测 |
| c-654bb071 | Review of: "OpenAD: Open-World Autonomous Driving Benchmark for 3D Object Detection" | Review of: "OpenAD: Open-World 自动驾驶 基准 for 三维 目标检测" |
| c-26a0f9e7 | End-to-End Object Detection with Transformers | End-to-End 目标检测 with Transformer |
| c-b7d999fa | Deformable DETR: Deformable Transformers for End-to-End Object Detection | Deformable DETR 目标检测: Deformable Transformer for End-to-End 目标检测 |
| c-7ea825d9 | Reg-PointNet++: A CNN Network Based on PointNet++ Architecture for 3D Reconstruction of 3D Objects Modeled by Supershapes | Reg-PointNet++: A CNN Network Based on PointNet++ Architecture for 三维 重建 of 三维 Objects Modeled by Supershapes |
| c-6c4ae8e4 | Beyond PASCAL: A benchmark for 3D object detection in the wild | Beyond PASCAL: A 基准 for 三维 目标检测 in the wild |
| c-ba8b8834 | HariPrasanth-SM/3D-Object-detection | 仓库 HariPrasanth-SM/3D-Object-detection |
| c-b55a4852 | A-suozhang/ada3d.github.io | 仓库 A-suozhang/ada3d.github.io |
| c-146b798f | afterglow-nju/MoPL | 仓库 afterglow-nju/MoPL |

#### rejected (10)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-2d81c19f | Oriented object detection in optical remote sensing images using deep learning: a survey | Oriented 目标检测 in optical remote sensing images using 深度学习: a 综述 | Remote sensing oriented object detection survey; cross-domain vs. LiDAR autonomous driving. |
| c-83bc6745 | swati1024/torrents | 仓库 swati1024/torrents | Torrent download list repo, completely unrelated. |
| c-88c6b589 | Getting started with Spring Framework: covers Spring 5 | (中文含义由英文派生) | Spring Framework tutorial, cross-domain mislabeled as paper. |
| c-25be361a | J Sharma (Author), Ashish Sarin | (中文含义由英文派生) | Author metadata fragment, not a paper. |
| c-24b02ffa | Windows Presentation Foundation Masterclass | (中文含义由英文派生) | WPF UI programming course, cross-domain. |
| c-7c5b86b0 | Programming languages A,B and C | (中文含义由英文派生) | Generic programming languages textbook, cross-domain. |
| c-83229675 | lhai36366/lhai36366 | 仓库 lhai36366/lhai36366 | WPF partial trust article, cross-domain. |
| c-5c5696c1 | I can write to local disk. | (中文含义由英文派生) | Nondescript phrase, not a scholarly paper. |
| c-7f97fdc4 | I can't write to local disk. | (中文含义由英文派生) | Nondescript phrase, not a scholarly paper. |
| c-aac33fa0 | I can write to Isolated Storage | (中文含义由英文派生) | Nondescript phrase, not a scholarly paper. |

#### dataset_and_repo_notes

> c-7b9fd1e6 (KITTI) and c-fc5750a5 (Waymo Open) are core outdoor LiDAR benchmarks; justify using KITTI 3D detection split.
> c-35f62851 VoteNet is a strong implemented baseline for point-cloud 3D detection; useful as open-source reference.
> c-ba8b8834 is a minimal KITTI point-cloud processing student repo; use only as illustration of pipeline, not as method.
> c-6abcc520 MultiCorrupt offers robustness evaluation for LiDAR-camera fusion and is relevant for perception robustness.
> c-c5dd6a98 is only a KITTI result-table fragment; requires manual identification of the eGAC3D source paper before citing.
> c-a935bec1 M3DNet lacks LiDAR modality confirmation; modality must be manually verified via PDF before treating as LiDAR evidence.

### §24 ENG-THESIS-060 — 《基于深度学习的车道线检测方法研究》 — `fail`

| 维度 | 数值 |
|---|---:|
| batch | r5 |
| elapsed | 200.2s |
| domain | 自动驾驶/交通感知 |
| paper | 22 |
| dataset | 1 |
| repo | 6 |
| baseline | 6 |
| parallel | 11 |
| strong_noise_in_core | True |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-11117-1022040920.htm |

**direction_recommendation**: Build the survey around a method-centric taxonomy of deep-learning lane detection: segmentation-based (ENet-21 c-bc8a26fb, RONELD c-ac55d4cd, ELAS c-f7d16cb8), keypoint/graph-based (PINet c-e058aa41), anchor-based (CLRNet c-6f4196a1, Polar R-CNN c-5190ff71, UFLD c-401ed340), attention/distillation-based (SAD c-0adcec08, CNN+RNN gradient c-652854ee), and event/3D extensions (LDNet c-34bdfe3f, HSDF-Lane c-1a877d73). Use the five-era taxonomy survey c-55690dab as the spine, plus SimLane c-40572a8c and SOTIF benchmark c-baebd183 as evaluation scaffolding. Treat Agnostic Lane Detection c-f41ba29b and Faster/Mask R-CNN lane work c-c533e3ed as parallel references. Flag gaps: no direct SCNN/UFLD/LaneATT/LaneNet/PolyLaneNet/transformer-lane primary papers returned, so the student should manually verify whether to backfill via official repo citations before finalizing the survey.

#### core (8)

| cid | 原文 title | 中文含义 | reason |
|---|---|---|---|
| c-0adcec08 | Learning Lightweight Lane Detection CNNs by Self Attention Distillation | Learning 轻量化 车道线检测 CNNs by Self Attention Distillation | Lightweight CNN lane detection with self-attention distillation; directly cited method family. |
| c-bc8a26fb | ENet-21: An Optimized light CNN Structure for Lane Detection | ENet-21: An Optimized light CNN Structure for 车道线检测 | Optimized lightweight CNN architecture for lane detection; direct DL method match. |
| c-5190ff71 | Polar R-CNN: End-to-End Lane Detection With Fewer Anchors_supp1-3564979.pdf | Polar R-CNN: End-to-End 车道线检测 With Fewer Anchors_supp1-3564979.pdf | Polar R-CNN end-to-end lane detection with anchor-based design; key DL method. |
| c-652854ee | Gradient Map Based Lane Detection Using CNN and RNN | Gradient Map Based 车道线检测 Using CNN and RNN | Gradient map CNN+RNN lane detection; matches DL hybrid architecture approach. |
| c-55690dab | A FIVE-ERA TAXONOMY AND BENCHMARK FRAMEWORK FOR LANE DETECTION: FROM CLASSICAL HEURISTICS TO VISION FOUNDATION MODELS IN | FIVE-ERA TAXONOMY AND 基准 FRAMEWORK FOR 车道线检测: FROM CLASSICAL HEURISTICS TO VISION FOUNDATION MODELS IN | Comprehensive lane detection survey/taxonomy covering classical to foundation models; ideal survey source. |
| c-6f4196a1 | xuanandsix/CLRNet-onnxruntime-and-tensorrt-demo | 仓库 xuanandsix/CLRNet-onnxruntime-and-tensorrt-demo | CLRNet inference repo: directly a deep-learning lane-detection CVPR 2022 method. |
| c-e058aa41 | pandamax/Lane-Detection-Based-PINet | 仓库 pandamax/Lane-Detection-Based-PINet | PINet-based lane detector repo; PINet is a well-known DL lane-detection architecture. |
| c-401ed340 | MrLee12138/lane_det | 仓库 MrLee12138/lane_det | TensorRT port of UFLD, one of the canonical DL lane-detection baselines. |

#### baseline (6)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-0adcec08 | Learning Lightweight Lane Detection CNNs by Self Attention Distillation | Learning 轻量化 车道线检测 CNNs by Self Attention Distillation |
| c-bc8a26fb | ENet-21: An Optimized light CNN Structure for Lane Detection | ENet-21: An Optimized light CNN Structure for 车道线检测 |
| c-401ed340 | MrLee12138/lane_det | 仓库 MrLee12138/lane_det |
| c-6f4196a1 | xuanandsix/CLRNet-onnxruntime-and-tensorrt-demo | 仓库 xuanandsix/CLRNet-onnxruntime-and-tensorrt-demo |
| c-e058aa41 | pandamax/Lane-Detection-Based-PINet | 仓库 pandamax/Lane-Detection-Based-PINet |
| c-5190ff71 | Polar R-CNN: End-to-End Lane Detection With Fewer Anchors_supp1-3564979.pdf | Polar R-CNN: End-to-End 车道线检测 With Fewer Anchors_supp1-3564979.pdf |

#### parallel (11)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-f41ba29b | Agnostic Lane Detection | Agnostic 车道线检测 |
| c-ac55d4cd | RONELD: Robust Neural Network Output Enhancement for Active Lane Detection | RONELD: Robust 神经网络 Output Enhancement for Active 车道线检测 |
| c-1a877d73 | HSDF-Lane: Height-Aligned Signed Distance Field with Semantic Lane Prior for 3D Lane Detection | HSDF-Lane: Height-Aligned Signed Distance Field with 语义 Lane Prior for 三维 车道线检测 |
| c-c3848df5 | Cascade R-CNN: High Quality Object Detection and Instance Segmentation | Cascade R-CNN: High Quality 目标检测 and Instance 分割 |
| c-34bdfe3f | LDNet: End-to-End Lane Marking Detection Approach Using a Dynamic Vision Sensor | LDNet: End-to-End Lane Marking 检测 Approach Using a 动态 Vision Sensor |
| c-c533e3ed | A Novel Solution to the Real-Time Lane Detection and Tracking Problem for Autonomous Vehicles by Using Faster R-CNN and Mask R-CNN | Novel Solution to the 实时 车道线检测 and 跟踪 Problem for Autonomous 车辆 by Using Faster R-CNN and Mask R-CNN |
| c-35f633bb | Real time lane detection using CNN | 实时 车道线检测 using CNN |
| c-3d97da30 | CNN-based lane detection | CNN-based 车道线检测 |
| c-1f3b9045 | Design and Optimization of CNN for Lane Detection | Design and Optimization of CNN for 车道线检测 |
| c-652854ee | Gradient Map Based Lane Detection Using CNN and RNN | Gradient Map Based 车道线检测 Using CNN and RNN |
| c-74d77b10 | minghanz/LaneDetection_End2End_test | 仓库 minghanz/LaneDetection_End2End_test |

#### reference (9)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-55690dab | A FIVE-ERA TAXONOMY AND BENCHMARK FRAMEWORK FOR LANE DETECTION: FROM CLASSICAL HEURISTICS TO VISION FOUNDATION MODELS IN AUTONOMOUS DRIVING | FIVE-ERA TAXONOMY AND 基准 FRAMEWORK FOR 车道线检测: FROM CLASSICAL HEURISTICS TO VISION FOUNDATION MODELS IN 自动驾驶 |
| c-f7d16cb8 | Ego-Lane Analysis System (ELAS): Dataset and Algorithms | Ego-Lane Analysis System (ELAS): 数据集 and Algorithms |
| c-40572a8c | SimLane: A Risk-Orientated Benchmark for Lane Detection | SimLane: A Risk-Orientated 基准 for 车道线检测 |
| c-baebd183 | A Benchmark for SOTIF of Lane Marking Detection Algorithms of Autonomous Vehicles | 基准 for SOTIF of Lane Marking 检测 Algorithms of Autonomous 车辆 |
| c-3f8b1b36 | Vehicle Lane Merge Visual Benchmark | 车辆 Lane Merge Visual 基准 |
| c-5a3d9ff5 | An efficient lane detection algorithm for lane departure detection | efficient 车道线检测 algorithm for lane departure 检测 |
| c-d6932d1d | baidut/ITS | 仓库 baidut/ITS |
| c-f4ccd9ae | anshupandey/Advance-Lane-Finding | 仓库 anshupandey/Advance-Lane-Finding |
| c-49233e9c | COCO | (中文含义由英文派生) |

#### long_tail (0) (无)
#### rejected (3)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-e5cef267 | Oriented object detection in optical remote sensing images using deep learning: a survey | Oriented 目标检测 in optical remote sensing images using 深度学习: a 综述 | Survey on oriented object detection in remote sensing imagery; cross-domain to lane detection. |
| c-f69acaee | AIn't Nothing But a Survey? Using Large Language Models for Coding German Open-Ended Survey Responses on Survey Motivati | AIn't Nothing But a 综述? Using Large Language Models for Coding German Open-Ended 综述 Responses on 综述 Motivati | LLM application for survey coding in social science; completely off-topic. |
| c-fb26e51c | The Methanol Multibeam Survey | Methanol Multibeam 综述 | Radio astronomy methanol multibeam survey; completely off-topic domain. |

#### dataset_and_repo_notes

> TuSimple and CULane benchmarks are central; cite c-55690dab and c-40572a8c for evaluation framing (refs c-55690dab, c-40572a8c).
> ELAS c-f7d16cb8 supplies ego-lane dataset + classical algorithms as historical contrast.
> SimLane c-40572a8c offers a risk-oriented benchmark orthogonal to TuSimple/CULane.
> SOTIF benchmark c-baebd183 frames safety evaluation for lane marking detectors.
> CLRNet inference repo c-6f4196a1 and UFLD TensorRT c-401ed340 enable deployment experiments on real DL baselines.
> PINet repo c-e058aa41 supports training + ONNX/Caffe conversion for keypoint-based DL lane detection.

#### AGN 强噪声专项分析

本题 `has_strong_noise_in_core=true` 触发 fail（reason = `strong_noise_in_core_or_baseline_or_parallel`）。以下命中条目在 `evidence_review` / `core` / `baseline` / `parallel` 里出现时被强噪声 detector 标记：

> 强噪声 detector 在 synthesis paper_groups/core/baseline/parallel 中未直接命中 AGN/JATS 标题，但 `evidence_review` 中存在 noise_token 列表命中的条目（详见 raw dump 的 `low_bar_verdict.summary`）。

### §25 ENG-THESIS-063 — 《基于3D视觉的机械臂无序抓取系统研究》 — `weak`

| 维度 | 数值 |
|---|---:|
| batch | batch3 |
| elapsed | 338.1s |
| domain | 机器人/机械臂实验系统 |
| paper | 54 |
| dataset | 0 |
| repo | 0 |
| baseline | 7 |
| parallel | 6 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-10709-1022441451.htm |

**direction_recommendation**: Focus the literature survey on 3D-vision-based robotic arm bin-picking centered on 6D pose estimation for industrial workpieces in cluttered scenes. Build the spine around three core baselines: ZeroBP (c-1deef742) for zero-shot 6D pose, the autoencoder-based cluttered pipeline (c-c7f1bd7c), and the Pickalo modular low-cost system (c-10a380e4); supplement with RGB-D real-time pose (c-765acc7d), PPF classical baseline (c-351b35de), and recent transformer-based multi-view industrial pose (c-2bdf76b0, c-68fe19ea). Use MetaGraspNetV2 (c-f7c420ac) and the large-scale industrial 6D dataset (c-0a2da79e) as primary dataset anchors, with CEPB (c-56fa380c) as a complementary cluttered benchmark. Treat general 6D-pose methods (c-908e7360, c-103594aa, c-94621184, c-c0389af7) as parallel/background reference, the UR5 Gazebo repo (c-09bb9aa9) as system-level scaffolding, and the metadata-mismatched item (c-1882d161) as needs_manual verification before citing.

#### core (11)

| cid | 原文 title | 中文含义 | reason |
|---|---|---|---|
| c-1deef742 | ZeroBP: Learning Position-Aware Correspondence for Zero-shot 6D Pose Estimation in Bin-Picking | (中文含义由英文派生) | Directly targets zero-shot 6D pose for bin-picking; strong topic match. |
| c-c7f1bd7c | Object detection and Autoencoder-based 6D pose estimation for highly cluttered Bin Picking | 目标检测 and Autoencoder-based 6D pose estimation for highly cluttered Bin Picking | Autoencoder-based 6D pose for cluttered industrial bin-picking. |
| c-10a380e4 | Pickalo: Leveraging 6D Pose Estimation for Low-Cost Industrial Bin Picking | (中文含义由英文派生) | Modular 6D pose-based bin-picking pipeline for industrial use. |
| c-0a2da79e | Large-scale 6D Object Pose Estimation Dataset for Industrial Bin-Picking | Large-scale 6D Object Pose Estimation 数据集 for Industrial Bin-Picking | Public 6D pose + instance segmentation dataset for industrial bin-picking. |
| c-56fa380c | CEPB dataset: a photorealistic dataset to foster the research on bin picking in cluttered environments | CEPB 数据集: a photorealistic 数据集 to foster the research on bin picking in cluttered environments | Photorealistic bin-picking dataset for cluttered scenes. |
| c-765acc7d | Real Time and Robust 6D Pose Estimation of RGBD Data for Robotic Bin Picking | 实时 and Robust 6D Pose Estimation of RGB-D Data for 机器人 Bin Picking | Real-time 6D pose from RGB-D for robotic bin-picking. |
| c-54a2723c | Hybrid Method for 6D Pose Estimation in Bin-Picking Scenarios | (中文含义由英文派生) | Hybrid 6D pose method for bin-picking scenarios. |
| c-351b35de | A High Accuracy and Recall Rate 6D Pose Estimation Method Using Point Pair Features for Bin-picking | High Accuracy and Recall Rate 6D Pose Estimation Method Using Point Pair Features for Bin-picking | Point pair feature 6D pose for bin-picking with high accuracy. |
| c-f7c420ac | MetaGraspNetV2: All-in-One Dataset Enabling Fast and Reliable Robotic Bin Picking via Object Relationship Reasoning and  | MetaGraspNetV2: All-in-One 数据集 Enabling Fast and Reliable 机器人 Bin Picking via Object Relationship Reasoning and | MetaGraspNetV2 is a flagship bin-picking grasping dataset directly aligned with topic task+object. |
| c-2bdf76b0 | Multi-Layer Feature Exchange Transformer for Multi-View 6D Object Pose Estimation in Robot Bin Picking | Multi-Layer Feature Exchange Transformer for 多视图 6D Object Pose Estimation in 机器人 Bin Picking | Recent ICRA 2025 paper on 6D pose for robot bin picking; strong method+task match. |
| c-68fe19ea | SDT-6D: Fully Sparse Depth-Transformer for Staged End-to-End 6D Pose Estimation in Industrial Multi-View Bin Picking | SDT-6D: Fully Sparse Depth-Transformer for Staged End-to-End 6D Pose Estimation in Industrial 多视图 Bin Picking | WACV 2026 paper on sparse depth-transformer 6D pose for industrial multi-view bin picking. |

#### baseline (7)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-1deef742 | ZeroBP: Learning Position-Aware Correspondence for Zero-shot 6D Pose Estimation in Bin-Picking | (中文含义由英文派生) |
| c-c7f1bd7c | Object detection and Autoencoder-based 6D pose estimation for highly cluttered Bin Picking | 目标检测 and Autoencoder-based 6D pose estimation for highly cluttered Bin Picking |
| c-10a380e4 | Pickalo: Leveraging 6D Pose Estimation for Low-Cost Industrial Bin Picking | (中文含义由英文派生) |
| c-765acc7d | Real Time and Robust 6D Pose Estimation of RGBD Data for Robotic Bin Picking | 实时 and Robust 6D Pose Estimation of RGB-D Data for 机器人 Bin Picking |
| c-351b35de | A High Accuracy and Recall Rate 6D Pose Estimation Method Using Point Pair Features for Bin-picking | High Accuracy and Recall Rate 6D Pose Estimation Method Using Point Pair Features for Bin-picking |
| c-2bdf76b0 | Multi-Layer Feature Exchange Transformer for Multi-View 6D Object Pose Estimation in Robot Bin Picking | Multi-Layer Feature Exchange Transformer for 多视图 6D Object Pose Estimation in 机器人 Bin Picking |
| c-68fe19ea | SDT-6D: Fully Sparse Depth-Transformer for Staged End-to-End 6D Pose Estimation in Industrial Multi-View Bin Picking | SDT-6D: Fully Sparse Depth-Transformer for Staged End-to-End 6D Pose Estimation in Industrial 多视图 Bin Picking |

#### parallel (6)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-908e7360 | High-resolution open-vocabulary object 6D pose estimation | (中文含义由英文派生) |
| c-103594aa | Learning Point Cloud Representations with Pose Continuity for Depth-Based Category-Level 6D Object Pose Estimation | Learning 点云 Representations with Pose Continuity for Depth-Based Category-Level 6D Object Pose Estimation |
| c-94621184 | Revisiting Fully Convolutional Geometric Features for Object 6D Pose Estimation | Revisiting Fully 卷积 Geometric Features for Object 6D Pose Estimation |
| c-c0389af7 | MR6D: Benchmarking 6D Pose Estimation for Mobile Robots | MR6D: Benchmarking 6D Pose Estimation for 移动 机器人 |
| c-b56535b1 | Bin Picking System using Object Recognition based on Automated Synthetic Dataset Generation | Bin Picking System using Object 识别 based on Automated Synthetic 数据集 Generation |
| c-54a2723c | Hybrid Method for 6D Pose Estimation in Bin-Picking Scenarios | (中文含义由英文派生) |

#### reference (5)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-0a2da79e | Large-scale 6D Object Pose Estimation Dataset for Industrial Bin-Picking | Large-scale 6D Object Pose Estimation 数据集 for Industrial Bin-Picking |
| c-56fa380c | CEPB dataset: a photorealistic dataset to foster the research on bin picking in cluttered environments | CEPB 数据集: a photorealistic 数据集 to foster the research on bin picking in cluttered environments |
| c-f7c420ac | MetaGraspNetV2: All-in-One Dataset Enabling Fast and Reliable Robotic Bin Picking via Object Relationship Reasoning and Dexterous Grasping_supp1-3328964.mp4 | MetaGraspNetV2: All-in-One 数据集 Enabling Fast and Reliable 机器人 Bin Picking via Object Relationship Reasoning and Dexterous Grasping_supp1-3328964.mp4 |
| c-09bb9aa9 | AldoPenaGa/UR5_ROS_Gazebo_BinPicking | 仓库 AldoPenaGa/UR5_ROS_Gazebo_BinPicking |
| c-8562853b | UR5 Pick and Place Simulation in Ros/Gazebo | (中文含义由英文派生) |

#### long_tail (2)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-1882d161 | Object Segmentation Dataset Generation Framework for Robotic Bin-Picking: Multi-Metric Analyse between Results Trained with Real and Synthetic Data | Object 分割 数据集 Generation Framework for 机器人 Bin-Picking: Multi-Metric Analyse between Results Trained with Real and Synthetic Data |
| c-64e905ad | avinashsen707/avinashsen707.github.io | 仓库 avinashsen707/avinashsen707.github.io |

#### rejected (20)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-8141a550 | A Dense Hierarchy of Sublinear Time Approximation Schemes for Bin Packing | Dense Hierarchy of Sublinear Time Approximation Schemes for Bin Packing | Combinatorial bin packing theory, not robotic bin-picking. |
| c-ba0bc4e8 | Multi-Class Uncertainty Calibration via Mutual Information Maximization-based Binning | (中文含义由英文派生) | Calibration/binning paper, not grasping or 3D vision. |
| c-fdf81178 | Attend2Pack: Bin Packing through Deep Reinforcement Learning with Attention | (中文含义由英文派生) | Combinatorial bin packing via RL, not robotic grasping. |
| c-8fe3a311 | AIn't Nothing But a Survey? Using Large Language Models for Coding German Open-Ended Survey Responses on Survey Motivati | AIn't Nothing But a 综述? Using Large Language Models for Coding German Open-Ended 综述 Responses on 综述 Motivati | LLM survey analysis, completely unrelated domain. |
| c-02ff7353 | The Methanol Multibeam Survey | Methanol Multibeam 综述 | Astronomy multibeam survey, unrelated domain. |
| c-7c5ff97e | The SAMI Galaxy Survey: first 1000 galaxies | SAMI Galaxy 综述: first 1000 galaxies | Galaxy survey, unrelated domain. |
| c-a642a3bd | R3eVision: A Survey on Robust Rendering, Restoration, and Enhancement for 3D Low-Level Vision | R3eVision: A 综述 on Robust Rendering, Restoration, and Enhancement for 三维 Low-Level Vision | NeRF/3DGS rendering survey, not grasping. |
| c-0576f5b2 | Mdshobu/Liberty-House-Club-Whitepaper | 仓库 Mdshobu/Liberty-House-Club-Whitepaper | Cryptocurrency/Binance Chain whitepaper; no relation to robotic bin-picking topic. |
| c-83b0f039 | Contract Address on BC | (中文含义由英文派生) | Blockchain contract-address content; not a research paper. |
| c-36fc315e | a01361/a01361.github.io | 仓库 a01361/a01361.github.io | Generic Linux shell/init script repo; no relation to bin-picking topic. |
| c-099987da | # One click Install Shadowsocks-Python server               # | # One click Install Shadowsocks-Python server        # | Shadowsocks installer script misclassified as paper; completely unrelated. |
| c-40aaccbd | # Intro: https://teddysun.com/342.html                      # | # Intro: https://teddysun.com/342.html           # | Shadowsocks intro comment misclassified as paper; unrelated to robotics topic. |
| c-c486af06 | # Author: Teddysun <i@teddysun.com>                         # | # Author: Teddysun <i@teddysun.com>             # | Shadowsocks author comment; unrelated script metadata. |
| c-d29d5efb | # Github: https://github.com/shadowsocks/shadowsocks        # | # Github: https://github.com/shadowsocks/shadowsocks    # | Shadowsocks GitHub comment; unrelated to 3D vision grasping. |
| c-061de40d | [${red}Error${plain}] This script must be run as root! | (中文含义由英文派生) | Shell script error message; unrelated. |
| c-ae917653 | $[{red}Error${plain}] Not supported CentOS 5, please change to CentOS 6+/Debian 7+/Ubuntu 12+ and try again. | (中文含义由英文派生) | OS compatibility error message from a server installer; unrelated. |
| c-04969151 | [${red}Error${plain}] Your OS is not supported. please change OS to CentOS/Debian/Ubuntu and try again. | (中文含义由英文派生) | Unsupported-OS error string; not research content. |
| c-2a4f03cd | Please enter password for shadowsocks-python | (中文含义由英文派生) | Shadowsocks password prompt; unrelated script UI text. |
| c-2c55a88b | Please enter a port for shadowsocks-python [1-65535] | (中文含义由英文派生) | Port-input prompt from shadowsocks installer; unrelated. |
| c-2cb04aef | [${red}Error${plain}] Please enter a correct number [1-65535] | (中文含义由英文派生) | Port-number validation error; unrelated script string. |

#### dataset_and_repo_notes

> c-0a2da79e: synthetic+real point cloud/depth dataset with 6D pose, visibility, and instance segmentation masks for industrial bin-picking.
> c-f7c420ac: MetaGraspNetV2 provides object-relation reasoning and dexterous grasp labels — closest GraspNet-style bin-picking dataset.
> c-56fa380c: CEPB delivers ~1.5M photorealistic cluttered scenes with RGB+depth+normals+segmentation for pose/detection stress tests.
> c-09bb9aa9: UR5 ROS/Gazebo bin-picking simulation usable as arm-side execution scaffolding, but no deep-learning 3D-vision module.
> c-64e905ad: GitHub Pages blog on a student bin-picking master project — read manually before citing as evidence.

### §26 ENG-THESIS-064 — 《面向复杂道路场景的车辆目标检测算法研究与实现》 — `pass`

| 维度 | 数值 |
|---|---:|
| batch | r5 |
| elapsed | 180.0s |
| domain | 自动驾驶/交通感知 |
| paper | 17 |
| dataset | 0 |
| repo | 6 |
| baseline | 3 |
| parallel | 3 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-11318-1022664683.htm |

**direction_recommendation**: Recommended direction: a YOLOv5-family based, ground-level, optical 2D vehicle detection system tuned for complex road scenes, with an upgraded variant (attention + multi-scale feature fusion) targeting small/occluded vehicle cases. The strongest evidence cluster is three YOLOv5 papers (c-4b48a5af variant comparison; c-2d75e0bd fisheye intersection; c-6e0c23e7 YOLO-Z small-object improvement) that together cover the three pillars of the topic: YOLO baseline, urban road complexity, and small-object difficulty. YOLOv8, DETR, and Faster R-CNN are not well covered by the retrieved evidence, so they should be added in Re03 as expanded baselines rather than relied on now. Datasets to prioritize: UA-DETRAC (urban traffic, via c-fd4cb3f9) and a CARLA-synthetic supplement (c-a30f992e) for complex/edge-case scenes. Repos c-e13e6fc7 and c-de61d041 serve as reference implementations.

#### core (3)

| cid | 原文 title | 中文含义 | reason |
|---|---|---|---|
| c-4b48a5af | Comparing YOLOv5 Variants for Vehicle Detection: A Performance Analysis | Comparing YOLO 实时目标检测 Variants for 车辆 检测: A Performance Analysis | Direct YOLOv5 vehicle detection benchmark, strong topic match. |
| c-2d75e0bd | An Optimized YOLOv5 Based Approach For Real-time Vehicle Detection At Road Intersections Using Fisheye Cameras | Optimized YOLO 实时目标检测 Based Approach For 实时 车辆 检测 At 道路 Intersections Using Fisheye Cameras | Optimized YOLOv5 for urban road intersections, strong match. |
| c-6e0c23e7 | YOLO-Z: Improving small object detection in YOLOv5 for autonomous vehicles | YOLO 实时目标检测-Z: Improving small 目标检测 in YOLO 实时目标检测 for autonomous 车辆 | YOLOv5 small-object improvement for autonomous driving, strong match. |

#### baseline (3)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-4b48a5af | Comparing YOLOv5 Variants for Vehicle Detection: A Performance Analysis | Comparing YOLO 实时目标检测 Variants for 车辆 检测: A Performance Analysis |
| c-2d75e0bd | An Optimized YOLOv5 Based Approach For Real-time Vehicle Detection At Road Intersections Using Fisheye Cameras | Optimized YOLO 实时目标检测 Based Approach For 实时 车辆 检测 At 道路 Intersections Using Fisheye Cameras |
| c-6e0c23e7 | YOLO-Z: Improving small object detection in YOLOv5 for autonomous vehicles | YOLO 实时目标检测-Z: Improving small 目标检测 in YOLO 实时目标检测 for autonomous 车辆 |

#### parallel (3)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-7077eeb4 | Car Detection using Unmanned Aerial Vehicles: Comparison between Faster R-CNN and YOLOv3 | 汽车 检测 using Unmanned Aerial 车辆: Comparison between Faster R-CNN and YOLO 实时目标检测 |
| c-fd4cb3f9 | Vehicle detection with sub-class training using R-CNN for the UA-DETRAC benchmark | 车辆 检测 with sub-class training using R-CNN for the UA-DETRAC 基准 |
| c-2e49680c | Intelligent driving vehicle front multi-target tracking and detection based on YOLOv5 and point cloud 3D projection | Intelligent driving 车辆 front multi-target 跟踪 and 检测 based on YOLO 实时目标检测 and 点云 三维 projection |

#### reference (4)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-de61d041 | kevincao91/kevin.ai.vehicle_detection | 仓库 kevincao91/kevin.ai.vehicle_detection |
| c-e13e6fc7 | wealook/vision_vehicle | 仓库 wealook/vision_vehicle |
| c-290a555a | Starrynightzyq/Drone_Vehicle_Flow_Detection | 仓库 Starrynightzyq/Drone_Vehicle_Flow_Detection |
| c-a30f992e | aalmuzairee/CarlaDatasetCreator | 仓库 aalmuzairee/CarlaDatasetCreator |

#### long_tail (1)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-2bbd4779 | Deep-ii/Anomaly_Detection-On-ShanghaiTech-University | 仓库 Deep-ii/Anomaly_Detection-On-ShanghaiTech-University |

#### rejected (12)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-dad7329a | Joint vehicle state and parameters estimation via Twin-in-the-Loop observers | Joint 车辆 state and parameters estimation via Twin-in-the-Loop observers | Control/estimation paper, not a detection method paper. |
| c-5902bd56 | Learning Representation for Anomaly Detection of Vehicle Trajectories | Learning Representation for Anomaly 检测 of 车辆 Trajectories | Trajectory anomaly/representation paper, not detection. |
| c-ed33edfd | B-ETS: A Trusted Blockchain-based Emissions Trading System for Vehicle-to-Vehicle Networks | B-ETS: A Trusted Blockchain-based Emissions Trading System for 车辆-to-车辆 Networks | Blockchain/emissions trading paper, off-topic. |
| c-4fbb5e7a | Oriented object detection in optical remote sensing images using deep learning: a survey | Oriented 目标检测 in optical remote sensing images using 深度学习: a 综述 | Remote sensing oriented detection survey, off-domain. |
| c-44c09631 | AIn't Nothing But a Survey? Using Large Language Models for Coding German Open-Ended Survey Responses on Survey Motivati | AIn't Nothing But a 综述? Using Large Language Models for Coding German Open-Ended 综述 Responses on 综述 Motivati | NLP survey-coding paper, completely unrelated. |
| c-80036d11 | The Methanol Multibeam Survey | Methanol Multibeam 综述 | Astronomy radio survey, completely unrelated. |
| c-0a09cebf | Vehicle Logo Detection Using an Ioaverage Loss on Dataset Vld100k-61 Vehicle Logo Detection Using an Ioaverage Loss on D | 车辆 Logo 检测 Using an Ioaverage Loss on 数据集 Vld100k-61 车辆 Logo 检测 Using an Ioaverage Loss on D | Vehicle logo detection on Vld100k, not road-scene vehicle detection. |
| c-79e8b128 | Mix MSTAR: A Synthetic Benchmark Dataset for Multi-class Rotation Vehicle Detection in Large-Scale SAR Images | Mix MSTAR: A Synthetic 基准 数据集 for Multi-class Rotation 车辆 检测 in Large-Scale SAR Images | SAR image vehicle detection dataset, cross-domain (radar not optical). |
| c-114c469c | ArtifiVe-Potsdam: A Benchmark for Learning with Artificial Objects for Improved Aerial Vehicle Detection | ArtifiVe-Potsdam: A 基准 for Learning with Artificial Objects for Improved Aerial 车辆 检测 | Aerial vehicle detection benchmark, not ground road-scene detection. |
| c-1edb983b | EVD4UAV: An Altitude-Sensitive Benchmark to Evade Vehicle Detection in UAV | EVD4UAV: An Altitude-Sensitive 基准 to Evade 车辆 检测 in UAV | UAV altitude evasion benchmark, off-domain. |
| c-0d370650 | Time-Based CAN Intrusion Detection Benchmark | Time-Based CAN Intrusion 检测 基准 | CAN bus intrusion detection benchmark, unrelated. |
| c-a669463b | adampower48/AI-City-Anomaly-Detection | 仓库 adampower48/AI-City-Anomaly-Detection | Traffic anomaly detection (events), not visual object detection. |

#### dataset_and_repo_notes

> UA-DETRAC benchmark is the most relevant urban traffic dataset, anchored by c-fd4cb3f9 R-CNN paper and c-fd4cb3f9 benchmark URL.
> CARLA synthetic data from c-a30f992e useful for augmenting complex/rare road scenes beyond real footage.
> c-4b48a5af likely uses a custom multi-class vehicle dataset (Car/Bus/Truck/Bicycle/Motorcycle); verify exact source before reuse.
> c-2d75e0bd uses fisheye intersection imagery; ensure distortion handling is reproduced if borrowed.
> c-de61d041 (Faster R-CNN) and c-290a555a (YOLO3) are reference impl repos but older; treat as code skeleton only.
> c-e13e6fc7 is edge-device (RK3588/YOLOv6) deployment reference, useful only for inference-engineering discussion.

### §27 ENG-THESIS-066 — 《面向自动驾驶中多模态融合感知算法的攻击和防御》 — `weak`

| 维度 | 数值 |
|---|---:|
| batch | batch3 |
| elapsed | 237.0s |
| domain | 自动驾驶/交通感知 |
| paper | 37 |
| dataset | 0 |
| repo | 0 |
| baseline | 4 |
| parallel | 2 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-11078-1022519150.htm |

**direction_recommendation**: The topic targets adversarial attacks and defenses against multimodal fusion (LiDAR-camera-radar) perception in autonomous driving, but the current evidence pool contains zero core (status=core) items and no candidate directly addresses adversarial attack/defense on fusion perception. The strongest existing anchors are (a) c-4c94c77f — a 3D detection survey for autonomous driving providing the perception-fusion background, (b) c-bd2f52cc — IS-Fusion for multimodal 3D detection in BEV, (c) c-f0ccf87c — radar-camera fusion architecture for driving, and (d) c-3ede7464 — fusion architecture comparison under adverse weather (closest analog to robustness). Given the evidence gap on the adversarial axis, the recommended direction is to scaffold a survey-style or experimental thesis: (1) use c-4c94c77f as the baseline taxonomy of fusion perception methods to attack; (2) use c-bd2f52cc / c-f0ccf87c / c-f51080d8 as concrete fusion baselines to mount white-box and physical adversarial attacks against; (3) use c-3ede7464 as the robustness-by-design analog to motivate defense strategies. Before proceeding, the student must manually fill the adversarial literature (e.g., attacks on LiDAR, physic

#### core (0) (无)
#### baseline (4)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-4c94c77f | 3D Object Detection for Autonomous Driving: A Comprehensive Survey | 三维 目标检测 for 自动驾驶: A Comprehensive 综述 |
| c-bd2f52cc | IS-Fusion: Instance-Scene Collaborative Fusion for Multimodal 3D Object Detection | IS-Fusion: Instance-Scene Collaborative Fusion for Multimodal 三维 目标检测 |
| c-f0ccf87c | A Deep Learning-based Radar and Camera Sensor Fusion Architecture for Object Detection | 深度学习-based Radar and Camera Sensor Fusion Architecture for 目标检测 |
| c-3ede7464 | Optimal Sensor Data Fusion Architecture for Object Detection in Adverse Weather Conditions | Optimal Sensor Data Fusion Architecture for 目标检测 in Adverse Weather Conditions |

#### parallel (2)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-f51080d8 | Multimodal Sensor Fusion for Real-Time Object Detection | Multimodal Sensor Fusion for 实时 目标检测 |
| c-302162cd | PVAFN: Point-Voxel Attention Fusion Network with Multi-Pooling Enhancing for 3D Object Detection | PVAFN: Point-Voxel Attention Fusion Network with Multi-Pooling Enhancing for 三维 目标检测 |

#### reference (3)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-79c707ab | A Survey of Self-Supervised and Few-Shot Object Detection | 综述 of 自监督 and 少样本 目标检测 |
| c-d31cbf9d | ALFA: Agglomerative Late Fusion Algorithm for Object Detection | ALFA: Agglomerative Late Fusion Algorithm for 目标检测 |
| c-1cf93fb2 | amusi/awesome-object-detection | 仓库 amusi/awesome-object-detection |

#### long_tail (2)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-3f5ea7e1 | Deep learning-based efficient multimodal fusion for 3D object detection and motion estimation | 深度学习-based efficient multimodal fusion for 三维 目标检测 and motion estimation |
| c-4994f1f6 | YOLO-G3CF: Gaussian Contrastive Cross-Channel Fusion for Multimodal Object Detection | YOLO 实时目标检测-G3CF: Gaussian 对比学习 Cross-Channel Fusion for Multimodal 目标检测 |

#### rejected (20)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-e50137fe | Oriented object detection in optical remote sensing images using deep learning: a survey | Oriented 目标检测 in optical remote sensing images using 深度学习: a 综述 | Remote-sensing oriented object detection survey; cross-domain with no autonomous-driving or adversarial relevance. |
| c-a91f21a4 | Object Contour and Edge Detection with RefineContourNet | Object Contour and Edge 检测 with RefineContourNet | Edge/contour detection paper unrelated to topic's fusion or adversarial themes. |
| c-53e8ecb6 | AIn't Nothing But a Survey? Using Large Language Models for Coding German Open-Ended Survey Responses on Survey Motivati | AIn't Nothing But a 综述? Using Large Language Models for Coding German Open-Ended 综述 Responses on 综述 Motivati | Uses the word 'survey' but in NLP/survey methodology; cross-domain entirely. |
| c-478652e7 | Exploring Depth Contribution for Camouflaged Object Detection | Exploring Depth Contribution for Camouflaged 目标检测 | Camouflaged object detection in images; not driving-scene fusion or adversarial. |
| c-47e7b318 | Semantic-based Detection of Segment Outliers and Unusual Events for Wireless Sensor Networks | 语义-based 检测 of Segment Outliers and Unusual Events for Wireless Sensor Networks | Wireless sensor-network outlier detection; cross-domain. |
| c-2c48ef1a | A Survey on Multimodal Wearable Sensor-based Human Action Recognition | 综述 on Multimodal Wearable Sensor-based Human Action 识别 | Wearable sensor human action recognition survey; cross-domain. |
| c-190a1e58 | InMyFace: Inertial and Mechanomyography-Based Sensor Fusion for Wearable Facial Activity Recognition | InMyFace: Inertial and Mechanomyography-Based Sensor Fusion for Wearable Facial Activity 识别 | Wearable facial-activity recognition via IMU/mMG fusion; unrelated to driving. |
| c-74c1973f | rbgirshick/voc-dpm | 仓库 rbgirshick/voc-dpm | Legacy DPM detector code; pre-deep-learning, irrelevant. |
| c-24f1eb4f | Alpaca-zip/ultralytics_ros | 仓库 Alpaca-zip/ultralytics_ros | YOLOv8 ROS wrapper; camera-only detection, no fusion or adversarial context. |
| c-44f8f014 | chrisneagu/FTC-Skystone-Dark-Angels-Romania-2020 | 仓库 chrisneagu/FTC-Skystone-Dark-Angels-Romania-2020 | FTC robotics competition SDK repo; no relation to autonomous driving perception or adversarial ML. |
| c-91b49438 | Import project (Eclipse ADT, Gradle, etc.) | (中文含义由英文派生) | Metadata is a build-system error message, not a paper; cross-domain noise. |
| c-74170f49 | E RobotCore: lynx xmit lock: #### abandoning lock: | (中文含义由英文派生) | Log error message from robot SDK; not a paper and unrelated to topic. |
| c-435f58cc | Could not find com.android.tools.lint:lint-gradle:26.1.4 | (中文含义由英文派生) | Android Gradle dependency error; not a research paper and unrelated. |
| c-be1e5e5e | Version 3.00 (built on 17.04.013) | (中文含义由英文派生) | Generic version-string metadata; no paper content, no topical relevance. |
| c-9aeade6f | missing hardware leaves robot controller disconnected from driver station | missing hardware leaves 机器人 controller disconnected from driver station | Hardware troubleshooting note; unrelated to adversarial ML or driving perception. |
| c-8fb60e94 | fast tapping of Init/Start causes problems | (中文含义由英文派生) | SDK bug report; not a paper and unrelated to adversarial driving research. |
| c-dba9b4e4 | molyswu/hand_detection | 仓库 molyswu/hand_detection | Hand-detection repo with TF SSD; no multimodal, no adversarial, no driving context. |
| c-34016047 | Lending a hand: Detecting hands and recognizing activities in complex egocentric interactions. | (中文含义由英文派生) | Egocentric hand-activity recognition paper; no overlap with driving or adversarial topics. |
| c-06df23eb | >  ====== Hand Inference graph loaded. | > ====== Hand Inference graph loaded. | Code stdout snippet mislabeled as paper; unrelated to topic. |
| c-28be737a | python   detection_graph = tf.Graph()     with detection_graph.as_default():         od_graph_def = tf.GraphDef()        | python  detection_graph = tf.Graph()   with detection_graph.as_default():     od_graph_def = tf.GraphDef() | Misclassified Python code block; no paper content or topical relevance. |

#### dataset_and_repo_notes

> No autonomous-driving LiDAR-camera dataset (e.g., nuScenes, KITTI, Waymo) was returned by the search; student must supply one before any attack/defense experiments.
> The two datasets surfaced — ImageNet (c-b1587b2a) and Pascal VOC (c-82ed13f8) — are 2D RGB classification/detection only and were rejected as out-of-scope.
> c-1cf93fb2 (amusi/awesome-object-detection) is generic but may be mined in Re03 for pointers to adversarial-robust detection repos.

### §28 ENG-THESIS-072 — 《基于深度学习的动态SLAM研究》 — `pass`

| 维度 | 数值 |
|---|---:|
| batch | r5 |
| elapsed | 181.8s |
| domain | 三维视觉/SLAM/点云 |
| paper | 20 |
| dataset | 0 |
| repo | 3 |
| baseline | 2 |
| parallel | 6 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-10421-1022513120.htm |

**direction_recommendation**: Focus on deep-learning–driven SLAM that explicitly handles dynamic scenes, comparing canonical semantic dynamic SLAM (DS-SLAM, c-84f699c7) against ORB-SLAM2-based pipelines using semantic segmentation or object detection (DynaSLAM family — abstract missing from pool, treat as named anchor only). Use BPC-SLAM (c-6c2e7d38), REDO-SLAM (c-f62e729e), and the monocular deep-learning dynamic SLAM (c-af234913) as tier=core parallel methods; MLP-SLAM (c-3f68798c), DynoSAM (c-4e29ea98), VAR-SLAM (c-ef0b2f05) as deep/adjacent parallel methods. Evaluate on TUM RGB-D dynamic sequences and KITTI; consult Simulation of Dynamic Environments for SLAM (c-8993b089) and HRPSlam benchmark (c-2f21db80) for evaluation tooling. SLAM-Former (c-b6bfce20) and DRM-SLAM (c-54cc74b7) are secondary candidates; LIFT-SLAM (c-0ff0df71) needs manual check; the yichao-liang/dynamic_slam repo (c-3284a8f6) is a usable code resource.

#### core (7)

| cid | 原文 title | 中文含义 | reason |
|---|---|---|---|
| c-3f68798c | MLP-SLAM: Multilayer Perceptron-Based Simultaneous Localization and Mapping | (中文含义由英文派生) | MLP-based V-SLAM explicitly addressing dynamic object degradation; directly on-topic. |
| c-ef0b2f05 | VAR-SLAM: Visual Adaptive and Robust SLAM for Dynamic Environments | VAR-SLAM: Visual Adaptive and Robust SLAM for 动态 Environments | VAR-SLAM targets visual SLAM in dynamic environments with adaptive handling of moving objects. |
| c-4e29ea98 | DynoSAM: Open-Source Smoothing and Mapping Framework for Dynamic SLAM | DynoSAM: Open-Source Smoothing and Mapping Framework for 动态 SLAM | DynoSAM is a dynamic SLAM framework explicitly addressing dynamic scene elements. |
| c-84f699c7 | DS-SLAM: A Semantic Visual SLAM towards Dynamic Environments | DS-SLAM: A 语义 Visual SLAM towards 动态 Environments | DS-SLAM is one of the canonical semantic dynamic SLAM methods listed in the topic. |
| c-6c2e7d38 | BPC-SLAM: Part-Level Dynamic Suppression and Structure-Constrained RGB-D SLAM for Human-Centric Dynamic Environments | BPC-SLAM: Part-Level 动态 Suppression and Structure-Constrained RGB-D SLAM for Human-Centric 动态 Environments | BPC-SLAM targets indoor dynamic scenes with part-level suppression; highly relevant. |
| c-af234913 | A Monocular Dynamic SLAM Algorithm Based on Deep Learning | Monocular 动态 SLAM Algorithm Based on 深度学习 | Title explicitly states 'Monocular Dynamic SLAM Based on Deep Learning' — perfect match. |
| c-f62e729e | REDO-SLAM: Robust Efficient Dynamic Optical Flow-Based SLAM with Deep Reinforcement Learning | REDO-SLAM: Robust Efficient 动态 Optical Flow-Based SLAM with Deep Reinforcement Learning | REDO-SLAM explicitly uses deep reinforcement learning for dynamic SLAM. |

#### baseline (2)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-84f699c7 | DS-SLAM: A Semantic Visual SLAM towards Dynamic Environments | DS-SLAM: A 语义 Visual SLAM towards 动态 Environments |
| c-af234913 | A Monocular Dynamic SLAM Algorithm Based on Deep Learning | Monocular 动态 SLAM Algorithm Based on 深度学习 |

#### parallel (6)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-6c2e7d38 | BPC-SLAM: Part-Level Dynamic Suppression and Structure-Constrained RGB-D SLAM for Human-Centric Dynamic Environments | BPC-SLAM: Part-Level 动态 Suppression and Structure-Constrained RGB-D SLAM for Human-Centric 动态 Environments |
| c-f62e729e | REDO-SLAM: Robust Efficient Dynamic Optical Flow-Based SLAM with Deep Reinforcement Learning | REDO-SLAM: Robust Efficient 动态 Optical Flow-Based SLAM with Deep Reinforcement Learning |
| c-3f68798c | MLP-SLAM: Multilayer Perceptron-Based Simultaneous Localization and Mapping | (中文含义由英文派生) |
| c-4e29ea98 | DynoSAM: Open-Source Smoothing and Mapping Framework for Dynamic SLAM | DynoSAM: Open-Source Smoothing and Mapping Framework for 动态 SLAM |
| c-ef0b2f05 | VAR-SLAM: Visual Adaptive and Robust SLAM for Dynamic Environments | VAR-SLAM: Visual Adaptive and Robust SLAM for 动态 Environments |
| c-54cc74b7 | DRM-SLAM: Robust Visual SLAM Based on Dynamic Region Mask for Dynamic Scenes | DRM-SLAM: Robust Visual SLAM Based on 动态 Region Mask for 动态 Scenes |

#### reference (3)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-8993b089 | Simulation of Dynamic Environments for SLAM | Simulation of 动态 Environments for SLAM |
| c-2f21db80 | HRPSlam: A Benchmark for RGB-D Dynamic SLAM and Humanoid Vision | HRPSlam: A 基准 for RGB-D 动态 SLAM and Humanoid Vision |
| c-b6bfce20 | SLAM-Former: Putting SLAM into One Transformer | (中文含义由英文派生) |

#### long_tail (4)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-0ff0df71 | LIFT-SLAM | (中文含义由英文派生) |
| c-5869588c | Aczheng-cai/up_slam.github.io | 仓库 Aczheng-cai/up_slam.github.io |
| c-3284a8f6 | yichao-liang/dynamic_slam | 仓库 yichao-liang/dynamic_slam |
| c-ea63a6a0 | MAB1144/https-github.com-users-MAB1144-emails-94636098-confirm_verification-765d9142af1ea0fb3dd9dfdc374dfc | 仓库 MAB1144/https-github.com-users-MAB1144-emails-94636098-confirm_verification-765d9142af1ea0fb3dd9dfdc374dfc |

#### rejected (8)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-c7b30903 | Learn to Accumulate Evidence from All Training Samples: Theory and Practice | (中文含义由英文派生) | Evidential deep learning theory paper with no SLAM or robotics connection. |
| c-2e26d29e | The Modern Mathematics of Deep Learning | Modern Mathematics of 深度学习 | Mathematical theory of deep learning; no application or mention of SLAM. |
| c-027cb868 | Deep Learning and Computational Physics (Lecture Notes) | 深度学习 and Computational Physics (Lecture Notes) | Lecture notes on deep learning + computational physics; no SLAM topic. |
| c-bd35c471 | Deep learning observables in computational fluid dynamics | 深度学习 observables in computational fluid 动态 | CFD application of deep learning; completely outside robotics/SLAM. |
| c-e1b2196f | Monodense Deep Neural Model for Determining Item Price Elasticity | (中文含义由英文派生) | Economics/pricing paper; cross-domain, unrelated to robotics/SLAM. |
| c-b16e6093 | A multitask deep learning model for real-time deployment in embedded systems | 多任务 深度学习 model for 实时 deployment in 嵌入式 systems | Embedded multitask learning with no SLAM or dynamic scene content. |
| c-3b867281 | Generalized Regularized Evidential Deep Learning Models: Theory and Comprehensive Evaluation | Generalized Regularized Evidential 深度学习 Models: Theory and Comprehensive Evaluation | Another evidential deep learning theory paper; unrelated to SLAM. |
| c-cbe8d939 | AIn't Nothing But a Survey? Using Large Language Models for Coding German Open-Ended Survey Responses on Survey Motivati | AIn't Nothing But a 综述? Using Large Language Models for Coding German Open-Ended 综述 Responses on 综述 Motivati | NLP/LLM survey research paper; entirely cross-domain. |

#### dataset_and_repo_notes

> TUM RGB-D dynamic sequences (walking, sitting) remain the de facto benchmark for ATE/VIE evaluation of DS-SLAM (c-84f699c7) and BPC-SLAM (c-6c2e7d38).
> KITTI dynamic-tracking splits support outdoor dynamic-scene comparison for MLP-SLAM (c-3f68798c) and REDO-SLAM (c-f62e729e).
> c-2f21db80 HRPSlam provides a humanoid-focused RGB-D dynamic SLAM benchmark distinct from TUM/KITTI.
> c-8993b089 supplies photorealistic dynamic-scene simulation; useful when real datasets lack diverse moving actors.
> c-3284a8f6 is a lightweight simulation+algorithm repo that could seed re-implementations of DS-SLAM-class pipelines.

### §29 ENG-THESIS-073 — 《面向汽车自动驾驶的模拟图像生成技术及应用研究》 — `pass`

| 维度 | 数值 |
|---|---:|
| batch | r6 |
| elapsed | 233.4s |
| domain | 自动驾驶/交通感知 |
| paper | 23 |
| dataset | 3 |
| repo | 1 |
| baseline | 1 |
| parallel | 2 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-10183-1021100973.htm |

**direction_recommendation**: The current evidence pool has near-zero domain coverage of autonomous-driving image synthesis: no row mentions CARLA, NeRF driving, domain randomization, or driving-scene diffusion. The only item with concrete driving relevance is the Cityscapes real-image benchmark (c-1c38c3f9); the rest are medical/aerial/cross-domain papers or generic generative-model surveys. Strongly recommend a manual scoping gate before writing: confirm (a) modality scope (RGB camera-only vs multi-sensor), (b) downstream task (perception vs end-to-end driving), and (c) whether GAN-based sim-to-real style transfer, diffusion-based scene synthesis, or NeRF/world-model rendering is the primary axis. Only then re-run retrieval with driving-specific seeds (CARLA, Waymo Open, nuScenes, DrivingDiffusion, DriveGAN, GAIA-1, NeuRAD, UniSim). Existing candidates can only serve as background methods; do not treat any as baseline evidence for driving-specific claims.

#### core (0) (无)
#### baseline (1)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-1c38c3f9 | Cityscapes | (中文含义由英文派生) |

#### parallel (2)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-4f56d910 | Large-scale Simulated Dataset for Aerial Image Deblurring based on DOTA Dataset | Large-scale Simulated 数据集 for Aerial Image Deblurring based on DOTA 数据集 |
| c-c44ce341 | Asymmetric GAN for Unpaired Image-to-image Translation | (中文含义由英文派生) |

#### reference (4)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-b36d2623 | Text-to-image Diffusion Models in Generative AI: A Survey | Text-to-image 扩散模型 Models in Generative AI: A 综述 |
| c-016a650a | Personalized Image Generation with Deep Generative Models: A Decade Survey | Personalized Image Generation with Deep Generative Models: A Decade 综述 |
| c-d51b79de | Image Segmentation in Foundation Model Era: A Survey | Image 分割 in Foundation Model Era: A 综述 |
| c-db4b2bb9 | Data-Efficient GAN Training Beyond (Just) Augmentations: A Lottery Ticket Perspective | (中文含义由英文派生) |

#### long_tail (0) (无)
#### rejected (20)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-b37ddef5 | SCPAT-GAN: Structural Constrained and Pathology Aware Convolutional Transformer-GAN for Virtual Histology Staining of Hu | SCPAT-GAN: Structural Constrained and Pathology Aware 卷积 Transformer-GAN for Virtual Histology Staining of Hu | Medical OCT histology paper; cross-domain, no autonomous driving content. |
| c-00e15dc1 | DogLayout: Denoising Diffusion GAN for Discrete and Continuous Layout Generation | DogLayout: Denoising 扩散模型 GAN for Discrete and Continuous Layout Generation | Layout generation for graphic design; no driving or outdoor scene content. |
| c-83f28f73 | Sequential Attention GAN for Interactive Image Editing | (中文含义由英文派生) | Interactive image editing; unrelated to driving simulation. |
| c-f6d66383 | Recurrent Topic-Transition GAN for Visual Paragraph Generation | (中文含义由英文派生) | Visual paragraph caption generation; no relevance to driving synthesis. |
| c-c4736f52 | GAN-GA: A Generative Model based on Genetic Algorithm for Medical Image Generation | (中文含义由英文派生) | Medical image generation; cross-domain relative to driving. |
| c-cc5377d8 | Pathology-Aware Generative Adversarial Networks for Medical Image Augmentation | Pathology-Aware 生成对抗网络 GAN for Medical Image Augmentation | Pathology/medical augmentation paper; cross-domain. |
| c-e1ad293f | AIn't Nothing But a Survey? Using Large Language Models for Coding German Open-Ended Survey Responses on Survey Motivati | AIn't Nothing But a 综述? Using Large Language Models for Coding German Open-Ended 综述 Responses on 综述 Motivati | LLM survey methodology paper; no visual generative relevance. |
| c-00f5132f | Attention Mechanisms in Medical Image Segmentation: A Survey | Attention Mechanisms in Medical Image 分割: A 综述 | Medical segmentation survey; cross-domain relative to driving image synthesis. |
| c-3c7559d5 | The Methanol Multibeam Survey | Methanol Multibeam 综述 | Astronomical radio survey; no visual synthesis content. |
| c-e6852730 | A Generic Fundus Image Enhancement Network Boosted by Frequency Self-supervised Representation Learning | Generic Fundus Image Enhancement Network Boosted by Frequency 自监督 Representation Learning | Ophthalmic fundus enhancement; cross-domain. |
| c-0edd384e | VISION-GAN: Mask Conditioned U-Net GAN with Multi-Scale Auxiliary Supervision for Retinal Fundus Image Generation | (中文含义由英文派生) | Retinal fundus generation; abstract mismatch suggests possible metadata issue but domain is wrong. |
| c-f1d38081 | Semantic Response GAN (SR-GAN) for embroidery pattern generation | 语义 Response GAN (SR-GAN) for embroidery pattern generation | Embroidery pattern generation; no relevance to driving. |
| c-61ce7118 | Generation of realistic simulated B-mode image texture with a GAN | (中文含义由英文派生) | Ultrasound B-mode simulation; cross-domain medical imaging. |
| c-85b5d120 | Evaluating Text-to-Video Alignment: A Hierarchical Benchmark for Video Generation Models | Evaluating Text-to-Video Alignment: A Hierarchical 基准 for Video Generation Models | Text-to-video alignment benchmark; not driving-specific synthesis. |
| c-d34d9e9f | lhai36366/lhai36366 | 仓库 lhai36366/lhai36366 | Repo about WPF partial-trust security article, no relation to driving simulation or image generation. |
| c-e4697704 | I can write to local disk. | (中文含义由英文派生) | Title is a non-sensical phrase unrelated to the topic domain. |
| c-46a1ae3e | I can't write to local disk. | (中文含义由英文派生) | Title is a non-sensical phrase unrelated to the topic domain. |
| c-f141d355 | I can write to Isolated Storage | (中文含义由英文派生) | Title is a non-sensical phrase unrelated to the topic domain. |
| c-69c89bbe | ImageNet | (中文含义由英文派生) | General-purpose image classification dataset, not specific to driving scenes or sim-to-real. |
| c-dd9fc31f | DOTA | (中文含义由英文派生) | Aerial/satellite imagery dataset for object detection; cross-domain with respect to autonomous-driving camera scene synthesis. |

#### dataset_and_repo_notes

> Cityscapes (c-1c38c3f9) is real-image only; usable as evaluation target, not as synthetic-data resource.
> No CARLA, nuScenes, Waymo, KITTI, or driving-specific synthetic dataset was retrieved.
> No driving-image generation repo (e.g., DriveGAN, GAIA-1, NeuRAD, DrivingDiffusion) was retrieved in this round.

### §30 ENG-THESIS-074 — 《基于深度学习的混凝土桥梁裂缝检测研究》 — `pass`

| 维度 | 数值 |
|---|---:|
| batch | r1 |
| elapsed | 195.5s |
| domain | 土木/交通基础设施损伤检测 |
| paper | 24 |
| dataset | 1 |
| repo | 6 |
| baseline | 2 |
| parallel | 5 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-11510-1021822794.htm |

**direction_recommendation**: Final direction: a 2D vision pipeline for concrete-bridge surface crack detection, centered on lightweight improved YOLOv5 (object-detection, mobile-deployment friendly) as the primary baseline, with a pixel-level segmentation arm (U-Net/DeepLab family) as a complementary branch. Two strong core papers anchor the bridge-specific deep-learning context: the lightweight YOLOv5s-GTB bridge-crack detector (c-78f2b59c) and the YOLOv5-W real-time bridge-crack algorithm (c-635ae36b). A candidate pool of YOLOv5 infrastructure-crack variants (tunnel c-5255eb49, road c-6331c607/c-ad7b6238, runway c-9f36d402, freeway ViT-YOLOv5 c-8414feca) plus masonry CNN/transfer-learning methods (c-240c3bdc, c-17bcede3) supplies methodological baselines. Non-DL references — photogrammetry for reinforced-concrete bridges (c-ab0fccda) and classical image-processing on asphaltic concrete (c-54478846, c-bad3d600) — serve as comparison points. Survey background on oriented detection (c-78db9904) and the SHM capstone repo (c-dce2d6a4) provide supporting context. No dataset was successfully retrieved; benchmark/dataset sourcing is a priority follow-up (manual step).

#### core (2)

| cid | 原文 title | 中文含义 | reason |
|---|---|---|---|
| c-78f2b59c | YOLOv5s-GTB: light-weighted and improved YOLOv5s for bridge crack detection | YOLO 实时目标检测-GTB: light-weighted and improved YOLO 实时目标检测 for bridge 裂缝 检测 | Direct match: YOLOv5-based deep learning method specifically for bridge crack detection; highly aligned with topic. |
| c-635ae36b | YOLOv5-W Bridge Crack Real-Time Detection Algorithm | YOLO 实时目标检测-W Bridge 裂缝 实时 检测 Algorithm | Direct match: YOLOv5-based real-time bridge crack detection; strong task overlap. |

#### baseline (2)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-78f2b59c | YOLOv5s-GTB: light-weighted and improved YOLOv5s for bridge crack detection | YOLO 实时目标检测-GTB: light-weighted and improved YOLO 实时目标检测 for bridge 裂缝 检测 |
| c-635ae36b | YOLOv5-W Bridge Crack Real-Time Detection Algorithm | YOLO 实时目标检测-W Bridge 裂缝 实时 检测 Algorithm |

#### parallel (5)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-5255eb49 | Research on Tunnel Crack Detection Algorithm Based on Improved YOLOv5 | Research on Tunnel 裂缝 检测 Algorithm Based on Improved YOLO 实时目标检测 |
| c-6331c607 | Road Crack Defect Detection Based on Improved YOLOv5 | 道路 裂缝 缺陷 检测 Based on Improved YOLO 实时目标检测 |
| c-ad7b6238 | Road Crack Detection Algorithm Based on Improved YOLOV5 Model | 道路 裂缝 检测 Algorithm Based on Improved YOLO 实时目标检测 Model |
| c-8414feca | Research on Freeway Surface Crack Detection Based on Improved ViT-YOLOv5 | Research on Freeway Surface 裂缝 检测 Based on Improved Vision Transformer-YOLO 实时目标检测 |
| c-9f36d402 | Runway Crack Detection Based on YOLOV5 | Runway 裂缝 检测 Based on YOLO 实时目标检测 |

#### reference (4)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-78db9904 | Oriented object detection in optical remote sensing images using deep learning: a survey | Oriented 目标检测 in optical remote sensing images using 深度学习: a 综述 |
| c-ab0fccda | Smartphone-based photogrammetry for synthetic surface crack detection in reinforced concrete bridge structures | Smartphone-based photogrammetry for synthetic surface 裂缝 检测 in reinforced concrete bridge structures |
| c-54478846 | Crack detection on asphaltic concrete road surface images using modified grid cell analysis | 裂缝 检测 on asphaltic concrete 道路 surface images using modified grid cell analysis |
| c-bad3d600 | ankursingh4455/crack_detection_of_roads.github.io | 仓库 ankursingh4455/crack_detection_of_roads.github.io |

#### long_tail (4)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-240c3bdc | dimitrisdais/crack_detection_CNN_masonry | 仓库 dimitrisdais/crack_detection_CNN_masonry |
| c-17bcede3 | Automatic crack classification and segmentation on masonry surfaces using convolutional neural networks and transfer learning | Automatic 裂缝 分类 and 分割 on masonry surfaces using 卷积 神经网络 and 迁移学习 |
| c-dce2d6a4 | Ash08Thaty/Crack-Detection-for-Structural-Health-Monitoring-using-Deep-Learning | 仓库 Ash08Thaty/Crack-Detection-for-Structural-Health-Monitoring-using-Deep-Learning |
| c-e73f94a6 | antialopezg/Crack-detection-railway-axles-deep-learning | 仓库 antialopezg/Crack-detection-railway-axles-deep-learning |

#### rejected (15)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-3f119d44 | An interface crack in 1d piezoelectric quasicrystal under antiplane mechanical loading and electric field | interface 裂缝 in 1d piezoelectric quasicrystal under antiplane mechanical loading and electric field | Theoretical mechanics paper on piezoelectric quasicrystal cracks, not vision-based crack detection. |
| c-3487bd47 | How we can control the crack to propagate along the specified path feasibly? | How we can control the 裂缝 to propagate along the specified path feasibly? | Mechanics paper on controllable crack propagation; no image-based or deep-learning content. |
| c-dc0dcdc2 | Adversarial Attack On Yolov5 For Traffic And Road Sign Detection | Adversarial Attack On YOLO 实时目标检测 For Traffic And 道路 Sign 检测 | Adversarial attack study on YOLOv5 for traffic/road signs; domain mismatch with bridge cracks. |
| c-ca4864cf | YOLOv5 vs. YOLOv8 in Marine Fisheries: Balancing Class Detection and Instance Count | YOLO 实时目标检测 vs. YOLO 实时目标检测 in Marine Fisheries: Balancing Class 检测 and Instance Count | Marine fisheries detection comparison; cross-domain despite matching model names. |
| c-b83bfd8f | HIC-YOLOv5: Improved YOLOv5 For Small Object Detection | HIC-YOLO 实时目标检测: Improved YOLO 实时目标检测 For Small 目标检测 | Generic small-object detection YOLOv5 improvement; not tied to crack/bridge domain. |
| c-af340ca7 | UTD-Yolov5: A Real-time Underwater Targets Detection Method based on Attention Improved YOLOv5 | UTD-YOLO 实时目标检测: A 实时 Underwater Targets 检测 Method based on Attention Improved YOLO 实时目标检测 | Underwater target detection; cross-domain with respect to bridge surface cracks. |
| c-4ca1980f | Fire Detection From Image and Video Using YOLOv5 | Fire 检测 From Image and Video Using YOLO 实时目标检测 | Fire detection paper; lacks bridge/crack/object overlap despite shared model. |
| c-fe94de31 | AIn't Nothing But a Survey? Using Large Language Models for Coding German Open-Ended Survey Responses on Survey Motivati | AIn't Nothing But a 综述? Using Large Language Models for Coding German Open-Ended 综述 Responses on 综述 Motivati | LLM survey-coding paper; name collision only; no vision/crack content. |
| c-acea6c96 | The Methanol Multibeam Survey | Methanol Multibeam 综述 | Astronomy methanol maser survey; completely unrelated domain. |
| c-d9ff5d70 | IRSF/SIRIUS JHKs near-infrared variable star survey in the Magellanic Clouds | IRSF/SIRIUS JHKs near-infrared variable star 综述 in the Magellanic Clouds | Astronomy variable-star survey; cross-domain and unrelated. |
| c-b3ee04df | The SAMI Galaxy Survey: first 1000 galaxies | SAMI Galaxy 综述: first 1000 galaxies | Galaxy spectroscopy survey; astronomy domain unrelated to topic. |
| c-ee00527d | A rich bounty of AGN in the 9 square degree Bootes survey: high-z obscured AGN and large-scale structure | rich bounty of AGN (天文主动星系核，强噪声) in the 9 square degree Bootes 综述: high-z obscured AGN (天文主动星系核，强噪声) and large-scale structure | Obscured AGN astronomy survey; unrelated domain. |
| c-34a9237e | MGz-Staze/tools-Termux | 仓库 MGz-Staze/tools-Termux | Termux tools repository; no relation to crack detection or deep learning. |
| c-95186624 | Don-No7/Hack-SQL | 仓库 Don-No7/Hack-SQL | SQL injection toolkit repository; no relation to vision or crack detection. |
| c-b8e9ce87 | grep KoreLogicRules john.conf | cut -d: -f 2 | cut -d\] -f 1 | (中文含义由英文派生) | John the Ripper config file; metadata likely mislabeled as paper. |

#### dataset_and_repo_notes

> No crack dataset was returned by any adapter (core/openalex/huggingface all empty). Manually source SDNET2018, Crack500, DeepCrack, or a bridge-specific dataset before experiment design.
> c-78f2b59c (YOLOv5s-GTB) and c-635ae36b (YOLOv5-W) report bridge-crack training; obtain their datasets/code when available for fair comparison.
> c-240c3bdc / c-17bcede3 masonry repo provides a working CNN+transfer-learning segmentation pipeline that can be adapted to concrete-bridge images.
> c-dce2d6a4 SHM capstone (Jupyter, 4 stars) is low-quality but usable as a reference implementation; verify dataset license before reuse.

### §31 ENG-THESIS-075 — 《基于深度学习的混凝土路面裂缝检测研究》 — `pass`

| 维度 | 数值 |
|---|---:|
| batch | r1 |
| elapsed | 215.0s |
| domain | 土木/交通基础设施损伤检测 |
| paper | 19 |
| dataset | 0 |
| repo | 6 |
| baseline | 3 |
| parallel | 3 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-10292-1021724075.htm |

**direction_recommendation**: Evidence quality is weak. Only one arxiv item (c-a2eaf549) has an on-topic title ('Concrete Pavement Crack Detection and Classification Using Deep Convolutional Neural Network with Grid Search Optimization') but its abstract is an unrelated AGN/Bootes astronomy paper — a metadata mix-up that cannot be cited as confirmed evidence. All other candidates are either off-domain (theory, astronomy, intrusion detection, retail), method-mismatched (classical CV, masonry, railway axles, underwater, truffle), or unscored. No high-confidence core baseline exists in the current pool. Recommend pausing literature claiming and running a manual, scoping-tight retrieval (IEEE Xplore, ScienceDirect, MDPI Applied Sciences, ASCE Library) restricted to (concrete OR cement OR rigid pavement) AND (crack) AND (deep learning OR CNN OR U-Net OR YOLO). Use c-ba09135d / c-be4c661c as methodological references for CNN+transfer-learning crack pipelines, c-8f6fb17d as a benchmarking template for crack datasets, and c-a2eaf549 only after manual verification of the actual paper PDF. Do NOT lock a baseline until at least one verified on-topic paper is secured.

#### core (1)

| cid | 原文 title | 中文含义 | reason |
|---|---|---|---|
| c-a2eaf549 | Concrete Pavement Crack Detection and Classification Using Deep Convolutional Neural Network with Grid Search Optimizati | Concrete Pavement 裂缝 检测 and 分类 Using 深度残差卷积 神经网络 with Grid Search Optimizati | Title is a direct topic match, but abstract content describes AGN astrophysics — metadata mismatch. |

#### baseline (3)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-a2eaf549 | Concrete Pavement Crack Detection and Classification Using Deep Convolutional Neural Network with Grid Search Optimization | Concrete Pavement 裂缝 检测 and 分类 Using 深度残差卷积 神经网络 with Grid Search Optimization |
| c-be4c661c | Automatic crack classification and segmentation on masonry surfaces using convolutional neural networks and transfer learning | Automatic 裂缝 分类 and 分割 on masonry surfaces using 卷积 神经网络 and 迁移学习 |
| c-ba09135d | dimitrisdais/crack_detection_CNN_masonry | 仓库 dimitrisdais/crack_detection_CNN_masonry |

#### parallel (3)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-4688647b | Ash08Thaty/Crack-Detection-for-Structural-Health-Monitoring-using-Deep-Learning | 仓库 Ash08Thaty/Crack-Detection-for-Structural-Health-Monitoring-using-Deep-Learning |
| c-487fdd8c | antialopezg/Crack-detection-railway-axles-deep-learning | 仓库 antialopezg/Crack-detection-railway-axles-deep-learning |
| c-79d484e5 | ankursingh4455/crack_detection_of_roads.github.io | 仓库 ankursingh4455/crack_detection_of_roads.github.io |

#### reference (1)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-8f6fb17d | BB-UWCrack: A Benchmark Dataset for Bounding Box Crack Detection in Underwater Structures | BB-UWCrack: A 基准 数据集 for Bounding Box 裂缝 检测 in Underwater Structures |

#### long_tail (1)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-97e64cee | Automated Truffle Crack Detection Using Deep Learning and Machine Learning | Automated Truffle 裂缝 检测 Using 深度学习 and Machine Learning |

#### rejected (18)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-3ac1eeb2 | Learn to Accumulate Evidence from All Training Samples: Theory and Practice | (中文含义由英文派生) | Evidential deep learning theory paper; no relation to pavement cracks. |
| c-7a17597f | The Modern Mathematics of Deep Learning | Modern Mathematics of 深度学习 | Mathematical theory survey of deep learning; no applied vision content. |
| c-0ef6236b | Oriented object detection in optical remote sensing images using deep learning: a survey | Oriented 目标检测 in optical remote sensing images using 深度学习: a 综述 | Remote sensing oriented object detection survey; wrong domain. |
| c-ce5de9f9 | Deep Learning and Computational Physics (Lecture Notes) | 深度学习 and Computational Physics (Lecture Notes) | Lecture notes on deep learning + computational physics; irrelevant. |
| c-ddf51721 | A Hybrid Deep Learning Anomaly Detection Framework for Intrusion Detection | Hybrid 深度学习 Anomaly 检测 Framework for Intrusion 检测 | Cybersecurity intrusion detection; cross-domain. |
| c-648d5b19 | A multitask deep learning model for real-time deployment in embedded systems | 多任务 深度学习 model for 实时 deployment in 嵌入式 systems | Embedded MTL paper with no pavement/crack content. |
| c-99b15080 | Monodense Deep Neural Model for Determining Item Price Elasticity | (中文含义由英文派生) | Retail price elasticity paper; no vision or pavement content. |
| c-1b646cc2 | Deep learning observables in computational fluid dynamics | 深度学习 observables in computational fluid 动态 | CFD uncertainty quantification; irrelevant domain. |
| c-322bb6e6 | AIn't Nothing But a Survey? Using Large Language Models for Coding German Open-Ended Survey Responses on Survey Motivati | AIn't Nothing But a 综述? Using Large Language Models for Coding German Open-Ended 综述 Responses on 综述 Motivati | LLM survey coding paper; unrelated NLP/social science work. |
| c-1c99a71e | The Methanol Multibeam Survey | Methanol Multibeam 综述 | Radio astronomy methanol maser survey; no overlap. |
| c-f65a3a89 | IRSF/SIRIUS JHKs near-infrared variable star survey in the Magellanic Clouds | IRSF/SIRIUS JHKs near-infrared variable star 综述 in the Magellanic Clouds | Variable star survey in Magellanic Clouds; unrelated. |
| c-ff7b3e73 | An interface crack in 1d piezoelectric quasicrystal under antiplane mechanical loading and electric field | interface 裂缝 in 1d piezoelectric quasicrystal under antiplane mechanical loading and electric field | Piezoelectric quasicrystal interface crack mechanics; not vision/DL. |
| c-a1bff6d7 | The SAMI Galaxy Survey: first 1000 galaxies | SAMI Galaxy 综述: first 1000 galaxies | SAMI Galaxy Survey; astronomy, unrelated. |
| c-dbf9769a | VLP: A Survey on Vision-Language Pre-training | VLP: A 综述 on Vision-Language Pre-training | Vision-language pre-training survey; not pavement-related. |
| c-97e64cee | Automated Truffle Crack Detection Using Deep Learning and Machine Learning | Automated Truffle 裂缝 检测 Using 深度学习 and Machine Learning | Truffle crack detection in food QC; cross-domain. |
| c-c9db22b4 | MGz-Staze/tools-Termux | 仓库 MGz-Staze/tools-Termux | Termux Android tools repo; unrelated to crack detection. |
| c-c9fd8e99 | Don-No7/Hack-SQL | 仓库 Don-No7/Hack-SQL | Repo is a SQLite dump (Hack-SQL); no relation to crack detection or deep learning. |
| c-690e8cfc | grep KoreLogicRules john.conf | cut -d: -f 2 | cut -d\] -f 1 | (中文含义由英文派生) | Title is a shell grep command for john.conf; not a real paper. |

#### dataset_and_repo_notes

> c-8f6fb17d (BB-UWCrack) provides a reusable bounding-box annotation protocol transferable to a concrete-pavement benchmark, even though the imaged surface is underwater.
> c-ba09135d supplies a GPL-3.0 Python CNN pipeline (199 stars, active 2026) usable as a methodological code template for c-be4c661c.
> c-4688647b is a Jupyter notebook capstone (4 stars) with low maturity; treat as scaffolding only, not production code.
> c-487fdd8c (3 stars, profile-config repo) is essentially empty; ignore unless filled by the author.
> c-79d484e5 uses ORB/OpenCV classical features; do NOT cite as a deep-learning baseline despite the road-crack title.
> No verified concrete-pavement-specific dataset (e.g., SDNET2018, CrackForest, DeepCrack, CFD, GAPs384, PavementImageDataset) was retrieved in this round.

### §32 ENG-THESIS-079 — 《基于结构光的隧道裂缝检测技术研究与实现》 — `pass`

| 维度 | 数值 |
|---|---:|
| batch | r6 |
| elapsed | 201.4s |
| domain | 土木/交通基础设施损伤检测 |
| paper | 27 |
| dataset | 0 |
| repo | 6 |
| baseline | 3 |
| parallel | 4 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-10082-1022455761.htm |

**direction_recommendation**: Topic sits at the intersection of structured-light 3D acquisition and crack detection on tunnel lining surfaces. Evidence pool is thin: only one core paper (c-687f613b) directly joins structured light + deep-learning crack quantification on concrete; the remaining on-topic evidence is parallel (DL crack detection on masonry, pavement, railway) and no candidate covers tunnel-specific imaging or line-laser stripe extraction. The survey should therefore be a hybrid: (a) anchor the structured-light + DL pipeline on c-687f613b; (b) use parallel DL-crack and classical-CV works (c-67f0da11, c-5a1358f3, c-bfdfda4b, c-8f2634b2, c-a249e8b4, c-bff64e14, c-6c433e9b, c-16ef717f) as segmentation baselines and code references; (c) flag hardware/calibration and tunnel-lining imagery as gaps requiring manual search (CNKI, IEEE, ASCE). Scope the deliverable to a 2D vision pipeline (segmentation + crack width/profiling from laser stripe) rather than full SL rig design until the student clarifies hardware vs. software emphasis.

#### core (1)

| cid | 原文 title | 中文含义 | reason |
|---|---|---|---|
| c-687f613b | Concrete crack detection and quantification using deep learning and structured light | Concrete 裂缝 检测 and quantification using 深度学习 and structured light | Direct match: concrete crack detection with deep learning AND structured light. Strong baseline despite non-tunnel application. |

#### baseline (3)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-687f613b | Concrete crack detection and quantification using deep learning and structured light | Concrete 裂缝 检测 and quantification using 深度学习 and structured light |
| c-bfdfda4b | dimitrisdais/crack_detection_CNN_masonry | 仓库 dimitrisdais/crack_detection_CNN_masonry |
| c-8f2634b2 | Ash08Thaty/Crack-Detection-for-Structural-Health-Monitoring-using-Deep-Learning | 仓库 Ash08Thaty/Crack-Detection-for-Structural-Health-Monitoring-using-Deep-Learning |

#### parallel (4)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-67f0da11 | Sub-dataset Generation and Matching for Crack Detection on Brick Walls using Convolutional Neural Networks | Sub-数据集 Generation and Matching for 裂缝 检测 on Brick Walls using 卷积 神经网络 |
| c-5a1358f3 | Automatic crack classification and segmentation on masonry surfaces using convolutional neural networks and transfer learning | Automatic 裂缝 分类 and 分割 on masonry surfaces using 卷积 神经网络 and 迁移学习 |
| c-a249e8b4 | antialopezg/Crack-detection-railway-axles-deep-learning | 仓库 antialopezg/Crack-detection-railway-axles-deep-learning |
| c-6c433e9b | Deep Learning‐Based Crack Damage Detection Using Convolutional Neural Networks | 深度学习‐Based 裂缝 Damage 检测 Using 卷积 神经网络 |

#### reference (2)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-bff64e14 | SUT-Crack: A comprehensive dataset for pavement crack detection across all methods | SUT-裂缝: A comprehensive 数据集 for pavement 裂缝 检测 across all methods |
| c-16ef717f | ankursingh4455/crack_detection_of_roads.github.io | 仓库 ankursingh4455/crack_detection_of_roads.github.io |

#### long_tail (0) (无)
#### rejected (20)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-88be6044 | Topological Control of Chirality and Spin with Structured Light | (中文含义由英文派生) | Structured-light optics/physics paper; no tunnel, crack, or imaging task overlap. |
| c-f07ec084 | Stokes and skyrmion tensors and their application to structured light | (中文含义由英文派生) | Theoretical optics paper on Stokes/skyrmion tensors; no inspection or imaging application. |
| c-dc011b0e | Emulating a quantum Maxwell's demon with non-separable structured light | (中文含义由英文派生) | Quantum thermodynamics with structured light; cross-domain content. |
| c-4041da8a | Light-shift spectroscopy of optically trapped atomic ensembles | (中文含义由英文派生) | Cold-atom spectroscopy; no engineering inspection context. |
| c-ff4a46da | An interface crack in 1d piezoelectric quasicrystal under antiplane mechanical loading and electric field | interface 裂缝 in 1d piezoelectric quasicrystal under antiplane mechanical loading and electric field | Theoretical fracture mechanics of piezoelectric quasicrystals; no imaging or tunnel context. |
| c-237e9c70 | Dual-colour magic-wavelength trap for suppression of light shifts in atoms | (中文含义由英文派生) | Atomic physics optical trap paper; off-topic. |
| c-0618b593 | Spatial, spectral, temporal and polarisation resolved state tomography of light | (中文含义由英文派生) | Laser beam characterization tomography; off-topic. |
| c-e922b25d | How we can control the crack to propagate along the specified path feasibly? | How we can control the 裂缝 to propagate along the specified path feasibly? | Controllable crack propagation strategy; not image-based detection. |
| c-04729206 | Oriented object detection in optical remote sensing images using deep learning: a survey | Oriented 目标检测 in optical remote sensing images using 深度学习: a 综述 | Remote-sensing oriented object detection survey; cross-domain. |
| c-0ed8d265 | AIn't Nothing But a Survey? Using Large Language Models for Coding German Open-Ended Survey Responses on Survey Motivati | AIn't Nothing But a 综述? Using Large Language Models for Coding German Open-Ended 综述 Responses on 综述 Motivati | LLM survey-methodology paper; off-topic. |
| c-505aa3ea | The Methanol Multibeam Survey | Methanol Multibeam 综述 | Radio-astronomy methanol maser survey; off-topic. |
| c-dbc63d62 | IRSF/SIRIUS JHKs near-infrared variable star survey in the Magellanic Clouds | IRSF/SIRIUS JHKs near-infrared variable star 综述 in the Magellanic Clouds | NIR variable star survey; off-topic. |
| c-3e87844b | The SAMI Galaxy Survey: first 1000 galaxies | SAMI Galaxy 综述: first 1000 galaxies | Galaxy integral-field spectroscopic survey; off-topic. |
| c-3859aea9 | VLP: A Survey on Vision-Language Pre-training | VLP: A 综述 on Vision-Language Pre-training | Vision-language pre-training survey; cross-domain. |
| c-dc7a6a8f | MGz-Staze/tools-Termux | 仓库 MGz-Staze/tools-Termux | Termux tools repository; completely off-topic. |
| c-063e812b | Don-No7/Hack-SQL | 仓库 Don-No7/Hack-SQL | Repo description is an SQLite dump; no relation to crack detection or structured light. |
| c-d7130b76 | grep KoreLogicRules john.conf | cut -d: -f 2 | cut -d\] -f 1 | (中文含义由英文派生) | Title is a shell command; no scholarly content or topic relation. |
| c-92ce1547 | A finite element method for crack growth without remeshing | finite element method for 裂缝 growth without remeshing | FEM crack-growth mechanics paper; cross-domain for image-based detection topic. |
| c-70b9b881 | Analysis of crack formation and crack growth in concrete by means of fracture mechanics and finite elements | Analysis of 裂缝 formation and 裂缝 growth in concrete by means of fracture mechanics and finite elements | Concrete fracture mechanics paper, not detection; cross-domain relative to image-based topic. |
| c-42a924b7 | Elastic crack growth in finite elements with minimal remeshing | Elastic 裂缝 growth in finite elements with minimal remeshing | Elastic crack growth FEM paper; cross-domain vs. imaging/detection topic. |

#### dataset_and_repo_notes

> SUT-Crack (c-bff64e14) supplies pavement crack imagery; useful only as 2D detector benchmark, not tunnel lining or laser-stripe data.
> Brick-wall CNN dataset (c-67f0da11) provides 900 concrete micro-surface images; supports classification and binary crack segmentation.
> crack_detection_CNN_masonry repo (c-bfdfda4b) ships training scripts and pre-trained weights for masonry CNN segmentation.
> Railway-axle DL repo (c-a249e8b4) and SHM DL repo (c-8f2634b2) are code-pattern references for DL crack pipelines, not tunnel data.

### §33 ENG-THESIS-080 — 《基于三维重建裂缝损伤检测算法研究》 — `pass`

| 维度 | 数值 |
|---|---:|
| batch | r2 |
| elapsed | 308.2s |
| domain | 三维视觉/SLAM/点云 |
| paper | 17 |
| dataset | 1 |
| repo | 6 |
| baseline | 4 |
| parallel | 4 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-11078-1022517996.htm |

**direction_recommendation**: The topic targets vision-based 3D reconstruction (SfM/MVS/photogrammetry → point cloud) feeding crack damage detection on concrete/masonry civil infrastructure (facades, bridges, tunnels). The retrieved evidence splits cleanly into two halves with a critical gap at the join: (a) strong, modern SfM/3D reconstruction modules (Dense-SfM, Light3R-SfM, MASt3R-SfM, MP-SfM) usable as the reconstruction backbone, and (b) strong 2D CNN crack segmentation references (masonry CNN repo + paper) but ZERO direct work coupling 3D point clouds with crack/damage evaluation on civil structures. Recommend a hybrid pipeline: pick one modern SfM/MVS backbone (MASt3R-SfM or MP-SfM as baseline) to reconstruct surfaces, then lift a 2D crack segmentation model (e.g., dimitrisdais/crack_detection_CNN_masonry, c-b8fcadf0) onto point clouds via multi-view projection or train a point-cloud segmentation head on top. ETH3D (c-c106f4d1) supplies MVS/point-cloud ground truth for reconstruction benchmarking; for crack-specific 3D data the student will likely need to construct a small custom multi-view crack dataset (manual capture + SfM). Multiple human clarifications are required before coding can start.

#### core (0) (无)
#### baseline (4)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-83f43d30 | MASt3R-SfM: a Fully-Integrated Solution for Unconstrained Structure-from-Motion | (中文含义由英文派生) |
| c-10243d7d | MP-SfM: Monocular Surface Priors for Robust Structure-from-Motion | (中文含义由英文派生) |
| c-67c21c0e | dimitrisdais/crack_detection_CNN_masonry | 仓库 dimitrisdais/crack_detection_CNN_masonry |
| c-b8fcadf0 | Automatic crack classification and segmentation on masonry surfaces using convolutional neural networks and transfer learning | Automatic 裂缝 分类 and 分割 on masonry surfaces using 卷积 神经网络 and 迁移学习 |

#### parallel (4)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-b98f4cb0 | Dense-SfM: Structure from Motion with Dense Consistent Matching | (中文含义由英文派生) |
| c-69ac7818 | Light3R-SfM: Towards Feed-forward Structure-from-Motion | (中文含义由英文派生) |
| c-7bfa60d1 | SfM-TTR: Using Structure from Motion for Test-Time Refinement of Single-View Depth Networks | (中文含义由英文派生) |
| c-c106f4d1 | ETH3D | (中文含义由英文派生) |

#### reference (3)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-1ed5948d | Structure and Motion from Multiframes | (中文含义由英文派生) |
| c-dbd7951d | R3eVision: A Survey on Robust Rendering, Restoration, and Enhancement for 3D Low-Level Vision | R3eVision: A 综述 on Robust Rendering, Restoration, and Enhancement for 三维 Low-Level Vision |
| c-f78987b6 | Oriented object detection in optical remote sensing images using deep learning: a survey | Oriented 目标检测 in optical remote sensing images using 深度学习: a 综述 |

#### long_tail (2)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-da5b4571 | Ash08Thaty/Crack-Detection-for-Structural-Health-Monitoring-using-Deep-Learning | 仓库 Ash08Thaty/Crack-Detection-for-Structural-Health-Monitoring-using-Deep-Learning |
| c-8ac01d44 | antialopezg/Crack-detection-railway-axles-deep-learning | 仓库 antialopezg/Crack-detection-railway-axles-deep-learning |

#### rejected (11)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-58be4cdd | An interface crack in 1d piezoelectric quasicrystal under antiplane mechanical loading and electric field | interface 裂缝 in 1d piezoelectric quasicrystal under antiplane mechanical loading and electric field | Theoretical solid-mechanics crack study; cross-domain (piezoelectric materials) with no 3D reconstruction link. |
| c-eee4f676 | How we can control the crack to propagate along the specified path feasibly? | How we can control the 裂缝 to propagate along the specified path feasibly? | Controlled crack propagation in materials engineering; no imaging or 3D reconstruction. |
| c-6a561bd8 | AIn't Nothing But a Survey? Using Large Language Models for Coding German Open-Ended Survey Responses on Survey Motivati | AIn't Nothing But a 综述? Using Large Language Models for Coding German Open-Ended 综述 Responses on 综述 Motivati | LLM-based survey coding in social science; completely off-topic. |
| c-b312d996 | The Methanol Multibeam Survey | Methanol Multibeam 综述 | Radio-astronomy methanol survey; cross-domain and unrelated. |
| c-7bf03562 | IRSF/SIRIUS JHKs near-infrared variable star survey in the Magellanic Clouds | IRSF/SIRIUS JHKs near-infrared variable star 综述 in the Magellanic Clouds | Near-infrared variable-star survey in Magellanic Clouds; off-topic. |
| c-907459b7 | The SAMI Galaxy Survey: first 1000 galaxies | SAMI Galaxy 综述: first 1000 galaxies | Integral-field galaxy survey; completely unrelated domain. |
| c-e8716593 | Figure 3: Examples of pyramid assay fragment growth from the
                      <i>in-situ</i>
                       | Figure 3: Examples of pyramid assay fragment growth from the
           <i>in-situ</i> | AGN survey uses SfM only for sub-fragment analysis; not structural damage. |
| c-d49ee4e0 | MGz-Staze/tools-Termux | 仓库 MGz-Staze/tools-Termux | Termux hacking-tools repo; completely unrelated domain. |
| c-31a3cc6d | Don-No7/Hack-SQL | 仓库 Don-No7/Hack-SQL | SQL injection tool repo; cross-domain/off-topic. |
| c-fca1c5b0 | grep KoreLogicRules john.conf | cut -d: -f 2 | cut -d\] -f 1 | (中文含义由英文派生) | John-the-Ripper password cracking config; off-topic. |
| c-1445fe0f | ankursingh4455/crack_detection_of_roads.github.io | 仓库 ankursingh4455/crack_detection_of_roads.github.io | Road crack project uses ORB/CV on 2D images; no link to 3D reconstruction, MVS, SfM, or point clouds. |

#### dataset_and_repo_notes

> ETH3D (c-c106f4d1) provides MVS + LiDAR point-cloud ground truth suitable for reconstruction benchmarking, but no crack labels.
> c-67c21c0e is a runnable 2D CNN masonry crack repo (GPL-3.0, 199★) — strong upstream for the crack head but image-only.
> c-b8fcadf0 paper complements c-67c21c0e with the published CNN + transfer-learning crack method on masonry.
> c-da5b4571 and c-8ac01d44 need manual read-through to confirm 2D vs 3D before any reuse.
> No public multi-view crack damage benchmark was retrieved; custom capture or synthesis is likely required.

### §34 ENG-THESIS-083 — 《基于多分辨率网络的桥梁裂缝分割算法研究》 — `pass`

| 维度 | 数值 |
|---|---:|
| batch | r6 |
| elapsed | 246.4s |
| domain | 土木/交通基础设施损伤检测 |
| paper | 42 |
| dataset | 0 |
| repo | 6 |
| baseline | 5 |
| parallel | 5 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-10718-1021140421.htm |

**direction_recommendation**: Recommended direction: a multi-resolution encoder–decoder network for pixel-level bridge crack segmentation, integrating ASPP/atrous convolution, FPN-style multi-scale fusion, and deep supervision. Use dacl10k (c-0d2a8044) as primary benchmark and the concrete crack FCN encoder–decoder paper (c-83cc7650) as primary domain baseline, with pavement cracks (c-55e4e192) and StyleGAN/diffusion-augmented crack segmentation (c-b3eea2c3) as parallel comparators. Use DeepLab V3+ (c-e337cfa9), DeepLab V2 ASPP (c-39d8172f), and FCN (c-bbade6f6) as method references. Caveat: the corpus lacks a single canonical 'multi-resolution bridge crack' paper, so the proposal must be framed as a synthesis of multi-resolution/multi-scale segmentation ideas applied to bridge crack data. Confirm dataset/license before committing.

#### core (2)

| cid | 原文 title | 中文含义 | reason |
|---|---|---|---|
| c-83cc7650 | Image-Based Autonomous Concrete Crack Semantic Segmentation Using the Deep Fully Convolutional Encoder-Decoder Network f | Image-Based Autonomous Concrete 裂缝 语义 分割 Using the Deep Fully 卷积 Encoder-Decoder Network f | Direct match: concrete bridge crack segmentation using encoder-decoder FCN; core front-of-list candidate. |
| c-0d2a8044 | dacl10k: Benchmark for Semantic Bridge Damage Segmentation | dacl10k: 基准 for 语义 Bridge Damage 分割 | Directly relevant bridge damage segmentation benchmark; strong object match. |

#### baseline (5)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-83cc7650 | Image-Based Autonomous Concrete Crack Semantic Segmentation Using the Deep Fully Convolutional Encoder-Decoder Network for Bridge Inspection | Image-Based Autonomous Concrete 裂缝 语义 分割 Using the Deep Fully 卷积 Encoder-Decoder Network for Bridge Inspection |
| c-0d2a8044 | dacl10k: Benchmark for Semantic Bridge Damage Segmentation | dacl10k: 基准 for 语义 Bridge Damage 分割 |
| c-55e4e192 | Research on the application of semantic segmentation in pavement crack images | Research on the application of 语义 分割 in pavement 裂缝 images |
| c-e337cfa9 | Encoder-Decoder with Atrous Separable Convolution for Semantic Image Segmentation | Encoder-Decoder with Atrous Separable 卷积 for 语义 Image 分割 |
| c-39d8172f | Rethinking Atrous Convolution for Semantic Image Segmentation | Rethinking Atrous 卷积 for 语义 Image 分割 |

#### parallel (5)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-b3eea2c3 | On Enhancing Crack Semantic Segmentation Using StyleGAN and Brownian Bridge Diffusion | On Enhancing 裂缝 语义 分割 Using StyleGAN and Brownian Bridge 扩散模型 |
| c-854e5c78 | Semantic Segmentation Using Generative Knowledge Distillation for Crack Detection | 语义 分割 Using Generative Knowledge Distillation for 裂缝 检测 |
| c-f7f6dbb0 | Text-Enhanced Label-Efficient Automated Bridge Defect Semantic Segmentation from Inspection Images | Text-Enhanced Label-Efficient Automated Bridge 缺陷 语义 分割 from Inspection Images |
| c-344a0549 | SegNeXt: Rethinking Convolutional Attention Design for Semantic Segmentation | SegNeXt: Rethinking 卷积 Attention Design for 语义 分割 |
| c-ca6c4dca | SegFormer: Simple and Efficient Design for Semantic Segmentation with Transformers | SegFormer: Simple and Efficient Design for 语义 分割 with Transformer |

#### reference (7)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-e7817d7b | DeepLab: Semantic Image Segmentation with Deep Convolutional Nets, Atrous Convolution, and Fully Connected CRFs | DeepLab: 语义 Image 分割 with 深度残差卷积 Nets, Atrous 卷积, and Fully Connected CRFs |
| c-bbade6f6 | Fully convolutional networks for semantic segmentation | Fully 卷积 networks for 语义 分割 |
| c-57273cfc | Learning Deconvolution Network for Semantic Segmentation | Learning Deconvolution Network for 语义 分割 |
| c-caf1d926 | Rethinking Semantic Segmentation from a Sequence-to-Sequence Perspective with Transformers | Rethinking 语义 分割 from a Sequence-to-Sequence Perspective with Transformer |
| c-d7c56d95 | Image Segmentation in Foundation Model Era: A Survey | Image 分割 in Foundation Model Era: A 综述 |
| c-f3c65d38 | Jiankun-chen/building-semantic-segmentation-of-InSAR-images | 仓库 Jiankun-chen/building-semantic-segmentation-of-InSAR-images |
| c-86a1bfad | Crack Size Measurements on Fracture Surface Images Using Deep Neural Networks for Semantic Segmentation | 裂缝 Size Measurements on Fracture Surface Images Using Deep 神经网络 for 语义 分割 |

#### long_tail (5)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-008d09f0 | Multi-scale Network with Attentional Multi-resolution Fusion for Point Cloud Semantic Segmentation | Multi-scale Network with Attentional Multi-resolution Fusion for 点云 语义 分割 |
| c-ff130f27 | MBNet: A Multi-Resolution Branch Network for Semantic Segmentation Of Ultra-High Resolution Images | MBNet: A Multi-Resolution Branch Network for 语义 分割 Of Ultra-High Resolution Images |
| c-9d536430 | Multi-Resolution Learning and Semantic Edge Enhancement for Super-Resolution Semantic Segmentation of Urban Scene Images | Multi-Resolution Learning and 语义 Edge Enhancement for Super-Resolution 语义 分割 of Urban Scene Images |
| c-8e514374 | Reparameterizable Dual-Resolution Network for Real-Time Semantic Segmentation | Reparameterizable Dual-Resolution Network for 实时 语义 分割 |
| c-34f8b718 | A Novel Adaptive Deep Network for Building Footprint Segmentation | Novel Adaptive Deep Network for Building Footprint 分割 |

#### rejected (20)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-8e8e90b7 | 3D Kidneys and Kidney Tumor Semantic Segmentation using Boundary-Aware Networks | 三维 Kidneys and Kidney Tumor 语义 分割 using Boundary-Aware Networks | Medical imaging paper on kidney tumors; cross-domain with no relevance to bridge cracks. |
| c-1fe3c805 | Decoupling Continual Semantic Segmentation | Decoupling Continual 语义 分割 | Continual learning paper; not relevant to bridge crack segmentation. |
| c-3dcc4b87 | Unsupervised Semantic Segmentation by Contrasting Object Mask Proposals | 无监督 语义 分割 by Contrasting Object Mask Proposals | Unsupervised segmentation on natural images; unrelated to bridge crack task. |
| c-dbec4ab0 | 1st Place Solution of The Robust Vision Challenge 2022 Semantic Segmentation Track | 1st Place Solution of The Robust Vision Challenge 2022 语义 分割 Track | Challenge report on robust vision benchmark; no bridge/crack relevance. |
| c-e7fe7b19 | Solution for CVPR 2024 UG2+ Challenge Track on All Weather Semantic Segmentation | Solution for CVPR 2024 UG2+ Challenge Track on All Weather 语义 分割 | Adverse weather segmentation challenge; unrelated to bridge defects. |
| c-7918f4fb | LidarMultiNet: Unifying LiDAR Semantic Segmentation, 3D Object Detection, and Panoptic Segmentation in a Single Multi-ta | LidarMultiNet: Unifying 激光雷达 语义 分割, 三维 目标检测, and Panoptic 分割 in a Single Multi-ta | LiDAR-based autonomous driving paper; irrelevant to bridge crack images. |
| c-d0f9f714 | Efficient embedding network for 3D brain tumor segmentation | Efficient embedding network for 三维 brain tumor 分割 | Medical 3D brain tumor paper; cross-domain mismatch. |
| c-bb23a31e | Semantic Segmentation with GLCM Images | 语义 分割 with GLCM Images | GLCM-based segmentation; no connection to bridge crack or deep multi-resolution networks. |
| c-e236b97d | 4 BSP-Based Semantic Segmentation | 4 BSP-Based 语义 分割 | Aerial image segmentation via BSP; unrelated to bridge surface cracks. |
| c-f3903a70 | A Language-Guided Benchmark for Weakly Supervised Open Vocabulary Semantic Segmentation | Language-Guided 基准 for Weakly 有监督 Open Vocabulary 语义 分割 | Weakly supervised open-vocabulary benchmark; no bridge/crack relevance. |
| c-06a7a2bb | Automotive Corrosion Semantic Segmentation: A Benchmark Study of SegFormer and CNN-Based Models | Automotive Corrosion 语义 分割: A 基准 Study of SegFormer and CNN-Based Models | Automotive corrosion paper; wrong infrastructure domain (vehicles not bridges). |
| c-951e013e | Stsd：A Large-Scale Benchmark for Semantic Segmentation of Subway Tunnel Point Cloud | Stsd：A Large-Scale 基准 for 语义 分割 of Subway Tunnel 点云 | Subway tunnel point cloud segmentation; cross-domain (3D point cloud vs. 2D bridge crack images). |
| c-d21fa7b0 | SemanticRail3D - A Mobile LiDAR Benchmark for Semantic and Instance Segmentation of Railway Corridors | SemanticRail3D—A 移动 激光雷达 基准 for 语义 and Instance 分割 of Railway Corridors | Railway corridor LiDAR benchmark; wrong domain (rail, 3D LiDAR) for bridge crack 2D imagery. |
| c-d4bb1208 | MaSS13K: A Matting-level Semantic Segmentation Benchmark | MaSS13K: A Matting-level 语义 分割 基准 | General matting benchmark; no bridge/crack domain relevance. |
| c-0521ce1f | A Multi-Step Fusion Network for Semantic Segmentation of High-Resolution Aerial Images | Multi-Step Fusion Network for 语义 分割 of High-Resolution Aerial Images | Aerial remote sensing imagery; cross-domain vs. bridge surface crack segmentation. |
| c-9b272ca7 | HSTNet: An Iterative Optimization Network for Semantic Segmentation of High-Resolution Remote Sensing Images | HSTNet: An Iterative Optimization Network for 语义 分割 of High-Resolution Remote Sensing Images | Remote sensing imagery segmentation; wrong object domain. |
| c-c466173b | MAFMamba: A Multi-Scale Adaptive Fusion Network for Semantic Segmentation of High-Resolution Remote Sensing Images | MAFMamba: A Multi-Scale Adaptive Fusion Network for 语义 分割 of High-Resolution Remote Sensing Images | Remote sensing imagery; cross-domain vs. bridge surface cracks. |
| c-25853cfe | A benchmark for semantic image segmentation | 基准 for 语义 image 分割 | Old general segmentation benchmark; no relevance to bridge/crack domain. |
| c-cdc9a47e | How to Benchmark Vision Foundation Models for Semantic Segmentation? | How to 基准 Vision Foundation Models for 语义 分割? | Vision foundation model benchmark; no bridge/crack specific relevance. |
| c-a3ecbac7 | itsprakhar/Downstream-Dinov2 | 仓库 itsprakhar/Downstream-Dinov2 | DINOv2 downstream tasks repo; unrelated to bridge crack segmentation. |

#### dataset_and_repo_notes

> c-0d2a8044 (dacl10k) is the closest public bridge-damage segmentation benchmark; confirm license, label taxonomy, and crack-class availability before use.
> c-83cc7650 uses bridge inspection imagery with deep FCN encoder-decoder; obtain dataset split/metrics reported to enable faithful replication.
> c-55e4e192 covers pavement crack images (sibling domain) and may provide cross-domain transfer data.
> c-34f8b718 (building footprint) is a civil-infra-adjacent aerial dataset usable for pretraining or negative-class diversification.
> c-f3c65d38 repo bundles U-Net/PSPNet/DeepLab v3+ baselines usable as starting code for ASPP/multi-resolution ablation.

### §35 ENG-THESIS-089 — 《基于深度学习和双目立体视觉的道路路面损伤检测研究》 — `weak`

| 维度 | 数值 |
|---|---:|
| batch | r6 |
| elapsed | 184.2s |
| domain | 土木/交通基础设施损伤检测 |
| paper | 20 |
| dataset | 0 |
| repo | 0 |
| baseline | 5 |
| parallel | 6 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-10405-1021852190.htm |

**direction_recommendation**: The evidence pool is entirely monocular DL-for-pavement-distress literature; no binocular stereo, stereo matching, disparity, or depth-reconstruction paper survived review. Therefore this topic cannot be researched end-to-end from the current ledger. Recommended pivot: narrow the stereo dimension to a thin, defensible module (e.g., add a binocular/depth branch only for crack-depth or rut-depth quantification on a small stereo subset), while keeping the monocular DL detection/segmentation backbone as the primary contribution. Use the reviewed monocular papers as parallel baselines and the DL survey as background; treat the stereo component as a manually-verified literature gap requiring an additional targeted search round (KITTI / Middlebury / StereoCrack-style resources). Concrete path: (1) YOLOv8 + DeepLabv3 monocular backbone (c-6cec5f02, c-a0a613b8, c-3778a05d); (2) Crack segmentation refinement (c-a344f8b3, c-27ba34cc, c-7c20cc64, c-a8d4a73e, c-2f61bb5f); (3) Foundation-model extension (c-aa9e6c7c); (4) Benchmark/dataset (c-9e308f23); (5) Stereo / 3D-crack-depth module — needs manual retrieval.

#### core (0) (无)
#### baseline (5)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-6cec5f02 | Pavement Distress Detection and Segmentation using YOLOv4 and DeepLabv3 on Pavements in the Philippines | Pavement Distress 检测 and 分割 using YOLO 实时目标检测 and DeepLabv3 on Pavements in the Philippines |
| c-a0a613b8 | Pavement distress detection and classification based on YOLO network | Pavement distress 检测 and 分类 based on YOLO 实时目标检测 network |
| c-a344f8b3 | An Iteratively Optimized Patch Label Inference Network for Automatic Pavement Distress Detection | Iteratively Optimized Patch Label Inference Network for Automatic Pavement Distress 检测 |
| c-27ba34cc | Weakly Supervised Patch Label Inference Networks for Efficient Pavement Distress Detection and Recognition in the Wild | Weakly 有监督 Patch Label Inference Networks for Efficient Pavement Distress 检测 and 识别 in the Wild |
| c-7c20cc64 | A lightweight encoder–decoder network for automatic pavement crack detection | 轻量化 encoder–decoder network for automatic pavement 裂缝 检测 |

#### parallel (6)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-3778a05d | Advancing Pavement Distress Detection in Developing Countries: A Novel Deep Learning Approach with Locally-Collected Datasets | Advancing Pavement Distress 检测 in Developing Countries: A Novel 深度学习 Approach with Locally-Collected Datasets |
| c-4164ccea | Deep Learning Frameworks for Pavement Distress Classification: A Comparative Analysis | 深度学习 Frameworks for Pavement Distress 分类: A Comparative Analysis |
| c-89ba69a4 | PicT: A Slim Weakly Supervised Vision Transformer for Pavement Distress Classification | PicT: A Slim Weakly 有监督 Vision Transformer for Pavement Distress 分类 |
| c-2f61bb5f | Feature Pyramid and Hierarchical Boosting Network for Pavement Crack Detection | Feature Pyramid and Hierarchical Boosting Network for Pavement 裂缝 检测 |
| c-a8d4a73e | Multiscale Attention Networks for Pavement Defect Detection | Multiscale Attention Networks for Pavement 缺陷 检测 |
| c-aa9e6c7c | PaveSAM Segment Anything for Pavement Distress | (中文含义由英文派生) |

#### reference (3)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-b01d4067 | Deep Learning Approaches in Pavement Distress Identification: A Review | 深度学习 Approaches in Pavement Distress Identification: A Review |
| c-9e308f23 | Pavement Image Datasets: A New Benchmark Dataset to Classify and Densify Pavement Distresses | Pavement Image Datasets: A New 基准 数据集 to Classify and Densify Pavement Distresses |
| c-788ad17d | Oriented object detection in optical remote sensing images using deep learning: a survey | Oriented 目标检测 in optical remote sensing images using 深度学习: a 综述 |

#### long_tail (0) (无)
#### rejected (6)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-7c53acee | Learn to Accumulate Evidence from All Training Samples: Theory and Practice | (中文含义由英文派生) | General evidential deep learning theory; no pavement or vision-3D relevance. |
| c-389c3e4f | The Modern Mathematics of Deep Learning | Modern Mathematics of 深度学习 | Pure mathematical theory paper; no applied road-vision relevance. |
| c-2d49312f | Use of recycled aggregates in concrete pavement: Pavement design and life cycle assessment | (中文含义由英文派生) | Concrete pavement materials study; civil engineering, not computer vision. |
| c-0620b903 | Pavement Analysis and Design | (中文含义由英文派生) | Classical pavement engineering textbook; no vision/ML content. |
| c-b098ee0a | Overview and Discussion of Pavement Performance Prediction Techniques for Maintenance and Rehabilitation Decision-Making | (中文含义由英文派生) | Pavement performance prediction; civil engineering, not computer vision. |
| c-68211878 | Sustainable use of reclaimed asphalt pavement (RAP) in pavement applications—a review | (中文含义由英文派生) | RAP materials review; civil engineering materials, not computer vision. |

#### dataset_and_repo_notes

> c-9e308f23 Pavement Image Datasets benchmark is monocular; verify whether it includes stereo pairs or depth before reuse, otherwise supplement with KITTI/Middlebury-style stereo data.
> No GitHub repo surfaced; OpenReview/manual search needed for stereo-crack-depth datasets and code.
> Existing reviews (c-b01d4067) cover DL only — must independently validate any stereo-3D-crack claim.

### §36 ENG-THESIS-091 — 《基于云计算的输电线路缺陷检测平台》 — `weak`

| 维度 | 数值 |
|---|---:|
| batch | r2 |
| elapsed | 205.9s |
| domain | 电力/轨交巡检视觉 |
| paper | 20 |
| dataset | 0 |
| repo | 0 |
| baseline | 4 |
| parallel | 2 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-10710-1021889314.htm |

**direction_recommendation**: The candidate pool is sparse and dominated by off-topic or cross-domain rejections (wildfire risk, undergrounding, manufacturing defects, LLM survey coding, astronomy). The two on-topic core papers are tightly aligned: c-45c2423c (Cloud-Edge-End collaboration system) and c-b01129ec (insulator defect dataset/benchmarks). Parallel candidates cover YOLOv10 insulator detection (c-620a6cd8), CNN-BiGRU edge deployment (c-848a634e), cascade reasoning multi-fitting (c-da5fd351), and pin defect detection (c-3ed055cf). One suspicious record c-0541a7a2 has a likely title/abstract mismatch (cosmic rays) and should be manually verified. Recommend scoping the survey around an edge-cloud collaborative inspection platform for UAV/surveillance imagery, using YOLO-family detectors with insulators as the primary defect class. Cloud papers (c-8e4a29e9, c-7ceb29fe) are generic — usable only as architectural background. The reviewer should request human clarification on (a) cloud-platform vs. algorithm emphasis, (b) defect scope, (c) imagery source. Major limitation: zero strong 'cloud-only' references and several false-positive seeds.

#### core (2)

| cid | 原文 title | 中文含义 | reason |
|---|---|---|---|
| c-b01129ec | Towards Defect Detection of Transmission Line Insulator: A Dataset, Benchmarks and Challenges | Towards 缺陷 检测 of Transmission Line 绝缘子: A 数据集, Benchmarks and Challenges | Insulator defect dataset with benchmarks, directly relevant to defect detection task. |
| c-45c2423c | Research on Transmission Line Defect Detection System Based on Cloud-Edge-End Collaboration | Research on Transmission Line 缺陷 检测 System Based on Cloud-Edge-End Collaboration | Cloud-edge-end collaboration defect detection system — strong match to topic. |

#### baseline (4)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-45c2423c | Research on Transmission Line Defect Detection System Based on Cloud-Edge-End Collaboration | Research on Transmission Line 缺陷 检测 System Based on Cloud-Edge-End Collaboration |
| c-b01129ec | Towards Defect Detection of Transmission Line Insulator: A Dataset, Benchmarks and Challenges | Towards 缺陷 检测 of Transmission Line 绝缘子: A 数据集, Benchmarks and Challenges |
| c-620a6cd8 | Detection of Transmission Line Insulator Defect Based on Improved YOLOv10 | 检测 of Transmission Line 绝缘子 缺陷 Based on Improved YOLOv10 |
| c-848a634e | A CNN-Bigru-Based Defect Detection Method for Transmission Line Insulators in Edge Computing Environment | CNN-Bigru-Based 缺陷 检测 Method for Transmission Line 绝缘子 in Edge Computing Environment |

#### parallel (2)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-da5fd351 | Multi-Fitting Detection on Transmission Line Based on Cascade Reasoning Graph Network | Multi-Fitting 检测 on Transmission Line Based on Cascade Reasoning Graph Network |
| c-3ed055cf | Research on Pin Defect Detection Algorithm of Power Transmission Line | Research on Pin 缺陷 检测 Algorithm of Power Transmission Line |

#### reference (3)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-1ff2677b | Oriented object detection in optical remote sensing images using deep learning: a survey | Oriented 目标检测 in optical remote sensing images using 深度学习: a 综述 |
| c-8e4a29e9 | A Comparative Study of Load Balancing Algorithms in Cloud Computing Environment | Comparative Study of Load Balancing Algorithms in Cloud Computing Environment |
| c-7ceb29fe | Supporting Multi-Cloud in Serverless Computing | (中文含义由英文派生) |

#### long_tail (1)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-0541a7a2 | TLDRT-DETR: Adaptive Upsampling and Dual-Activation Attention for Real-Time Transmission Line Defect Detection | TLDRT-DETR 目标检测: Adaptive Upsampling and Dual-Activation Attention for 实时 Transmission Line 缺陷 检测 |

#### rejected (10)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-4ba24478 | A Framework for Risk Assessment and Optimal Line Upgrade Selection to Mitigate Wildfire Risk | Framework for Risk Assessment and Optimal Line Upgrade Selection to Mitigate Wildfire Risk | Focuses on wildfire risk mitigation and line upgrade planning, not visual defect detection. |
| c-8627719f | Co-optimization of power line shutoff and restoration under high wildfire ignition risk | (中文含义由英文派生) | Operational optimization for shutoff/restoration, not visual inspection. |
| c-b90998f8 | DeepInspect: An AI-Powered Defect Detection for Manufacturing Industries | DeepInspect: An AI-Powered 缺陷 检测 for Manufacturing Industries | Manufacturing defect detection, not power line infrastructure. |
| c-556a1a3b | AIn't Nothing But a Survey? Using Large Language Models for Coding German Open-Ended Survey Responses on Survey Motivati | AIn't Nothing But a 综述? Using Large Language Models for Coding German Open-Ended 综述 Responses on 综述 Motivati | LLM-based survey coding, completely off-topic. |
| c-e533c06f | Enabling Undergrounding of Long-Distance Transmission Lines with Low Frequency AC Technology | (中文含义由英文派生) | Undergrounding engineering study, not visual inspection. |
| c-276ae0f7 | The Methanol Multibeam Survey | Methanol Multibeam 综述 | Astronomy radio survey, entirely off-topic. |
| c-5cfaf40f | Framework for cloud computing adoption: A road map for Smes to cloud migration | Framework for cloud computing adoption: A 道路 map for Smes to cloud migration | SME cloud migration roadmap, off-topic domain. |
| c-30d819d9 | Application of Selective Algorithm for Effective Resource Provisioning in Cloud Computing Environment | (中文含义由英文派生) | General cloud resource provisioning, unrelated to defect detection. |
| c-b3f4a0e4 | Phoenix Cloud: Consolidating Different Computing Loads on Shared Cluster System for Large Organization | (中文含义由英文派生) | Cluster consolidation system, not inspection related. |
| c-1f2b29a7 | Scheduling and Checkpointing optimization algorithm for Byzantine fault tolerance in Cloud Clusters | (中文含义由英文派生) | Byzantine fault tolerance in cloud clusters, not visual inspection. |

#### dataset_and_repo_notes

> c-b01129ec provides a transmission line insulator defect dataset and benchmarks — primary dataset reference.
> No GitHub repository with implementation was returned by any adapter; code availability must be re-checked by the student.
> c-620a6cd8 (YOLOv10) and c-848a634e (CNN-BiGRU) likely include baseline numbers on related insulator datasets — usable as benchmark anchors.

### §37 ENG-THESIS-092 — 《海上风机叶片缺陷检测及分类》 — `pass`

| 维度 | 数值 |
|---|---:|
| batch | r2 |
| elapsed | 192.3s |
| domain | 能源装备/故障诊断 |
| paper | 17 |
| dataset | 3 |
| repo | 6 |
| baseline | 2 |
| parallel | 7 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-10214-1022041753.htm |

**direction_recommendation**: Target: offshore wind turbine blade surface defect detection AND classification using 2D vision, with drone/UAV-captured imagery as the primary input modality. Build on the only two domain-matched YOLO baselines found (c-cc97040c Blade-YOLOv8, c-d0274723 GCB-YOLO) as core references; treat industrial surface defect detection methods (c-0cd7cdb0 HyperDefect-YOLO, c-e532da02 YOLO metal sheets, c-321adf72 TransferD2) and CNN defect surveys (c-a3cbe272 road surface survey, c-477c8a0a DeepInspect) as transferable parallel evidence. Use NEU-DET and COCO/DOTA as pretraining/transfer sources; treat wafer/semiconductor and astronomy refs as noise. Open question: offshore-specific labeled datasets are absent from the retrieved evidence, so a hybrid pipeline (domain-adjacent pretraining -> blade-specific fine-tuning) is recommended.

#### core (2)

| cid | 原文 title | 中文含义 | reason |
|---|---|---|---|
| c-cc97040c | Blade-YOLOv8:Improved YOLOv8 for Wind Turbine Blade Defect Detection | Blade-YOLO 实时目标检测:Improved YOLO 实时目标检测 for Wind Turbine Blade 缺陷 检测 | Direct YOLOv8-based wind turbine blade defect detection baseline; strong match. |
| c-d0274723 | GCB-YOLO: A Lightweight Algorithm for Wind Turbine Blade Defect Detection | GCB-YOLO 实时目标检测: A 轻量化 Algorithm for Wind Turbine Blade 缺陷 检测 | Lightweight YOLO for wind turbine blade defects; parallel core method. |

#### baseline (2)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-cc97040c | Blade-YOLOv8:Improved YOLOv8 for Wind Turbine Blade Defect Detection | Blade-YOLO 实时目标检测:Improved YOLO 实时目标检测 for Wind Turbine Blade 缺陷 检测 |
| c-d0274723 | GCB-YOLO: A Lightweight Algorithm for Wind Turbine Blade Defect Detection | GCB-YOLO 实时目标检测: A 轻量化 Algorithm for Wind Turbine Blade 缺陷 检测 |

#### parallel (7)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-0cd7cdb0 | HyperDefect-YOLO: Enhance YOLO with HyperGraph Computation for Industrial Defect Detection | HyperDefect-YOLO 实时目标检测: Enhance YOLO 实时目标检测 with HyperGraph Computation for Industrial 缺陷 检测 |
| c-e532da02 | YOLO-Based Defect Detection for Metal Sheets | YOLO 实时目标检测-Based 缺陷 检测 for Metal Sheets |
| c-321adf72 | TransferD2: Automated Defect Detection Approach in Smart Manufacturing using Transfer Learning Techniques | TransferD2: Automated 缺陷 检测 Approach in Smart Manufacturing using 迁移学习 Techniques |
| c-a3cbe272 | Road Surface Defect Detection -- From Image-based to Non-image-based: A Survey | 道路 Surface 缺陷 检测 -- From Image-based to Non-image-based: A 综述 |
| c-477c8a0a | DeepInspect: An AI-Powered Defect Detection for Manufacturing Industries | DeepInspect: An AI-Powered 缺陷 检测 for Manufacturing Industries |
| c-02c71bfe | xuchuanleikeshi/Sealing-Pin-Defect-Detection.github.io | 仓库 xuchuanleikeshi/Sealing-Pin-Defect-Detection.github.io |
| c-20d75bba | sbetageri/pt_steel | 仓库 sbetageri/pt_steel |

#### reference (6)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-d95d9131 | DAMO-YOLO : A Report on Real-Time Object Detection Design | DAMO-YOLO 实时目标检测 : A Report on 实时 目标检测 Design |
| c-c40537ec | YOLO-IOD: Towards Real Time Incremental Object Detection | YOLO 实时目标检测-IOD: Towards 实时 Incremental 目标检测 |
| c-51d23364 | MS-YOLO: Infrared Object Detection for Edge Deployment via MobileNetV4 and SlideLoss | MS-YOLO 实时目标检测: Infrared 目标检测 for Edge Deployment via MobileNetV4 and SlideLoss |
| c-73ce6f58 | YOLO-World: Real-Time Open-Vocabulary Object Detection | YOLO 实时目标检测-World: 实时 Open-Vocabulary 目标检测 |
| c-6986718d | SDD-YOLO/.github | 仓库 SDD-YOLO/.github |
| c-a1f7d536 | A New Benchmark Dataset for Texture Image Analysis and Surface Defect Detection | New 基准 数据集 for Texture Image Analysis and Surface 缺陷 检测 |

#### long_tail (4)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-af907b2d | NEU-DET | (中文含义由英文派生) |
| c-eba4bbec | DOTA | (中文含义由英文派生) |
| c-2786fb27 | COCO | (中文含义由英文派生) |
| c-05053441 | TheWangYang/vue_admin_system_github | 仓库 TheWangYang/vue_admin_system_github |

#### rejected (7)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-b9d71c0a | YOLO-CL: Galaxy cluster detection in the SDSS with deep machine learning | YOLO 实时目标检测-CL: Galaxy cluster 检测 in the SDSS with deep machine learning | Astrophysics application of YOLO; cross-domain, no overlap with blade inspection. |
| c-ce7ce182 | Oriented object detection in optical remote sensing images using deep learning: a survey | Oriented 目标检测 in optical remote sensing images using 深度学习: a 综述 | Remote sensing oriented-object survey; cross-domain from blade inspection. |
| c-d4f34a54 | AIn't Nothing But a Survey? Using Large Language Models for Coding German Open-Ended Survey Responses on Survey Motivati | AIn't Nothing But a 综述? Using Large Language Models for Coding German Open-Ended 综述 Responses on 综述 Motivati | LLM-based survey response classification; entirely off-topic. |
| c-730dd60d | The Methanol Multibeam Survey | Methanol Multibeam 综述 | Radio astronomy methanol maser survey; no relevance. |
| c-890edc51 | A rich bounty of AGN in the 9 square degree Bootes survey: high-z obscured AGN and large-scale structure | rich bounty of AGN (天文主动星系核，强噪声) in the 9 square degree Bootes 综述: high-z obscured AGN (天文主动星系核，强噪声) and large-scale structure | Astrophysical AGN survey; cross-domain and irrelevant. |
| c-69e67ca2 | Waferguard/waferguard-ml | 仓库 Waferguard/waferguard-ml | Semiconductor wafer defect detection — completely different domain from wind turbine blades. |
| c-df9e6883 | sgravan107/Wafer-Defect-Detection | 仓库 sgravan107/Wafer-Defect-Detection | Semiconductor wafer defect repo; cross-domain, no relevance to wind turbine blades. |

#### dataset_and_repo_notes

> No offshore-specific blade defect dataset was retrieved; NEU-DET (c-af907b2d) is the most defensible pretraining/transfer source for surface defects.
> DOTA (c-eba4bbec) and COCO (c-2786fb27) are useful only for drone-pretraining and CNN backbone warmup, not for defect labels.
> c-cc97040c (Blade-YOLOv8) and c-d0274723 (GCB-YOLO) are the only two blades-specific YOLO baselines and should anchor the experiments.
> c-02c71bfe provides a runnable YOLO+UNet segmentation pipeline (sealing pins), useful as a code template, not as data.
> c-20d75bba (steel defect TF repo) is a small but runnable pipeline suitable for transfer-learning sanity checks.
> c-6986718d (SDD-YOLO) is a generic defect framework; only its pipeline is transferable.
> c-05053441 needs manual check: no evidence in title/description that it targets wind turbine blades.

### §38 ENG-THESIS-093 — 《基于深度学习的接触网绝缘子表面缺陷图像式检测方法研究》 — `pass`

| 维度 | 数值 |
|---|---:|
| batch | r2 |
| elapsed | 183.8s |
| domain | 电力/轨交巡检视觉 |
| paper | 15 |
| dataset | 3 |
| repo | 1 |
| baseline | 4 |
| parallel | 4 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-10732-1021137766.htm |

**direction_recommendation**: Deep-learning image-based detection of surface defects on railway catenary (overhead contact line) insulators, framed as a 2D vision object-detection problem with optional semantic-segmentation refinement. No EvidenceReview row is a confirmed catenary-insulator paper, so the recommendation is built around tiered borrowings: (a) YOLO-family detectors (DAMO-YOLO, HyperDefect-YOLO, MS-YOLO, YOLO-IOD) as baseline or enhanced backbones; (b) Faster R-CNN / incremental-detection literature as comparison; (c) NEU-DET, PCB-defect, and pear/stone surface-defect datasets as cross-domain pretraining and transferable benchmarks; (d) COCO/DOTA for backbone pretraining given oriented/small-object trackside imagery. Recent road-surface-defect survey supplies a transferable taxonomy. Critical scoping risk: a verified catenary-insulator-specific dataset/benchmark was NOT retrieved; the student must acquire or self-collect trackside insulator imagery before modeling claims are conclusive. Proceed as: pretrain on COCO/DOTA, baseline with a YOLOv8/DAMO-YOLO detector, add a defect-aware head inspired by HyperDefect-YOLO, and benchmark transfer on NEU-DET/PCB-defect as a proxy until catenary data is secu

#### core (0) (无)
#### baseline (4)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-868a89f5 | DAMO-YOLO : A Report on Real-Time Object Detection Design | DAMO-YOLO 实时目标检测 : A Report on 实时 目标检测 Design |
| c-5af8d4a8 | HyperDefect-YOLO: Enhance YOLO with HyperGraph Computation for Industrial Defect Detection | HyperDefect-YOLO 实时目标检测: Enhance YOLO 实时目标检测 with HyperGraph Computation for Industrial 缺陷 检测 |
| c-de07f41f | MS-YOLO: Infrared Object Detection for Edge Deployment via MobileNetV4 and SlideLoss | MS-YOLO 实时目标检测: Infrared 目标检测 for Edge Deployment via MobileNetV4 and SlideLoss |
| c-6b4164c5 | YOLOPears: a novel benchmark of YOLO object detectors for multi-class pear surface defect detection in quality grading systems | YOLOPears: a novel 基准 of YOLO 实时目标检测 object detectors for multi-class pear surface 缺陷 检测 in quality grading systems |

#### parallel (4)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-22b8d5db | YOLO-IOD: Towards Real Time Incremental Object Detection | YOLO 实时目标检测-IOD: Towards 实时 Incremental 目标检测 |
| c-2933fd35 | Developing a Resource-Constraint EdgeAI model for Surface Defect Detection | Developing a Resource-Constraint EdgeAI model for Surface 缺陷 检测 |
| c-88f36b64 | DeepInspect: An AI-Powered Defect Detection for Manufacturing Industries | DeepInspect: An AI-Powered 缺陷 检测 for Manufacturing Industries |
| c-17a3f47a | Yonatan-Estifanos-github/SurfaceDefectNet-Deep-Learning-for-Surface-Defect-Detection | 仓库 Yonatan-Estifanos-github/SurfaceDefectNet-Deep-Learning-for-Surface-Defect-Detection |

#### reference (2)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-124d6aab | Road Surface Defect Detection -- From Image-based to Non-image-based: A Survey | 道路 Surface 缺陷 检测 -- From Image-based to Non-image-based: A 综述 |
| c-552f5160 | A New Benchmark Dataset for Texture Image Analysis and Surface Defect Detection | New 基准 数据集 for Texture Image Analysis and Surface 缺陷 检测 |

#### long_tail (5)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-5635ced7 | Oriented object detection in optical remote sensing images using deep learning: a survey | Oriented 目标检测 in optical remote sensing images using 深度学习: a 综述 |
| c-82b1eafb | AIn't Nothing But a Survey? Using Large Language Models for Coding German Open-Ended Survey Responses on Survey Motivation | AIn't Nothing But a 综述? Using Large Language Models for Coding German Open-Ended 综述 Responses on 综述 Motivation |
| c-ca4ba581 | The Methanol Multibeam Survey | Methanol Multibeam 综述 |
| c-fac1dcf1 | YOLO-CL: Galaxy cluster detection in the SDSS with deep machine learning | YOLO 实时目标检测-CL: Galaxy cluster 检测 in the SDSS with deep machine learning |
| c-4288ccef | Online Metallic Surface Defect Detection Using Deep LearningOnline Metallic Surface Defect Detection Using Deep Learning | Online Metallic Surface 缺陷 检测 Using Deep LearningOnline Metallic Surface 缺陷 检测 Using 深度学习 |

#### rejected (5)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-5635ced7 | Oriented object detection in optical remote sensing images using deep learning: a survey | Oriented 目标检测 in optical remote sensing images using 深度学习: a 综述 | Remote sensing oriented object detection survey; cross-domain mismatch. |
| c-82b1eafb | AIn't Nothing But a Survey? Using Large Language Models for Coding German Open-Ended Survey Responses on Survey Motivati | AIn't Nothing But a 综述? Using Large Language Models for Coding German Open-Ended 综述 Responses on 综述 Motivati | Linguistic survey coding paper; completely unrelated domain. |
| c-ca4ba581 | The Methanol Multibeam Survey | Methanol Multibeam 综述 | Radio astronomy methanol survey; no overlap whatsoever. |
| c-fac1dcf1 | YOLO-CL: Galaxy cluster detection in the SDSS with deep machine learning | YOLO 实时目标检测-CL: Galaxy cluster 检测 in the SDSS with deep machine learning | Astronomy/galaxy cluster detection; cross-domain mismatch. |
| c-4288ccef | Online Metallic Surface Defect Detection Using Deep LearningOnline Metallic Surface Defect Detection Using Deep Learning | Online Metallic Surface 缺陷 检测 Using Deep LearningOnline Metallic Surface 缺陷 检测 Using 深度学习 | Title suggests metallic defect detection but abstract concerns obscured AGN; metadata mismatch/fabrication risk. |

#### dataset_and_repo_notes

> NEU-DET (c-6a621c99): standard steel-surface defect benchmark; use to standardize metrics and as proxy defect-texture training corpus.
> PCB-defect (c-a19ac215): annotated defect dataset; auxiliary pretraining for general surface defects.
> DOTA (c-1a735315) and COCO (c-e442a6b9): pretraining corpora for the YOLO/Faster R-CNN backbone; DOTA also supplies oriented-bbox priors relevant to trackside insulator poses.
> SurfaceDefectNet repo (c-17a3f47a): segmentation-based defect reference implementation; not insulator-specific, but useful code skeleton.
> No verified catenary-insulator-specific dataset was retrieved; field/trackside image acquisition is mandatory before credible model evaluation.

### §39 ENG-THESIS-096 — 《基于石墨烯薄膜电热效应的风机叶片防冰除冰系统研究》 — `weak`

| 维度 | 数值 |
|---|---:|
| batch | r2 |
| elapsed | 179.6s |
| domain | 能源装备/故障诊断 |
| paper | 22 |
| dataset | 0 |
| repo | 0 |
| baseline | 1 |
| parallel | 3 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-10517-1022609100.htm |

**direction_recommendation**: The evidence base has NO direct paper on graphene-film electrothermal de-icing of wind turbine blades. Closest anchor is c-ba4d7e62 (implanted carbon fibre resistive heating for blade anti-icing), with c-d58d697f providing FEM-Joule-heating methodology and c-eb26ec2a plus c-56e257d9 covering icing simulation and ice-adhesion theory. Recommend the student anchor the work on c-ba4d7e62 as the primary baseline (resistive heating on composite blade), generalize the heating element from carbon fibre to graphene film, and supplement with c-eb26ec2a (icing accretion simulation), c-56e257d9 (ice adhesion review), c-6e4b9c13 / c-e15f4856 (mitigation technology survey), and c-d58d697f (Joule-heating FEM) for the electrothermal simulation backbone. The graphene-specific novelty must be argued from materials-science literature outside the retrieved set; the student must manually pull graphene Joule-heating papers (e.g. Bae 2012-type, Janas/Bonaccorso graphene heater reviews) and icing-detection papers since none were retrieved.

#### core (1)

| cid | 原文 title | 中文含义 | reason |
|---|---|---|---|
| c-ba4d7e62 | Utilising implanted carbon fibre as a resistive heating element in wind turbine blade anti-icing systems | (中文含义由英文派生) | Direct match: resistive heating anti-icing on wind turbine blade composite surface. |

#### baseline (1)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-ba4d7e62 | Utilising implanted carbon fibre as a resistive heating element in wind turbine blade anti-icing systems | (中文含义由英文派生) |

#### parallel (3)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-eb26ec2a | Numerical Simulation of Icing Characteristics on a Blade Airfoil for Vertical-Axis Wind Turbine under Various Icing Conditions | (中文含义由英文派生) |
| c-56e257d9 | A Brief Review of Blade Surface Icing Adhesive Theories for Wind Turbines | Brief Review of Blade Surface Icing Adhesive Theories for Wind Turbines |
| c-bc865519 | Wind Tunnel Tests on Anti-Icing Performance of Wind Turbine Blade with NACA0018 Airfoil with Bio-Wax PCMS-PUR Coating | (中文含义由英文派生) |

#### reference (15)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-d58d697f | Finite Element Convergence for the Joule Heating Problem with Mixed Boundary Conditions | (中文含义由英文派生) |
| c-6e4b9c13 | Conventional wind turbine icing mitigation technologies | (中文含义由英文派生) |
| c-e15f4856 | Wind Turbine Icing Physics and Anti-/De-icing Technology | (中文含义由英文派生) |
| c-f84ba1a4 | Field measurements of wind turbine icing | (中文含义由英文派生) |
| c-5e2682c9 | Plasma-based technologies for wind turbine icing mitigation | (中文含义由英文派生) |
| c-c89b8199 | Micromechanical modelling of wind turbine blade materials | (中文含义由英文派生) |
| c-e8860f4b | Wind Turbine Blade Design Requirements | (中文含义由英文派生) |
| c-da002701 | Wind Turbine Blade Design | (中文含义由英文派生) |
| c-655db3c0 | Introduction to wind turbine blade design | (中文含义由英文派生) |
| c-86e14f16 | Wind Turbine Aerodynamics Part B: Turbine Blade Flow Fields | (中文含义由英文派生) |
| c-0ff7388f | An Examination of Rotational Effects on Large Wind Turbine Blades | Examination of Rotational Effects on Large Wind Turbine Blades |
| c-99de39d9 | Modeling the effect of wind speed and direction shear on utility-scale wind turbine power production | (中文含义由英文派生) |
| c-48d636b0 | An aerodynamic measurement system to improve the efficiency of wind turbine rotor blades | aerodynamic measurement system to improve the efficiency of wind turbine rotor blades |
| c-08a48562 | Material optimization of flexible blades for wind turbines | (中文含义由英文派生) |
| c-74cbe89a | Effects of Inflow Turbulence on Structural Deformation of Wind Turbine Blades | (中文含义由英文派生) |

#### long_tail (0) (无)
#### rejected (3)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-034957ff | Frequency support Scheme based on parametrized power curve for de-loaded Wind Turbine under various wind speed | (中文含义由英文派生) | Grid frequency control paper; cross-domain (power systems vs. blade icing). |
| c-ed4abd0b | SDWPF: A Dataset for Spatial Dynamic Wind Power Forecasting Challenge at KDD Cup 2022 | SDWPF: A 数据集 for Spatial 动态 Wind Power Forecasting Challenge at KDD Cup 2022 | Wind power forecasting dataset; cross-domain (data science vs. blade icing). |
| c-75d8ef40 | The perils of automated fitting of datasets: the case of a wind turbine cost model | perils of automated fitting of datasets: the case of a wind turbine cost model | Wind turbine cost modeling critique; no icing or blade-surface content. |

#### dataset_and_repo_notes

> No public wind-turbine blade icing dataset was retrieved by Core/HuggingFace/OpenAlex — student must source NREL/IEA Wind Task reports or lab-measured accretion data for validation.
> No GitHub repository implements graphene-film electrothermal blade anti-icing — student must build the COMSOL/MATLAB model from scratch, reusing only FEM theory from c-d58d697f.
> No graphene-specific heater paper was retrieved — student must manually pull graphene Joule-heater literature (e.g. Bae et al. ACS Nano 2012; Janas/Bonaccorso reviews) from Google Scholar.
> c-f84ba1a4 field-icing measurements can serve as empirical anchor for icing-detection component.

### §40 ENG-THESIS-100 — 《基于深度学习的配电设备视觉识别技术研究》 — `weak`

| 维度 | 数值 |
|---|---:|
| batch | r6 |
| elapsed | 221.9s |
| domain | 电力/轨交巡检视觉 |
| paper | 27 |
| dataset | 3 |
| repo | 6 |
| baseline | 4 |
| parallel | 1 |
| strong_noise_in_core | False |
| source_url | https://cdmd.cnki.com.cn/Article/CDMD-10335-1021830761.htm |

**direction_recommendation**: Evidence is thin on direct YOLOv5/v8/Faster R-CNN applied to insulator, switchgear or transformer datasets. The four strongest anchors are c-c06f76ab (DL object detection for power-equipment rust defects), c-afd06f32 (CapsNet-based electric power equipment detector), c-c9bf4d1c (fire/smoke detection on transmission/distribution equipment), and c-28c9117f (CycleGAN visible-infrared enhancement for infrared power equipment detection). These four should be treated as the only tier=core anchors (auditor-assigned, not citation-verified). Recommended direction: a YOLOv8-based multi-task pipeline for distribution-equipment recognition (component classification + defect localization), evaluated against distribution-grade benchmarks, with CycleGAN-style image enhancement as an augmentation/robustness module and CapsNet + DL-rust work as methodological baselines. Background method references (c-f841b989 oriented-detection survey, c-e616edf9 few-shot survey, c-c179daf8 HIC-YOLOv5 small-object improvement, c-df5ca10f RefineContourNet) are admissible as method-only background. Generic datasets (COCO/VOC/VisDrone) are flagged for manual confirmation since none are power-domain. Several Crossref/

#### core (4)

| cid | 原文 title | 中文含义 | reason |
|---|---|---|---|
| c-c06f76ab | Research on the Application of Deep Learning Object Detection in Rust Defect Detection of Power Equipment | Research on the Application of 深度学习 目标检测 in Rust 缺陷 检测 of Power Equipment | Direct match: deep learning object detection for rust defects on power equipment; parallel work to topic. |
| c-afd06f32 | Accurate Object Detection of Electric Power Equipment Based on CapsNet Framework | Accurate 目标检测 of Electric Power Equipment Based on CapsNet Framework | CapsNet-based object detection for electric power equipment; directly aligned with topic. |
| c-c9bf4d1c | Fire and Smoke Detection of Power System Transmission and Distribution Equipment | Fire and Smoke 检测 of Power System Transmission and Distribution Equipment | Fire/smoke detection for transmission & distribution equipment; parallel visual task on power equipment. |
| c-28c9117f | CycleGAN-Based Visible-Infrared Image Enhancement Method for Infrared Power Equipment Object Detection | CycleGAN-Based Visible-Infrared Image Enhancement Method for Infrared Power Equipment 目标检测 | Visible-infrared image enhancement for power equipment detection; directly relevant module. |

#### baseline (4)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-c06f76ab | Research on the Application of Deep Learning Object Detection in Rust Defect Detection of Power Equipment | Research on the Application of 深度学习 目标检测 in Rust 缺陷 检测 of Power Equipment |
| c-afd06f32 | Accurate Object Detection of Electric Power Equipment Based on CapsNet Framework | Accurate 目标检测 of Electric Power Equipment Based on CapsNet Framework |
| c-c9bf4d1c | Fire and Smoke Detection of Power System Transmission and Distribution Equipment | Fire and Smoke 检测 of Power System Transmission and Distribution Equipment |
| c-28c9117f | CycleGAN-Based Visible-Infrared Image Enhancement Method for Infrared Power Equipment Object Detection | CycleGAN-Based Visible-Infrared Image Enhancement Method for Infrared Power Equipment 目标检测 |

#### parallel (1)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-c179daf8 | HIC-YOLOv5: Improved YOLOv5 For Small Object Detection | HIC-YOLO 实时目标检测: Improved YOLO 实时目标检测 For Small 目标检测 |

#### reference (5)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-df5ca10f | Object Contour and Edge Detection with RefineContourNet | Object Contour and Edge 检测 with RefineContourNet |
| c-f841b989 | Oriented object detection in optical remote sensing images using deep learning: a survey | Oriented 目标检测 in optical remote sensing images using 深度学习: a 综述 |
| c-e616edf9 | A Survey of Self-Supervised and Few-Shot Object Detection | 综述 of 自监督 and 少样本 目标检测 |
| c-9dbe8a1c | 3D Object Detection for Autonomous Driving: A Comprehensive Survey | 三维 目标检测 for 自动驾驶: A Comprehensive 综述 |
| c-a349c4c8 | Organizational Description System for Digital Twin of Distribution Network Equipment Based on Object-oriented Equipment Model | (中文含义由英文派生) |

#### long_tail (4)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-6b761827 | TJU-DHD: A Diverse High-Resolution Dataset for Object Detection | TJU-DHD: A Diverse High-Resolution 数据集 for 目标检测 |
| c-aa9a2c8e | amusi/awesome-object-detection | 仓库 amusi/awesome-object-detection |
| c-e0e987b7 | Alpaca-zip/ultralytics_ros | 仓库 Alpaca-zip/ultralytics_ros |
| c-659ebcfe | Smorodov/Deep-learning-object-detection-links. | 仓库 Smorodov/Deep-learning-object-detection-links. |

#### rejected (19)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-36e3f770 | AIn't Nothing But a Survey? Using Large Language Models for Coding German Open-Ended Survey Responses on Survey Motivati | AIn't Nothing But a 综述? Using Large Language Models for Coding German Open-Ended 综述 Responses on 综述 Motivati | NLP/LLM survey on survey coding methodology, unrelated to vision/power domain. |
| c-1ac6db9d | Exploring Depth Contribution for Camouflaged Object Detection | Exploring Depth Contribution for Camouflaged 目标检测 | Camouflaged object detection in computer vision; no power equipment relevance. |
| c-cda3f98f | PVAFN: Point-Voxel Attention Fusion Network with Multi-Pooling Enhancing for 3D Object Detection | PVAFN: Point-Voxel Attention Fusion Network with Multi-Pooling Enhancing for 三维 目标检测 | 3D LiDAR detection for autonomous driving; no 2D power equipment relevance. |
| c-6f2063d1 | Super Sparse 3D Object Detection | Super Sparse 三维 目标检测 | Sparse 3D LiDAR detection for autonomous driving; cross-modality and cross-domain. |
| c-f9853874 | Table 1: KITTI object detection benchmark on
                      <i>test</i>
                      set of the proposed | Table 1: KITTI 目标检测 基准 on
           <i>test</i>
           set of the proposed | Metadata-broken entry; abstract indicates camouflaged detection, unrelated to power equipment. |
| c-34c2465f | rbgirshick/voc-dpm | 仓库 rbgirshick/voc-dpm | Legacy DPM-based detector; predates deep learning era, not applicable. |
| c-fad3da70 | chrisneagu/FTC-Skystone-Dark-Angels-Romania-2020 | 仓库 chrisneagu/FTC-Skystone-Dark-Angels-Romania-2020 | FTC robotics competition SDK; unrelated to visual recognition or power systems. |
| c-c9f9f1c6 | Import project (Eclipse ADT, Gradle, etc.) | (中文含义由英文派生) | Eclipse/Gradle import error message; no relation to topic. |
| c-3d07aa7a | E RobotCore: lynx xmit lock: #### abandoning lock: | (中文含义由英文派生) | RobotCore driver lock message; unrelated to power equipment vision. |
| c-12c41f06 | Could not find com.android.tools.lint:lint-gradle:26.1.4 | (中文含义由英文派生) | Android Gradle lint error log; no topical relevance. |
| c-9355e601 | Version 3.00 (built on 17.04.013) | (中文含义由英文派生) | Generic software version string; no topical relevance. |
| c-6eefd0d9 | missing hardware leaves robot controller disconnected from driver station | missing hardware leaves 机器人 controller disconnected from driver station | Robotics controller error log; unrelated domain. |
| c-6f7a2509 | fast tapping of Init/Start causes problems | (中文含义由英文派生) | Software init bug report; unrelated to topic. |
| c-d5ab8cb9 | molyswu/hand_detection | 仓库 molyswu/hand_detection | Hand detection repo; cross-domain mismatch with power equipment. |
| c-04784a30 | Lending a hand: Detecting hands and recognizing activities in complex egocentric interactions. | (中文含义由英文派生) | Egocentric hand-activity paper; cross-domain mismatch. |
| c-e03c2d7f | >  ====== Hand Inference graph loaded. | > ====== Hand Inference graph loaded. | TF inference log snippet; not a research artifact. |
| c-3498f3e1 | python   detection_graph = tf.Graph()     with detection_graph.as_default():         od_graph_def = tf.GraphDef()        | python  detection_graph = tf.Graph()   with detection_graph.as_default():     od_graph_def = tf.GraphDef() | TF code snippet for hand detection; no topical relevance. |
| c-f33abdf4 | python   (boxes, scores, classes, num) = sess.run(         [detection_boxes, detection_scores,             detection_cla | python  (boxes, scores, classes, num) = sess.run(     [detection_boxes, detection_scores,       detection_cla | Generic TF detection inference code; unrelated to topic. |
| c-8b72a0ee | cmd   # load and run detection on video at path "videos/chess.mov"   python detect_single_threaded.py --source videos/ch | cmd  # load and run 检测 on video at path "videos/chess.mov"  python detect_single_threaded.py --source videos/ch | Chess-piece detection CLI snippet; unrelated to power systems. |

#### dataset_and_repo_notes

> c-ff971cdb COCO is the default pretraining corpus for YOLOv5/v8; verify it is used only as pretraining, not as evaluation, for the power-equipment task.
> c-0e078424 Pascal VOC is a legacy 2D detection benchmark; cite only for historical comparison.
> c-163cc23f VisDrone (drone imagery) is only tangentially relevant for aerial inspection of overhead distribution lines.
> c-aa9a2c8e amusi/awesome-object-detection can be used to discover additional YOLO/Faster R-CNN references not in the current ledger.
> c-e0e987b7 ultralytics_ros provides a YOLOv8 ROS/ROS2 wrapper usable as a deployment target for field inspection robots.
> c-c179daf8 HIC-YOLOv5 small-object improvement is method-level relevant for detecting small insulators/fittings.

## §41 一屏保留 / 剔除总计

| 类别 | 累计桶内条数 |
|---|---:|
| core (LLM ER 直接命中) | 121 |
| baseline (可复现基础方案) | 130 |
| parallel (同任务平行方案) | 173 |
| reference (综述 / 启发) | 188 |
| long_tail (仓库 / 数据集 / 长尾) | 181 |
| **保持总数**（core+baseline+parallel+reference+long_tail） | **793** |
| **剔除总数**（rejected） | **538** |

### 各 case 桶保留明细

| case_id | core | baseline | parallel | reference | long_tail | rejected |
|---|---:|---:|---:|---:|---:|---:|
| ENG-THESIS-002 | 3 | 2 | 4 | 3 | 1 | 7 |
| ENG-THESIS-003 | 7 | 5 | 1 | 6 | 1 | 8 |
| ENG-THESIS-004 | 2 | 2 | 2 | 3 | 4 | 15 |
| ENG-THESIS-005 | 0 | 1 | 0 | 18 | 87 | 104 |
| ENG-THESIS-010 | 2 | 3 | 3 | 2 | 3 | 11 |
| ENG-THESIS-014 | 0 | 4 | 5 | 1 | 2 | 10 |
| ENG-THESIS-015 | 1 | 2 | 3 | 0 | 1 | 11 |
| ENG-THESIS-016 | 6 | 4 | 6 | 4 | 8 | 6 |
| ENG-THESIS-018 | 4 | 1 | 7 | 4 | 4 | 20 |
| ENG-THESIS-022 | 2 | 3 | 5 | 8 | 4 | 18 |
| ENG-THESIS-024 | 3 | 3 | 7 | 6 | 0 | 8 |
| ENG-THESIS-027 | 5 | 3 | 2 | 4 | 1 | 16 |
| ENG-THESIS-028 | 0 | 4 | 2 | 3 | 1 | 13 |
| ENG-THESIS-032 | 0 | 3 | 1 | 5 | 0 | 7 |
| ENG-THESIS-033 | 7 | 5 | 9 | 10 | 2 | 0 |
| ENG-THESIS-035 | 7 | 5 | 9 | 5 | 1 | 5 |
| ENG-THESIS-040 | 0 | 2 | 3 | 1 | 1 | 7 |
| ENG-THESIS-043 | 4 | 3 | 3 | 6 | 0 | 6 |
| ENG-THESIS-046 | 3 | 3 | 6 | 3 | 6 | 17 |
| ENG-THESIS-048 | 1 | 3 | 3 | 6 | 6 | 7 |
| ENG-THESIS-050 | 4 | 3 | 8 | 8 | 0 | 5 |
| ENG-THESIS-051 | 4 | 1 | 5 | 0 | 2 | 10 |
| ENG-THESIS-058 | 12 | 5 | 5 | 3 | 11 | 10 |
| ENG-THESIS-060 | 8 | 6 | 11 | 9 | 0 | 3 |
| ENG-THESIS-063 | 11 | 7 | 6 | 5 | 2 | 20 |
| ENG-THESIS-064 | 3 | 3 | 3 | 4 | 1 | 12 |
| ENG-THESIS-066 | 0 | 4 | 2 | 3 | 2 | 20 |
| ENG-THESIS-072 | 7 | 2 | 6 | 3 | 4 | 8 |
| ENG-THESIS-073 | 0 | 1 | 2 | 4 | 0 | 20 |
| ENG-THESIS-074 | 2 | 2 | 5 | 4 | 4 | 15 |
| ENG-THESIS-075 | 1 | 3 | 3 | 1 | 1 | 18 |
| ENG-THESIS-079 | 1 | 3 | 4 | 2 | 0 | 20 |
| ENG-THESIS-080 | 0 | 4 | 4 | 3 | 2 | 11 |
| ENG-THESIS-083 | 2 | 5 | 5 | 7 | 5 | 20 |
| ENG-THESIS-089 | 0 | 5 | 6 | 3 | 0 | 6 |
| ENG-THESIS-091 | 2 | 4 | 2 | 3 | 1 | 10 |
| ENG-THESIS-092 | 2 | 2 | 7 | 6 | 4 | 7 |
| ENG-THESIS-093 | 0 | 4 | 4 | 2 | 5 | 5 |
| ENG-THESIS-096 | 1 | 1 | 3 | 15 | 0 | 3 |
| ENG-THESIS-100 | 4 | 4 | 1 | 5 | 4 | 19 |

## §42 修复贡献按 case（Re04-fix 后实跑）

> 每个 case 的 (dataset 召回数, repo 召回数, baseline 召回数, 是否触发 canonical method fallback) — 让用户能直接看出 H1/H2/H3/H4 对每个 case 的实际帮助。

| case_id | title | dataset | repo | baseline | canonical_fallback | 修复后 status |
|---|---|---:|---:|---:|---|---|
| ENG-THESIS-002 | 基于深度学习的磁瓦在线检测技术研究 | 0 | 1 | 3 | Y | pass |
| ENG-THESIS-003 | 基于点云多平面检测的三维重建关键技术研究 | 0 | 4 | 3 | Y | weak |
| ENG-THESIS-004 | 基于改进YOLOv4模型的快速目标检测与测距算法研究 | 3 | 6 | 2 | Y | pass |
| ENG-THESIS-005 | 随机纹理背景下弱小缺陷检测的深度学习方法研究 | 4 | 6 | 1 | Y | weak |
| ENG-THESIS-010 | 基于深度学习的交通标志检测与识别研究 | 0 | 4 | 3 | Y | pass |
| ENG-THESIS-014 | 基于生成对抗网络的织物缺陷检测算法研究 | 2 | 0 | 4 | Y | pass |
| ENG-THESIS-015 | 基于患者虚拟定位的三维人体重建关键技术研究 | 0 | 0 | 2 | Y | weak |
| ENG-THESIS-016 | 基于深度学习的视觉SLAM语义地图的研究 | 0 | 0 | 4 | Y | weak |
| ENG-THESIS-018 | 基于深度学习的三维点云补全方法研究 | 0 | 0 | 1 | Y | weak |
| ENG-THESIS-022 | 基于深度学习的钢铁表面缺陷检测研究 | 4 | 6 | 3 | Y | pass |
| ENG-THESIS-024 | 基于深度学习的无监督三维点云配准算法研究 | 2 | 3 | 3 | Y | pass |
| ENG-THESIS-027 | 基于YOLOv5模型的遥感影像飞机目标检测 | 2 | 5 | 3 | Y | pass |
| ENG-THESIS-028 | 基于YOLOv5的绝缘子检测与缺陷识别方法研究 | 0 | 0 | 4 | Y | weak |
| ENG-THESIS-032 | 基于深度学习的液晶屏表面缺陷检测方法研究 | 0 | 0 | 3 | Y | weak |
| ENG-THESIS-033 | 基于YOLOV5的肺结节检测算法研究 | 0 | 0 | 5 | Y | weak |
| ENG-THESIS-035 | 基于深度学习的带钢表面缺陷检测方法 | 1 | 1 | 5 | Y | pass |
| ENG-THESIS-040 | 基于改进YOLO网络与极限学习机的绝缘子故障检测 | 2 | 0 | 2 | Y | pass |
| ENG-THESIS-043 | 基于无人机平台的动态目标检测系统开发 | 0 | 0 | 3 | Y | weak |
| ENG-THESIS-046 | 基于视觉的机械臂的目标检测和避障路径规划研究与应用 | 0 | 6 | 3 | Y | pass |
| ENG-THESIS-048 | 面向动态环境的视觉SLAM研究 | 0 | 6 | 3 | Y | fail |
| ENG-THESIS-050 | 基于深度学习的自动驾驶感知算法 | 0 | 0 | 3 | Y | weak |
| ENG-THESIS-051 | 基于深度学习的语义SLAM研究 | 0 | 2 | 1 | Y | pass |
| ENG-THESIS-058 | 基于深度学习的激光点云环境感知 | 2 | 6 | 5 | Y | pass |
| ENG-THESIS-060 | 基于深度学习的车道线检测方法研究 | 1 | 6 | 6 | Y | fail |
| ENG-THESIS-063 | 基于3D视觉的机械臂无序抓取系统研究 | 0 | 0 | 7 | Y | weak |
| ENG-THESIS-064 | 面向复杂道路场景的车辆目标检测算法研究与实现 | 0 | 6 | 3 | Y | pass |
| ENG-THESIS-066 | 面向自动驾驶中多模态融合感知算法的攻击和防御 | 0 | 0 | 4 | Y | weak |
| ENG-THESIS-072 | 基于深度学习的动态SLAM研究 | 0 | 3 | 2 | Y | pass |
| ENG-THESIS-073 | 面向汽车自动驾驶的模拟图像生成技术及应用研究 | 3 | 1 | 1 | Y | pass |
| ENG-THESIS-074 | 基于深度学习的混凝土桥梁裂缝检测研究 | 1 | 6 | 2 | Y | pass |
| ENG-THESIS-075 | 基于深度学习的混凝土路面裂缝检测研究 | 0 | 6 | 3 | Y | pass |
| ENG-THESIS-079 | 基于结构光的隧道裂缝检测技术研究与实现 | 0 | 6 | 3 | Y | pass |
| ENG-THESIS-080 | 基于三维重建裂缝损伤检测算法研究 | 1 | 6 | 4 | Y | pass |
| ENG-THESIS-083 | 基于多分辨率网络的桥梁裂缝分割算法研究 | 0 | 6 | 5 | Y | pass |
| ENG-THESIS-089 | 基于深度学习和双目立体视觉的道路路面损伤检测研究 | 0 | 0 | 5 | Y | weak |
| ENG-THESIS-091 | 基于云计算的输电线路缺陷检测平台 | 0 | 0 | 4 | Y | weak |
| ENG-THESIS-092 | 海上风机叶片缺陷检测及分类 | 3 | 6 | 2 | Y | pass |
| ENG-THESIS-093 | 基于深度学习的接触网绝缘子表面缺陷图像式检测方法研究 | 3 | 1 | 4 | Y | pass |
| ENG-THESIS-096 | 基于石墨烯薄膜电热效应的风机叶片防冰除冰系统研究 | 0 | 0 | 1 | Y | weak |
| ENG-THESIS-100 | 基于深度学习的配电设备视觉识别技术研究 | 3 | 6 | 4 | Y | weak |

**注**：H1 (query_matrix canonical method fallback) / H2 (dataset hint) / H3 (GitHub ranked pull) / H4 (ER chunk routing) 在 balanced40 实际生效率：

- H1 (canonical method fallback, baseline+parallel 中是否有真实有名 baseline) 命中率 = **40/40** (100.0%)
- H2 (dataset 召回命中) = **16/40**
- H3 (repo 召回命中) = **25/40**
- H4 (ER chunk routing, evidence_review 中包含 paper-like row) = 全部 case 触发
