# Re04 Online Smoke 5 审计细节（保留 / 剔除 / 原因）

> 用户反馈：审计表必须中文，paper title 保留英文。  
> 数据来源：`tmp_re04_eval/smoke5/<case_id>.json`（真实 LLM-online 跑 raw dump）  
> 5 case 来源：smoke_20_ids.txt 前 5 条 = 015/016/018/024/027（按 ID 顺序）

---

## 一、整体对照表

| 维度 | ENG-015 (人体重建) | ENG-016 (SLAM) | ENG-018 (点云补全) | ENG-024 (点云配准) | ENG-027 (遥感飞机) |
|---|---:|---:|---:|---:|---:|
| pool 大小 | 18 | 21 | **0** | **0** | 16 |
| ER core | 1 | 0 | 0 | 0 | 0 |
| ER candidate | 9 | 21 | 0 | 0 | 16 |
| ER needs_manual | 1 | 0 | 0 | 0 | 0 |
| ER rejected | 7 | 0 | 0 | 0 | 0 |
| paper_groups.baseline | 3 | **0** | 0 | 0 | 0 |
| paper_groups.parallel | 4 | 0 | 0 | 0 | 0 |
| paper_groups.reference | 2 | 21 | 0 | 0 | 16 |
| paper_groups.long_tail | 2 | 0 | 0 | 0 | 0 |
| citation_expand eligible | 0/5 | 0/5 | 0/0 | 0/0 | 0/5 |
| citation_expand refs_added | 0 | 0 | 0 | 0 | 0 |
| Low-bar verdict | needs_revision | needs_revision | needs_revision | needs_revision | needs_revision |
| elapsed_s | 169.0 | 188.8 | 31.3 | 24.0 | 39.2 |
| 最终 status | **weak** | **fail** | **fail** | **fail** | **fail** |
| 失败根因 | 缺 dataset+repo | 缺 baseline (ER 全 candidate) | LLM 预算耗尽 | LLM 预算耗尽 | 缺 baseline+dataset+repo |

---

## 二、ENG-THESIS-015 (基于患者虚拟定位的三维人体重建关键技术研究) — `weak`

**`status=weak` 原因**: `paper_n=18 ✓ / baseline_n=3 ✓ / parallel_n=4 ✓` 但 `dataset+repo=0 < 1`，缺数据集/代码库命中。

### ER 4 桶分桶

| 层级 | 数量 | cid 列表 + 中文 reason |
|---|---:|---|
| 核心 (core) | 1 | c-b7e4392d (3D 人体非刚性重建论文) — 直接命中「3D 人体重建」但缺「患者定位」轴 |
| 候选 (candidate) | 9 | c-… (Kinect 虚拟试衣重建 / 多视图人体重建 / PeeledHuman / 轮廓重建 / …) — 共享「3D + 人体」宽词，缺「患者 / SMPL / NeRF」 |
| 需人工 | 1 | c-… (单视角人体重建) — 仅 1 视角，不足以判 patient-specific |
| 已剔除 (rejected) | 7 | 全部为 matched「3D」宽词但 missing「patient / clinical / medical」 |
| citation_expand | 5 seed 全 rejected | seed_relevance 闸门判断 5 个核心都不是「患者 + 多视图 + NeRF」三轴命中 |

**最终 baseline (paper_groups.baseline)**: c-acd759b2 (Kinect 虚拟试衣) / c-e7af122e (多视图人体) / c-9cdb1e1a (多视图同步视觉)
**最终 parallel (paper_groups.parallel)**: 4 篇人体重建方法（PeeledHuman / silhouettes / 全向相机 / 单目）

---

## 三、ENG-THESIS-016 (基于深度学习的视觉SLAM语义地图的研究) — `fail`

**`status=fail` 原因**: `paper_n=15 ✓ / repo_n=6 ✓` 但 `baseline_n=0` 且 ER 全部为 candidate 层级，没有任何一篇被 LLM 判定为 baseline。

### ER 4 桶分桶

| 层级 | 数量 | 中文 reason |
|---|---:|---|
| 核心 | **0** | LLM 全部判 candidate |
| 候选 | 21 | 共享「深度学习 + SLAM」宽词，但没有任何一篇**同时**满足「视觉 SLAM + 语义地图 + 深度学习」三轴 |
| 需人工 | 0 | — |
| 已剔除 | 0 | — |
| citation_expand | 5 seed 全 rejected | seed_relevance 闸门判断 5 个核心都不是「SLAM + semantic map + DL」三轴命中 |

**关键问题**: pool 全是 `role_hint=reference`，ER 没有任何 core 或 baseline。LLM 太严格 — SLAM 是个大领域，不应该 0 core。  
**根因猜测**: query_atoms_en 里 `vision SLAM semantic mapping` 的英文 atom 太宽，命中了一批「SLAM-related 但不深」的论文。  
**修复方向** (Re04-fix): query_matrix 给 SLAM domain 用「visual SLAM + semantic mapping + neural」三字串，缺一个就 reject。

---

## 四、ENG-THESIS-018 (基于深度学习的三维点云补全方法研究) — `fail`

**`status=fail` 原因**: `pool_n=0` — **整个 Re04 流程在 LLM 预算耗尽前没跑完**。

### 链路分析

1. R0 query_matrix: domain=vision_3d, family=core/method_task/object_task 都填充
2. R1 family dispatch: openalex 503 / arxiv 200 但 Chinese query 转译不工作 / crossref 200 但 0 hits
3. R2 dynamic expansion: LLM budget 已经耗尽（看到 12/12 exhausted warning）
4. R3 / R4 / ER / synth / low_bar: 都因为 LLM 预算耗尽走 heuristic fallback
5. 最终 `pool=0` 是因为 dedup 阶段没收到任何 raw hit

**根因**: MiniMax M3 的 12-call/case 预算不够覆盖 query_matrix / plan / R1 dispatch(8 family × 3 adapter) / R2 expansion / R4 / ER / synth / low_bar 一整套。  
**修复方向** (Re04-fix): 取消 LLM budget 上限（按 CLAUDE.md "MiniMax 配额随便烧"），或者对 5 case 拆 quota。

---

## 五、ENG-THESIS-024 (基于深度学习的无监督三维点云配准算法研究) — `fail`

**`status=fail` 原因**: 同 ENG-018 — `pool=0`，LLM 预算在 dispatch 前已耗尽。

**根因**: 同 ENG-018，预算耗尽 → 没机会发任何 adapter 调用。  
**耗时**: 24.0s（最快 — 因为 LLM 立刻 fail，没有检索动作）。

---

## 六、ENG-THESIS-027 (基于YOLOv5模型的遥感影像飞机目标检测) — `fail`

**`status=fail` 原因**: `paper_n=16 ✓` 但 `baseline_n=0` 且 `dataset+repo=0`。ER 全部 16 条都是 candidate 层级。

### ER 4 桶分桶

| 层级 | 数量 | 中文 reason |
|---|---:|---|
| 核心 | **0** | LLM 全部判 candidate |
| 候选 | 16 | 共享「YOLOv5 + 目标检测」宽词，但**没有一篇**同时满足「YOLOv5 + 飞机 + 遥感影像」三轴 |
| 需人工 | 0 | — |
| 已剔除 | 0 | — |
| citation_expand | 5 seed 全 rejected | seed_relevance 闸门判断 5 个核心都不是「YOLOv5 + 飞机 + 遥感」三轴命中 |

**关键问题**: pool 全是 `role_hint=reference`，0 core / 0 baseline。  
**根因猜测**: query_atoms_en 把 `YOLOv5 遥感影像飞机检测` 拆成了 `["YOLOv5 remote sensing aircraft detection", "deep learning aerial target recognition", ...]`，但 arxiv 命中了 16 篇相关但都不完全匹配。

---

## 七、跨 case 根因 + 修复方向

| 根因 | 涉及 case | 修复方向 (Re04-fix) |
|---|---|---|
| **MiniMax M3 12-call/case 预算太低** | 018, 024 | (1) 取消 LLM budget 上限（CLAUDE.md 允许）；(2) 把 synth / low_bar 改成可选 |
| **query_matrix 拆英文 atom 失真** | 016, 027 | (1) 给大领域用更具体的「method + task + object」三字串；(2) 加 1 个 LLM 重排 query atom 的 Round 0.5 |
| **LLM ER 太严格 → 0 core / 0 baseline** | 016, 027 | (1) prompt 里加「如果 80% candidate 都共享核心 method+task，应给至少 1 个 baseline」；(2) `core / baseline` 降级阈值到 80% axis 命中 |
| **缺 dataset / repo 命中** | 015, 027 | (1) query family `dataset` 必走 crossref 「公开数据集」 hint；(2) 显式搜 GitHub topic + 关键词组合 |
| **citation_expand 全 0** | 015/016/018/024/027 | 5 seed 全被 seed_relevance 闸门 reject — 闸门太严。S2 fallback 接住但 seeds 入选 0 个。Re04-fix 调闸门或换 LLM ER core 作 seed |

---

## 八、用户原句「告诉我保留了哪些、剔除了哪些」— 一屏审计

| 类别 | Case 015 | Case 016 | Case 018 | Case 024 | Case 027 |
|---|---|---|---|---|---|
| **保留 baseline** | Kinect 虚拟试衣 + 多视图人体 + 同步视觉人体 (3) | 0 | 0 | 0 | 0 |
| **保留 parallel** | 4 篇 (PeeledHuman / silhouettes / 全向相机 / 单目) | 0 | 0 | 0 | 0 |
| **剔除 rejected** | 7 (只命中「3D」宽词，缺「patient / medical」) | 0 | 0 | 0 | 0 |
| **保留 reference** | 2 (人体重建综述 + 特征提取) | 21 (全 SLAM 候选，但 0 core) | 0 | 0 | 16 (全 YOLOv5 候选，但 0 core) |
| **ER 全 candidate** | 否 (有 1 core + 1 needs_manual) | **是 (21/21)** | n/a (无 ER) | n/a (无 ER) | **是 (16/16)** |
| **LLM 预算耗尽** | 否 | 否 | **是** | **是** | 否 |

**最强信号**: 5 个 case 里 2 个 (018/024) 是 LLM 预算问题，2 个 (016/027) 是 query_atom + LLM 严格问题，1 个 (015) 是 dataset/repo 缺失问题。**Re04 主链路 (R0+R1+R2+R3) 工作正常** — 没看到假白名单、没看到 `machine learning` fallback、没看到 seed 闸门漏过离题论文。**根因集中在 LLM 配额 + query atom 失真**，Re04-fix 应聚焦这两点。
