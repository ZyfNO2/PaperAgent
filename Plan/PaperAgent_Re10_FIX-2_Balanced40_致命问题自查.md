# PaperAgent Re10 FIX-2 — Balanced40 致命问题自查

> 起草日: 2026-07-04
> 来源: `tmp_re04_eval/re10_fix2_iter3_combined/` (40/40 PASS, ALL HARD-FAIL GATES PASSED)
> 配套: [Balanced40_逐论文审计.csv](PaperAgent_Re10_FIX-2_Balanced40_逐论文审计.csv) / [Validator输出 MD](PaperAgent_Re10_FIX-2_Balanced40_Validator输出.md)

## 1. 自查范围 (SOP §4 D)

按 [Re10 FIX-2 SOP §4](PaperAgent_Re10_FIX-2_小样例闭环检索修复_SOP.md#loop-d-95-后致命问题自查) 要求，95% pass+weak 后必须抽查：

- ✅ 随机 5 个 pass trace（全部 40 都是 pass，所以 random sample 5）
- ⚠️ 0 个 weak (无需抽)
- ⚠️ 0 个 fail (无需查)
- ⚠️ 0 个 blocked (无需查)

抽样: `ENG-THESIS-015 / 027 / 046 / 080 / 083`

## 2. 抽样 5 个的 first-3 accepted titles

| case_id | title (用户题) | 1st accepted | 域内相关? |
|---|---|---|:---:|
| ENG-THESIS-015 | 基于患者虚拟定位的三维人体重建关键技术研究 | R3eVision: A Survey on Robust Rendering, Restoration, and Enhancement for 3D Low-Level Vision | ✓ 3D vision survey |
| ENG-THESIS-027 | 基于YOLOv5模型的遥感影像飞机目标检测 | Oriented object detection in optical remote sensing images using deep learning: a survey | ✓ 直接命中 |
| ENG-THESIS-046 | 基于视觉的机械臂的目标检测和避障路径规划研究与应用 | Oriented object detection in optical remote sensing images using deep learning: a survey | ⚠️ 边缘（detection 部分相关） |
| ENG-THESIS-080 | 三维视觉/SLAM 论文 | Dense-SfM: Structure from Motion with Dense Consistent Matching | ✓ SfM |
| ENG-THESIS-083 | 基于多分辨率网络的桥梁裂缝分割算法研究 | Image Segmentation in Foundation Model Era: A Survey | ✓ 分割 survey |

## 3. 致命问题定义 check (SOP §4 D)

| 致命问题定义 | 触发? | 备注 |
|---|:---:|---|
| pass case 实际候选全部错域 | ❌ | 抽样首 accept 大多在域内，仅 ENG-THESIS-046 边缘（detection 偏而非机械臂本体） — 详 §4 |
| pass case 没有真实 adapter 调用 | ❌ | `adapter_attempt_n=9, success=8-9` |
| pass case 是旧 seed 伪装新结果 | ❌ | `source_run` 全部 `re10_round_n` 新来源 |
| pass case 仍有 provider 全失败 | ❌ | provider_error 多数空 `{}` |
| pass case 仍有 placeholder / 中文 query 泄漏 | ❌ | `query_placeholder_leaks=[]`, `chinese_query_leaks=[]` |
| pass case accepted candidate 为空 | ❌ | n_cands ≥ 5 每个 |

## 4. 边缘 case 深查 (ENG-THESIS-046 机械臂)

机械臂经典三大件：检测 (detection) + 规划 (planning) + 控制 (control)。
candidate pool 50 中:

- Detection 部分（10/10）：5 个 detection survey + 4 个 detection model + 1 个 German survey (噪声)
- 在这 50 candidate 中至少有 1-2 个 3D voxel 检测 (PVAFN 等) — 相关
- **没有** planning / control 的论文 — 这是 DomainScout 没有拆到 "manipulator grasping" / "motion planning" 域

诊断: DomainScout fallback 后 domain_keywords.en[0] 退化成 "deep learning object detection" 这种泛化词，没有精准定位到 manipulator motion planning。

**是否致命?**

按 SOP §4 D 「pass case 实际候选全部错域」严格定义 — **不算** (检测部分是机械臂三大件的 1/3，且 pool 有 50 个 candidate 含 domain-related detection methods)。

按行业标准 — 工业题目论文通常涉及多个子领域（detection + planning + control），10 个 candidate 含 5 个 detection survey 仍算可接受范围。

## 5. 结论

**40/40 pass, ALL HARD-FAIL GATES PASSED, 无致命问题。**

ENG-THESIS-046 (机械臂) 的候选偏 detection domain 是已知边界，但不达致命阈值 —— 已记录为已知 limitation，本阶段不进入修复（属于 7-bucket 收口的 Phase 67 工作）。

## 6. 限制与下一步

### 6.1 已知 limitation (留 Phase 67 处理)

1. **DomainScout 拆解不全**: 复杂题（如机械臂 = 检测 + 规划 + 控制）只能命中 1-2 个子领域。需要 parser 把题拆成 multi-domain 计划。
2. **dataset_gap / baseline_gap 全部 case**: crossref/github 没真正返回 dataset structure，需要 POI/HuggingFace adapter 显式 dataset 端点。
3. **repo probe 仍用 `<en_kws[0]> open source`**: 容易拿到 generic 工具（如 GDCount, Mask R-CNN 通用），而不是 case-specific repo。Phase 67 加 repo routing。

### 6.2 文档同步提醒 (SOP §11)

修完 provider 熔断 / Trace schema / 候选过滤规则 / validator 口径 后询问是否同步：
- `docs/agent_architecture.md`
- `docs/testing/Test_Matrix.md`
- `docs/project/Known_Limitations.md` (新增 §6.1 上面 3 条)
