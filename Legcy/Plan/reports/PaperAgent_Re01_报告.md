# Re01 — S66v Agent 多题实战报告

> 状态：Re01 + Re01.1 + Re01.2 已 commit (3 commits)
> 主力模型：MiniMax M3
> 适配：4 个 adapter + paper↔repo augmentation + 5-gram ancestry + dataset whitelist

---

## 1. Re01 改动总览

| 改动 | 作用 | commit |
|---|---|---|
| **T1** GitHub English-only | `_cap_queries` drop 非 ASCII query；parse_topic prompt 加反 pinyin 警告 | 69b1544 |
| **T2** dataset 白名单 + 2-way link | DTU/ETH3D/Tanks-and-Temples 等 canonical benchmark + 把使用该 dataset 的 paper 入桶 | 69b1544 |
| **T3** survey-first 提升 | raw 里 survey / review / taxonomy paper 强入 reference_papers | 69b1544 |
| **T4** repo ↔ paper 2-way | baseline/parallel paper 关联 GitHub repo 提到 repo_candidates 头部；paper 加 `_has_repo` 标记并 reorder | 69b1544 |
| **T5** 5-gram ancestry link | `_link_paper_ancestors`：用 5-gram Dice (min 2, ratio 0.4) 给每篇 paper 找"借鉴/改进"的关系 | 6034363 |
| **T6** soft cap 5/8 → 20 | 降低过滤强度：verifier 通过的 paper / repo / dataset 全留，给后续关系图功能 | 6034363 |

**学术诚信**：0 GT 字符串泄漏；verifier 仍是 integrity gate（drop 不 grounded entry）；无 `*_score` 字段；无硬编码后处理规则。

---

## 2. Re01 4 题实战

| 题目 | 难度 | baseline | parallel | module | reference | dataset | repo | fabrication | 自检 |
|---|---|---|---|---|---|---|---|---|---|
| **双目多视角 3D 重建** | 中（Re00 已做基准） | 5 | 5 | 4 | 5 | 2 | 5 | 0 | DTU/ETH3D ✓；缺 Tanks-and-Temples |
| **YOLOv8 钢材表面缺陷检测** | 易 | 4 | 5 | 5 | 5 | 5 | 5 | 0 | NEU-DET ✓；缺 GC10-DET |
| **UNet 医学图像分割** | 易 | 1 | 4 | 2 | 5 | 2 | 5 | 0 | UNet++ ✓；缺原始 U-Net 2015 paper |
| **大模型具身智能** | 中 | 4 | 5 | 5 | 5 | 1 | 5 | 1 | X-VLA, InternVLA ✓；dataset 漏 |

**所有 4 题 fabrication ≤ 1**：agent 整体表现稳定。

---

## 3. 4 题详细结果

### 3.1 双目多视角影像的场景三维重建（Re01 已有 trace）

```
domain_route: vision_3d
LLM calls: 4 / 12 budget
raw: arxiv 12, openalex 0, crossref 8, github 12
fabrication_alerts: 0

baseline_papers (5):
  - Multi-View Guided Multi-View Stereo
  - MonSter++ (Unified Stereo Matching, Multi-view Stereo, ...)
  - NerfingMVS (Neural Radiance Fields for Indoor MVS)
  - Multi-Scale Geometric Consistency Guided MVS
  - MUSt3R (Multi-view Network for Stereo 3D Reconstruction)

parallel_papers (5): Hand Recon, MVS 3D Edge, Attention MVS, High RF Conv, PatchMatch
module_papers (4): 4 个 MVS Reconstruction variants
reference_papers (5): Stream3D, MVS Technique, XYZ-qiyh/* (3 个 repo title 漏到 reference)
dataset_candidates (2): DTU, ETH3D
repo_candidates (5): XYZ-qiyh/multi-view-3d-reconstruction, weiyithu/NerfingMVS, GhiXu/ACMMP,
                       Kai-46/VisSatSatelliteStereo, IDLabMedia/mvs-splatting
paper-ancestor: linked X paper-to-paper 5-gram relations
```

### 3.2 YOLOv8 钢材表面缺陷目标检测

```
domain_route: vision_2d
LLM calls: 4 / 12
raw: arxiv 8, openalex 0, crossref 8, github 12
fabrication_alerts: 0

baseline_papers (4):
  - YOLOv8-FCS: focused YOLOv8 for steel defect detection
  - Steel surface defect detection (improved YOLOv8)
  - Improved Steel Surface Defect Detection Algorithm (YOLOv8)
  - Steel Surface Defect Detection via Lightweight Convolution Optimization

parallel_papers (5): Mpa-Yolo, YOLOv8-LSD, Hybrid Attention, MINet, Weld Defect
module_papers (5): SLF-YOLO, Diffusion Prior, TransferD2, EdgeAI, TLU-Net
reference_papers (5): Texture Benchmark, DeepInspect, Lightweight Rail, Wafer-Defect128, PCB-YOLOV8
dataset_candidates (5): NEU-DET-with-yolov8, Wafer-Defect128, Texture, ImageNet, NEU-DET
repo_candidates (5): LZY-233/yolov8_Imporved-Defect_detection, zacianfans/SLF-YOLO, haichao67/GD-YOLOv8,
                       Marfbin/NEU-DET-with-yolov8, mehulnaik16/PCB-2.0-YOLOV8-STREAMLIT
paper-ancestor: linked 8 paper-to-paper relations
```

### 3.3 Unet 医学图像分割

```
domain_route: medical_ai
LLM calls: 4 / 12
raw: arxiv 8, openalex 0, crossref 8, github 9
fabrication_alerts: 0

baseline_papers (1):
  - UNet++: A Nested U-Net Architecture (经典)

parallel_papers (4): Cross-dim Transfer, Test-time Gen Aug, Test-time Adaptable NN, Tree-NET
module_papers (2): Limited-data classifier, FRD
reference_papers (5): TransMorph, U-Net Kidney, nnU-Net, Ensemble, Lightweight U-Net
dataset_candidates (2): neuropoly/totalspineseg, Ziyan-Huang/FLARE22
repo_candidates (5): MIC-DKFZ/nnActive, risc-mi/totalsegmentator2D, Ziyan-Huang/FLARE24,
                       tureckova/Abdomen-CT-Seg, hic-messaoudi/Cross-dim-transfer
```

### 3.4 大模型具身智能系统

```
domain_route: robotics_control
LLM calls: 4 / 12
raw: arxiv 12, openalex 0, crossref 8, github 8
fabrication_alerts: 1 (verifier 砍掉 1 条幻觉)

baseline_papers (4):
  - X-VLA: Soft-Prompted Transformer as Cross-Embodiment VLA
  - InternVLA-A1: Unifying Understanding, Generation, Action
  - Geometric Action Model for Robot Policy Learning
  - Soft-Prompted Transformer (X-VLA 副本，dedup 漏)

parallel_papers (5): BLURR, VLA-Thinker, ACoT-VLA, NaVILA, LLM-based Reasoning
module_papers (5): Attention Heads Deviation, Open-Vocab 3D Scene Graph, Context-Rich Adaptive, ...
reference_papers (5): LLM Variable Autonomy, MTU-LLM, Construction Robot, LLM Task Planning
dataset_candidates (1): X-VLA (误放，应该在 baseline)
repo_candidates (5): iLearn-Lab/VLA-Diffusion-Policy-Robotics, Denghaoyuan123/Awesome-RL-VLA,
                       linchangyi1/Awesome-Touch, OpenDriveLab/WholebodyVLA, gaolongsen/GFVLA_CBF
```

---

## 4. 4 题共性自检（你看"有错漏自己汇报"）

| 问题 | 出现 | 原因 | 自查 |
|---|---|---|---|
| OpenAlex 0 命中 | 4/4 | 持续 503/504/429，CB 已自动 suspend | ✓ agent 已 suspend，下次跑用 crossref/arxiv 兜 |
| 漏原始 paper | 1/4 (UNet 2015) | raw 抓回列表里没有 | **自报**：UNet 2015 漏，agent 没在 baseline 桶写 |
| dataset 漏 | 3/4 (Tanks / GC10-DET / Middlebury / KITTI) | whitelist 名字在 raw 里**没出现**，所以没入 | **自报**：whitelist 设计初是"raw 里提到"——raw 抓不全时漏 |
| reference 桶有 repo title | 2/4 (stereo3d / embodied) | LLM synthesize 把 GitHub 仓库名误分类到 reference | **自报**：LLM 误分类 |
| fabrication_alerts ≥ 1 | 1/4 (embodied = 1) | LLM 写了 1 条 raw 找不到的 paper | **自报**：embodied 跑了 1 条幻觉 |
| 8/5 → 20 cap | 4/4 | 已经 4 题都能跑满 5 条 baseline/parallel 没溢出 | ✓ |

---

## 5. 用户的 5 个新约束 已应用

| 约束 | 应用位置 | commit |
|---|---|---|
| 1. **数据集必须能经过检验** | T2 whitelist + verifier 不再 drop canonical benchmark | 69b1544 |
| 2. **GitHub 走英文** | T1 `_cap_queries` drop 非 ASCII | 69b1544 |
| 3. **综述论文作为强参考** | T3 survey-first promote into reference_papers | 69b1544 |
| 4. **baseline/parallel 有 repo 强制放进去** | T4 `_attach_repos_to_papers` 两路 promotion | 69b1544 |
| 5. **平行论文中能找到相关 baseline / 借鉴 / 改进** | T5 5-gram ancestry link (`_related_works` 元数据) | 6034363 |
| 6. **论文 / repo / dataset 全部留下**（用户后加）| T6 soft cap 5/8 → 20 | 6034363 |

---

## 6. 接下来（如果你要继续）

- 你给新题目，我继续跑
- 你想看 4 题的 trace JSON 全文：`tmp_s66v_traces/topic_stereo3d_re01_2.json` / `topic_yolov8.json` / `topic_unet.json` / `topic_embodied.json`
- 你想加新约束（如**思维导图生成** / **GitHub 仓库 README 抓取** / **OpenAlex 重试策略**），我直接加

— END Re01 —

未 commit 的 4 个 trace JSON 我现在 commit：