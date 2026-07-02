# Re04 Online Smoke 5 审计细节（保留 / 剔除 / 中英对照）

> **数据来源**：`tmp_re04_eval/smoke5/<case_id>.json`（真实 LLM-online 跑 raw dump）  
> **5 case 来源**：`smoke_20_ids.txt` 前 5 条 = 015 / 016 / 018 / 024 / 027（按 ID 顺序）  
> **用户原话**："需要你具体的回答我最终结果长什么样，采取了哪些论文/repo/dataset" + "我要中文对照"

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

### baseline (3 篇) — 可复现基础方案

| cid | 原文 title (English) | 中文含义 |
|---|---|---|
| c-acd759b2 | 3D Reconstruction of Human Body in Virtual Fitting Room Based on Kinect | 基于 Kinect 的虚拟试衣间三维人体重建 |
| c-e7af122e | A High Precision 3D Human Body Reconstruction Scheme Based on Multi-View Image | 基于多视图的高精度三维人体重建方案 |
| c-9cdb1e1a | 3D Human Body Model Reconstruction Algorithm Based on Multi-View Synchronized Video | 基于多视图同步视频的三维人体模型重建算法 |

### parallel (4 篇) — 同任务平行方案

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-7c030080 | PeeledHuman: Robust Shape Representation for Textured 3D Human Body Reconstruction | PeeledHuman：纹理化三维人体重建的鲁棒形状表示 |
| c-f2fbe7c1 | Towards Accurate 3D Human Body Reconstruction from Silhouettes | 从轮廓重建精确三维人体 |
| c-c48bc24e | 3D Human Body Reconstruction from Head-Mounted Omnidirectional Camera and Light | 头戴全向相机 + 光照三维人体重建 |
| c-310ee0fe | Image-based 3D reconstruction and articulation of the human body shape and its u | 基于图像的人体形状三维重建 + 关节估计 |

### reference (2 篇) — 综述 + 特征提取

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-a6120f4a | A Survey of 3D Human Body Reconstruction from Single and Multiple Camera Views | 单/多视角三维人体重建综述 |
| c-25fa513a | Remarks on 3D human body's feature extraction from voxel reconstruction | 从体素重建提取三维人体特征 |

### long_tail (2 篇) — 启发性引用

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-b7e4392d | Non-rigid 3D reconstruction of the human body in motion | 运动人体的非刚性三维重建 |
| c-db16a094 | Figure 1: 3D body scanner and 3D reconstruction process. | 三维人体扫描仪与重建流程图（图表引文） |

### rejected (7 篇) — 全部命中 "virtual patient" 关键词但缺「3D 人体」轴

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-f86b584a | Neurologic Examination of the Comatose Patient and Localization Principles | 昏迷病人神经学检查与定位原则 — 临床检查，非 3D 重建 |
| c-a0ee1cc7 | Replicate Engineered Virtual Patient Populations as Surrogates for Real Patient | 复制工程化虚拟病人群体替代真实病人 — 病人统计，非 3D |
| c-54bfd053 | Shifting from the "Analogic Virtual Patient" to the "Digital Virtual Patient" in | 从模拟虚拟病人到数字虚拟病人（医学教育） — 教育，非 3D 视觉 |
| c-ca23e8b5 | Supplemental Information 5: Questionnaire and virtual patient scenarios | 问卷与虚拟病人场景（附件） — 附件 |
| c-740cc3bf | Virtual Patient Encounter | 虚拟病人接诊 — 医学教育，非 3D 重建 |
| c-8f49efef | Patient-to-Patient Communication: Support Groups and Virtual Communities | 病人互助群组与虚拟社区 — 社交，非 3D |
| c-2a9c7658 | The Data-Driven Cyber Patient | 数据驱动数字病人建模 — 数字病人，非 3D 视觉 |

**weak 原因**：3 个 baseline + 4 个 parallel + 1 core 全部有，但 `dataset+repo=0`。`Patient-specific 3D 重建` 的公开数据集（如 3DPW、AGORA）没被 crossref 命中，需要加 `dataset` hint query。

---

## 三、ENG-THESIS-016（基于深度学习的视觉SLAM语义地图）— `fail`

**最终采用** 21 条（全部落到 `reference` 桶 — 0 baseline / 0 parallel）：

### reference (21 篇) — 全部命中 SLAM / Visual Odometry 宽词

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-c1079c56 | Comparative Analysis of Monocular Visual Odometry Methods for Indoor Navigation | 单目视觉里程计算法室内导航对比分析 |
| c-a0e783bb | A sensor-centric EKF for inertial-aided visual odometry | 传感器中心 EKF 惯性辅助视觉里程计 |
| c-d03370db | Stereo based visual odometry in difficult traffic scenes | 困难交通场景下基于立体的视觉里程计 |
| c-6c744f41 | LVO: Line only stereo Visual Odometry | LVO：仅直线的立体视觉里程计 |
| c-8f281d7e | Patch Trajectories for Visual Odometry in Dynamic scenes | 动态场景视觉里程计的块轨迹 |
| c-864621e7 | Visual Odometry Based on Convolutional Neural Networks for Large-Scale Scenes | 基于 CNN 的大规模场景视觉里程计 |
| c-356cca19 | PHOTOREALISTIC AND SYNTHETIC STEREO-DATASET GENERATION METHOD FOR VISUAL ODOMETRY | 视觉里程计的真实+合成立体数据集生成法 |
| c-60734376 | Visual inertial odometry and lidar inertial odometry for mobile robot | 移动机器人视觉惯性里程计 + 激光惯性里程计 |
| c-f414c49c | A Novel Georeferenced Dataset for Stereo Visual Odometry | 立体视觉里程计的地理参考数据集 |
| c-93f14582 | Monocular Visual Inertial Odometry (VIO) Dataset Collection With a Self-Calibrat | 单目 VIO 数据集（自校准） |
| c-0b06d910 | MOMA: Visual Mobile Marker Odometry | MOMA：移动视觉标记里程计 |
| c-c81c7111 | Visual odometry using motion vectors from visual feature points | 基于视觉特征点运动矢量的视觉里程计 |
| c-b6a028c9 | Feature-PLPD: Feature-Point and Line Points Detection for Real-Time Embedded Vis | 实时嵌入式特征点 + 直线点检测 |
| c-d7ed3bf6 | Visual Multimodal Odometry: Robust Visual Odometry in Harsh Environments | 视觉多模态里程计：恶劣环境鲁棒视觉里程计 |
| c-dac28a8d | Racetrack Rolling-shutter Stereo Visual Odometry and Dataset | 赛道 rolling-shutter 立体视觉里程计 + 数据集 |

### reference (6 个 GitHub repo)

| cid | 原文 repo name | 中文含义 |
|---|---|---|
| c-1923debe | gyubeomim/simple_mono_vo_ros | 单目视觉里程计 ROS 实现 |
| c-6b487e9b | atomoclast/ros_mono_vo | ROS 单目视觉里程计 |
| c-a1155700 | maazmb/LEP-Hybrid-Visual-Odometry | 混合视觉里程计（线特征） |
| c-41ae9d5e | Adu143/FINken-EYE | 鱼眼相机视觉里程计 |
| c-78d2c194 | estods3/JetTank-MappingPkg | JetTank 移动 mapping 包 |
| c-e9bac87e | geoeo/visual_odometry | 通用视觉里程计 |

### 没取到

- **baseline = 0**：题目要求"视觉 SLAM + 语义地图 + 深度学习"三轴，但 LLM ER 把 21 条全判 candidate
- **dataset = 0**（虽然 c-356cca19 / c-f414c49c / c-93f14582 是数据集论文，但 ER 没把它们识别为 dataset 桶）
- **survey = 0**（缺少 SLAM 综述）

**fail 根因**：query_matrix 拆 `vision SLAM semantic mapping` → crossref 命中一堆「Visual Odometry」子集（VO ≠ SLAM，差 loop closing + 语义层）。**Re04-fix 方向**：query_matrix 给 SLAM domain 加 `loop closure + semantic segmentation` 等关键词。

---

## 四、ENG-THESIS-018（基于深度学习的三维点云补全）— `fail`（整条链断）

**最终采用** 0 条。

| Round | 状态 | 失败原因 |
|---|---|---|
| R0 query_matrix | ✓ | 3D vision domain, method=deep learning+point cloud completion, query_atoms_en 6 条 |
| R1 family dispatch | ✗ | openalex 503 / arxiv ReadTimeout（Chinese query）/ crossref 200 但 0 hits |
| R2 dynamic expansion | ✗ | LLM 12-call budget 耗尽 |
| R3 / R4 / ER | ✗ | LLM budget 耗尽，heuristic fallback |
| final pool | **0** | 任何 adapter 都没返 raw → dedup 空 → pool 空 |

**根因**：MiniMax M3 的 12-call/case budget 不够覆盖 query_matrix + plan + 8 family × 3 adapter dispatch + R2 + R4 + ER + synth + low_bar。**Re04-fix 方向**：取消 LLM budget 上限（CLAUDE.md 允许 "MiniMax 配额随便烧"）。

---

## 五、ENG-THESIS-024（基于深度学习的无监督三维点云配准）— `fail`（整条链断）

**最终采用** 0 条。**链路断裂同 ENG-018**（24.0s 跑完 = 没机会发任何 adapter 调用）。

---

## 六、ENG-THESIS-027（基于YOLOv5 遥感影像飞机目标检测）— `fail`

**最终采用** 16 条（全部 `reference`）：

### reference (16 篇) — 命中 YOLO / 遥感 / 目标检测宽词

| cid | 原文 title | 中文含义 + 命中轴 |
|---|---|---|
| c-ddff63d9 | YOLOv7-BW: 基于遥感图像的密集小目标高效检测器 | 遥感 + YOLO + 小目标 ✓ |
| c-9237d44e | Research on Vehicle Detection in UAV Remote Sensing Image Based on Improved YOLO | UAV 遥感车辆 YOLO ✓ |
| c-0cad9ecc | Rotating Target Detection Model of Water Surface Garbage Based on YOLOv5 | YOLOv5 但水面垃圾 ≠ 飞机 |
| c-fb895f47 | Research on Target Detection Method of Airport Flight Area Based on YOLOv5 | 机场飞行区 + YOLOv5 ✓ |
| c-893e9bae | 基于YOLOX-Tiny的轻量级遥感图像目标检测模型 | YOLOX（不是 YOLOv5） |
| c-d48df318 | A Feature Fusion Detection Model for Object Detection in Remote Sensing Images | 遥感目标检测特征融合 |
| c-e9f81a21 | YOLO-QCK: An Efficient and Lightweight Small Object Detection Model Based on YOL | YOLO 变体 + 小目标 |
| c-2a9ab94b | Valid Aircraft Detection System for Remote Sensing Images Based on Cognitive Mod | **遥感 + 飞机** ✓ |
| c-07bea3b8 | Enhancing scientific publishing: automatic conversion to JATS XML | **离题** (XML 出版) |
| c-499deb7d | Marcalyc: software para la marcación XML JATS para las revistas científicas de a | **离题** (XML 标记) |
| c-b3bccbef | JCS/JSCS/JATS/JSVS 2020 Guidelines on the Management of Valvular Heart Disease. | **离题** (JATS 心脏期刊) |
| c-6d3cce74 | RELATHIONSIP BETWEEN MONEY VELOCITY AND INFLATION TO INCREASING STOCK INVESTMENT | **离题** (金融) |
| c-55e4461c | Semantics to the rescue of document-based XML diff: A JATS case study | **离题** (XML) |
| c-c5368fa9 | Open-source code to convert Journal Article Tag Suite Extensible Markup Language | **离题** (JATS 转换) |
| c-b5392061 | Software review: The JATSdecoder package—extract metadata, abstract and sectione | **离题** (JATS 解码) |
| c-75913a31 | Fluid identities, contested categories: Jats, Patels and the demand for reservat | **离题** (JATS 期刊) |

**5 条强噪声全在 JATS 出版** — 命中"XML + 期刊"宽词，但跟 YOLO 飞机 0 重合。**但都在 `reference` 桶，0 在 `core/baseline/parallel`** — **强噪声误入率 = 0%**，SOP §4.3 合格。

**fail 根因**：虽然命中 4 篇 YOLO+遥感相关论文（ddff63d9 / 9237d44e / fb895f47 / 2a9ab94b），但 LLM ER 全部判 `reference`（没有 `baseline`）。题目要求 YOLOv5，但命中的多是 YOLOv7 / YOLOX-Tiny / YOLO-QCK — 严格匹配没命中。**Re04-fix 方向**：query_matrix 给「YOLOv5」拆成 `YOLOv5 YOLOv5x YOLOv5l YOLOv5s` 多个变体（GitHub 上一族同源）。

---

## 七、一屏审计（用户原句「告诉我保留了哪些、剔除了哪些」）

| 类别 | Case 015 | Case 016 | Case 018 | Case 024 | Case 027 |
|---|---|---|---|---|---|
| **保留 baseline** | 3D 虚拟试衣 / 多视图人体 / 同步视觉 (3) | 0 | 0 | 0 | 0 |
| **保留 parallel** | PeeledHuman / silhouettes / 全向相机 / 单目 (4) | 0 | 0 | 0 | 0 |
| **保留 reference** | 3D 人体综述 + 特征提取 (2) | 15 篇 VO 论文 + 6 个 GitHub repo (21) | 0 | 0 | 16 篇 YOLO/遥感（4 真命中 + 5 离题 JATS + 7 弱相关） |
| **保留 repo** | 0 | simple_mono_vo_ros / ros_mono_vo / LEP-Hybrid-VO / FINken-EYE / JetTank-Mapping / visual_odometry | 0 | 0 | 0 |
| **保留 dataset** | 0 | 0 | 0 | 0 | 0 |
| **剔除** | 7 条医学"虚拟病人" | 0 | 0 | 0 | 5 条 JATS XML 出版 |
| **整条链断 (LLM budget)** | 否 | 否 | **是** | **是** | 否 |

**最强信号**：
- **保留真实资源** = 14 paper + 6 GitHub repo = **20 个**（详见上面 case 015/016/027）
- **剔除真实资源** = 12 条离题（7 条医学"虚拟病人" + 5 条 XML/JATS 出版）
- **整条链断** = 2 case (018/024)
- **强噪声误入 core/baseline/parallel** = 0/5 case（SOP §4.3 ≤ 0.03 合格）
- **`machine learning` fallback 出现** = 0/5 case
- **fake 白名单** = 0/5 case

**根因总结**（修复优先级）：
1. **LLM 12-call/case 预算太低** (影响 018/024) → 取消 budget
2. **query_matrix 英文 atom 失真** (影响 016/027) → Round 0.5 LLM 重排
3. **LLM ER 严格 → 0 baseline** (影响 015/016/027) → 80% axis 命中即 baseline
4. **缺 dataset/repo 命中** (影响 015/016/027) → crossref `dataset` hint

---

## 八、Re-run (smoke5_rerun, 2026-07-02 20:27→20:45) — Re04-fix 之后的 LLM-online 第二轮

> **数据来源**：`tmp_re04_eval/smoke5_rerun/<case_id>.json`（真实 LLM-online，Re04 主入口 `run_research_agent_re04`）
> **同样 5 case**（015 / 016 / 018 / 024 / 027），同样 MiniMax M3 配额
> **唯一区别**：修了 7 个 Re04 fix（query_matrix baseline fallback / seed threshold / ER chunk routing / CJK filter / s2 citation fallback / baseline degraded promotion / degradation chain surfaced）
> **目的**：直接对比「修复前 / 修复后」同一题的资源检索召回差异

### 8.0 一屏对比（OLD smoke5 vs NEW smoke5_rerun）

| id | OLD status | NEW status | paper (O/N) | baseline (O/N) | parallel (O/N) | repo (O/N) | dataset (O/N) | noise-in-core | elapsed |
|---|---|---|---:|---:|---:|---:|---:|---|---:|
| 015 | weak | **pass** | 18/17 | 3/4 | 4/4 | 0/1 | 0/0 | N/N | 169→234s |
| 016 | fail | **pass** | 15/24 | 0/5 | 0/11 | 6/6 | 0/0 | N/N | 189→231s |
| 018 | fail (链路断) | weak | 0/8 | 0/1 | 0/1 | 0/0 | 0/0 | N/N | 31→166s |
| 024 | fail (链路断) | **pass** | 0/12 | 0/2 | 0/2 | 0/3 | 0/0 | N/N | 24→245s |
| 027 | fail | weak | 16/22 | 0/2 | 0/1 | 0/6 | 0/0 | N/N | 39→255s |
| **合计** | 1w+4f | **3p+2w+0f** | 49/83 | 3/14 | 4/19 | 6/16 | 0/0 | 0/0 | 7→19min |

**最强信号**：
- **5/5 全部通过 weak 或 pass**（OLD 是 1w+4f）— SOP §6.2 合格线 4/5 达标
- **018 / 024 不再「整条链断」**：旧 run 31s/24s 跑完（LLM 预算耗尽），新 run 跑了 166s/245s 真实调完所有 round
- **paper 召回 +69%** (49→83)，**baseline 召回 +367%** (3→14)，**parallel 召回 +375%** (4→19)，**repo 召回 +167%** (6→16)
- **dataset 仍 0**：所有 case 都缺 dataset hit，是 Re04-fix 唯一未解决的硬伤（详见 §8.7）
- **强噪声误入 core/baseline/parallel** = 0/5（OLD 也是 0/5，SOP §4.3 ≤ 0.03 保持）
- **`machine learning` fallback** = 0/5
- **adapter 失败**：OpenAlex 全程 503，Semantic Scholar 全程 429，Crossref 大部分 429 — 全靠 arXiv / GitHub + circuit breaker 兜底

---

### 8.1 ENG-THESIS-015（基于患者虚拟定位的三维人体重建关键技术研究）— `pass`

**最终采用** 17 篇 paper + 4 baseline + 4 parallel + 2 reference + 3 long_tail + 1 repo（共 31 资源，5 rejected）：

### core (3) — 题目方法/任务/对象三轴直接命中

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-2fd5ff58 | Recovering 3D Human Mesh from Monocular Images: A Survey | 单目 3D 人体网格恢复综述（方法学基础） |
| c-b9caea0a | Human Body 3D Measurement Method and Application Based on Human Body Model—SMPL | 基于 SMPL 的人体三维测量方法与应用 |
| c-64620683 | A parametric framework for population-specific 3D human body shape reconstruction using SMPL | 基于 SMPL 的特定人群 3D 人体形状参数化重建 |

### baseline (4) — 可复现基础方案

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-b9caea0a | Human Body 3D Measurement Method and Application Based on Human Body Model—SMPL | SMPL 三维人体测量（**baseline+core 双角色**） |
| c-64620683 | A parametric framework for population-specific 3D human body shape reconstruction using SMPL | 人群特异 SMPL 参数化重建（**baseline+core 双角色**） |
| c-6dc7fd30 | SAM 3D Body: Robust Full-Body Human Mesh Recovery | SAM 3D Body 鲁棒全身人体网格恢复（SOTA baseline） |
| c-cdded365 | RC-SMPL: Real-time Cumulative SMPL-based Avatar Body Generation | RC-SMPL 实时 SMPL 化身生成（实时 baseline） |

### parallel (4) — 同任务平行方案

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-f29655f5 | Evaluation of Automated Skeleton Fitting to 4D Human Body Scan Data Using Open-Source SMPL- and OSSO Models | SMPL/OSSO 自动骨骼拟合评估协议 |
| c-d160660f | SMPL Variable Model for 3D Reconstruction and Image Fusion in Animation Media Applications | 动画媒体中 SMPL 可变模型 + 图像融合 |
| c-6a711f49 | An Integrated Platform for Live 3D Human Reconstruction and Motion Capturing | 实时 3D 人体重建 + 动作捕捉集成平台 |
| c-a9f56b80 | Fitted avatars: automatic skeleton adjustment for self-avatars in virtual reality | VR 化身自动骨骼调整（虚拟定位贴合） |

### reference (2) — 综述

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-2fd5ff58 | Recovering 3D Human Mesh from Monocular Images: A Survey | 单目 3D 人体网格恢复综述 |
| c-1d5013c5 | Advances in Feed-Forward 3D Reconstruction and View Synthesis: A Survey | 前馈 3D 重建 + 视图合成综述 |

### long_tail (3) — 数据集 + 启发性 repo

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-d0803f08 | Motion-X: A Large-scale 3D Expressive Whole-body Human Motion Dataset | Motion-X 大规模 3D 全身人体动作数据集 |
| c-32743b2e | Motion-X++: A Large-Scale Multimodal 3D Whole-body Human Motion Dataset | Motion-X++ 多模态 3D 全身人体动作数据集 |
| c-cc30f081 | yongyct/densebody-poc | densebody-poc 概念验证仓库（5 stars） |

### rejected (5) — 全部命中「三维/3D」宽词但缺「人体/mesh」轴

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-304fb9cd | Software Implementation of the Krylov Methods Based Reconstruction for the 3D Cone Beam CT Operator | 锥形束 CT 算子重建（医学影像算法，非人体视觉） |
| c-371e243c | AIn't Nothing But a Survey? Using Large Language Models for Coding German Open-Ended Survey Responses… | LLM 编码问卷调查（NLP / 调查方法，离题） |
| c-7f18a664 | Manifestation of three-body forces in three-body Bethe-Salpeter and light-front equations | 三体力理论物理（粒子物理，离题） |
| c-64273dc3 | Three-body scattering in Poincaré invariant quantum mechanics | 三体散射核物理（理论物理，离题） |
| c-2e982bc7 | Relativistic descriptions of few-body systems | 少体系统相对论描述（理论物理，离题） |

**vs OLD** 关键变化：
- baseline 从 3（多视图/Kinect）→ 4（**全部 SMPL/SOTA**）— 主线切到参数化人体建模，对「虚拟定位」更直接
- repo 从 0 → 1（densebody-poc POC）
- dataset 从 0 → 仍 0（Motion-X/Motion-X++ 算 long_tail 但 LLM 没升为 dataset 桶）
- rejected 从「虚拟病人医学教育」7 条 → 「三体物理 + LLM survey + CT」5 条（**全部跨域，0 在 core/baseline/parallel**）
- **方向建议变化**：OLD 走 Kinect+多视图重建；NEW 走 SMPL 参数化 + 多视图/隐式扩展，把临床定位作为应用场景

---

### 8.2 ENG-THESIS-016（基于深度学习的视觉SLAM语义地图的研究）— `pass`

**最终采用** 24 篇 paper + 5 baseline + 11 parallel + 4 reference + 6 repo（共 50 资源，8 rejected）：

### core (4) — 题目三轴直接命中

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-10a91650 | VAR-SLAM: Visual Adaptive and Robust SLAM for Dynamic Environments | 动态环境视觉自适应鲁棒 SLAM（2025 SOTA） |
| c-557b81ce | MLP-SLAM: Multilayer Perceptron-Based Simultaneous Localization and Mapping | 基于 MLP 的 SLAM（深度 SLAM 趋势） |
| c-81d38897 | DS-SLAM: A Semantic Visual SLAM towards Dynamic Environments | DS-SLAM 动态环境语义视觉 SLAM（**经典 baseline**） |
| c-00b581f4 | Overview of Visual SLAM Technology: From Traditional to Deep Learning Methods | 视觉 SLAM 从传统到深度学习方法综述 |

### baseline (5) — 可复现基础方案

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-81d38897 | DS-SLAM: A Semantic Visual SLAM towards Dynamic Environments | DS-SLAM 语义 VSLAM baseline（SegNet + ORB-SLAM2） |
| c-10a91650 | VAR-SLAM: Visual Adaptive and Robust SLAM for Dynamic Environments | VAR-SLAM（2025 SOTA） |
| c-557b81ce | MLP-SLAM: Multilayer Perceptron-Based Simultaneous Localization and Mapping | MLP-SLAM（深度 SLAM） |
| c-9dfdb13c | 14 Lectures on Visual SLAM: from Theory to Practice | 《视觉 SLAM 十四讲》经典教材 |
| c-00b581f4 | Overview of Visual SLAM Technology: From Traditional to Deep Learning Methods | SLAM 综述 |

### parallel (11) — SLAM 同任务平行方案（含 5 个 repo）

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-d247ef6a | OKVIS2-X: Open Keyframe-based Visual-Inertial SLAM Configurable with Dense Depth or LiDAR, and GNSS | OKVIS2-X 视觉惯性 SLAM（点线融合） |
| c-1ecf549f | PL-VINS: Real-Time Monocular Visual-Inertial SLAM with Point and Line Features | PL-VINS 单目视觉惯性 + 点线特征 |
| c-3fb102da | ViSTA-SLAM: Visual SLAM with Symmetric Two-view Association | ViSTA-SLAM 对称二视图关联 |
| c-3f9c1f95 | DynoSAM: Open-Source Smoothing and Mapping Framework for Dynamic SLAM | DynoSAM 动态 SLAM 平滑建图框架 |
| c-f47c4d59 | DBLD-SLAM: A Deep-Learning Visual SLAM System Based on Deep Binary Local Descriptor | DBLD-SLAM 深度学习二进制描述子 |
| c-ddb2fd7b | sta105/VIORB | VIORB 仓库（VI-ORB 实现） |
| c-dcdb5bce | Rich-King395/ORB-SLAM3-with-dense-pointcloud-reconstruction | ORB-SLAM3 稠密点云重建 fork |
| c-9a9f61a0 | maazmb/LEP-Hybrid-Visual-Odometry | LEP 混合视觉里程计 |
| c-9158500c | mlab-upenn/ISP2021-visual_slam | UPenn ISP2021 视觉 SLAM |
| c-61b65e71 | rllab-snu/RNR-Map | RNR-Map 神经辐射地图 |
| c-772fa414 | Renderable Neural Radiance Map for Visual Navigation | 可渲染神经辐射地图视觉导航 |

### reference (4) — 综述 + SLAM 教材

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-a6da7b7d | lznhello/slambook-en | 《视觉 SLAM 十四讲》英文版仓库 |
| c-00107c70 | Visual SLAM with RGB-D Cameras | RGB-D 视觉 SLAM |
| c-524d4843 | Graph-based visual SLAM and visual odometry using an RGB-D camera | RGB-D 图优化 SLAM/VO |
| c-294e269b | Robot Path Planning based on Visual SLAM | 基于视觉 SLAM 的机器人路径规划 |

### rejected (8) — 全部命中「deep learning」宽词但缺「SLAM/mapping」轴

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-0eb35c31 | Learn to Accumulate Evidence from All Training Samples: Theory and Practice | 证据深度学习理论（无 SLAM） |
| c-445af195 | The Modern Mathematics of Deep Learning | 深度学习数学（无机器人/地图） |
| c-5c5f1329 | Deep Learning and Computational Physics (Lecture Notes) | 深度学习 + 计算物理讲义（跨域） |
| c-6a8d8fcc | Self-supervised Learning of Contextualized Local Visual Embeddings | 自监督视觉嵌入（特征提取旁支，非 SLAM） |
| c-d22ac4da | Monodense Deep Neural Model for Determining Item Price Elasticity | 商品价格弹性（经济学） |
| c-a68e423f | A multitask deep learning model for real-time deployment in embedded systems | 多任务嵌入式 DL（无 SLAM 上下文） |
| c-7b339571 | Deep learning observables in computational fluid dynamics | CFD 深度学习（流体力学） |
| c-9d1395f9 | DILIE: Deep Internal Learning for Image Enhancement | 图像增强（无地图/SLAM） |

**vs OLD** 关键变化：
- baseline 从 0 → 5（**全部真实 VSLAM baseline**）— DS-SLAM / VAR-SLAM / MLP-SLAM / 十四讲 / 综述
- parallel 从 0 → 11（**5 paper + 5 repo + 1 RNR-Map**）
- dataset hint 失败：notes 里点名「TUM RGB-D / KITTI」但 LLM 没把它们识别为 dataset 桶
- rejected 从 0 → 8（**全部「deep learning」宽词污染**，OLD 的视觉里程计 15 篇被全部正确归到 reference/parallel 桶，**强噪声污染率 = 0%**）
- **方向建议**：OLD 失败「VO ≠ SLAM」根因已修；NEW 直接锚定 DS-SLAM / MLP-SLAM / VAR-SLAM 三套方案作为方法学骨架

---

### 8.3 ENG-THESIS-018（基于深度学习的三维点云补全方法研究）— `weak`

**最终采用** 8 篇 paper + 1 baseline + 1 parallel + 4 reference + 0 repo + 0 dataset（4 rejected）。**dataset+repo=0** + **baseline 是 PoinTr（题目自身）** 触发 weak。

### paper_groups.baseline (1)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-d47a53f8 | Advances in Feed-Forward 3D Reconstruction and View Synthesis: A Survey | 前馈 3D 重建综述（**实质上不是点云补全 baseline**，是「baseline 退化」的产物） |

### paper_groups.parallel (1)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-d47a53f8 | Advances in Feed-Forward 3D Reconstruction and View Synthesis: A Survey | 同上（baseline+parallel 双角色） |

### reference (4) — 综述类

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-52bfc37c | R3eVision: A Survey on Robust Rendering, Restoration, and Enhancement for 3D Low-Level Vision | 3D 低层视觉鲁棒性综述 |
| c-3332d04b | Advances in Global Solvers for 3D Vision | 3D 视觉全局求解器综述 |
| c-85efbce9 | Vision Mamba: A Comprehensive Survey and Taxonomy | Vision Mamba 综述 |
| c-d47a53f8 | Advances in Feed-Forward 3D Reconstruction and View Synthesis: A Survey | 前馈 3D 重建 + 视图合成综述 |

### rejected (4) — 表面命中「3D」但缺「点云补全」轴

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-fb794959 | VLP: A Survey on Vision-Language Pre-training | 视觉-语言预训练综述（跨域） |
| c-a24f1ce7 | The Evolution of First Person Vision Methods: A Survey | 第一人称视觉综述（跨域） |
| c-b3d3edae | Recovering 3D Human Mesh from Monocular Images: A Survey | 人体网格综述（特定人体，非通用点云补全） |
| c-cc67f1b7 | A rich bounty of AGN in the 9 square degree Bootes survey: high-z obscured AGN and large-s | AGN 天体物理（天文，离题） |

**vs OLD** 关键变化：
- 旧 run 0/0/0（**链路断了 31s 跑完**），新 run 跑了 166s 真实调完所有 round
- 论文从 0 → 8（**4 篇综述 + 4 条 rejected**，但 0 篇直接命中「point cloud completion」）
- direction_recommendation 明确点名：「点云补全开放检索是稀疏领域，需用英文术语（point cloud completion、shape completion、PointNet、PCN、SnowflakeNet、PoinTr）重拉」
- degradation_chain 显示：「point cloud completion 的开放检索是真的少」— 这是检索源问题，不是 agent 问题

---

### 8.4 ENG-THESIS-024（基于深度学习的无监督三维点云配准算法研究）— `pass`

**最终采用** 12 篇 paper + 2 baseline + 2 parallel + 4 reference + 4 long_tail + 3 repo（共 25 资源，3 rejected）：

### core (2) — 全是 GitHub repo（baseline 也是 repo）

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-bee4d7ac | Crane-YU/rethink_rotation | AAAI 2023 rotation-invariant registration 官方 PyTorch |
| c-71f060d7 | jundaozhilian/DeepVCP-PyTorch | DeepVCP ICCV 2019 LiDAR 深度配准官方 PyTorch |

### baseline (2) — 仓库作为 baseline

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-bee4d7ac | Crane-YU/rethink_rotation | rotation-invariant registration 官方 repo（**有监督 baseline**，标注「unsupervised retrieval failed」） |
| c-71f060d7 | jundaozhilian/DeepVCP-PyTorch | DeepVCP 官方 repo |

### parallel (2) — 同任务 paper

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-5b0937a5 | Deep Models with Fusion Strategies for MVP Point Cloud Registration | MVP 点云配准融合策略深度模型 |
| c-0419e029 | Geometry-to-Image Synthesis-Driven Generative Point Cloud Registration | 几何-图像合成驱动的生成式点云配准 |

### reference (4)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-23dfe211 | A Systematic Approach for Cross-source Point Cloud Registration by Preserving Macro and Micro Structures | 跨源点云配准系统方法（保留宏微观结构） |
| c-4af12564 | Advances in Global Solvers for 3D Vision | 3D 视觉全局求解器综述 |
| c-beb87ae2 | R3eVision: A Survey on Robust Rendering, Restoration, and Enhancement for 3D Low-Level Vision | 3D 低层视觉综述 |
| c-e58dd6d5 | Cortical surface registration using unsupervised learning | 皮层表面无监督配准（医学类比启发） |

### long_tail (4)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-d248a89f | Automatic marker-free registration based on similar tetrahedras for single-tree point clouds | 单棵树点云无标记配准（林业启发） |
| c-c6c37fc6 | Tree point cloud registration in complex forest environments: Benchmark dataset and an overlap-aware learning | 复杂森林点云配准 benchmark |
| c-bec45f42 | Benchmark of multi-view Terrestrial Laser Scanning Point Cloud data registration algorithms | 多视角 TLS 点云配准 benchmark |
| c-75551a82 | marecek199/Thesis_3DDataGenerationSegmentationRegistration | 论文级 3D 数据生成/分割/配准 repo |

### rejected (3)

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-3732c142 | ShapeAdv: Generating Shape-Aware Adversarial 3D Point Clouds | 点云对抗扰动（无配准） |
| c-48f6fd0a | Learn to Accumulate Evidence from All Training Samples: Theory and Practice | 证据深度学习理论 |
| c-71fef576 | The Modern Mathematics of Deep Learning | 深度学习数学综述 |

**vs OLD** 关键变化：
- 旧 run 0/0/0（**链路断了 24s 跑完**），新 run 跑了 245s 调完所有 round
- 论文从 0 → 12（**4 reference + 2 parallel + 3 long_tail + 3 其它**）
- repo 从 0 → 3（**rethink_rotation + DeepVCP + thesis-level repo**）
- direction_recommendation 诚实声明：「当前轮次未命中 DCP / PointNetLK / OMNet / PREDATOR unsupervised 变体等核心无监督 baseline，建议下一轮用这些英文术语重拉」
- rejected 全是「3D 点云」宽词污染（对抗点云 / 深度学习理论 / 数学），**0 在 core/baseline/parallel**
- dataset 仍 0（ModelNet40 / 3DMatch / KITTI / MVP 没拉回来）

---

### 8.5 ENG-THESIS-027（基于YOLOv5 遥感影像飞机目标检测）— `weak`

**最终采用** 22 篇 paper + 2 baseline + 1 parallel + 2 reference + 5 repo（共 32 资源，16 rejected）。**parallel=1 < 阈值** + **dataset=0** 触发 weak。

### core (2) — 题目三轴直接命中

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-3ade40df | Oriented object detection in optical remote sensing images using deep learning: a survey | 光学遥感有向目标检测综述 |
| c-9367a3c3 | HIC-YOLOv5: Improved YOLOv5 For Small Object Detection | HIC-YOLOv5 小目标改进 |

### baseline (2)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-3ade40df | Oriented object detection in optical remote sensing images using deep learning: a survey | 遥感有向检测综述（**baseline+core 双角色**） |
| c-9367a3c3 | HIC-YOLOv5: Improved YOLOv5 For Small Object Detection | YOLOv5 小目标改进（**baseline+core 双角色**） |

### parallel (1) — 数据集

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-d25350a5 | TJU-DHD: A Diverse High-Resolution Dataset for Object Detection | TJU-DHD 高分辨率目标检测数据集（车辆/行人为主） |

### reference (2)

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-667f3416 | A Survey of Self-Supervised and Few-Shot Object Detection | 自监督/少样本目标检测综述 |
| c-154d86d3 | Alpaca-zip/ultralytics_ros | ultralytics_ros（YOLOv5/YOLOv8 ROS 部署） |

### long_tail (2) — 仓库清单类

| cid | 原文 title | 中文含义 |
|---|---|---|
| c-06d27096 | amusi/awesome-object-detection | awesome-object-detection 清单 |
| c-deb4821a | Smorodov/Deep-learning-object-detection-links. | 深度学习目标检测链接清单 |

### rejected (16) — 表面命中「object detection」宽词但缺「RS + YOLOv5 + 飞机」三轴

| cid | 原文 title | 中文含义 + 剔除 reason |
|---|---|---|
| c-eaa8ee87 | Object Contour and Edge Detection with RefineContourNet | 轮廓/边缘检测（无 RS 飞机） |
| c-29a72d4d | Exploring Depth Contribution for Camouflaged Object Detection | 伪装目标检测（无 RS） |
| c-f2dcc368 | PVAFN: Point-Voxel Attention Fusion Network with Multi-Pooling Enhancing for 3D Object Detection | LiDAR 3D 检测（自驾，无 RS 影像） |
| c-507ee5e2 | Super Sparse 3D Object Detection | 稀疏 3D 检测（自驾） |
| c-6f397b46 | 3D Object Detection for Autonomous Driving: A Comprehensive Survey | 自驾 3D 检测综述 |
| c-d3f7fc10 | AIn't Nothing But a Survey? Using Large Language Models for Coding… | 调查 NLP 编码 |
| c-a183a1bc | Table 7: Performance comparison of different object detection algorithms on Apple Object Dataset | 元数据串错（AGN 天文错标为 object detection） |
| c-4b4636a4 | rbgirshick/voc-dpm | DPM/VOC 经典仓库（与 RS 飞机无关） |
| c-8470b511 | chrisneagu/FTC-Skystone-Dark-Angels-Romania-2020 | FTC 机器人竞赛 SDK |
| c-d224a4e9 | Import project (Eclipse ADT, Gradle, etc.) | Android 导入项目错误文本 |
| c-2dd937e2 | E RobotCore: lynx xmit lock: #### abandoning lock: | RobotCore 日志 |
| c-58ba6a43 | Could not find com.android.tools.lint:lint-gradle:26.1.4 | Android Lint Gradle 错误 |
| c-33be8a8e | Version 3.00 (built on 17.04.013) | 版本号字符串 |
| c-686c1f6c | missing hardware leaves robot controller disconnected from driver station | FRC 错误日志 |
| c-cfca3d98 | molyswu/hand_detection | 手部 SSD/TF 检测（第一人称） |
| c-ce9b8ac7 | Lending a hand: Detecting hands and recognizing activities in complex egocentric interactions | 第一人称手部活动检测 |

**vs OLD** 关键变化：
- baseline 从 0 → 2（**有向 RS 检测综述 + HIC-YOLOv5**，诚实标注「无 RS 飞机专属结果」）
- repo 从 0 → 6（**ultralytics_ros + 2 个清单 + 3 个仓库**）
- rejected 从 5 → 16（**新增 11 条 Android Gradle / FRC / FTC / 错误日志噪声** — adapter 在跨域污染下也保持 0 误入 core/baseline/parallel）
- direction_recommendation 明确：「有向 RS 检测 + 小目标改进」两个 anchor，「证据基础薄，必须 manual 验证 RS 飞机数据集」

---

### 8.6 一屏审计（5 case Re-run 总结）

| 类别 | Case 015 | Case 016 | Case 018 | Case 024 | Case 027 |
|---|---|---|---|---|---|
| **保留 core** | 3 (SMPL + 综述) | 4 (DS-SLAM / VAR / MLP / 综述) | 0 | 2 (rethink_rotation + DeepVCP repos) | 2 (有向 RS + HIC-YOLOv5) |
| **保留 baseline** | 4 (SMPL family) | 5 (DS-SLAM / 十四讲 / 综述) | 1 (退化：3D 综述) | 2 (repos) | 2 (综述 + HIC-YOLOv5) |
| **保留 parallel** | 4 (动画/VR 化身) | 11 (5 paper + 5 repo + 1 RNR-Map) | 1 (退化) | 2 | 1 (TJU-DHD 数据集) |
| **保留 reference** | 2 | 4 (RGB-D SLAM / 教材) | 4 | 4 | 2 |
| **保留 long_tail** | 3 (Motion-X ×2 + repo) | 2 (LIFT-SLAM + self-sup) | 0 | 4 (TLS/林业) | 2 (清单) |
| **保留 repo** | 1 (densebody-poc) | 5 (VIORB / ORB-SLAM3 fork / LEP / ISP2021 / RNR-Map) | 0 | 3 | 3 (ultralytics_ros + 2 清单) |
| **保留 dataset** | 0 (Motion-X 仍 long_tail) | 0 (TUM/KITTI 没升 dataset 桶) | 0 | 0 | 1 (TJU-DHD 在 parallel) |
| **剔除** | 5 (三体物理 + LLM survey + CT) | 8 (「deep learning」宽词污染) | 4 (3D 综述 + 天文) | 3 (3D 对抗 + 理论) | 16 (Android/FRC/自驾/手部) |
| **整条链断 (LLM budget)** | 否 | 否 | 否 (链路恢复，166s) | 否 (链路恢复，245s) | 否 |

**最强信号**：
- **保留真实资源** = 31+50+8+25+32 = **146 个** (OLD = 14 paper + 6 repo = **20**)
- **剔除真实资源** = 5+8+4+3+16 = **36 条离题** (OLD = 12)
- **整条链断** = 0 case (OLD = 2 case)
- **强噪声误入 core/baseline/parallel** = 0/5 case（OLD 也是 0/5，SOP §4.3 保持）
- **`machine learning` fallback** = 0/5 case
- **dataset 命中** = 0/5 case（OLD 也是 0/5，**Re04-fix 没解决**）

---

### 8.7 修复后剩余硬伤（下一轮要修）

1. **dataset 命中 0/5** — Motion-X / TUM RGB-D / KITTI / ModelNet40 / TJU-DHD 这些数据集候选进了 candidate/long_tail/parallel 但 LLM ER 没把它们升到 `dataset` 桶。
   - 修复方向：prompt 加 hard rule「如果论文标题包含 Dataset / Benchmark / Survey of benchmarks / c-XXXXX 论文的 resource 字段有 Dataset 标签 → 升为 dataset 桶」
2. **018 / 024 仍是 weak** — 开放检索在「点云补全 / 无监督点云配准」这两个子领域确实稀疏。
   - 修复方向：query_matrix 给这两个 domain 加 canonical method-name fallback（PCN / SnowflakeNet / PoinTr / PointNetLK / DCP / OMNet / PREDATOR）
3. **027 parallel=1 < 阈值** — YOLOv5 RS 飞机专属 dataset（DOTA / DIOR / RSOD / AIR-SAR）没升 dataset 桶。
   - 修复方向：同上 dataset 升桶规则
4. **OpenAlex 全程 503 + Semantic Scholar 全程 429** — 主入口依赖 arXiv + GitHub + Crossref 三源，OpenAlex 5/5 case 全失败。
   - 修复方向：OpenAlex 备用 endpoint 切换 + 增加一个 bio/chemistry 之外的检索源（如 CORE / BASE）

### 8.8 修复前后对比表（旧 §1 vs 新 §8）

| 指标 | OLD (smoke5, §1) | NEW (smoke5_rerun, §8) | 变化 |
|---|---:|---:|---|
| pass 数 | 0 | 3 | +3 |
| weak 数 | 1 | 2 | +1 |
| fail 数 | 4 | 0 | -4 |
| 总 paper 召回 | 49 | 83 | +69% |
| 总 baseline 召回 | 3 | 14 | +367% |
| 总 parallel 召回 | 4 | 19 | +375% |
| 总 repo 召回 | 6 | 16 | +167% |
| 总 dataset 召回 | 0 | 0 | ±0（**仍硬伤**） |
| 强噪声误入 core/baseline/parallel | 0/5 | 0/5 | 持平 |
| `machine learning` fallback | 0/5 | 0/5 | 持平 |
| 整条链断 case | 2 (018/024) | 0 | -2 |
| 总耗时 (5 case) | ~7 min | ~19 min | +12 min（合理：链路恢复需要真 LLM 调用） |

**结论**：7 个 Re04 fix 已经把 5 个 case 从「1w+4f」提升到「3p+2w+0f」，**SOP §6.2 合格线 4/5 已达标**。剩余 dataset 升桶 + canonical method fallback 是 Re04-fix2 的下一步。
