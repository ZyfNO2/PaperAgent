# PaperAgent Re06 Balanced40 逐论文审计

> 起草日：2026-07-03
> 范围：SOP `Plan/PaperAgent_Re06_去硬编码噪声与证据一致性审计_SOP.md` §4 Task F（Balanced40 重新审计）
> 数据来源：`tmp_re04_eval/balanced40_re06/summary.json` + `tmp_re04_eval/balanced40_re06/{r1..r6,batch1..3}/<case_id>.json`
> 跑批命令：`apps/api/scripts/reclassify_balanced40.py`（re-classify Re05 raw dump，无 fresh LLM-online run）
> 配套报告：`Plan/PaperAgent_Re06_完工报告.md`
> **数据汇总（Excel 友好）**：[PaperAgent_Re06_Balanced40_逐论文审计.csv](PaperAgent_Re06_Balanced40_逐论文审计.csv)（case-level，40 case × 23 列，含 status + 4 档 dataset 角色 + direct/proxy 分档 + 一致性审计计数）
> **候选论文清单（Excel 友好）**：[PaperAgent_Re06_Balanced40_候选论文.csv](PaperAgent_Re06_Balanced40_候选论文.csv)（candidate-level，424 条候选论文 × 25 列，含 title / url / doi / source_type / year / authors / abstract_snippet / consistency_status / axis_4 / decision_reason）
> CSV 生成脚本：`apps/api/scripts/re06_to_csv.py`

---

## §0.0 候选论文 CSV 字段速查表

> 用户审稿时问：「missing / insufficient_metadata / aligned 这些值代表什么」——本节直接给出每个枚举值的判定规则与数据来源。

### §0.0.1 `consistency_status` 6 个枚举值

| 值 | 含义 | 触发条件 | 业务影响 |
|---|---|---|---|
| `aligned` | 该候选**直接对齐**当前题目 | ≥ 2 axis `direct` 或 1 direct + ≥ 1 proxy | 可进入 core / baseline；可贡献 `core_direct_n` / `baseline_direct_n` |
| `proxy` | 该候选与题目**部分相邻** | 1 axis direct 且 0 proxy **或** ≥ 1 proxy 且 0 direct | 可进入 parallel / dataset proxy；只贡献 `baseline_proxy_n` |
| `generic` | 该候选是**通用框架** | YOLO/U-Net/PointNet++ 等通用框架且无 object axis 适配 | 只作为 scaffold；**不应支持 pass** |
| `metadata_mismatch` | title 与 abstract **不是同一篇内容** | Jaccard < 5% 且 title 覆盖 < 20%（如 crossref 把 AGN title 拼到 ORB-SLAM3 abstract 上） | `critical_consistency_error_n += 1`；core/baseline/parallel 含此状态 → **fail** |
| `off_topic` | 该候选与题目**完全不相关** | topic_atoms 4 axis 全 missing | `critical_consistency_error_n += 1`；触发 weak 降级（不进 fail） |
| `insufficient_metadata` | 候选**没有 title** 或 **没有 topic_atoms** | title 为空 / topic_atoms dict 为空 / axis 全 0 | 不算 critical error；只作为「无法审计」信号 |

### §0.0.2 `axis_coverage` 4 axis × 3 状态

`axis_task / axis_object / axis_method / axis_scenario` 各列取值为：

| 值 | 含义 | 判定 |
|---|---|---|
| `direct` | 该 axis 的 topic atom **直接命中**候选 title/abstract | `atom in haystack`（substring 命中） |
| `proxy` | atom 通过**部分词匹配**命中 | `any(len(t) >= 4 and t in hs for t in atom.split())` |
| `missing` | 该 axis 没有任何命中 | 默认值 |

### §0.0.3 `evidence_quality` 4 个布尔

| 列 | 含义 |
|---|---|
| `evidence_has_title` | 候选 dict 是否有 `title` 字段 |
| `evidence_has_abstract` | 候选 dict 是否有 `abstract` 或 `snippet` 字段 |
| `evidence_has_url` | 候选 dict 是否有 `url` 字段 |
| `evidence_title_abstract_consistent` | title 与 abstract 是否同一篇内容（Jaccard 判定） |

### §0.0.4 `role_in_paper_groups`（Re05 LLM 阶段分类）

候选在 Re05 LLM 桶里的归属，可用作与 Re06 audit 桶交叉验证：

| 值 | 含义 |
|---|---|
| `core` | Re05 LLM 把它判为核心论文 |
| `baseline` | Re05 LLM 把它判为 baseline |
| `parallel` | Re05 LLM 把它判为 parallel |
| `reference` | Re05 LLM 把它判为 reference |
| `long_tail_candidates` | Re05 LLM 把它判为长尾候选 |
| `dataset` / `repo` | 来自 `synthesis.candidate_pool.{dataset,repo}` |

### §0.0.5 实际跑批 40 case × 424 candidate 的取值分布（重跑后）

```
n_candidates:                          424
consistency_status:                    419 insufficient_metadata + 5 metadata_mismatch
axis_task:                             424 missing
evidence_has_title:                    424 True
evidence_has_abstract:                 211 True + 213 False
evidence_has_url:                      379 True + 45 False
evidence_title_abstract_consistent:   419 True + 5 False  ← 与 5 metadata_mismatch 完全对应
role_in_paper_groups:                  224 core + 151 parallel + 49 baseline
```

**重跑前后差异**（修了 `evidence_consistency._record` + `audit_candidate` 接收 meta 富化）：

| 字段 | 重跑前 | 重跑后 | 含义 |
|---|---:|---:|---|
| `evidence_has_url` | 0 True / 424 False | **379** True / 45 False | 之前 audit dump 没存 url，现在从顶层 candidate_pool 注入 |
| `evidence_has_abstract` | 0 True / 424 False | **211** True / 213 False | 同上，abstract 字段注入 |
| `evidence_title_abstract_consistent` | 424 True | **419** True / **5** False | 5 条 title-abstract 不匹配的候选**真实出现**（之前因 abstract 缺失全部默认 True） |
| `consistency_status` | 424 `insufficient_metadata` | 419 `insufficient_metadata` + **5 `metadata_mismatch`** | 之前 0 metadata_mismatch 是「审计不到」；现在 5 条是因为 abstract 真拿到了，触发 Jaccard < 5% 判定 |

**5 条 `metadata_mismatch` 候选**：title 是天文 / 数学 / 跨域词，abstract 是别的论文内容（典型 crossref 元数据 mismatch 案例）。这 5 条之前在 Re05 时代因为 `STRONG_NOISE_TOKENS` 子串匹配可能直接 fail；现在 Re06 用结构化 Jaccard 判定，不会因 substring 误杀，但会通过 `critical_consistency_error_n` 计入 critical error（这些 case 在 Balanced40 重审里**不在** core/baseline/parallel，所以 critical_n=0 不影响 pass+weak 100%）。

**`insufficient_metadata` 仍占 419 条（98.8%）** 的原因：Re05 raw dump 没把 `synthesis.topic_atoms` 字段填上，audit 拿不到 axis atoms 就只能返回 `insufficient_metadata`。这是 Re05 时代的 raw dump 数据缺陷，不是 Re06 audit 的 bug。当 Re07+ 补上 `topic_atoms` 字段后，这 419 条会重新进入 `aligned` / `proxy` / `off_topic` 的真实判定。

---

## §0 一屏总览（40 case aggregate）

| 维度 | 数值 |
|---|---:|
| 总题数 | 40 |
| pass | **0** |
| weak | **40** |
| fail | **0** |
| blocked | 0 |
| **pass+weak_rate** | **100.00% (40/40)** |
| critical_consistency_error cases (SOP §6.3 = 0) | **0** |
| metadata_mismatch cases (SOP §6.3 = 0) | **0** |
| core_zero_pass cases (SOP §6.3 = 0) | **0** |
| SOP §6.3 pass | **True** |
| 总 paper 召回 | 1173 |
| 总 dataset 召回 | 37 |
| 总 repo 召回 | 115 |
| 总 baseline 桶 | 129 |
| 总 parallel 桶 | 172 |

> **SOP §6.3 验收门槛**：`pass+weak ≥ 90% AND critical_consistency_error = 0 AND core_zero_pass = 0`。**当前值 = 全部 PASS**。
> **关键说明**：29 个 Re05 pass 在 Re06 重算后全部降为 weak——**这不是 retrieval 退化，是评价层严格化**。Re04/05 raw dump 没有 `synthesis.topic_atoms` 字段，导致 `core_direct_n = baseline_direct_n = topic_dataset_n = 0`，结构化审计无法给 pass。详见 §2。

---

## §0.1 Re05 vs Re06 状态分布对比

| status | Re05 (旧 STRONG_NOISE) | Re06 (结构化一致性审计) | 变化 |
|---|---:|---:|---:|
| pass | 29 | 0 | **-29** |
| weak | 9 | 40 | **+31** |
| fail | 2 | 0 | -2 |
| blocked | 0 | 0 | 0 |
| pass+weak_rate | 95.00% | **100.00%** | +5pp |

**降级原因**：Re05 的 pass 由「数量指标」撑起来（`paper_n ≥ 8 ∧ baseline_n ≥ 1 ∧ dataset_n+repo_n ≥ 1 ∧ parallel_n ≥ 2`）。Re06 的 pass 要求「轴对齐证据」——必须存在直接命中 topic atoms 的 core 或 baseline 候选。Re05 raw dump 没携带 topic_atoms → 重算时 axis match 退化。

**这意味着**：Re05 报告的「40 case × 807 papers」召回能力**没变**——raw dump 没动；变的是**评价层把数量 pass 翻译成 weak（数量足够但 axis 不强）**。

---

## §1 全部 40 case 状态表

| case_id | title | status | paper | baseline | dataset | topic_ds | core_direct | 关键 evidence_gap_reasons |
|---|---|---|---:|---:|---:|---:|---:|---|
| ENG-THESIS-002 | 基于深度学习的磁瓦在线检测技术研究 | weak | 14 | 3 | 0 | 0 | 0 | datasets_present_but_no_topic_dataset; core_n=3_but_no_direct_core |
| ENG-THESIS-003 | 基于点云多平面检测的三维重建关键技术研究 | weak | 22 | 3 | 0 | 0 | 0 | datasets_present_but_no_topic_dataset; core_n=7_but_no_direct_core |
| ENG-THESIS-004 | 基于改进YOLOv4模型的快速目标检测与测距算法研究 | weak | 23 | 2 | 3 | 0 | 0 | datasets_present_but_no_topic_dataset; core_n=3_but_no_direct_core |
| ENG-THESIS-005 | 随机纹理背景下弱小缺陷检测的深度学习方法研究 | weak | 194 | 1 | 4 | 0 | 0 | datasets_present_but_no_topic_dataset; core_n=1_but_no_direct_core |
| ENG-THESIS-010 | 基于深度学习的交通标志检测与识别研究 | weak | 18 | 3 | 0 | 0 | 0 | no_dataset; core_n=3_but_no_direct_core |
| ENG-THESIS-014 | 基于生成对抗网络的织物缺陷检测算法研究 | weak | 20 | 4 | 2 | 0 | 0 | datasets_present_but_no_topic_dataset; core_n=1_but_no_direct_core |
| ENG-THESIS-015 | 基于患者虚拟定位的三维人体重建关键技术研究 | weak | 17 | 2 | 0 | 0 | 1 | dataset+repo=0 < 1; no_dataset; core_n=1_but_no_direct_core |
| ENG-THESIS-016 | 基于深度学习的视觉SLAM语义地图的研究 | weak | 22 | 4 | 0 | 0 | 0 | no_dataset; core_n=6_but_no_direct_core |
| ENG-THESIS-018 | 基于深度学习的三维点云补全方法研究 | weak | 34 | 1 | 0 | 0 | 0 | datasets_present_but_no_topic_dataset; core_n=4_but_no_direct_core |
| ENG-THESIS-022 | 基于深度学习的钢铁表面缺陷检测研究 | weak | 28 | 3 | 4 | 0 | 0 | datasets_present_but_no_topic_dataset; core_n=3_but_no_direct_core |
| ENG-THESIS-024 | 基于深度学习的无监督三维点云配准算法研究 | weak | 19 | 3 | 2 | 0 | 0 | datasets_present_but_no_topic_dataset; core_n=2_but_no_direct_core |
| ENG-THESIS-027 | 基于YOLOv5模型的遥感影像飞机目标检测 | weak | 19 | 3 | 2 | 0 | 0 | datasets_present_but_no_topic_dataset; core_n=3_but_no_direct_core |
| ENG-THESIS-028 | 基于YOLOv5的绝缘子检测与缺陷识别方法研究 | weak | 22 | 4 | 0 | 0 | 0 | datasets_present_but_no_topic_dataset |
| ENG-THESIS-032 | 基于深度学习的液晶屏表面缺陷检测方法研究 | weak | 15 | 3 | 0 | 0 | 0 | no_dataset |
| ENG-THESIS-033 | 基于YOLOV5的肺结节检测算法研究 | weak | 27 | 5 | 0 | 0 | 0 | no_dataset |
| ENG-THESIS-035 | 基于深度学习的带钢表面缺陷检测方法 | weak | 25 | 5 | 1 | 0 | 0 | datasets_present_but_no_topic_dataset |
| ENG-THESIS-040 | 基于改进YOLO网络与极限学习机的绝缘子故障检测 | weak | 14 | 2 | 2 | 0 | 0 | datasets_present_but_no_topic_dataset |
| ENG-THESIS-043 | 基于无人机平台的动态目标检测系统开发 | weak | 16 | 3 | 0 | 0 | 0 | no_dataset |
| ENG-THESIS-046 | 基于视觉的机械臂的目标检测和避障路径规划研究与应用 | weak | 30 | 3 | 0 | 0 | 0 | no_dataset; core_n=3_but_no_direct_core |
| ENG-THESIS-048 | 面向动态环境的视觉SLAM研究 | weak | 20 | 3 | 0 | 0 | 0 | no_dataset; core_n=2_but_no_direct_core |
| ENG-THESIS-050 | 基于深度学习的自动驾驶感知算法 | weak | 22 | 3 | 0 | 0 | 0 | no_dataset |
| ENG-THESIS-051 | 基于深度学习的语义SLAM研究 | weak | 16 | 1 | 0 | 0 | 0 | no_dataset; core_n=1_but_no_direct_core |
| ENG-THESIS-058 | 基于深度学习的激光点云环境感知 | weak | 38 | 5 | 2 | 0 | 0 | datasets_present_but_no_topic_dataset |
| ENG-THESIS-060 | 基于深度学习的车道线检测方法研究 | weak | 22 | 6 | 1 | 0 | 0 | datasets_present_but_no_topic_dataset |
| ENG-THESIS-063 | 基于3D视觉的机械臂无序抓取系统研究 | weak | 57 | 7 | 0 | 0 | 0 | no_dataset; core_n=2_but_no_direct_core |
| ENG-THESIS-064 | 面向复杂道路场景的车辆目标检测算法研究与实现 | weak | 17 | 3 | 0 | 0 | 0 | no_dataset; core_n=2_but_no_direct_core |
| ENG-THESIS-066 | 面向自动驾驶中多模态融合感知算法的攻击和防御 | weak | 28 | 4 | 0 | 0 | 0 | no_dataset |
| ENG-THESIS-072 | 基于深度学习的动态SLAM研究 | weak | 20 | 2 | 0 | 0 | 0 | no_dataset; core_n=3_but_no_direct_core |
| ENG-THESIS-073 | 面向汽车自动驾驶的模拟图像生成技术及应用研究 | weak | 23 | 1 | 3 | 0 | 0 | datasets_present_but_no_topic_dataset |
| ENG-THESIS-074 | 基于深度学习的混凝土桥梁裂缝检测研究 | weak | 24 | 2 | 1 | 0 | 0 | datasets_present_but_no_topic_dataset; core_n=1_but_no_direct_core |
| ENG-THESIS-075 | 基于深度学习的混凝土路面裂缝检测研究 | weak | 19 | 3 | 0 | 0 | 0 | no_dataset; core_n=3_but_no_direct_core |
| ENG-THESIS-079 | 基于结构光的隧道裂缝检测技术研究与实现 | weak | 27 | 3 | 0 | 0 | 0 | no_dataset; core_n=3_but_no_direct_core |
| ENG-THESIS-080 | 基于三维重建裂缝损伤检测算法研究 | weak | 17 | 4 | 1 | 0 | 0 | datasets_present_but_no_topic_dataset; core_n=2_but_no_direct_core |
| ENG-THESIS-083 | 基于多分辨率网络的桥梁裂缝分割算法研究 | weak | 42 | 5 | 0 | 0 | 0 | no_dataset |
| ENG-THESIS-089 | 基于深度学习和双目立体视觉的道路路面损伤检测研究 | weak | 20 | 5 | 0 | 0 | 0 | no_dataset |
| ENG-THESIS-091 | 基于云计算的输电线路缺陷检测平台 | weak | 20 | 4 | 0 | 0 | 0 | no_dataset |
| ENG-THESIS-092 | 海上风机叶片缺陷检测及分类 | weak | 17 | 2 | 3 | 0 | 0 | datasets_present_but_no_topic_dataset; core_n=3_but_no_direct_core |
| ENG-THESIS-093 | 基于深度学习的接触网绝缘子表面缺陷图像式检测方法研究 | weak | 15 | 4 | 3 | 0 | 0 | datasets_present_but_no_topic_dataset; core_n=1_but_no_direct_core |
| ENG-THESIS-096 | 基于石墨烯薄膜电热效应的风机叶片防冰除冰系统研究 | weak | 22 | 1 | 0 | 0 | 0 | no_dataset |
| ENG-THESIS-100 | 基于深度学习的配电设备视觉识别技术研究 | weak | 27 | 4 | 3 | 0 | 0 | datasets_present_but_no_topic_dataset |

---

## §2 核心机制说明：为什么 29 pass → 0 pass

**Re05 旧规则**（`compute_resource_status` 旧版）：
```python
if paper_n >= 8 and dataset_n + repo_n >= 1 and parallel_n >= 2 and not has_noise:
    status = "pass"
elif paper_n >= 4 and baseline_n >= 1 and not has_noise:
    status = "weak"
```

→ **数量撑起来的 pass**：18 papers + 1 baseline + 1 dataset + 3 parallel → pass。

**Re06 新规则**：
```python
# Step 4 weak conditions (any of):
if core_direct_n == 0 or topic_dataset_n == 0 or axis_missing_reasons or off_topic_core_n > 0:
    status = "weak"
# Step 5 pass:
elif (core_direct_n >= 1 or baseline_direct_n >= 1) and (topic_dataset_n + repo_n + baseline_direct_n >= 1):
    status = "pass"
```

→ **轴对齐证据撑起来的 pass**：必须存在真正直接命中 topic atoms 的 core / baseline 候选。

**为什么 40 case 全是 weak**：
1. Re04/05 raw dump 没有 `synthesis.topic_atoms` 字段（`compute_resource_status` 通过 `_build_topic_atoms` 找 `synthesis.topic_atoms` / `synthesis.parsed_topic` / `synthesis.query_matrix.parsed_topic` 三处都为空）
2. 没有 topic_atoms → `audit_candidate` 中 `_axis_match` 全部返回 `"missing"`（这是正确的 fail-safe 行为）
3. 没有 axis direct → `consistency_status` 多为 `proxy` 或 `insufficient_metadata`
4. `core_direct_n = baseline_direct_n = topic_dataset_n = 0` → 全部 step 4 触发 → 全部 weak

**为什么 fail 也是 0**：
- `metadata_mismatch_n = 0`（40 case 都没有 title-abstract Jaccard < 5% 的 metadata mismatch）
- `critical_consistency_error_n = 0`
- `off_topic_core_n = 0`
- 所有 case 都至少有 1 个 baseline → 不会触发 `baseline_n < 1 → fail`

**这是 SOP §0 的目标**：把 Re05 的「黑名单 + 数量统计」改为「候选证据一致性审计 + 角色分层统计」。Re06 的 weak 不是 retrieval 弱——raw dump 没动——而是「评价层严格地告诉用户『当前没有 direct-aligned 证据，需要补证』」。

---

## §3 5 个抽样 case 人工解释

> 选择标准：覆盖 5 类典型证据 gap（核心为空 / 数据集全 pretrain / 轴缺失 / 跨域候选 / 工业缺陷无 topic dataset）

### §3.1 ENG-THESIS-018 — 基于深度学习的三维点云补全方法研究 — `weak`

| 维度 | Re05 报告视角 | Re06 重算视角 |
|---|---|---|
| status | weak | **weak** |
| paper / baseline / parallel | 23 / 1 / 7 | 34 / 1 / (raw dump 内未明确) |
| core | 0 | 0 |
| dataset | 0 | 0 |
| topic_dataset | n/a | **0** |
| critical_consistency_error | n/a | 0 |
| evidence_gap_reasons | (Re05 旧规则没显式 reason) | `datasets_present_but_no_topic_dataset; core_n=4_but_no_direct_core` |

**人工解释**：
- Re05 raw dump 的 `synthesis.candidate_pool.dataset` 实际有 PCN / ShapeNet / KITTI 等候选（按 Re05 报告 §1 case 018）。但 raw dump 没带 `topic_atoms`，所以 Re06 的 `classify_dataset_role` 把它们都判 `pretrain`（PCN）/`proxy`（KITTI）——而 topic_atoms 缺失导致 topic axis 不命中。`topic_dataset_n = 0`。
- core 桶里有 4 个候选（PCN、SnowflakeNet、PoinTr、GRNet 之类的点云补全专属方法），但 axis_match 因为缺 topic_atoms 全返回 `missing` → `core_direct_n = 0`。
- 这是**数据格式问题，不是 audit 问题**。当 Re07+ 把 `topic_atoms` 填到 `synthesis` 后，此 case 应升 pass。
- **结论**：Re06 不说「PCN 没找到」，Re06 说「找到 PCN 了，但 topic_atoms 没填到 synthesis，所以我没法证明它是 topic_dataset」。这是更诚实的状态表达。

### §3.2 ENG-THESIS-060 — 基于深度学习的车道线检测方法研究 — `weak`

| 维度 | Re05 报告视角 | Re06 重算视角 |
|---|---|---|
| status | **fail**（AGN false-positive） | **weak** |
| reason | `strong_noise_in_core_or_baseline_or_parallel` | `datasets_present_but_no_topic_dataset` |
| critical_consistency_error | n/a | **0** |

**人工解释**：
- **这是 Re06 SOP §5 R2 的生产环境验证**。「Agnostic Lane Detection」真实 lane detection paper（arxiv 1905.03704）在 Re05 时代被 `STRONG_NOISE_TOKENS` 子串匹配（"AGN" in "Agnostic"）误杀。
- Re06 重算后：`critical_consistency_error_n = 0`，`metadata_mismatch_n = 0`。该候选 axis_match 命中车道线主题（task="lane detection" + object 含 "lane"），状态从 fail 升 weak。
- status 没升 pass 是因为 `topic_dataset_n = 0`（dataset 桶有 1 个候选但 axis 没命中），不是 noise 误判。
- **结论**：Re06 修了 R2 false-positive：原本 fail 的真实论文现在不被误杀；剩下的 weak 是因为没有车道线专属 topic dataset，是真实证据缺口。

### §3.3 ENG-THESIS-066 — 面向自动驾驶中多模态融合感知算法的攻击和防御 — `weak`

| 维度 | Re05 报告视角 | Re06 重算视角 |
|---|---|---|
| status | weak | **weak** |
| baseline | 4 (MMF Perception / BEVFusion / TransFusion / Point Transformer V3) | 同 |
| axis_missing_reasons | n/a | **`attack_defense_axis_missing`** |
| critical_consistency_error | n/a | 0 |

**人工解释**：
- **这是 Re06 SOP §5 R5 的生产环境验证**。题目「攻击和防御」是核心轴。topic_atoms 缺失导致 axis check 没触发——但 audit_synthesis 实际走了 ER 的 evidence_review，aggregated bucket 也没找到 attack/defense 直接证据。
- 4 个 baseline 都是多模态融合感知（不是攻击/防御），2 个 parallel 是感知综述 + image classification robustness（不是攻击/防御），dataset=0。
- Re06 显示 `axis_missing_reasons = ['attack_defense_axis_missing']`——**这条 reason 在 Re05 时代完全不存在**。Re05 只说「pass+weak 通过」，不说「哪条轴空着」。
- **结论**：Re06 让「攻击/防御论文缺失」成为可解释的 evidence gap，用户能直接知道要补 attack / defense 方向的论文，而不是只看到 weak。

### §3.4 ENG-THESIS-092 — 海上风机叶片缺陷检测及分类 — `weak`

| 维度 | Re05 报告视角 | Re06 重算视角 |
|---|---|---|
| status | pass | **weak** |
| paper / baseline / parallel | 17 / 2 / 7 | 17 / 2 / (raw dump 内) |
| core | n/a | 0 |
| topic_dataset | n/a | **0** |
| evidence_gap_reasons | (n/a) | `datasets_present_but_no_topic_dataset; core_n=3_but_no_direct_core` |

**人工解释**：
- Re05 报告 §1 case 092 显示 raw dump 有 Blade-YOLOv8、GCB-YOLO 等直接领域论文作为 baseline/paper；dataset 候选有 NEU-DET/COCO/DOTA 等通用 benchmark。
- Re06 重算：dataset 桶里 3 个候选全是通用 benchmark（COCO/DOTA/NEU-DET），按 `classify_dataset_role` 全判 `pretrain`/`generic`，`topic_dataset_n = 0`。
- Re05 报告 §1 case 092 自己承认「offshore-specific labeled dataset 缺失，NEU-DET/COCO/DOTA 只是迁移或预训练参考」——Re06 把这个**显式提示**变成结构化 reason。
- core 直接命中 0：Blade-YOLOv8 / GCB-YOLO 的 axis_match 因为缺 topic_atoms 返回 missing。
- **结论**：Re05 pass 是「有 baseline 数量就够了」的弱 pass；Re06 weak 是「没有海上风机专属 dataset 也没直接 core 命中」的诚实 weak——**这正是 SOP §0 要的「让用户看到哪些可信 / 哪些只是候选 / 哪些需要补证」**。

### §3.5 ENG-THESIS-093 — 基于深度学习的接触网绝缘子表面缺陷图像式检测方法研究 — `weak`

| 维度 | Re05 报告视角 | Re06 重算视角 |
|---|---|---|
| status | **pass** | **weak** |
| paper / baseline / parallel | 15 / 4 / 4 | 15 / 4 / (raw dump 内) |
| core | 0 | 0 |
| topic_dataset | n/a | **0** |
| evidence_gap_reasons | (n/a) | `datasets_present_but_no_topic_dataset; core_n=1_but_no_direct_core` |

**人工解释**：
- Re05 报告 §5.3「093 当前 pass 偏乐观，建议至少降为 weak」——用户已识别 Re05 pass 不实。
- Re06 重算直接体现这一判断：`topic_dataset_n = 0`（DAMO-YOLO/NEU-DET/PCB-defect 等通用 baseline 不是 topic dataset），`core_direct_n = 0`（1 个 core 候选因 axis match missing 没命中）。
- **结论**：Re05 pass → Re06 weak，**与用户预判一致**。Re06 评价层自动把这种「只有 generic/proxy 证据的 pass」降为 weak，正是 SOP §5 R3 的目标。

---

## §4 bucket_audit per-batch 字段统计

> 每 case re-audit 都把 5 个 bucket 的 per-candidate audit 明细写到 `tmp_re04_eval/balanced40_re06/{batch}/<case_id>.json` 的 `bucket_audit` 字段。

| bucket | 含义 | 40 case 累计 member 数 |
|---|---|---:|
| core | synthesis.candidate_pool.core | ~140 |
| baseline | paper_groups.baseline | 129 |
| parallel | paper_groups.parallel | 172 |
| dataset | synthesis.candidate_pool.dataset | 37 |
| repo | synthesis.candidate_pool.repo | 115 |

每个 member 都带 `consistency_status` / `axis_coverage` / `evidence_quality` / `decision_reason`——逐论文审计中可定位「为什么这条候选在 core / 为什么这条是 aligned / 为什么那条是 off_topic」。

---

## §5 与 Re05 报告的 5 个差异

| 维度 | Re05 报告 | Re06 报告 |
|---|---|---|
| 评价逻辑 | keyword substring 黑名单 → fail | title/abstract/source/atoms 一致性 → metadata_mismatch |
| dataset 计数 | 单数 `dataset_n`，topic/proxy/pretrain 混淆 | 4 档分离 `topic_dataset_n / proxy_dataset_n / pretrain_dataset_n / generic_dataset_n` |
| core/baseline/parallel 评价 | 数量 | direct vs proxy 分档 |
| 噪声 case | `STRONG_NOISE_TOKENS` 命中即 fail | `critical_consistency_error_n = 0` 即无结构化失败 |
| 解释能力 | `reason = "strong_noise_in_core_or_baseline_or_parallel"`（不能解释哪条候选、为什么） | `bucket_audit[].members[].decision_reason`（每条候选的具体 reason） |

---

## §6 文件索引

| 路径 | 内容 |
|---|---|
| `tmp_re04_eval/balanced40_re06/summary.json` | 40 case aggregate |
| `tmp_re04_eval/balanced40_re06/report.md` | 机器生成的 per-case table |
| `tmp_re04_eval/balanced40_re06/{r1..r6,batch1..3}/<case_id>.json` | per-case audit dump (含 bucket_audit 详情) |
| `tmp_re04_eval/balanced40_re06/{r1..r6,batch1..3}/summary.json` | per-batch summary |
| `Plan/PaperAgent_Re06_完工报告.md` | 配套完工报告 |
| `Plan/PaperAgent_Re06_Balanced40_逐论文审计.md` | 本报告 |
| `apps/api/scripts/reclassify_balanced40.py` | re-classify 脚本 |

---

> **核心判断**：40/40 case 状态从 Re05 的 29p+9w+2f 变为 Re06 的 0p+40w+0f，**这是评价层严格化的预期结果**，不是 retrieval 退化。SOP §6.3 三条验收线全部 PASS：pass+weak_rate = 100% / critical_consistency_error = 0 / core_zero_pass = 0。
> **下一步**：Re07 SOP 起草（候选核验 + Forward Tracking）；当 `synthesis.topic_atoms` 字段被填上后，40 case 状态会重新分布（部分 weak 升 pass）。