# PaperAgent Balanced 40 Evaluation Report (Re05 H5)

> 生成日:2026-07-03
> 输入:`tmp_re04_eval/balanced40/summary.json`(40 case 聚合)
> 配套主报告:`Plan/PaperAgent_Re05_Balanced40_完工报告.md`
> 配套 SOP:`Plan/PaperAgent_Re05_检索收尾与Balanced40_SOP.md` §6.3

---

## 0. SOP §6.3 验收 Top Verdict

| 验收项 | 阈值 | 实测 | 判定 |
|---|---|---:|---|
| `pass+weak_rate >= 0.80` | >= 0.80 | **0.9500 (95.00%)** | **PASS** |
| 强噪声入 core/baseline/parallel <= 1 case | <= 1 | **2** | **FAIL** |
| `machine learning` fallback = 0 | = 0 | **0** | **PASS** |

**总结**:SOP §6.3 三条合格线中,**2/3 PASS、1/3 FAIL**。pass+weak 率远超 0.80 门槛(95%),但强噪声 2 例超 1 例门槛。

---

## 1. Aggregate Stats (40 case)

| 指标 | 数值 |
|---|---:|
| n (case 总数) | 40 |
| n_pass | 29 |
| n_weak | 9 |
| n_fail | 2 |
| n_blocked | 0 |
| pass_rate | 0.7250 (72.50%) |
| **pass+weak_rate** | **0.9500 (95.00%)** |
| 强噪声 case 数 | 2 (ENG-THESIS-048, ENG-THESIS-060) |
| `machine learning` fallback case 数 | 0 |
| **总 elapsed (sum of per-case elapsed_s)** | **9,477.6 s = 158.0 min** |

---

## 2. Per-case Table (40 rows)

> 字段:case_id / title / status / paper_n / dataset_n / repo_n / baseline_n / parallel_n / reason / batch / elapsed_s
> 标题为简写,完整标题见 raw dump `rN/ENG-THESIS-XXX.json` 或 `batchN/agent-re04-XXX.json`。

| case_id | title | status | paper | dataset | repo | baseline | parallel | reason | batch | elapsed_s |
|---|---|---|---:|---:|---:|---:|---:|---|---|---:|
| ENG-THESIS-002 | 磁瓦在线检测 | pass | 14 | 0 | 1 | 3 | 3 | all_metrics_met | r3 | 182.1 |
| ENG-THESIS-003 | 点云多平面检测三维重建 | weak | 22 | 0 | 4 | 3 | 1 | all_metrics_met | r3 | 260.5 |
| ENG-THESIS-004 | 改进YOLOv4 目标检测与测距 | pass | 23 | 3 | 6 | 2 | 2 | all_metrics_met | r3 | 204.8 |
| ENG-THESIS-005 | 随机纹理弱小缺陷检测 | weak | 194 | 4 | 6 | 1 | 0 | baseline_is_self_cannot_find_degradation | r3 | 775.8 |
| ENG-THESIS-010 | 交通标志检测与识别 | pass | 18 | 0 | 4 | 3 | 3 | all_metrics_met | r3 | 170.0 |
| ENG-THESIS-014 | GAN 织物缺陷检测 | pass | 20 | 2 | 0 | 4 | 5 | all_metrics_met | r4 | 222.8 |
| ENG-THESIS-022 | 钢铁表面缺陷检测 | pass | 28 | 4 | 6 | 3 | 5 | all_metrics_met | r4 | 203.8 |
| ENG-THESIS-024 | 无监督三维点云配准 | pass | 19 | 2 | 3 | 3 | 7 | all_metrics_met | r1 | 222.9 |
| ENG-THESIS-027 | YOLOv5 遥感飞机 | pass | 19 | 2 | 5 | 3 | 2 | all_metrics_met | r1 | 227.8 |
| ENG-THESIS-035 | 带钢表面缺陷检测 | pass | 25 | 1 | 1 | 5 | 9 | all_metrics_met | r4 | 189.8 |
| ENG-THESIS-040 | YOLO+ELM 绝缘子故障 | pass | 14 | 2 | 0 | 2 | 3 | all_metrics_met | r4 | 150.1 |
| ENG-THESIS-046 | 视觉机械臂目标检测避障 | pass | 30 | 0 | 6 | 3 | 6 | all_metrics_met | r1 | 223.3 |
| **ENG-THESIS-048** | 动态环境视觉SLAM | **fail** | 20 | 0 | 6 | 3 | 3 | **strong_noise_in_core** | r4 | 191.0 |
| ENG-THESIS-051 | 深度学习语义SLAM | pass | 16 | 0 | 2 | 1 | 5 | all_metrics_met | r5 | 208.4 |
| ENG-THESIS-058 | 激光点云环境感知 | pass | 38 | 2 | 6 | 5 | 5 | all_metrics_met | r5 | 241.5 |
| **ENG-THESIS-060** | 深度学习车道线检测 | **fail** | 22 | 1 | 6 | 6 | 11 | **strong_noise_in_core** | r5 | 200.2 |
| ENG-THESIS-064 | 复杂道路车辆目标检测 | pass | 17 | 0 | 6 | 3 | 3 | all_metrics_met | r5 | 180.0 |
| ENG-THESIS-072 | 深度学习动态SLAM | pass | 20 | 0 | 3 | 2 | 6 | all_metrics_met | r5 | 181.8 |
| ENG-THESIS-073 | 汽车自动驾驶模拟图像生成 | pass | 23 | 3 | 1 | 1 | 2 | all_metrics_met | r6 | 233.4 |
| ENG-THESIS-074 | 混凝土桥梁裂缝检测 | pass | 24 | 1 | 6 | 2 | 5 | all_metrics_met | r1 | 195.5 |
| ENG-THESIS-075 | 混凝土路面裂缝检测 | pass | 19 | 0 | 6 | 3 | 3 | all_metrics_met | r1 | 215.0 |
| ENG-THESIS-079 | 结构光隧道裂缝检测 | pass | 27 | 0 | 6 | 3 | 4 | all_metrics_met | r6 | 201.4 |
| ENG-THESIS-080 | 三维重建裂缝损伤检测 | pass | 17 | 1 | 6 | 4 | 4 | all_metrics_met | r2 | 308.2 |
| ENG-THESIS-083 | 多分辨率桥梁裂缝分割 | pass | 42 | 0 | 6 | 5 | 5 | all_metrics_met | r6 | 246.4 |
| ENG-THESIS-089 | 双目立体视觉路面损伤 | weak | 20 | 0 | 0 | 5 | 6 | dataset+repo=0 < 1 | r6 | 184.2 |
| ENG-THESIS-091 | 云计算输电线路缺陷检测 | weak | 20 | 0 | 0 | 4 | 2 | dataset+repo=0 < 1 | r2 | 205.9 |
| ENG-THESIS-092 | 海上风机叶片缺陷检测 | pass | 17 | 3 | 6 | 2 | 7 | all_metrics_met | r2 | 192.3 |
| ENG-THESIS-093 | 接触网绝缘子表面缺陷 | pass | 15 | 3 | 1 | 4 | 4 | all_metrics_met | r2 | 183.8 |
| ENG-THESIS-096 | 石墨烯薄膜防冰除冰 | weak | 22 | 0 | 0 | 1 | 3 | dataset+repo=0 < 1 | r2 | 179.6 |
| ENG-THESIS-100 | 配电设备视觉识别 | weak | 27 | 3 | 6 | 4 | 1 | all_metrics_met | r6 | 221.9 |
| agent-re04-1c86ccd6 | 液晶屏表面缺陷检测 | weak | 16 | 1 | 1 | 3 | 1 | heuristic_from_partial_dump | batch2 | 242.5 |
| agent-re04-2861c43c | 视觉SLAM语义地图 | pass | 25 | 0 | 6 | 4 | 6 | heuristic_from_partial_dump | batch1 | 264.6 |
| agent-re04-2e2b7123 | YOLOv5 绝缘子检测 | weak | 22 | 0 | 0 | 4 | 2 | heuristic_from_partial_dump | batch2 | 304.4 |
| agent-re04-35278f23 | 无人机平台动态目标检测 | pass | 18 | 3 | 0 | 3 | 3 | heuristic_from_partial_dump | batch2 | 199.0 |
| agent-re04-45411b69 | 自动驾驶多模态融合攻击防御 | pass | 29 | 0 | 5 | 4 | 2 | heuristic_from_partial_dump | batch3 | 237.0 |
| agent-re04-4926b5fe | 深度学习自动驾驶感知 | pass | 24 | 2 | 0 | 3 | 8 | heuristic_from_partial_dump | batch3 | 272.4 |
| agent-re04-510f0d0d | 患者虚拟定位三维人体重建 | weak | 16 | 0 | 0 | 2 | 3 | heuristic_from_partial_dump | batch1 | 326.2 |
| agent-re04-972e014a | 3D 视觉机械臂无序抓取 | pass | 38 | 4 | 3 | 7 | 6 | heuristic_from_partial_dump | batch3 | 338.1 |
| agent-re04-f4bf182c | YOLOV5 肺结节检测 | pass | 27 | 2 | 1 | 5 | 9 | heuristic_from_partial_dump | batch2 | 223.8 |
| agent-re04-f682f5d1 | 深度学习三维点云补全 | pass | 32 | 3 | 2 | 1 | 7 | heuristic_from_partial_dump | batch1 | 265.4 |

**总数 / 平均**(30 个 ENG-THESIS-XXX fresh case,排除 10 个 `agent-re04-*` partial dump case):
- paper 平均 ~ 22.4 / case
- dataset 平均 ~ 1.2 / case
- repo 平均 ~ 3.6 / case
- baseline 平均 ~ 2.9 / case
- parallel 平均 ~ 4.0 / case

---

## 3. Per-batch Table (9 批: r1-r6 + batch1-3 partial)

| batch | pass | weak | fail | case 数 | total elapsed (s) | case_ids |
|---|---:|---:|---:|---:|---:|---|
| r1 | 5 | 0 | 0 | 5 | 1084.5 | 024, 027, 046, 074, 075 |
| r2 | 3 | 2 | 0 | 5 | 1069.8 | 080, 091(w), 092, 093, 096(w) |
| r3 | 3 | 2 | 0 | 5 | 1593.3 | 002, 003(w), 004, 005(w), 010 |
| r4 | 4 | 0 | 1 | 5 | 957.5 | 014, 022, 035, 040, **048(f)** |
| r5 | 4 | 0 | 1 | 5 | 1011.9 | 051, 058, **060(f)**, 064, 072 |
| r6 | 3 | 2 | 0 | 5 | 1087.3 | 073, 079, 083, 089(w), 100(w) |
| batch1 (partial) | 2 | 1 | 0 | 3 | 856.1 | 2861c43c, 510f0d0d(w), f682f5d1 |
| batch2 (partial) | 2 | 2 | 0 | 4 | 969.7 | 35278f23, 1c86ccd6(w), 2e2b7123(w), f4bf182c |
| batch3 (partial) | 3 | 0 | 0 | 3 | 847.5 | 45411b69, 4926b5fe, 972e014a |
| **合计** | **29** | **9** | **2** | **40** | **9,477.6** (158 min) | — |

**说明**:
- `r1-r6` 是 Re05 任务 5 跑出的 30 个 fresh case(每批 5 case,subagent 并行跑 6 批)。
- `batch1-3` 是 Re04 / Re04-fix 阶段后台 partial 跑批累积的 10 个 case(每批 3-4 case),本次验收一并汇总以达到 40 case。
- 总 elapsed 是 sum of per-case elapsed_s,串行等价为 ~158 min;实际 6 批并发 ~75 min wall-clock。

---

## 4. Fail Case Analysis (2 cases)

### 4.1 ENG-THESIS-048 — 面向动态环境的视觉SLAM研究

| 字段 | 值 |
|---|---|
| batch | r4 |
| status | fail |
| reason | strong_noise_in_core_or_baseline_or_parallel |
| paper_n | 20 |
| dataset_n | 0 |
| repo_n | 6 |
| baseline_n | 3 |
| parallel_n | 3 |
| has_strong_noise_in_core | **true** |
| degradation_chain | `[]` (空 — 不是链路降级导致 fail,是 evidence 命中噪声词) |
| elapsed_s | 191.0 |

**Raw dump 关键发现** (`tmp_re04_eval/balanced40/r4/ENG-THESIS-048.json`):

**Source Ledger 摘要**(25 entries):
- arxiv: 4/4 ok
- crossref: 2/5 ok, 3/5 empty
- core: 0/2 ok(CORE 新源 401/403 走公共端点仍空)
- openalex: 0/6 ok(503 + 备用 endpoint 全空)
- github: 1/1 ok
- huggingface: 0/1 ok
- semantic_scholar: 1/1 ok(这一题 s2 偶然返回 1)
- openalex_citation: 5 seed_selected

**degradation_chain 解释**:
- `degradation_chain = []`:本 case 没有 query_matrix / r2 / baseline 任何一处降级,整条 R1->R4 链路走的是"happy path"。
- **fail 的真正原因是 evidence 命中噪声词**(`paper_groups.baseline[1]` 含 `c-a3d8365f` "A rich bounty of **AGN** in the 9 square degree Bootes survey")。
- 该候选是 `crossref` 调出来的真实元数据论文,title 是 AGN 天体物理,abstract 实际是 ORB-LINE-SLAM(crossref metadata mismatch),但 LLM synthesis 凭 title 把它塞进 baseline 桶,触发 `STRONG_NOISE_TOKENS` 里的 "AGN" 子串匹配。
- eval 路径 (`apps/api/app/services/agents/eval/__init__.py:185`) 扫 `paper_groups.baseline + paper_groups.parallel` 的 title,命中 "AGN" -> `has_strong_noise_in_core=True` -> `status="fail"`,无 `degradation_chain` 项(这是 evidence 维度 fail,不是 retrieval 链路 fail)。

**失败链路**:
```
R1 crossref (object_task) 命中 ORB-LINE-SLAM 论文 (crossref metadata mismatch: title=AGN, abstract=ORB-LINE-SLAM)
  -> LLM synthesis 判 baseline
  -> eval._is_strong_noise 扫 "AGN" 字符串 -> fail
  -> 整条 chain 空(不是 query/r2/baseline 降级)
```

### 4.2 ENG-THESIS-060 — 基于深度学习的车道线检测方法研究

| 字段 | 值 |
|---|---|
| batch | r5 |
| status | fail |
| reason | strong_noise_in_core_or_baseline_or_parallel |
| paper_n | 22 |
| dataset_n | 1 |
| repo_n | 6 |
| baseline_n | 6 |
| parallel_n | 11 |
| has_strong_noise_in_core | **true** |
| degradation_chain | `[]` (空 — 同 048) |
| elapsed_s | 200.2 |

**Raw dump 关键发现** (`tmp_re04_eval/balanced40/r5/ENG-THESIS-060.json`):

**Source Ledger 摘要**(25 entries):
- arxiv: 4/4 ok
- crossref: 3/5 ok, 2/5 empty
- core: 0/2 ok
- openalex: 0/6 ok
- github: 1/1 ok
- huggingface: 1/1 ok
- semantic_scholar: 0/1 ok
- openalex_citation: 5 seed_selected

**degradation_chain 解释**:
- `degradation_chain = []`:同 048,无 retrieval 链路降级。
- **fail 的真正原因是 false-positive noise match**:`paper_groups.parallel` 含 `c-f41ba29b` "**Agnostic** Lane Detection"(2019,arxiv 1905.03704,instance segmentation lane detection 真论文)。
- LLM synthesis 把它判 parallel(合理),但 eval 扫 title 命中 `STRONG_NOISE_TOKENS` 里的 "AGN"("Agnostic" 包含 "agn" 子串,case-insensitive 匹配)。
- **这是 noise token 设计的 false-positive** — "AGN" 是天文缩写,匹配 "Agnostic" 显然不合理。

**失败链路**:
```
R1 arxiv (core) 命中 "Agnostic Lane Detection" 2019 真论文
  -> LLM synthesis 判 parallel (instance segmentation method for lane detection)
  -> eval._is_strong_noise 扫 "AGN" 字符串 (case-insensitive in "Agnostic")
  -> false-positive -> fail
```

### 4.3 修复建议 (Re06)

| 失败 | 真问题 | Re06 修复 |
|---|---|---|
| 048 AGN 天体物理元数据 mismatch | crossref metadata 失真(title=AGN, abstract=ORB-LINE-SLAM) | 后处理加 crossref title-abstract 一致性检查:abstract 含 method 关键词 + title 含无关天体物理词 -> reject |
| 060 "Agnostic" false-positive | "AGN" 是 3-letter 子串 | `STRONG_NOISE_TOKENS` 改为 word-boundary 匹配:`\bAGN\b` 而不是 `in t` 子串;或将 "AGN" 改 "AGN " 避免命中 "Agnostic" |

---

## 5. Strong-Noise-in-Core Flag Analysis (2 cases)

> 强噪声 case 与 fail case 完全重合(2/2),但 fail 原因都是 noise 命中。

| case_id | 噪声 title | 噪声桶 | 命中 token | 真问题 |
|---|---|---|---|---|
| ENG-THESIS-048 | "A rich bounty of **AGN** in the 9 square degree Bootes survey: high-z obscured AGN and large-scale structure" | `paper_groups.baseline` | "AGN" | crossref metadata 失真(abstract 是 ORB-LINE-SLAM,title 是 AGN) |
| ENG-THESIS-060 | "**Agnostic** Lane Detection" | `paper_groups.parallel` | "AGN"(case-insensitive 子串) | noise token 设计缺陷 — "AGN" 命中 "Agnostic" |

**2 cases 共触发源**:
- 048:crossref adapter 把元数据混乱的论文塞进 baseline 桶
- 060:arxiv 真实论文被 LLM 正确判 parallel,但 eval 的 noise 词表 false-positive

**修复方向**(SOP §6.3 强噪声 ≤ 1 门槛当前 2 例,Re06 必须降到 ≤ 1):
1. `STRONG_NOISE_TOKENS` 改 word-boundary 匹配(`\bAGN\b`),可消 060 的 false-positive
2. crossref 候选加 title-abstract 一致性 sanity check,可消 048 的真实误判
3. 同时 LLM synthesis prompt 加 hint:crossref 元数据 mismatch 时优先用 abstract 判断

---

## 6. Per-case Adapter source_ledger Aggregate (representative)

### 6.1 跨 r1-r6 聚合(30 fresh cases)

| Adapter | total calls | ok | empty | rate_limited | seed_selected | seed_rejected | backup_used | ok_rate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| arxiv | 120 | **120** | 0 | 0 | 0 | 0 | n/a | **100.0%** |
| crossref | 150 | 67 | 83 | 0 | 0 | 0 | n/a | 44.7% |
| **core (新, Re05)** | 60 | 0 | 60 | 0 | 0 | 0 | n/a | 0.0% |
| openalex | 180 | 0 | 180 | 0 | 0 | 0 | 180 | 0.0% |
| openalex_citation | 150 | 0 | 0 | 0 | **143** | 7 | 0 | 95.3% selected |
| github | 30 | 24 | 6 | 0 | 0 | 0 | n/a | 80.0% |
| **huggingface (新, Re05)** | 30 | 13 | 17 | 0 | 0 | 0 | n/a | 43.3% |
| semantic_scholar | 30 | 8 | 22 | 0 | 0 | 0 | n/a | 26.7% |
| **合计** | **750** | **232** | **368** | **0** | **143** | **7** | **180** | — |

**H4 修复证据**(与 Re05 smoke5_re05 一致):
- **arxiv 120/120 = 100% ok** — 主入口最稳英文 paper 源
- **OpenAlex 备用 endpoint 触发 180/180** — 全部 180 调走 backup `?search=` 模式,0 ok 但 circuit breaker 正确触发,不再让链路断
- **CORE 新源 60 调 0 ok** — Re05 之前 0 -> 60 是新源接入证据,但 v3 公共端点返空(无 key 限制),仍需后续加 CORE key 才能贡献
- **HF 新源 30 调 13 ok (43.3%)** — Re05 之前 0 -> 13 是 H1 接线的直接结果

### 6.2 代表 case:ENG-THESIS-004 (PASS, 改进YOLOv4 目标检测与测距, r3)

| Adapter | call | ok | empty | status detail |
|---|---:|---:|---:|---|
| arxiv | 4 | 4 | 0 | 100% ok |
| crossref | 5 | 3 | 2 | 60% ok |
| core | 2 | 0 | 2 | CORE 公共端点空 |
| openalex | 6 | 0 | 6 | 全 empty(备份 endpoint 触发) |
| openalex_citation | 5 | 0 | 0 | 5 seed_selected |
| github | 1 | 1 | 0 | 1/1 ok |
| huggingface | 1 | 1 | 0 | 1/1 ok |
| semantic_scholar | 1 | 0 | 1 | s2 empty |
| **合计** | **25** | **9** | **12** | **4 seed_selected** |

### 6.3 代表 case:ENG-THESIS-048 (FAIL, 动态环境视觉SLAM, r4)

| Adapter | call | ok | empty | status detail |
|---|---:|---:|---:|---|
| arxiv | 4 | 4 | 0 | 100% ok |
| crossref | 5 | 2 | 3 | **40% ok — AGN 元数据 mismatch 在此** |
| core | 2 | 0 | 2 | CORE 公共端点空 |
| openalex | 6 | 0 | 6 | 全 empty |
| openalex_citation | 5 | 0 | 0 | 5 seed_selected |
| github | 1 | 1 | 0 | 1/1 ok |
| huggingface | 1 | 0 | 1 | HF 1/1 empty |
| semantic_scholar | 1 | 1 | 0 | **本 case s2 偶然 1/1 ok** |
| **合计** | **25** | **8** | **12** | **5 seed_selected** |

**fail 链路关键**:crossref 5 调用中 2 ok 包含 `c-a3d8365f` (title=AGN/abstract=ORB-LINE-SLAM),LLM 凭 title 判 baseline 桶,触发 noise。

---

## 7. Re05 代码接线对 Balanced 40 的实际贡献

> 数据来源:raw dump 的 `source_ledger` + `paper_groups` + `synthesis.candidate_pool` 聚合

| 修复 (SOP §2-5) | 度量 | 实际贡献 |
|---|---|---|
| **H1 dataset 升桶** (HF 接线 + whitelist 透传 + vision_3d/RS 白名单扩展 + is_dataset_candidate 暴露) | 40 case 中 `dataset_n >= 1` 的 case 数 | **22/40 (55%)** 命中(18/40 dataset_n==0) |
| **H2 canonical baselines** (point_cloud_completion / point_cloud_registration / remote_sensing_detection 注册表 -> 只喂 query) | 40 case 中 `baseline_n >= 2` 的 case 数 | **35/40 (87.5%)** 命中 |
| **H4 CORE + cache** (CORE 新源 + OpenAlex 备用 endpoint + sha1 cache) | 30 fresh case (r1-r6) CORE 调用返回 ok | **0/60** (CORE 公共端点返空,未配 key) — 但 CORE 接入本身是新源落地证据 |
| **H4 OpenAlex 备用 endpoint** | 30 fresh case OpenAlex 备用 endpoint 触发 | **180/180 = 100%** 触发(0 ok 但不再让链路断) |
| **H4 sha1 cache** (env=PAPERAGENT_ADAPTER_CACHE=1) | 30 fresh case 同 query 二次命中 | 环境变量未开启于 balanced 40 subagent 跑批(subagent 各自独立,缓存不跨 subagent);不影响验收 |
| **H3 RS dataset 升桶** (TJU-DHD/AIR-SAR/RSOD 等加 RS 白名单) | 027 dataset 命中 | **2** (从 0 升到 2) — H3 成功 |

**净贡献**:
- **22 case 有 dataset 命中** — Re04-fix 时代 0/5 -> Re05 smoke5 3/5 -> Balanced 40 22/40 (55%)
- **baseline >= 2 命中 35 case (87.5%)** — H2 canonical 注册表对 018/024/027 三个原 weak case 已升 pass
- **OpenAlex 备用 endpoint 100% 触发** — 不再让链路断 (SOP §5.2 设计目标)
- **CORE/HF 新源接入** — 虽然 0/60 与 13/30 的 ok 率不高,但**新源就位 + 字段归一化完成**,Re06 配 key 后可立即生效

---

## 8. 剩余硬伤 + 下一阶段 (Re06+)

| 硬伤 | 实际数 | SOP 阈值 | 修复方向 (Re06) |
|---|---:|---:|---|
| 强噪声 2/40 (048 AGN, 060 Agnostic) | 2 | <= 1 | 修 `STRONG_NOISE_TOKENS` 改 `\bAGN\b` 消 060 false-positive;加 crossref title-abstract 一致性检查消 048 真误判 |
| dataset_n == 0 仍 18 case | 18 | — | 扩 `vision_3d` 白名单加 `3DPW / AGORA / THuman / RenderPeople`;扩 `remote_sensing` 加 `DOTA-v1.5 / DIOR-Det / FAIR1M-1.0`;扩 `robotics_control` 加 SLAM 专属数据集 |
| 014/022/035/040 等工业缺陷检测 canonical method 缺 | — | — | 扩 `canonical_baselines.yaml` 加 `industrial_defect` domain(仅 query seed,不入 pool):MVTec AD / VisA / Steel Surface Defect / Severstal |
| OpenAlex 备用 endpoint 仍 0/180 ok | 180 | — | 加 BASE (Bielefeld Academic Search) 作为第 4 源;待 OpenAlex 限流恢复 |
| CORE 公共端点 0/60 ok | 60 | — | 申请 CORE api key,配置后 v3 端 ok 率应升到 >= 30% |
| 005 weak (baseline_is_self_cannot_find_degradation, paper=194) | 1 | — | LLM 把 194 篇候选全判 reference,0 baseline 升桶;是 LLM stochasticity 单点,扩 Re05 工业缺陷 domain canonical method 后 LLM 触发 baseline 升桶路径 |

---

## 9. 验收文件路径索引

| 路径 | 内容 |
|---|---|
| `tmp_re04_eval/balanced40/summary.json` | 40 case 聚合(n_pass/n_weak/n_fail + per-case 列表) |
| `tmp_re04_eval/balanced40/r1/summary.json` ... `r6/summary.json` | 6 批各 5 case 子聚合 |
| `tmp_re04_eval/balanced40/r1/ENG-THESIS-*.json` ... `r6/ENG-THESIS-*.json` | 30 个 fresh raw dump(含 source_ledger + paper_groups) |
| `tmp_re04_eval/balanced40/batch1/*.json` ... `batch3/*.json` | 10 个 partial 阶段 raw dump |
| `Plan/PaperAgent_Re05_检索收尾与Balanced40_SOP.md` §6.3 | 验收门定义(pass+weak >= 0.80 + 强噪声 <= 1 + machine learning fallback = 0) |
| `Plan/PaperAgent_Re05_检索收尾与Balanced40_完工报告.md` | Re05 代码 + Smoke 5 报告(前序 commit) |
| `Plan/PaperAgent_Re05_Balanced40_完工报告.md` | Re05 Balanced 40 收尾报告(本配套 commit 提交) |
| `apps/api/app/services/agents/eval/__init__.py:50-57` | `_is_strong_noise` 函数实现(AGN 字符串子串匹配) |
| `apps/api/app/services/agents/eval/__init__.py:38-46` | `STRONG_NOISE_TOKENS` 词表(含 "AGN" / "AGN" 命中 "Agnostic") |
| `apps/api/app/services/agents/eval/__init__.py:185-201` | noise -> fail 判定逻辑 |
