# PaperAgent Re09 真实补证执行明细 (3 fail + 13 weak)

> 起草日：2026-07-03  
> 范围：Re09 SOP §6 Step 3 — 真实补证执行 trace  
> 数据源：`tmp_re04_eval/balanced40_re09_fresh/repair_plans.json` + `summary.json` per-case  
> 16 case 总数：3 fail + 13 weak (Re08 status)  
> 16 case 全部执行了 Re08 repair_plan 中的 query（pass_sample 24 case 不在本报告范围）

**数据汇总（Excel 友好）**：[PaperAgent_Re09_Balanced40_逐论文审计.csv](PaperAgent_Re09_Balanced40_逐论文审计.csv) (case-level, 40 cases × 40 cols)
**候选论文清单（Excel 友好）**：[PaperAgent_Re09_Balanced40_候选论文.csv](PaperAgent_Re09_Balanced40_候选论文.csv) (candidate-level, 246 candidates × 21 cols)

---

## 0. 补证执行总览 (16 case)

| 指标 | 数值 |
|---|---:|
| 总 executed queries | 246 |
| 总 new_candidates 插入 | 246 |
| 总 failed queries | 77 (其中 52 个含 `X` 占位符) |
| 总 verified_new_candidates | 0 (因为 run 走的是 `verify_candidate_offline` rule layer，rule 命中 → bucket_inserts 计数 +1，但 offline verdict 不被计入 `verification_verified_n`) |
| bucket_inserts: core_paper | 9 (全部 ENG-THESIS-075) |
| bucket_inserts: baseline | 12 (015=6, 005=6) |
| bucket_inserts: parallel_paper | 198 (15 case × 12 候选) |
| bucket_inserts: dataset | 27 (9 case × 3 候选) |
| bucket_inserts: repo | 0 |

> 注：runner 在 `_process_case` 中调用 `verify_candidate_offline` 算 verdict 但不更新 `verification_records` 字段，所以 `verification_verified_n` 仍为旧 Re08 数值；新增的 246 个 candidate 体现在 `fresh_new_candidates_n` 字段而非 `verification_verified_n`。

---

## 1. 3 个 Re08 FAIL case 详细 trace

### ENG-THESIS-043 — `fail → fail`

**Title**: 基于无人机平台的动态目标检测系统开发

**Re08 reason**: quarantined_candidates=2; datasets_present_but_no_topic_dataset; all_evidence_critical_consistency_error; scenario_axis_missing

**修复后 status**: fail (paper_n=3 < 4; effective_baseline=0; dataset+repo=0; no_dataset_or_data_gap_note)

**Adapter calls**: huggingface 4 + openalex 5 = 9 calls

**Queries executed (9)**:
- 5 × openalex (全部命中，至少 1 个 candidate / query)
- 4 × huggingface (全部 `no_results`)

**New candidates (15) — sample 3**:
| title | source_type | url |
|---|---|---|
| UAV-YOLOv8: A Small-Object-Detection Model Based on Improved ... | openalex | (空) |
| A Modified YOLOv8 Detection Network for UAV Aerial Image Rec... | openalex | (空) |
| YOLO-Drone: An Optimized YOLOv8 Network for Tiny UAV Object ... | openalex | (空) |

**Failed queries (4)**:
- `[huggingface] UAV aerial imagery X benchmark` → no_results
- `[huggingface] UAV aerial imagery dynamic object detection real-world dataset` → no_results
- `[huggingface] X UAV aerial imagery dataset` → no_results (×2)

**Bucket inserts**: `dataset=3, parallel_paper=12`

**Fresh elapsed**: 63.04s

---

### ENG-THESIS-075 — `fail → weak` ⬆ (唯一改善)

**Title**: 基于深度学习的混凝土路面裂缝检测研究

**Re08 reason**: quarantined_candidates=2; no_dataset_or_data_gap_note; core_n=1_but_no_effective

**修复后 status**: weak (effective_baseline=0 < 1; dataset+repo=0 < 1)

**Adapter calls**: arxiv 2 + openalex 5 + github 1 + huggingface 4 = 12 calls

**Queries executed (12)**:
- 2 × arxiv (命中 6 candidate)
- 5 × openalex (命中)
- 1 × github (no_results)
- 4 × huggingface (no_results)

**New candidates (21) — sample 3**:
| title | source_type | url |
|---|---|---|
| Oriented object detection in optical remote sensing images u... | arxiv | http://arxiv.org/abs/2302.10473v6 |
| Data-driven Detection and Evaluation of Damages in Concrete ... | arxiv | http://arxiv.org/abs/2501.11836v1 |
| Deep Domain Adaptation for Pavement Crack Detection... | arxiv | http://arxiv.org/abs/2111.10101v3 |

**Failed queries (5)**:
- `[huggingface] concrete pavement dataset benchmark` → no_results
- `[huggingface] concrete pavement X dataset collection` → no_results
- `[github] concrete pavement crack detection implementation github` → no_results
- `[huggingface] X concrete pavement dataset` → no_results (×2)

**Bucket inserts**: `core_paper=9, parallel_paper=12`

**Fresh elapsed**: 78.82s

**Why improved**: arxiv adapter hit 6 candidate with arxiv_id URL (URL 不空)，verify_candidate_offline 把这些升级为 core_paper，触发 `core_n >= 1` 阈值。

---

### ENG-THESIS-048 — `fail → fail`

**Title**: 面向动态环境的视觉SLAM研究

**Re08 reason**: all_evidence_critical_consistency_error; object_axis_missing; scenario_axis_missing

**修复后 status**: fail (paper_n=0 < 4; effective_baseline=0; dataset+repo=0; object+scenario axis missing)

**Adapter calls**: openalex 4 + github 1 + huggingface 4 = 9 calls

**Queries executed (9)**: 4 openalex + 1 github (no_results) + 4 huggingface (no_results)

**New candidates (12) — sample 3**:
| title | source_type | url |
|---|---|---|
| Dynamic Graph CNN for Learning on Point Clouds... | openalex | (空) |
| Deep high dynamic range imaging of dynamic scenes... | openalex | (空) |
| SIFT Flow: Dense Correspondence across Scenes and Its Applic... | openalex | (空) |

**Failed queries (5)**: 全部 huggingface + 1 github，4 个含 `X` 占位符

**Bucket inserts**: `parallel_paper=12`

**Fresh elapsed**: 53.0s

---

## 2. 13 个 Re08 WEAK case 详细 trace

### ENG-THESIS-015 — `weak → weak`

**Title**: 基于患者虚拟定位的三维人体重建关键技术研究

**Adapter calls**: openalex 6 + github 3 + huggingface 6 = 15

**New candidates (24) — sample 3**:
- `[openalex] ChestX-Ray8: Hospital-Scale Chest X-Ray Database...` (空 url)
- `[openalex] Semiempirical GGA-type density functional...` (空 url)
- `[openalex] Benchmarking Heterogeneous Electrocatalysts...` (空 url)

**Failed queries (7)**: 6 huggingface + 1 github，6 个含 `X`

**Bucket inserts**: `baseline=6, parallel_paper=18`

**Fresh elapsed**: 96.08s

---

### ENG-THESIS-028 — `weak → fail` ⬇

**Title**: 基于YOLOv5的绝缘子检测与缺陷识别方法研究

**Adapter calls**: openalex 5 + huggingface 4 = 9

**New candidates (15) — sample 3**:
- `[openalex] Insulator defect detection with deep learning: A survey` (空 url)
- `[openalex] Comparing YOLOv3, YOLOv4 and YOLOv5 for Autonomous Landing...` (空 url)
- `[openalex] Aircraft Target Detection in Remote Sensing Images...` (空 url)

**Failed queries (4)**: 4 huggingface 全部含 `X`

**Bucket inserts**: `dataset=3, parallel_paper=12`

**Fresh elapsed**: 53.21s

---

### ENG-THESIS-032 — `weak → fail` ⬇

**Title**: 基于深度学习的液晶屏表面缺陷检测方法研究

**Adapter calls**: openalex 4 + github 1 + huggingface 4 = 9

**New candidates (12) — sample 3**:
- `[openalex] Mini-LED, Micro-LED and OLED displays...` (空 url)
- `[openalex] State of the Art in Defect Detection Based on Machine Vision...` (空 url)
- `[openalex] The Detection of Visual Contrast in the Behaving Mouse...` (空 url)

**Failed queries (5)**: 4 huggingface + 1 github，4 个含 `X`

**Bucket inserts**: `parallel_paper=12`

**Fresh elapsed**: 63.38s

---

### ENG-THESIS-066 — `weak → fail` ⬇

**Title**: 面向自动驾驶中多模态融合感知算法的攻击和防御

**Adapter calls**: openalex 5 + huggingface 4 = 9

**New candidates (15) — sample 3**:
- `[openalex] Sensor and Sensor Fusion Technology in Autonomous Vehicles...` (空 url)
- `[openalex] A Survey of Deep Learning-Based Object Detection...` (空 url)
- `[openalex] A Survey of Autonomous Driving...` (空 url)

**Failed queries (4)**: 4 huggingface 全部含 `X`

**Bucket inserts**: `dataset=3, parallel_paper=12`

**Fresh elapsed**: 54.17s

---

### ENG-THESIS-080 — `weak → fail` ⬇

**Title**: 基于三维重建裂缝损伤检测算法研究

**Adapter calls**: openalex 5 + huggingface 4 = 9

**New candidates (15) — sample 3**:
- `[openalex] One-stage 3D profile-based pavement crack detection...` (空 url)
- `[openalex] UAV PHOTOGRAMMETRY FOR METRIC EVALUATION OF CONCRETE BRIDGE...` (空 url)
- `[openalex] Structure from Motion Point Clouds for Structural Monitoring...` (空 url)

**Failed queries (4)**: 4 huggingface 全部含 `X`

**Bucket inserts**: `dataset=3, parallel_paper=12`

**Fresh elapsed**: 55.47s

---

### ENG-THESIS-091 — `weak → fail` ⬇

**Title**: 基于云计算的输电线路缺陷检测平台

**Adapter calls**: openalex 4 + github 1 + huggingface 4 = 9

**New candidates (12) — sample 3**:
- `[openalex] Detection of 2019 novel coronavirus (2019-nCoV)...` (空 url)
- `[openalex] Early dynamics of transmission and control of COVID-19...` (空 url)
- `[openalex] Pathogenesis and transmission of SARS-CoV-2 in golden hamste...` (空 url)

**Failed queries (5)**: 4 huggingface + 1 github，4 个含 `X`

**Bucket inserts**: `parallel_paper=12`

**Fresh elapsed**: 68.40s

---

### ENG-THESIS-093 — `weak → fail` ⬇

**Title**: (输电线路绝缘子检测 - 类同 028)

**Adapter calls**: openalex 5 + huggingface 4 = 9

**New candidates (15) — sample 3**:
- `[openalex] A Method of Insulator Faults Detection in Aerial Images...` (空 url)
- `[openalex] YOLO v7-ECA-PConv-NWD Detects Defective Insulators...` (空 url)
- `[openalex] A Survey on Audio-Video Based Defect Detection Through Deep...` (空 url)

**Failed queries (4)**: 4 huggingface 全部含 `X`

**Bucket inserts**: `dataset=3, parallel_paper=12`

**Fresh elapsed**: 72.78s

---

### ENG-THESIS-096 — `weak → fail` ⬇

**Title**: (海上风机叶片缺陷检测)

**Adapter calls**: openalex 4 + github 1 + huggingface 4 = 9

**New candidates (12) — sample 3**:
- `[openalex] Materials for Wind Turbine Blades: An Overview...` (空 url)
- `[openalex] Wind-Turbine and Wind-Farm Flows: A Review...` (空 url)
- `[openalex] Machine learning methods for wind turbine condition monitori...` (空 url)

**Failed queries (5)**: 4 huggingface + 1 github，4 个含 `X`

**Bucket inserts**: `parallel_paper=12`

**Fresh elapsed**: 66.74s

---

### ENG-THESIS-005 — `weak → weak`

**Title**: (随机纹理背景小目标检测)

**Adapter calls**: openalex 7 + github 2 + huggingface 6 = 15

**New candidates (21) — sample 3**:
- `[openalex] Real-Time Flying Object Detection with YOLOv8...` (空 url)
- `[openalex] YOLO-SE: Improved YOLOv8 for Remote Sensing Object Detection...` (空 url)
- `[openalex] Automatic object detection for behavioural research using YO...` (空 url)

**Failed queries (8)**: 6 huggingface + 2 github，6 个含 `X`

**Bucket inserts**: `dataset=3, baseline=6, parallel_paper=12`

**Fresh elapsed**: 96.18s

---

### ENG-THESIS-014 — `weak → fail` ⬇

**Title**: (织物缺陷检测)

**Adapter calls**: openalex 5 + huggingface 4 = 9

**New candidates (15) — sample 3**:
- `[openalex] Automated Visual Defect Detection for Flat Steel Surface...` (空 url)
- `[openalex] State of the Art in Defect Detection Based on Machine Vision...` (空 url)
- `[openalex] Fabric Defect Detection in Textile Manufacturing: A Survey...` (空 url)

**Failed queries (4)**: 4 huggingface 全部含 `X`

**Bucket inserts**: `dataset=3, parallel_paper=12`

**Fresh elapsed**: 69.64s

---

### ENG-THESIS-040 — `weak → fail` ⬇

**Title**: (绝缘子检测 - 类同 028/093)

**Adapter calls**: openalex 5 + huggingface 4 = 9

**New candidates (15) — sample 3**:
- `[openalex] Insulator defect detection with deep learning: A survey...` (空 url)
- `[openalex] The YOLO Framework: A Comprehensive Review of Evolution...` (空 url)
- `[openalex] MTI-YOLO: A Light-Weight and Real-Time Deep Neural Network...` (空 url)

**Failed queries (4)**: 4 huggingface 全部含 `X`

**Bucket inserts**: `dataset=3, parallel_paper=12`

**Fresh elapsed**: 69.59s

---

### ENG-THESIS-073 — `weak → fail` ⬇

**Title**: (驾驶场景图像生成)

**Adapter calls**: openalex 5 + huggingface 4 = 9

**New candidates (15) — sample 3**:
- `[openalex] A survey on Image Data Augmentation for Deep Learning...` (空 url)
- `[openalex] A Survey of Deep Learning-Based Object Detection...` (空 url)
- `[openalex] Scenic: a language for scenario specification...` (空 url)

**Failed queries (4)**: 4 huggingface 全部含 `X`

**Bucket inserts**: `dataset=3, parallel_paper=12`

**Fresh elapsed**: 76.92s

---

### ENG-THESIS-089 — `weak → fail` ⬇

**Title**: (路面病害检测)

**Adapter calls**: openalex 4 + github 1 + huggingface 4 = 9

**New candidates (12) — sample 3**:
- `[openalex] Review of Pavement Defect Detection Methods...` (空 url)
- `[openalex] Automatic Road Pavement Assessment with Image Processing...` (空 url)
- `[openalex] RoADS: A Road Pavement Monitoring System for Anomaly Detecti...` (空 url)

**Failed queries (5)**: 4 huggingface + 1 github，4 个含 `X`

**Bucket inserts**: `parallel_paper=12`

**Fresh elapsed**: 71.27s

---

## 3. 关键发现 / runner 缺陷

1. **X 占位符过滤不完整** — runner 的 `_process_case` 用 `if "{" in query_str or "}" in query_str` 拦截占位符 query，但 Re08 repair plan 的 query 模板里用 bare `X`（如 `X dynamic scene dataset`），所以 52/77 failed query 是这种伪查询，从未真正送入 adapter。
2. **pass_sample 路径完全跳过补证** — runner 第 273 行 `if not repair_plan.get("repair_plan"): pass` 让 24 个 Re08 pass case 走 0-candidate 起点 eval，24/24 全部退化到 fail。
3. **openalex candidate 几乎全无 url** — 大部分 openalex 返回的 candidate 的 `url` 字段为空，导致 `verify_candidate_offline` 的 URL 校验不通过，但 runner 仍把 verdict 标记为 keep 并 bucket insert 计数。
4. **core_paper bucket 只在 075 命中** — 因为只有 075 通过 arxiv 拿到 6 个 arxiv_id URL（`http://arxiv.org/abs/...`）的 candidate，其他都依赖空 url 的 openalex 结果，无法升 core。
5. **adapter 实际调用分布**：arxiv 2（仅 075）+ openalex 78 + github 11 + huggingface 68，crossref 0、semantic_scholar 0。Huggingface 在所有 fail/weak case 中都被用作 dataset 查询但 0 命中，5/9 失败率。
6. **没有 verify_bucket_online 调用** — runner 用的是 `verify_candidate_offline`，没有把 LLM 接入在线核验。所以 `verification_verified_n` 字段没增加，新增的 246 candidate 不算 verified。
7. **runner 不读 Re08 raw dump** — 评估完全基于 fresh online 检索结果，让 Re08 已经在 baseline/parallel bucket 里的 600+ 候选全部丢失。
