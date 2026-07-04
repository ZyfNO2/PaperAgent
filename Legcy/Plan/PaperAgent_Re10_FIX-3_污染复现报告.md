# PaperAgent Re10 FIX-3 污染复现报告

> 生成日期: 2026-07-04
> 数据来源: `PaperAgent_Re10_FIX-2_抽样10审计.md`, `PaperAgent_Re10_FIX-2_Balanced40_逐论文审计.md`

## 1. 污染现象概述

Re10 FIX-2 的审计报告显示存在严重的跨题目污染问题：**ORB_SLAM3、open_vins、awesome-visual-slam** 这三个通用视觉工程被多个无关题目接收，并且被 case-level audit 判为通过。

## 2. 污染案例详情

### 2.1 抽样10案例（全部10/10受污染）

| case_id | 题目 | 是否SLAM相关 | 污染候选 | 污染来源 |
|---------|------|-------------|----------|----------|
| TYPICAL-01 | 室内移动机器人目标搜寻与抓取研究 | 否 | ORB_SLAM3, open_vins, awesome-visual-slam | repo查询过泛 |
| TYPICAL-02 | 基于点云多平面检测的三维重建关键技术研究 | 否 | ORB_SLAM3, open_vins, awesome-visual-slam | repo查询过泛 |
| TYPICAL-03 | 随机纹理背景下弱小缺陷检测的深度学习方法研究 | 否 | ORB_SLAM3, open_vins, awesome-visual-slam | repo查询过泛 |
| TYPICAL-04 | 基于深度学习的视觉SLAM语义地图的研究 | **是** | ORB_SLAM3, open_vins, awesome-visual-slam | 合理但需更多证据 |
| TYPICAL-05 | 基于深度学习的三维点云补全方法研究 | 否 | ORB_SLAM3, open_vins, awesome-visual-slam | repo查询过泛 |
| TYPICAL-06 | 基于深度学习的钢铁表面缺陷检测研究 | 否 | ORB_SLAM3, open_vins, awesome-visual-slam | repo查询过泛 |
| TYPICAL-07 | 基于改进YOLOv5模型的快速目标检测与测距算法研究 | 否 | ORB_SLAM3, open_vins, awesome-visual-slam | repo查询过泛 |
| TYPICAL-08 | 基于多种数据库的改进YOLO算法研究 | 否 | ORB_SLAM3, open_vins, awesome-visual-slam | repo查询过泛 |
| TYPICAL-09 | 基于深度学习的新材料地板缺陷检测技术研究 | 否 | ORB_SLAM3, open_vins, awesome-visual-slam | repo查询过泛 |
| TYPICAL-10 | 基于深度卷积神经网络的巡检图像电力部件识别方法研究 | 否 | ORB_SLAM3, open_vins, awesome-visual-slam | repo查询过泛 |

**统计**: 10/10 case 受污染，其中9/10为非SLAM相关题目。

### 2.2 Balanced40案例（部分受污染）

根据 `PaperAgent_Re10_FIX-2_Balanced40_逐论文审计.md` 的搜索结果，ORB_SLAM3/open_vins/awesome-visual-slam 出现在多个case的accepted_titles中，包括：
- 非SLAM题目（如钢铁表面缺陷检测、YOLO算法研究等）
- SLAM相关题目（如视觉SLAM研究）

## 3. 污染根因分析

### 3.1 Repo查询过泛

**问题代码位置**:
- `apps/api/app/services/agents/search_reflection_helpers.py`
- `apps/api/app/services/agents/search_reflection_loop.py`

**问题模式**:
```python
probe = f"{first_en} open source"
```

以及后续多轮检索中使用：
```python
atom = en_atom_pool[0]
must_search.append(f"{atom} github repository")
must_search.append(f"{atom} dataset benchmark")
must_search.append(f"{atom} baseline method")
```

**影响**: 当第一个英文关键词过泛（如 `deep learning`、`3D reconstruction`、`computer vision`），后续 repo/dataset/baseline 查询都会偏向通用热门工程。

### 3.2 接收标准不严格

**问题**: 当前 audit 里 `accepted_n >= 1` 就容易被判为通过，但没有强制要求候选命中题目轴：
- 方法轴：YOLO / U-Net / Transformer / LLM / SLAM / PointNet 等
- 对象轴：钢材裂缝 / 农作物 / 医学问答 / 绝缘子 / 混凝土 等
- 任务轴：检测 / 分割 / 识别 / 问答 / 评估 / 重建 等
- 场景轴：表面缺陷 / 遥感 / 医学 / 工业质检 / 农业 等

### 3.3 final_candidate_pool 保留污染seed

**问题代码位置**: `apps/api/app/services/agents/search_reflection_loop.py`

如果污染 repo 被加入 `seed_pool`，最后：
```python
"final_candidate_pool": list(seed_pool.values())
```

会把它原样带到最终结果。

## 4. 污染影响评估

### 4.1 严重性：**高**

- 100% 的抽样10案例受污染
- 90% 的非SLAM案例不应出现ORB_SLAM3
- 污染候选被错误标记为"通过"

### 4.2 污染传播路径

```
查询生成（泛化） → 候选获取（热门工程） → 接收标准宽松 → 报告输出（污染扩散）
```

### 4.3 对用户的影响

- 用户可能基于错误的审计结果选择不相关的研究方向
- 垃圾候选占据了有限的展示位置
- 真正相关的候选可能被挤出

## 5. 修复方向

根据 `PaperAgent_Re10_FIX-3_ORB_SLAM污染与主题轴验收修复_SOP.md`，需要：

1. **查询生成**: 从 first atom 改成主题轴组合
2. **候选接收**: 每条候选必须有 topic_axis_match
3. **通用repo污染检测**: 检测同一批次中重复出现的 top repo
4. **Validator 通过条件重写**: 不再使用 `new_candidates_n >= 1`

## 6. 验证要求

修复后必须验证：

- [ ] Case 1 (YOLO钢材缺陷检测) 不得出现 ORB_SLAM3/open_vins/awesome-visual-slam 作为 accepted
- [ ] Case 1 应出现钢材、表面缺陷、YOLO、NEU-DET、defect detection 等相关证据
- [ ] Case 2 (视觉SLAM) 可以出现 ORB_SLAM3，但必须同时有 SLAM 论文或数据集/benchmark 证据
- [ ] Case 3 (医学问答) 不得出现 CV/SLAM/U-Net fallback
- [ ] 三个 case 都必须显示 topic_axis_match

---

**报告状态**: 已完成污染复现，准备进入 Loop A 修复验证阶段。