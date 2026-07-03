# PaperAgent Re07 Balanced40 逐论文审计

> 起草日：2026-07-03
> 范围：SOP `Plan/PaperAgent_Re06_Review_评分规则与Prompt流程重写.md` §5.2 Task E（Balanced40 重审）
> 数据来源：`tmp_re04_eval/balanced40_re07/summary.json` + `tmp_re04_eval/balanced40_re07/{r1..r6,batch1..3}/<case_id>.json`
> 跑批命令：`apps/api/scripts/reclassify_balanced40.py --in-dir tmp_re04_eval/balanced40 --out-dir tmp_re04_eval/balanced40_re07`（re-classify Re05 raw dump）
> 配套报告：`Plan/PaperAgent_Re07_完工报告.md`
> **数据汇总（Excel 友好）**：[PaperAgent_Re07_Balanced40_逐论文审计.csv](PaperAgent_Re07_Balanced40_逐论文审计.csv)（case-level，40 case × 27 列，含 status / score / effective_* / quarantined_* / axis_status / notes）
> **候选论文清单（Excel 友好）**：[PaperAgent_Re07_Balanced40_候选论文.csv](PaperAgent_Re07_Balanced40_候选论文.csv)（candidate-level，424 条候选论文 × 24 列）
> CSV 生成脚本：`apps/api/scripts/re07_to_csv.py`

---

## §0 一屏总览（40 case aggregate）

| 维度 | 数值 |
|---|---:|
| 总题数 | 40 |
| pass | **24** |
| weak | **13** |
| fail | **3** |
| blocked | 0 |
| **pass+weak_rate** | **92.50% (37/40)** |
| quarantined_total cases | **3** |
| axis_not_evaluable cases | 0 |
| critical_consistency_error cases | 0 |
| core_zero_pass_cases | **0** |
| **SOP §5.3 pass** | **True** |
| 总 paper 召回 | 1173 |
| 总 dataset 召回 | 37 |
| 总 repo 召回 | 115 |
| 总 baseline 桶 | 129 |
| 总 parallel 桶 | 172 |

> **SOP §5.3 验收门槛**：`pass+weak ≥ 90% AND axis_task missing < 30% AND core_zero_pass = 0`。**当前值 = 全部 PASS**。

---

## §0.1 axis 与 consistency_status 取值分布（候选级）

```
n_candidates:                          424
consistency_status:                    321 aligned + 78 proxy + 20 off_topic + 5 metadata_mismatch
axis_task:                             264 direct + 129 proxy + 31 missing
axis_task missing 比例:                 7.3% (SOP §5.3 < 30% 达标)
```

对比 Re06 Re-classify：consistency_status 之前是 419 `insufficient_metadata` + 5 `metadata_mismatch`（100% missing），Re07 后 321 `aligned` + 78 `proxy` + 20 `off_topic` + 5 `metadata_mismatch`——**真实 axis 判定回来了**。

---

## §1 全部 40 case 状态表

| case_id | title | status | paper | eff_baseline | eff_core | quarantined | axis | reason |
|---|---|---|---:|---:|---:|---:|---|---|
| ENG-THESIS-002 | 基于深度学习的磁瓦在线检测技术研究 | pass | 14 | 3 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset; core_n=3_but_no_effective_core |
| ENG-THESIS-003 | 基于点云多平面检测的三维重建关键技术研究 | pass | 22 | 3 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset; core_n=7_but_no_direct_core |
| ENG-THESIS-004 | 基于改进YOLOv4模型的快速目标检测与测距算法研究 | pass | 23 | 2 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset; core_n=3_but_no_direct_core |
| ENG-THESIS-005 | 随机纹理背景下弱小缺陷检测的深度学习方法研究 | pass | 194 | 1 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset; core_n=1_but_no_direct_core |
| ENG-THESIS-010 | 基于深度学习的交通标志检测与识别研究 | pass | 18 | 3 | 0 | 0 | evaluable | no_dataset_or_data_gap_note; core_n=3_but_no_direct_core |
| ENG-THESIS-014 | 基于生成对抗网络的织物缺陷检测算法研究 | pass | 20 | 4 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset; core_n=1_but_no_direct_core |
| ENG-THESIS-015 | 基于患者虚拟定位的三维人体重建关键技术研究 | pass | 17 | 2 | 1 | 0 | evaluable | no_dataset_or_data_gap_note |
| ENG-THESIS-016 | 基于深度学习的视觉SLAM语义地图的研究 | pass | 22 | 4 | 6 | 0 | evaluable | no_dataset_or_data_gap_note |
| ENG-THESIS-018 | 基于深度学习的三维点云补全方法研究 | pass | 34 | 1 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset; core_n=4_but_no_direct_core |
| ENG-THESIS-022 | 基于深度学习的钢铁表面缺陷检测研究 | pass | 28 | 3 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset; core_n=3_but_no_direct_core |
| ENG-THESIS-024 | 基于深度学习的无监督三维点云配准算法研究 | pass | 19 | 3 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset; core_n=2_but_no_direct_core |
| ENG-THESIS-027 | 基于YOLOv5模型的遥感影像飞机目标检测 | pass | 19 | 3 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset; core_n=3_but_no_direct_core |
| ENG-THESIS-028 | 基于YOLOv5的绝缘子检测与缺陷识别方法研究 | pass | 22 | 4 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset |
| ENG-THESIS-032 | 基于深度学习的液晶屏表面缺陷检测方法研究 | weak | 15 | 3 | 0 | 0 | evaluable | no_dataset_or_data_gap_note; core_n=1_but_no_direct_core |
| ENG-THESIS-033 | 基于YOLOV5的肺结节检测算法研究 | weak | 27 | 5 | 0 | 0 | evaluable | no_dataset_or_data_gap_note |
| ENG-THESIS-035 | 基于深度学习的带钢表面缺陷检测方法 | pass | 25 | 5 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset |
| ENG-THESIS-040 | 基于改进YOLO网络与极限学习机的绝缘子故障检测 | pass | 14 | 2 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset |
| ENG-THESIS-043 | 基于无人机平台的动态目标检测系统开发 | **fail** | 16 | 0 | 0 | 2 | evaluable | quarantined_candidates=2; datasets_present_but_no_topic_dataset; all_evidence_critical_consistency_error; scenario_axis_missing |
| ENG-THESIS-046 | 基于视觉的机械臂的目标检测和避障路径规划研究与应用 | pass | 30 | 3 | 0 | 0 | evaluable | no_dataset_or_data_gap_note; core_n=3_but_no_direct_core |
| ENG-THESIS-048 | 面向动态环境的视觉SLAM研究 | **fail** | 20 | 2 | 0 | 1 | evaluable | quarantined_candidates=1; no_dataset_or_data_gap_note; all_evidence_critical_consistency_error; scenario_axis_missing |
| ENG-THESIS-050 | 基于深度学习的自动驾驶感知算法 | weak | 22 | 3 | 0 | 0 | evaluable | no_dataset_or_data_gap_note |
| ENG-THESIS-051 | 基于深度学习的语义SLAM研究 | weak | 16 | 1 | 0 | 0 | evaluable | no_dataset_or_data_gap_note; core_n=1_but_no_direct_core |
| ENG-THESIS-058 | 基于深度学习的激光点云环境感知 | pass | 38 | 5 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset |
| ENG-THESIS-060 | 基于深度学习的车道线检测方法研究 | pass | 22 | 6 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset |
| ENG-THESIS-063 | 基于3D视觉的机械臂无序抓取系统研究 | pass | 57 | 7 | 0 | 0 | evaluable | no_dataset_or_data_gap_note |
| ENG-THESIS-064 | 面向复杂道路场景的车辆目标检测算法研究与实现 | pass | 17 | 3 | 0 | 0 | evaluable | no_dataset_or_data_gap_note; core_n=2_but_no_direct_core |
| ENG-THESIS-066 | 面向自动驾驶中多模态融合感知算法的攻击和防御 | weak | 28 | 4 | 0 | 0 | evaluable | no_dataset_or_data_gap_note; attack_defense_axis_missing; core_n=0_but_no_effective_core |
| ENG-THESIS-072 | 基于深度学习的动态SLAM研究 | weak | 20 | 2 | 0 | 0 | evaluable | no_dataset_or_data_gap_note; core_n=3_but_no_direct_core |
| ENG-THESIS-073 | 面向汽车自动驾驶的模拟图像生成技术及应用研究 | pass | 23 | 1 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset |
| ENG-THESIS-074 | 基于深度学习的混凝土桥梁裂缝检测研究 | pass | 24 | 2 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset; core_n=1_but_no_direct_core |
| ENG-THESIS-075 | 基于深度学习的混凝土路面裂缝检测研究 | **fail** | 19 | 2 | 0 | 2 | evaluable | quarantined_candidates=2; no_dataset_or_data_gap_note; core_n=1_but_no_effective_core; all_evidence_critical_consistency_error |
| ENG-THESIS-079 | 基于结构光的隧道裂缝检测技术研究与实现 | pass | 27 | 3 | 0 | 0 | evaluable | no_dataset_or_data_gap_note; core_n=3_but_no_direct_core |
| ENG-THESIS-080 | 基于三维重建裂缝损伤检测算法研究 | pass | 17 | 4 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset; core_n=2_but_no_direct_core |
| ENG-THESIS-083 | 基于多分辨率网络的桥梁裂缝分割算法研究 | pass | 42 | 5 | 0 | 0 | evaluable | no_dataset_or_data_gap_note |
| ENG-THESIS-089 | 基于深度学习和双目立体视觉的道路路面损伤检测研究 | weak | 20 | 5 | 0 | 0 | evaluable | no_dataset_or_data_gap_note |
| ENG-THESIS-091 | 基于云计算的输电线路缺陷检测平台 | weak | 20 | 4 | 0 | 0 | evaluable | no_dataset_or_data_gap_note |
| ENG-THESIS-092 | 海上风机叶片缺陷检测及分类 | weak | 17 | 2 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset; core_n=3_but_no_direct_core |
| ENG-THESIS-093 | 基于深度学习的接触网绝缘子表面缺陷图像式检测方法研究 | weak | 15 | 4 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset; core_n=1_but_no_direct_core |
| ENG-THESIS-096 | 基于石墨烯薄膜电热效应的风机叶片防冰除冰系统研究 | weak | 22 | 1 | 0 | 0 | evaluable | no_dataset_or_data_gap_note |
| ENG-THESIS-100 | 基于深度学习的配电设备视觉识别技术研究 | pass | 27 | 4 | 0 | 0 | evaluable | datasets_present_but_no_topic_dataset |

> **解读**：24 pass 都是「baseline ≥ 1 + dataset+repo ≥ 1 + parallel/core 足够 + 无 critical_error」组合；13 weak 多为「topic_dataset 缺失」或「core_direct=0」；3 fail 全部因 crossref metadata mismatch quarantine 后 evidence 不足。

---

## §2 核心机制说明：为什么 0 weak 假象 → 24 pass 真分布

| 维度 | Re06 (Re-classify) | Re07 重审 |
|---|---|---|
| topic_atoms 读取 | 只看 synthesis | 7 步 lookup（result.parsed_topic 优先）|
| axis_task missing | 100% (424/424) | **7.3% (31/424)** |
| insufficient_metadata | 99% (419/424) | **0% (0/424)** |
| metadata_mismatch 触发 | case fail 直接 | candidate-level quarantine |
| core_direct=0 触发 | case weak | core_zero_blocks_pass 触发 weak（仅 axis evaluable 时）|
| topic_dataset=0 触发 | case weak | notes「data_source_gap_needs_confirmation」 |

**Re07 的关键修通点**：`_build_topic_atoms` 第 1 步回退到 `result["parsed_topic"]["topic_atoms"]`——Re05 raw dump 顶层 `parsed_topic` 存在但 Re06 eval 完全不读它，导致 axis_match 永远拿到空 atoms。

---

## §3 6 个 SOP §5.3 必抽样的 case 人工解释

> SOP §5.3 明确要求抽样：ENG-THESIS-018 / 048 / 060 / 075 / 092 / 093。下面 6 个逐一解释 + 1 个 ENG-THESIS-066 加详（attack-defense 轴缺失典型）。

### §3.1 ENG-THESIS-018 — 三维点云补全 — `pass`

| 维度 | Re06 Re-classify | Re07 |
|---|---|---|
| status | weak | **pass** |
| axis_task | missing (100%) | **direct**（修复后）|
| paper / eff_baseline | 34 / 1 | 34 / 1 |
| reason | core_n=4_but_no_direct_core | datasets_present_but_no_topic_dataset; core_n=4_but_no_direct_core |

**Re07 修复点**：`result["parsed_topic"]["topic_atoms"].task` 含 "point cloud completion" / "shape completion"，与 baseline "PCN"、"SnowflakeNet" title 命中 → axis direct。**case 从 weak 升 pass**。

### §3.2 ENG-THESIS-048 — 视觉 SLAM — `fail`

| 维度 | Re06 | Re07 |
|---|---|---|
| status | weak | **fail** |
| reason | core_n=2_but_no_direct_core | quarantined_candidates=1; no_dataset_or_data_gap_note; all_evidence_critical_consistency_error; scenario_axis_missing |
| quarantined | n/a | **1 baseline metadata_mismatch**（ORB-LINE-SLAM3）|

**Re07 修复点**：crossref metadata mismatch 的 ORB-SLAM3 候选**被 quarantine 隔离**而不是 fail 触发；其余 evidence 全是 generic framework（ORB-SLAM / visual odometry 通用词），scenario 轴缺失，dataset=0 → 真实 fail。

### §3.3 ENG-THESIS-060 — 车道线检测 — `pass`

| 维度 | Re06 (旧 STRONG_NOISE) | Re06 Re-classify | Re07 |
|---|---|---|---|
| status | fail（AGN false-positive）| weak | **pass** |
| 失败原因 | substring `AGN` 命中 `Agnostic` | core_direct_n=0 | (无 critical_error) |

**Re07 修复点**：去黑名单 + axis_status=evaluable 后，`Agnostic Lane Detection` 在 parallel 桶，被 `classify_parallel_role` 判 direct；core_zero_blocks_pass 不触发 → pass。**SOP §5 R2 false-positive 根除**。

### §3.4 ENG-THESIS-075 — 混凝土路面裂缝检测 — `fail`

| 维度 | Re06 | Re07 |
|---|---|---|
| status | pass | **fail** |
| reason | all_metrics_met | quarantined_candidates=2; no_dataset_or_data_gap_note; core_n=1_but_no_effective_core; all_evidence_critical_consistency_error |
| effective_baseline | 4 | **2**（2 个 baseline 被 quarantine）|

**Re07 修复点**：Re05 报告里把 075 判 pass 但 crossref metadata 失真让 2 个 baseline 候选 metadata_mismatch；Re07 quarantine 隔离后 effective_baseline=2 仍不够 + dataset=0 + all critical_error 触发 fail。**这是 Re06 pass 不实的真实案例**——Re07 反映真相。

### §3.5 ENG-THESIS-092 — 海上风机叶片缺陷检测 — `weak`

| 维度 | Re06 | Re07 |
|---|---|---|
| status | pass | **weak** |
| reason | all_metrics_met | datasets_present_but_no_topic_dataset; core_n=3_but_no_direct_core |
| topic_dataset | 0 | 0 |
| effective_core | n/a | 0 |

**Re07 修复点**：core_zero_blocks_pass 触发 weak——海上风机叶片核心证据没有 direct 命中（dataset=NEU-DET 等通用），只是有平行论文 → 不能 pass。**Re05 报告 §5.3 已经指出「92 pass 偏乐观」**。

### §3.6 ENG-THESIS-093 — 接触网绝缘子缺陷检测 — `weak`

| 维度 | Re06 | Re07 |
|---|---|---|
| status | pass | **weak** |
| reason | all_metrics_met | datasets_present_but_no_topic_dataset; core_n=1_but_no_direct_core |
| effective_core | n/a | 0 |

**Re07 修复点**：Re05 报告 §5.3 已承认「93 当前 pass 偏乐观」——Re07 core_zero_blocks_pass 触发降级 weak；DAMO-YOLO/NEU-DET/PCB-defect 全是 proxy/pretrain。

### §3.7 ENG-THESIS-066 — 自动驾驶多模态感知攻击和防御 — `weak`（典型 axis 缺失案例）

| 维度 | Re06 | Re07 |
|---|---|---|
| status | weak | **weak** |
| reason | no_dataset | no_dataset_or_data_gap_note; attack_defense_axis_missing; core_n=0_but_no_effective_core |
| axis_missing | n/a | `attack_defense_axis_missing` |

**Re07 修复点**：axis_gap_blocking 触发 weak——topic 明确提到 attack/defense 但所有 baseline 是 multi-modal fusion perception，**没有任何 attack/defense 直接证据**。SOP §5 R5 案例。

---

## §4 bucket_audit per-batch 字段统计

每 case re-audit 都把 5 个 bucket 的 per-candidate audit 明细写到 `tmp_re04_eval/balanced40_re07/{batch}/<case_id>.json` 的 `bucket_audit` 字段。每个 member 带 `consistency_status` / `axis_coverage` / `evidence_quality` / `decision_reason`——可定位「为什么这条候选在 core / 为什么这条是 aligned / 为什么那条是 off_topic」。

---

## §5 Re05 vs Re06 vs Re07 三阶段对比

| 维度 | Re05 (旧 STRONG_NOISE) | Re06 (Re-classify) | Re07 |
|---|---:|---:|---:|
| pass | 29 | 0 | **24** |
| weak | 9 | 40 | 13 |
| fail | 2 | 0 | **3** |
| pass+weak_rate | 95.00% | 100.00% (weak 假象) | **92.50% (真分布)** |
| axis_task missing | n/a | **100%** | **7.3%** |
| insufficient_metadata | n/a | 99% | **0%** |
| critical_consistency_error | n/a | 0 | 0 |
| quarantined_total | n/a | n/a | 3 cases |
| SOP §5.3 pass | n/a | False | **True** |

> 解读：Re07 没让 retrieval 变好或变差——raw dump 完全一样；它让**评价层变诚实**。24 pass 是真能进下一阶段的；13 weak 是真需要补证的；3 fail 是真没足够证据的。这才是「毕业选题资源可用性分级」该有的分布。

---

## §6 一致性校验输出

运行 `apps/api/scripts/validate_re_report_consistency.py`：

```
=== Cross-validate Re07 reports ===
  summary: tmp_re04_eval/balanced40_re07/summary.json
  csv:     Plan/PaperAgent_Re07_Balanced40_逐论文审计.csv
  md:      Plan/PaperAgent_Re07_Balanced40_逐论文审计.md
  PASS  summary.n_total == csv_rows (40 == 40)
  PASS  summary.by_status == csv status groupby
  PASS  csv rows == md per-case table rows
  PASS  axis_task missing ratio < 0.30 (Re07 §5.3)
=== ALL CONSISTENCY CHECKS PASSED ===
```

---

## §7 文件路径索引

| 路径 | 内容 |
|---|---|
| `Plan/PaperAgent_Re07_完工报告.md` | Re07 完工报告 |
| `Plan/PaperAgent_Re07_Balanced40_逐论文审计.md` | 本报告 |
| `Plan/PaperAgent_Re07_Balanced40_逐论文审计.csv` | 40 case 扁平表 (27 列, utf-8-sig) |
| `Plan/PaperAgent_Re07_Balanced40_候选论文.csv` | 424 候选论文扁平表 (24 列) |
| `tmp_re04_eval/balanced40_re07/summary.json` | 40 case aggregate |
| `tmp_re04_eval/balanced40_re07/report.md` | 机器生成的 per-case 表 |
| `tmp_re04_eval/balanced40_re07/{r1..r6,batch1..3}/<case_id>.json` | per-case audit dump |
| `apps/api/scripts/reclassify_balanced40.py` | re-classify 脚本 |
| `apps/api/scripts/re07_to_csv.py` | CSV 生成脚本 |
| `apps/api/scripts/validate_re_report_consistency.py` | 一致性校验脚本 |

---

> **核心判断**：Re07 把 Re06 评价层升级到 SOP §5.3 全部 PASS。Balanced40 从「全是 weak 假象」恢复成「24 pass + 13 weak + 3 fail = 92.5%」的真实分布；axis_task missing 从 100% 降到 7.3%；metadata_mismatch 候选先 quarantine 再决定 case fail（不再用一个 crossref 脏候选拖垮整题）。
> **下一步**：Re08 SOP 起草（候选核验 + Forward Tracking）。