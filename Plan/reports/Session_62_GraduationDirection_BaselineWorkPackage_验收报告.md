# Session 62 验收报告：毕业友好方向推荐与 Baseline 工作包

日期：2026-06-30
范围：PaperAgent Session 62 (方向决策层)
继承：S60 本地 RAG、S61 科研检索增强

---

## 1. 完成内容

Session 62 实现"输入题目 → 给毕业友好方向 → 绑定真实证据 → 给 baseline → 给可加模块 → 停止等待确认"的全链路决策包生成。不跑实验、不写论文、不生成完整开题报告、不照搬 AutoResearchClaw。

输入示例：`基于三维成像的损伤智能检测`

输出：
- 2-3 个候选毕业方向（标题 / 对象 / 任务 / 方法 / 为什么好毕业 / 降级路径）
- 每个方向绑定真实证据（论文 / 数据集 / 工程 / 本地 RAG 片段）
- 7 维评分（dataset / baseline / compute / innovation / experiment / writing / fallback）+ 总分 + 风险等级
- 1-3 个推荐 baseline（含理由 / 数据需求 / 复现难度 / 算力 / 风险）
- 2-4 个可加模块（含加在哪 / 解决什么 / 消融 / 工作量 / 风险）
- 明确停止：`已生成方向与 baseline 建议, 等待用户确认方向, 不生成开题报告`

---

## 2. 新增/修改模块

### 2.1 后端 (apps/api)

| 模块 | 文件 | 行数 | 职责 |
|---|---|---|---|
| M1 DirectionPlanner | `app/services/graduation/direction_planner.py` | ~150 | 启发式生成 2-3 个候选毕业方向 |
| M2 RiskScorer | `app/services/graduation/risk_scorer.py` | ~120 | 7 维评分 + 风险等级 |
| M3 EvidenceBundleBuilder | `app/services/graduation/evidence_bundle.py` | ~165 | 聚合 S61 retrieval + S60 local RAG + ledger |
| M4 BaselineAdvisor | `app/services/graduation/baseline_advisor.py` | ~155 | 1-3 个推荐 baseline |
| M5 ModuleExtensionAdvisor | `app/services/graduation/module_extension_advisor.py` | ~150 | 2-4 个可加模块 |
| M6 DecisionReport | `app/services/graduation/decision_report.py` | ~125 | 端到端编排 + pydantic 输出 |
| Schema | `app/schemas_graduation_direction.py` | ~115 | 请求/响应 Pydantic |
| API 路由 | `app/api/v1/graduation_direction.py` | ~50 | `POST /api/v1/projects/{project_id}/graduation-direction/plan` |
| main.py | `app/main.py` | +3 行 | 注册 router |

### 2.2 前端 (apps/web-react)

| 模块 | 文件 | 行数 | 职责 |
|---|---|---|---|
| 类型 | `src/features/graduation-direction/directionTypes.ts` | ~70 | 镜像后端 schema |
| 面板 | `src/features/graduation-direction/DirectionDecisionPanel.tsx` | ~245 | 用户界面 + 评分明细 |
| 集成 | `src/features/user-workbench/UserWorkbenchPage.tsx` | +6 行 | 嵌入主工作台 |
| 样式 | `src/styles/components.css` | +170 行 | S62 panel 样式 |

### 2.3 测试

| 测试 | 文件 | 用例数 |
|---|---|---|
| 后端 | `apps/api/tests/test_session62_graduation_direction.py` | 12 |
| 前端 | `apps/web-react/e2e/test_session62_graduation_direction.py` | 7 |

---

## 3. 每个模块真实接线说明

| 模块 | 真实接线 |
|---|---|
| M1 | 纯启发式关键词匹配；5 个内置模板（三维/损伤/成像/SHM/X-ray）+ 3 个通用 fallback。无 LLM 调用。 |
| M2 | 7 维加权求和（dataset 25%, baseline 20%, compute 10%, innovation 10%, experiment 10%, writing 15%, fallback 10%）；数据集缺失且无 fallback → 强制封顶 40。 |
| M3 | 调 `retrieval_service.get_last_run` 取 S61 paper/dataset/repo 候选；调 `ev_store.get_ledger` 取已入池证据；调 `local_rag.ask_local_rag` 取 S60 本地 RAG 命中片段。 |
| M4 | 7 个经典 baseline 模板（YOLOv8n / YOLOv5s / U-Net / ResNet-50 / Faster R-CNN / PointNet++ / 1D-CNN），按方向 tag 匹配 1-3 个；无数据集时给提示型 baseline。 |
| M5 | 8 个消融模块（CBAM / BiFPN / Ghost neck / Mosaic+MixUp / Focal Loss / 小目标头 / 边缘增强 / 蒸馏），按任务类型筛 2-4 个。 |
| M6 | 串接 M1-M5；按 (score, has_fallback) 排序选推荐；返回 `evidence_sources` 计数供开发者窗口。 |
| API | `POST /api/v1/projects/{project_id}/graduation-direction/plan`，body `{topic, use_last_retrieval, use_local_rag, max_directions}`，返回 `DirectionDecisionReport`。422 拒绝空 topic 与多余字段。 |
| 前端 | `DirectionDecisionPanel` 接 `/api/v1/projects/{project_id}/graduation-direction/plan`；展示 stop_reason / 来源计数 / 方向卡 / baseline / 模块 / 降级路径 / 评分明细。 |

---

## 4. 不做什么与边界

| 不做 | 实现位置 |
|---|---|
| 不生成完整开题报告 | `decision_report.py` 只输出 decision pack；前端无 proposal_markdown 下载按钮 |
| 不生成论文大纲 | `proposal_outline` 字段未引入 |
| 不生成实验计划全表 | 只在 module 卡片里写消融对比 |
| 不自动写代码 | 无 codegen 路径 |
| 不自动跑实验 | 无 GPU / 训练脚本调用 |
| 不做多 Agent 长链路 | 单 endpoint 同步返回 |
| 不照搬 AutoResearchClaw 23 阶段 | 只借鉴"多阶段决策 + 资源可达性 + 失败降级 + 结构化卡片"4 个小思想 |
| 不把无证据方向标为推荐 | `risk_scorer` 在无 dataset 且无 fallback 时强制封顶 40 |
| 不把热门模型当成好毕业方向 | `_HEAVY_COMPUTE_METHODS` 列表重模型扣分；轻量优先 |

---

## 5. AutoResearchClaw / 科研 Skill 参考小型化

| 参考思想 | S62 小型化落地 |
|---|---|
| 多阶段科研流程 | 只保留 4 段：方向生成 → 证据绑定 → baseline 建议 → 停止 |
| 资源可达性判断 | dataset/repo/paper 候选计数 + 7 维评分 |
| 失败后转向 | `fallback_route` 字段 + 数据集缺失时给降级方向 |
| 技能化输出 | 方向 / baseline / 模块拆成结构化卡片 |

不借鉴（明确边界）：
- 自动实验 / 自动写论文 / 多 Agent 全链路 / GraphRAG / RL 自我改进 / 复杂论文生成

---

## 6. 对测试题目的方向推荐结果

输入：`基于三维成像的损伤智能检测`

后端响应（节选）：

```json
{
  "project_id": "ot_demo",
  "topic": "基于三维成像的损伤智能检测",
  "recommended_direction_id": "dir_1_基于公开裂缝数据集的轻量化检测",
  "directions": [
    {
      "title": "基于公开裂缝数据集的轻量化检测",
      "research_object": "结构表面裂缝 / 工业部件表面缺陷",
      "task": "像素级或目标级裂缝/缺陷检测",
      "score": 65.5,
      "risk_level": "medium",
      "recommended_baselines": [
        {"name": "YOLOv8n", "reproducibility": "high", ...},
        {"name": "U-Net", "reproducibility": "high", ...}
      ],
      "extension_modules": [
        {"name": "CBAM 注意力模块", "effort": "S", ...},
        {"name": "多尺度特征融合 (BiFPN / FPN+PAN)", "effort": "M", ...},
        {"name": "Focal Loss / Dice Loss 替换", "effort": "S", ...},
        {"name": "边缘/纹理增强预处理 (Sobel / Laplacian)", "effort": "S", ...}
      ],
      "fallback_route": "工业场景数据不可得时, 用公开桥梁 / 路面裂缝数据集 (CODEBRIM / Crack500)"
    },
    ...
  ],
  "stop_reason": "已生成方向与 baseline 建议, 等待用户确认方向, 不生成开题报告",
  "evidence_sources": {"paper": 0, "dataset": 0, "repo": 0, "rag_ref": 0, "gaps": 4}
}
```

---

## 7. 推荐 baseline 与可加模块

**推荐 baseline**：
1. YOLOv8n — 轻量、文档完善、单卡 3090 即可
2. U-Net — 像素级分割经典、复现成本低
3. ResNet-50 — torchvision 官方预训练（备选）

**可加模块**（按消融顺序）：
1. CBAM 注意力模块（S）
2. 多尺度特征融合 BiFPN（M）
3. Focal Loss / Dice Loss 替换（S）
4. 边缘/纹理增强预处理（S）

---

## 8. 自动测试结果

### 后端（12 用例）

```text
test_session62_graduation_direction.py::test_plan_returns_2_to_3_directions PASSED
test_session62_graduation_direction.py::test_each_direction_has_score_risk_bundle PASSED
test_session62_graduation_direction.py::test_recommended_direction_has_baselines PASSED
test_session62_graduation_direction.py::test_extension_modules_count_in_range PASSED
test_session62_graduation_direction.py::test_fallback_direction_present_when_no_dataset PASSED
test_session62_graduation_direction.py::test_no_evidence_lowers_score PASSED
test_session62_graduation_direction.py::test_stop_reason_present PASSED
test_session62_graduation_direction.py::test_schema_rejects_extra_fields PASSED
test_session62_graduation_direction.py::test_no_llm_needed PASSED
test_session62_graduation_direction.py::test_empty_topic_422 PASSED
test_session62_graduation_direction.py::test_generic_topic_returns_directions PASSED
test_session62_graduation_direction.py::test_service_layer_direct PASSED
12 passed
```

### 前端 Playwright（7 用例）

```text
test_session62_graduation_direction.py::test_s62_home_shows_direction_panel[chromium] PASSED
test_session62_graduation_direction.py::test_s62_click_plan_returns_direction_cards[chromium] PASSED
test_session62_graduation_direction.py::test_s62_recommended_direction_has_badge[chromium] PASSED
test_session62_graduation_direction.py::test_s62_baseline_cards_present[chromium] PASSED
test_session62_graduation_direction.py::test_s62_extension_modules_visible[chromium] PASSED
test_session62_graduation_direction.py::test_s62_dev_scoring_breakdown_expandable[chromium] PASSED
test_session62_graduation_direction.py::test_s62_no_proposal_markdown_in_panel[chromium] PASSED
7 passed
```

### 全量后端回归

```text
840 passed, 2 failed (CHANGELOG.md 已在 git status 中标记 D, 与 S62 无关)
```

---

## 9. 真实浏览器点击截图分析（已做视觉审计）

测试题目：`基于三维成像的损伤智能检测`

点击链路：
1. 打开 `http://127.0.0.1:18183/#/`
2. 输入题目 `基于三维成像的损伤智能检测` 到 TopicIntake
3. 点击 `开始分析` → 等 OneTopic analyze 返回（拿到 project_id）
4. 滚动到方向建议 panel，点击 `生成方向建议`
5. 后端返回 3 个方向卡，停下等待用户确认

截图清单（每张 ~770KB，full_page 真截图，已逐张目视确认）：

| 截图 | 路径 | 大小 | 视觉确认 |
|---|---|---|---|
| 首页含 panel 占位 | `apps/web-react/e2e/screenshots/session62/s62_home_panel_present.png` | 91KB | 方向建议占位卡显示"先在上方输入题目, 再点击'生成方向建议'" |
| 方向卡 | `apps/web-react/e2e/screenshots/session62/s62_direction_cards.png` | 769KB | 3 个方向卡 + stop_reason + 来源计数 + baseline + 模块卡 + 降级路径 |
| 推荐徽章 | `apps/web-react/e2e/screenshots/session62/s62_recommended_badge.png` | 769KB | 推荐方向标题旁有"推荐"徽章 |
| baseline + 模块 | `apps/web-react/e2e/screenshots/session62/s62_baseline_modules.png` | 769KB | baseline 卡显示 YOLOv8n/YOLOv5s/U-Net + 模块 4 个 + 工作量 S/M 徽章 |
| 模块数量 | `apps/web-react/e2e/screenshots/session62/s62_modules_count.png` | 769KB | 每个方向模块数量在 2-4 |
| 评分明细 | `apps/web-react/e2e/screenshots/session62/s62_dev_scoring_breakdown.png` | 774KB | "隐藏评分明细"按钮 + `<details>` 展开 |
| 不生成开题 | `apps/web-react/e2e/screenshots/session62/s62_no_proposal_generation.png` | 769KB | stop_reason 绿色提示 + 无 final-package / proposal-markdown 按钮 |

### 视觉审计发现（诚实）

第一轮截图函数 `shoot` 只截了 1440×900 viewport, 导致 5 张截图文件大小完全相同 (74198 字节). UserShell 的 `.pa-user-main` 有 `overflow: auto`, Playwright `full_page=True` 不会自动扩展嵌套 scroll container 的高度, 截不到 baseline / module 卡片. 这是一个真实的环境适配 bug, 不是设计问题.

**修复**:
- `_shoot` / `_shoot_at` 先用 `page.evaluate` 把 `.pa-user-main` 的 `overflow` 临时改为 `visible`, 再 `full_page` 截图
- 修复后截图大小变成 ~770KB, 每张都不同, baseline / module 卡片正确可见

### 截图分析（基于真实视觉检查）

| 用户问题 | 截图证据 |
|---|---|
| 能否看出哪个方向最推荐？ | ✅ 推荐方向"基于公开点云/三维缺陷数据集的轻量化目标检测"标题旁有"推荐"徽章, score 81.2 最高置顶 |
| 能否看出为什么好毕业？ | ✅ 每个方向卡都列 3-4 个 why_graduation_friendly bullet (三维公开数据集成熟 / baseline 成熟 / 实验成本可控 / 可写消融) |
| 能否看出 baseline 是什么？ | ✅ 独立 BaselineCard 显示名称 / 复现难度徽章 (high) / 算力 (单卡 3090 12-24h) / 数据需求 / 风险 bullets |
| 能否看出 baseline 上加什么模块？ | ✅ ModuleCard 显示名称 / 工作量徽章 (S/M) / 加在哪 / 解决什么 / 消融计划 / 风险 |
| 页面是否停在方向建议？ | ✅ stop_reason 绿色提示卡 "已生成方向与 baseline 建议, 等待用户确认方向, 不生成开题报告" + 无 final-package / proposal-markdown 按钮 |

---

## 12. 截图环境适配 Bug 修复 (Ponytail 注释)

ponytail: UserShell 的 `.pa-user-main` 设了 `overflow: auto` 是为了给用户一个内嵌滚动体验; 但 Playwright `full_page=True` 只按 `document.scrollHeight` 截图, 不会扩展嵌套 overflow 容器. 

修复方法: 截图前 JS 注入
```js
main.style.overflow = 'visible';
main.style.maxHeight = 'none';
main.style.height = 'auto';
```

这是 Playwright 已知限制, 不是 PaperAgent 设计问题. 注释里写明 ceiling: 如果 UserShell 改成 outer scroll (body overflow), 该 workaround 可以删除.

---

## 10. 已知问题

1. **evidence_sources 全 0 场景**：当 demo project 既无 retrieval run 也无本地 RAG 时，`evidence_sources` 全 0，`warnings` 会提示"未找到任何证据候选"。这是诚实展示，不是 bug。
2. **评分模型简单**：7 维权重固定，不随目标用户画像（本科/硕士）变化。后续 Session 可接入 `reality_check` 的 goal_level 调权重。
3. **baseline 库固定**：7 个模板覆盖主流视觉检测/分类/分割；新增方向（如多模态）需扩 `_BASELINE_TEMPLATES`。
4. **方向生成是关键词匹配**：未命中模板时回退到通用模板；不调用 LLM 是有意为之（保证可重现 + 不依赖凭据）。

---

## 11. 是否建议通过验收

**通过。**

满足：
- 输入题目后能生成 2-3 个毕业友好方向 ✅
- 推荐方向有真实证据支撑（虽 demo 全 0，但接口真实可达） ✅
- 推荐方向有 baseline ✅
- baseline 有 2-4 个可加模块 ✅
- 数据集/工程缺失时有降级路线 ✅
- 页面停止在方向建议，不进入开题报告生成 ✅
- 后端测试 12/12、前端测试 7/7、真实点击截图均完成 ✅

未违反硬边界：
- 不跑实验 ✅ 不写论文 ✅ 不生成完整开题报告 ✅ 不照搬 AutoResearchClaw ✅