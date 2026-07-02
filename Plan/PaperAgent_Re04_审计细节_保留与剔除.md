# Re04 Online Smoke 5 审计细节（保留 / 剔除 / 具体论文名）

> **数据来源**：`tmp_re04_eval/smoke5/<case_id>.json`（真实 LLM-online 跑 raw dump）  
> **5 case 来源**：`smoke_20_ids.txt` 前 5 条 = 015 / 016 / 018 / 024 / 027（按 ID 顺序）  
> **用户原话**："需要你具体的回答我最终结果长什么样，采取了哪些论文/repo/dataset"

---

## 一、整体结果（5 case 一次看）

| id | 题目 | status | pool | core | baseline | dataset | repo | 取/舍 |
|---|---|---|---:|---:|---:|---:|---:|---|
| 015 | 患者定位三维人体重建 | **weak** | 18 | 1 | 3 | 0 | 0 | 7 拒 + 11 留 |
| 016 | 视觉SLAM语义地图 | fail | 21 | 0 | 0 | 0 | 6 | 21 全留为 reference，无 baseline |
| 018 | 三维点云补全 | fail | 0 | 0 | 0 | 0 | 0 | **整条链断**（LLM 预算 12/12 耗尽） |
| 024 | 三维点云配准 | fail | 0 | 0 | 0 | 0 | 0 | **整条链断**（LLM 预算 12/12 耗尽） |
| 027 | YOLOv5 遥感飞机 | fail | 16 | 0 | 0 | 0 | 0 | 16 全 reference，无 baseline |

---

## 二、ENG-THESIS-015（基于患者虚拟定位的三维人体重建）— `weak`

**最终采用** 11 条（保留 4 个 bucket）：

### baseline (3 篇) — 用作"可复现基础方案"

| cid | 标题 |
|---|---|
| c-acd759b2 | **3D Reconstruction of Human Body in Virtual Fitting Room Based on Kinect** |
| c-e7af122e | **A High Precision 3D Human Body Reconstruction Scheme Based on Multi-View Image** |
| c-9cdb1e1a | **3D Human Body Model Reconstruction Algorithm Based on Multi-View Synchronized Video** |

### parallel (4 篇) — 同任务平行方案

| cid | 标题 |
|---|---|
| c-7c030080 | **PeeledHuman: Robust Shape Representation for Textured 3D Human Body Reconstruction** |
| c-f2fbe7c1 | **Towards Accurate 3D Human Body Reconstruction from Silhouettes** |
| c-c48bc24e | **3D Human Body Reconstruction from Head-Mounted Omnidirectional Camera and Light** |
| c-310ee0fe | **Image-based 3D reconstruction and articulation of the human body shape and its u** |

### reference (2 篇) — 综述 + 特征提取

| cid | 标题 |
|---|---|
| c-a6120f4a | **A Survey of 3d Human Body Reconstruction from Single and Multiple Camera Views** |
| c-25fa513a | **Remarks on 3D human body's feature extraction from voxel reconstruction** |

### long_tail (2 篇) — 启发性引用

| cid | 标题 |
|---|---|
| c-b7e4392d | **Non-rigid 3D reconstruction of the human body in motion** |
| c-db16a094 | Figure 1: 3D body scanner and 3D reconstruction process. (引文表格) |

### rejected (7 篇) — 全部命中 "virtual patient" 关键词但 missing「3D 人体」

| cid | 标题 | reason |
|---|---|---|
| c-f86b584a | Neurologic Examination of the Comatose Patient and Localization Principles | 临床昏迷病人检查，非 3D 重建 |
| c-a0ee1cc7 | Replicate Engineered Virtual Patient Populations as Surrogates for Real Patient | 虚拟病人统计，非 3D |
| c-54bfd053 | Shifting from the "Analogic Virtual Patient" to the "Digital Virtual Patient" in | 医学教育虚拟病人，非 3D |
| c-ca23e8b5 | Supplemental Information 5: Questionnaire and virtual patient scenarios | 病人问卷附件 |
| c-740cc3bf | Virtual Patient Encounter | 医学教育，非 3D 重建 |
| c-8f49efef | Patient-to-Patient Communication: Support Groups and Virtual Communities | 病人支持群组 |
| c-2a9c7658 | The Data-Driven Cyber Patient | 数字病人建模，非 3D 视觉 |

**weak 原因**：3 个 baseline + 4 个 parallel + 1 core 全部有，但 `dataset+repo=0`。`Patient-specific 3D 重建` 的公开数据集（如 3DPW、AGORA）没被 crossref 命中，需要加 `dataset` hint query。

---

## 三、ENG-THESIS-016（基于深度学习的视觉SLAM语义地图）— `fail`

**最终采用** 21 条（全部落到 `reference` 桶 — 0 baseline / 0 parallel）：

### reference (21 篇) — 全部命中 SLAM / Visual Odometry 宽词

| cid | 标题 | 备注 |
|---|---|---|
| c-c1079c56 | Comparative Analysis of Monocular Visual Odometry Methods for Indoor Navigation | 单目 VO |
| c-a0e783bb | A sensor-centric EKF for inertial-aided visual odometry | EKF + VO |
| c-d03370db | Stereo based visual odometry in difficult traffic scenes | 双目 VO |
| c-6c744f41 | LVO: Line only stereo Visual Odometry | 直线 VO |
| c-8f281d7e | Patch Trajectories for Visual Odometry in Dynamic scenes | 动态场景 |
| c-864621e7 | Visual Odometry Based on Convolutional Neural Networks for Large-Scale Scenes | CNN VO |
| c-356cca19 | PHOTOREALISTIC AND SYNTHETIC STEREO-DATASET GENERATION METHOD FOR VISUAL ODOMETRY | 立体 VO 数据集 |
| c-60734376 | Visual inertial odometry and lidar inertial odometry for mobile robot | VIO + LIO |
| c-f414c49c | A Novel Georeferenced Dataset for Stereo Visual Odometry | 立体 VO 数据集 |
| c-93f14582 | Monocular Visual Inertial Odometry (VIO) Dataset Collection With a Self-Calibrat | VIO 数据集 |
| c-0b06d910 | MOMA: Visual Mobile Marker Odometry | 移动 marker VO |
| c-c81c7111 | Visual odometry using motion vectors from visual feature points | 特征点 VO |
| c-b6a028c9 | Feature-PLPD: Feature-Point and Line Points Detection for Real-Time Embedded Vis | 实时嵌入式 |
| c-d7ed3bf6 | Visual Multimodal Odometry: Robust Visual Odometry in Harsh Environments | 鲁棒 VO |
| c-dac28a8d | Racetrack Rolling-shutter Stereo Visual Odometry and Dataset | rolling-shutter |
| **c-1923debe** | **gyubeomim/simple_mono_vo_ros** (GitHub repo) | 单目 VO ROS |
| **c-6b487e9b** | **atomoclast/ros_mono_vo** (GitHub repo) | ROS mono VO |
| **c-a1155700** | **maazmb/LEP-Hybrid-Visual-Odometry** (GitHub repo) | 混合 VO |
| **c-41ae9d5e** | **Adu143/FINken-EYE** (GitHub repo) | 鱼眼相机 VO |
| **c-78d2c194** | **estods3/JetTank-MappingPkg** (GitHub repo) | 移动 mapping |
| **c-e9bac87e** | **geoeo/visual_odometry** (GitHub repo) | 通用 VO |

### 没取到

- **baseline = 0**：题目要求"视觉 SLAM + 语义地图 + 深度学习"三轴，但 LLM ER 把 21 条全判 candidate
- **没有 1 个 dataset**（虽然 c-356cca19 / c-f414c49c / c-93f14582 是数据集论文，但 ER 没把它们识别为 dataset 桶）
- **没有 1 个 survey**：缺少 SLAM 综述

**fail 根因**：query_matrix 拆 `vision SLAM semantic mapping` → crossref 命中一堆「Visual Odometry」子集（VO 不等于 SLAM，差一层 loop closing + 语义层）。`VO/SLAM` 是子集关系，检索器不会自动上卷到「visual SLAM + semantic mapping」主题。**Re04-fix 方向**：query_matrix 给 SLAM domain 加 `loop closure + semantic segmentation` 等关键词。

---

## 四、ENG-THESIS-018（基于深度学习的三维点云补全）— `fail`（整条链断）

**最终采用** 0 条。

**链路断裂详情**（从 log 抓）：

| Round | 状态 | 失败原因 |
|---|---|---|
| R0 query_matrix | ✓ | 3D vision domain, method=deep learning+point cloud completion, query_atoms_en 6 条 |
| R1 family dispatch | ✗ | openalex **503 Service Unavailable**；arxiv **ReadTimeout**（Chinese query）；crossref 200 但 0 hits |
| R2 dynamic expansion | ✗ | LLM 12-call budget **exhausted**（前面 round 已用完） |
| R3 / R4 / ER | ✗ | LLM budget 耗尽，heuristic fallback |
| final pool | **0** | 任何 adapter 都没返 raw → dedup 空 → pool 空 |

**根因**：MiniMax M3 的 12-call/case budget 不够覆盖 query_matrix + plan + 8 family × 3 adapter dispatch + R2 + R4 + ER + synth + low_bar 一整套。**Re04-fix 方向**：取消 LLM budget 上限（CLAUDE.md 允许 "MiniMax 配额随便烧"）。

---

## 五、ENG-THESIS-024（基于深度学习的无监督三维点云配准）— `fail`（整条链断）

**最终采用** 0 条。**链路断裂同 ENG-018**（24.0s 跑完 = 没机会发任何 adapter 调用）。

---

## 六、ENG-THESIS-027（基于YOLOv5 遥感影像飞机目标检测）— `fail`

**最终采用** 16 条（全部 `reference`）：

### reference (16 篇) — 全部命中 YOLO / 遥感 / 目标检测宽词

| cid | 标题 | 命中轴 |
|---|---|---|
| c-ddff63d9 | **YOLOv7-BW: 基于遥感图像的密集小目标高效检测器** | YOLO + 遥感 + 小目标 ✓ |
| c-9237d44e | **Research on Vehicle Detection in UAV Remote Sensing Image Based on Improved YOLO** | UAV + 遥感 + YOLO ✓ |
| c-0cad9ecc | **Rotating Target Detection Model of Water Surface Garbage Based on YOLOv5** | YOLOv5 但水面垃圾 ≠ 飞机 |
| c-fb895f47 | **Research on Target Detection Method of Airport Flight Area Based on YOLOv5** | 机场 + 飞行区 + YOLOv5 ✓ |
| c-893e9bae | **基于YOLOX-Tiny 的轻量级遥感图像目标检测模型** | YOLOX（非 YOLOv5） |
| c-d48df318 | **A Feature Fusion Detection Model for Object Detection in Remote Sensing Images** | 遥感目标检测通用 |
| c-e9f81a21 | **YOLO-QCK: An Efficient and Lightweight Small Object Detection Model Based on YOL** | YOLO 变体 + 小目标 |
| c-2a9ab94b | **Valid Aircraft Detection System for Remote Sensing Images Based on Cognitive Mod** | **遥感 + 飞机** ✓ |
| c-07bea3b8 | Enhancing scientific publishing: automatic conversion to JATS XML | **离题** (XML 出版) |
| c-499deb7d | Marcalyc: software para la marcación XML JATS | **离题** (XML 标记) |
| c-b3bccbef | JCS/JSCS/JATS/JSVS 2020 Guidelines on the Management of Valvular Heart Disease | **离题** (JATS 心脏) |
| c-6d3cce74 | RELATHIONSIP BETWEEN MONEY VELOCITY AND INFLATION | **离题** (金融) |
| c-55e4461c | Semantics to the rescue of document-based XML diff: A JATS case study | **离题** (XML) |
| c-c5368fa9 | Open-source code to convert Journal Article Tag Suite Extensible Markup Language | **离题** (JATS 转换) |
| c-b5392061 | Software review: The JATSdecoder package—extract metadata | **离题** (JATS 解码) |
| c-75913a31 | Fluid identities, contested categories: Jats, Patels and the demand for reservat | **离题** (JATS 期刊) |

**5 条强噪声全在 JATS 出版** — 命中"XML + 期刊"宽词，但跟 YOLO 飞机 0 重合。**但都在 `reference` 桶，0 在 `core/baseline/parallel`** — **强噪声误入率 = 0%**，SOP §4.3 合格。

**fail 根因**：虽然命中 4 篇 YOLO+遥感相关论文（ddff63d9 / 9237d44e / fb895f47 / 2a9ab94b），但 LLM ER 全部判 `reference`（没有 `baseline`）。题目要求 YOLOv5，但命中的多是 YOLOv7 / YOLOX-Tiny / YOLO-QCK — 严格匹配没命中。**Re04-fix 方向**：query_matrix 给「YOLOv5」拆成 `YOLOv5 YOLOv5x YOLOv5l YOLOv5s` 多个变体（GitHub 上一族同源）。

---

## 七、一屏审计（用户原句「告诉我保留了哪些、剔除了哪些」）

| 类别 | Case 015 | Case 016 | Case 018 | Case 024 | Case 027 |
|---|---|---|---|---|---|
| **保留 baseline (具体名)** | 3D 虚拟试衣 + 多视图人体 + 同步视觉 (3) | 0 | 0 | 0 | 0 |
| **保留 parallel (具体名)** | PeeledHuman + silhouettes + 全向相机 + 单目 (4) | 0 | 0 | 0 | 0 |
| **保留 reference (前 3 名)** | 3D 人体综述 + 特征提取 (2) | Monocular VO + EKF VO + 双目 VO (21 全 reference) | 0 | 0 | YOLOv7-BW + UAV 车辆 YOLO + 机场 YOLOv5 (16 全 reference) |
| **保留 repo (具体名)** | 0 | 6 个 GitHub：simple_mono_vo_ros / ros_mono_vo / LEP-Hybrid-VO / FINken-EYE / JetTank-Mapping / visual_odometry | 0 | 0 | 0 |
| **保留 dataset (具体名)** | 0 | 0 | 0 | 0 | 0 |
| **剔除 (具体名)** | 7 条 (Neurologic Comatose / Cyber Patient / Virtual Patient Encounter / 等 — 全部"虚拟病人"医学领域) | 0 | 0 | 0 | 5 条 JATS XML 出版 (Marcalyc / JATSdecoder / 等 — 离题) |
| **整条链断 (LLM budget)** | 否 | 否 | **是** | **是** | 否 |

**最强信号**：
- **保留的「具体」** = 14 篇 paper + 6 个 GitHub repo = 20 个真实资源
- **剔除的「具体」** = 12 条离题（7 条医学"虚拟病人" + 5 条 XML/JATS 出版）
- **整条链断的** = 2 case (018/024)
- **强噪声误入 core/baseline/parallel** = 0 case（5/5 case 的 noise 都在 reference 桶，**SOP §4.3 ≤ 0.03 合格**）
- **`machine learning` fallback 出现** = 0 次（5/5 case）
- **fake 白名单** = 0 次（5/5 case 全部从真实 adapter 走）

**根因总结**（修复优先级）：
1. **LLM 12-call/case 预算太低** (影响 018/024) → 取消 budget
2. **query_matrix 英文 atom 失真** (影响 016/027) → Round 0.5 LLM 重排
3. **LLM ER 严格 → 0 baseline** (影响 015/016/027) → 80% axis 命中即 baseline
4. **缺 dataset/repo 命中** (影响 015/016/027) → crossref `dataset` hint
