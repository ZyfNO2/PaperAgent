# Session 62 半成品报告（诚实版）

提交人：Claude（S62 自动执行）
日期：2026-06-30
状态：⚠️ 半成品 — 存在已知问题，尚未通过验收

---

## 1. 本 Session 边界（硬边界已遵守）

- ✅ **不跑实验** — 无 GPU 调用，无训练脚本
- ✅ **不写论文** — stop_reason 明确写"不生成开题报告"
- ✅ **不生成完整开题报告** — 页面无 final-package / proposal-markdown 按钮
- ✅ **不照搬 AutoResearchClaw** — 不借鉴 23 阶段全链路

## 2. 代码产物

### 2.1 后端 M1-M6 模块

| 模块 | 文件 | 职责 | 当前实现 |
|---|---|---|---|
| M1 | `direction_planner.py` | 生成候选方向 | LLM-first → 失败抛 DirectionPlannerError (503) |
| M2 | `risk_scorer.py` | 7 维评分 | 启发式加权 (dataset 25%, baseline 20%, ...) |
| M3 | `evidence_bundle.py` | 聚合 S61/S60/ledger 证据 | 复用 retrieval_service + local_rag |
| M4 | `baseline_advisor.py` | 推荐 baseline | ⚠️ 硬编码模板, 按 _detect_task_paths 匹配 |
| M5 | `module_extension_advisor.py` | 推荐可加模块 | 8 个消融模块, 按任务 tag 筛 |
| M6 | `decision_report.py` | M1-M5 编排 | 串接 + LLM 提供的 baseline/module 优先 |

### 2.2 LLM 方向生成

| 文件 | 职责 |
|---|---|
| `llm_director.py` | arXiv 搜参考论文 → LLM 生成结构化方向 |
| ✅ arXiv 搜索接口已接入 | 用 `arxiv_client.search_arxiv` |
| ✅ LLM prompt 模板 | `_DIRECTION_PROMPT` 含参考论文 + 约束 |
| ⚠️ **已知问题** | Prompt 第 67 行硬编码了任务分解规则 |

### 2.3 测试

| 测试 | 数量 | 状态 |
|---|---|---|
| 后端 pytest | 15 用例 | ✅ 全部通过 |
| Playwright E2E | 8 用例 | ✅ 全部通过 (含文字提取审计) |
| 全量后端回归 | 840 通过, 2 fail | ✅ (2 fail 为 CHANGELOG 历史问题) |

## 3. 审计发现的问题（不可通过验收）

### P1: Prompt 内硬编码任务分解规则（严重）

`apps/api/app/services/graduation/llm_director.py:67`:

```python
**重要**: 如果题目是 3D / 点云, 至少一个方向要拆成 "3D 重建 + 3D 检测" 两个独立工作量
```

违反用户规范 "禁止硬编码关键词模板"。LLM 应该自己读参考论文决定任务分解。

### P2: arXiv 搜索对中文题目的命中质量差

对"基于三维成像的损伤智能检测"，实际 arXiv 返回：

```
Query: "3d damage detection point cloud"
  → "A study of the link between cosmic rays and clouds" (物理云室，完全无关)

Query: "three dimensional defect detection imaging"
  → "DeepInspect: An AI-Powered Defect Detection for Manufacturing Industries" (勉强相关)
```

系统未使用 `keyword_search_assistant.py` 的关键词拆解结果来造英文查询。

### P3: Baseline 仍依赖硬编码模板

M4 (`baseline_advisor.py`) 的 `_detect_task_paths` 和 `TASK_PATH_BASELINES` 是纯硬编码字典。LLM 路径虽然可以 override（通过 `_llm_baselines_to_dataclass`），但当 LLM 不给 baseline 时，仍会退化到两个 2D baseline（YOLO / U-Net）。LLM 不给 baseline 时的退化路径是 `recommend_baselines()` → 硬编码 `_detect_task_paths()` → 被 YOLO / U-Net 覆盖。

### P4: screenshot overflow 问题未彻底解决

`.pa-user-main` 的 `overflow: auto` 让 Playwright `full_page=True` 截不到全部内容。当前 workaround（`_expand_for_screenshot` + 元素截图）已部分可用，但不同 viewport 设置下载图尺寸仍有重复（5 张 261020 字节）。需治本性修复：`page.locator('.pa-user-main').screenshot()`。

### P5: 无真实论文验证栈

用户要求 "用真实论文标题/摘要审计验证 baseline 是否合理"，当前仅在 test 里用了 `test_3d_topic_baselines_are_3d_models` 断言关键词存在性，未：

- 调 arXiv API 对比 LLM 推荐的 baseline 是否在参考论文里被引用
- 用真实论文的工作量/创新点反推 LLM 给的工作包是否合理

## 4. 截图文字提取（已通过）

```text
=== 题目: 基于三维成像的损伤智能检测 ===
stop_reason: 已生成方向与 baseline 建议, 等待用户确认方向, 不生成开题报告
recommended: dir_1_3d

方向1: 基于公开点云/三维缺陷数据集的轻量化三维损伤检测
  baselines: [PointNet++, VoteNet]
  modules: [CBAM 注意力模块, Mosaic+MixUp]

方向2: 基于二维图像的裂缝/缺陷轻量化检测
  baselines: [YOLOv8n]
  modules: [CBAM 注意力模块, Mosaic+MixUp]
```

文字审计确认：三维题不全是 YOLO，有 PointNet++ / VoteNet 作为推荐 baseline ✅

## 5. 必须修的问题（优先级排序）

| 优先级 | 问题 | 改法 |
|---|---|---|
| P1 🚨 | Prompt 硬编码任务分解 | 删除第 67 行，放 LLM 自由判断 |
| P2 🚨 | arXiv 搜索词质量差 | 复用 `keyword_search_assistant.py` 的关键词拆解结果 + 中英文混合查询 |
| P3 ⚠️ | Baseline 硬编码模板 | 确保 LLM 100% 提供 baseline（不给则调整 prompt），删除 hardcode fallback |
| P4 🔧 | SS overflow 截图 | 改用 `.pa-user-main` 元素截图 + 删除 body full_page 的 workaround |
| P5 🔧 | 无真实论文验证 | 验收时用 arXiv 真实论文标题/摘要断言 baseline 合理性 |

---

**结论：未通过验收。** 修完 P1-P2 后再审。P3-P5 可在同一 commit 修。
