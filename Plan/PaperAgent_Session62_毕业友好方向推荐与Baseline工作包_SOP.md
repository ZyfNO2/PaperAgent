# PaperAgent Session 62 SOP：毕业友好方向推荐与 Baseline 工作包生成

日期：2026-06-30

继承 Rules：

- `Plan/PaperAgent_SOP执行Rules_真实接线与点击验收.md`
- 默认执行 `Ponytail full`：优先复用现有 one-topic / retrieval / local RAG / reality check，不新造大框架。

当前基线：

- Session 60：本地 RAG 最小闭环已验收通过，文献库可真实入库、索引、问答、引用。
- Session 61：科研检索增强已验收通过，能围绕题目检索论文、数据集、GitHub 工程，并输出 gap report / retry query。
- 当前系统已经具备“搜得到”和“能问文献库”的基础，下一步应进入“知道怎么选”。

## 1. 用户最终目标

目标流程：

```text
输入题目
→ 给出好毕业的方向
→ 查找相关领域论文
→ 给出工作建议
→ 建议 Baseline
→ 建议 Baseline 上可加的模块
→ 到这里停止
```

示例输入：

```text
基于三维成像的损伤智能检测
```

期望输出不是完整开题报告，而是一个可执行的毕业方向决策包：

```text
推荐方向：基于公开缺陷/裂缝数据集的轻量化检测
为什么好毕业：公开数据较多、baseline 成熟、实验成本低、可做消融
建议 baseline：YOLOv8n / YOLOv5s / U-Net
可加模块：注意力模块、多尺度特征融合、轻量化 neck、数据增强
风险：三维数据集不足时降级到二维裂缝/缺陷检测
停止：等待用户确认方向，不生成开题报告
```

## 2. 本 Session 目标

Session 62 只做“方向选择层”：

1. 从一个原始题目生成 2-3 个可毕业方向。
2. 对每个方向绑定真实检索证据：论文 / 数据集 / 工程 / RAG 文献片段。
3. 给每个方向计算毕业友好评分。
4. 为推荐方向给出 baseline。
5. 为 baseline 给出可加模块。
6. 到这里停止，等待用户选择方向。

## 3. 本轮不做什么

不做：

- 不生成完整开题报告。
- 不生成论文大纲。
- 不生成实验计划全表。
- 不自动写代码。
- 不自动跑实验。
- 不做多 Agent 长链路科研自动化。
- 不照搬 AutoResearchClaw 23 阶段。
- 不把没有证据的方向标为推荐。
- 不把“热门模型”当成“好毕业方向”。

## 4. AutoResearchClaw / 科研 Skill 参考如何小型化

只借鉴四个小思想：

| 参考思想 | S62 小型化落地 |
|---|---|
| 多阶段科研流程 | 只保留“方向生成 → 证据绑定 → baseline 建议 → 停止” |
| 资源可达性判断 | 用 dataset/repo/paper 候选判断是否好毕业 |
| 失败后转向 | 数据集/工程不足时给降级方向 |
| 技能化输出 | 把 baseline、模块、风险拆成结构化卡片 |

不借鉴：

- 自动实验。
- 自动写论文。
- 多 Agent 全链路。
- GraphRAG。
- RL/自我改进。
- 复杂论文生成。

## 5. 模块设计与约束

### M1：GraduationDirectionPlanner

建议文件：

```text
apps/api/app/services/graduation/direction_planner.py
```

职责：

- 根据原始题目、关键词拆解和检索结果，生成 2-3 个候选毕业方向。
- 每个方向必须是可做的缩小版，不是更大的泛化题目。
- 每个方向必须说明：
  - 研究对象。
  - 任务。
  - 方法路线。
  - 为什么比原题更好毕业。
  - 可降级路径。

不应该：

- 不应该生成 5 个以上方向。
- 不应该生成没有证据支撑的方向。
- 不应该只改题目措辞。
- 不应该推荐“多模态大模型”“三维全场景智能检测”这类过大方向。
- 不应该调用 LLM 生成不可解释方向；若调用 LLM，也必须有 heuristic fallback。

Ponytail 要求：

- 先用启发式方向模板，别先上复杂 planner。
- 如果 S61 gap report 显示 dataset=0，必须生成至少一个降级方向。

### M2：GraduationRiskScorer

建议文件：

```text
apps/api/app/services/graduation/risk_scorer.py
```

职责：

- 对每个方向计算毕业友好评分。
- 评分维度：
  - `dataset_availability`
  - `baseline_reproducibility`
  - `compute_cost`
  - `innovation_simplicity`
  - `experiment_rounds`
  - `writing_explainability`
  - `fallback_path`
- 输出总分与风险等级。

不应该：

- 不应该只按论文数量评分。
- 不应该只按 GitHub stars 评分。
- 不应该在无数据集/无工程时给高分。
- 不应该把大算力路线评为低风险。

最低规则：

```text
有公开数据集 + 有 baseline 工程 + 非大模型 → 高友好度
有论文但无数据集 → 中低友好度
无数据集 + 无工程 → 不推荐
三维数据不足但二维可替代 → 推荐降级方向
```

### M3：EvidenceBundleBuilder

建议文件：

```text
apps/api/app/services/graduation/evidence_bundle.py
```

职责：

- 为每个方向绑定 S61 检索候选和 S60 本地 RAG 文献片段。
- 输出：
  - 相关论文。
  - 数据集候选。
  - GitHub 工程候选。
  - 本地 RAG 引用片段。
  - 缺口。

不应该：

- 不应该编造论文/数据集/工程。
- 不应该把 source_failed 当 no_result。
- 不应该让 LLM 直接写 supports。
- 不应该只返回标题，不返回来源。

### M4：BaselineAdvisor

建议文件：

```text
apps/api/app/services/graduation/baseline_advisor.py
```

职责：

- 根据方向和证据，给出建议 baseline。
- baseline 必须来自：
  - 已检索到的 GitHub 工程。
  - 已知成熟方法模板。
  - 本地 RAG 文献中的方法描述。
- 每个 baseline 必须给：
  - 名称。
  - 为什么适合。
  - 所需数据。
  - 复现难度。
  - 预计训练成本。
  - 风险。

不应该：

- 不应该推荐没有数据集支撑的 baseline。
- 不应该推荐不可复现或过重模型作为默认 baseline。
- 不应该推荐“最新最强”但本科/硕士难做的模型。
- 不应该把 baseline 和创新模块混在一起。

推荐优先级：

```text
轻量成熟模型 > 常用公开实现 > 论文官方代码 > 重模型 > 纯理论方法
```

### M5：ModuleExtensionAdvisor

建议文件：

```text
apps/api/app/services/graduation/module_extension_advisor.py
```

职责：

- 给 baseline 推荐 2-4 个可加模块。
- 每个模块必须说明：
  - 加在哪里。
  - 解决什么问题。
  - 怎么做消融。
  - 风险。
  - 工作量。

可选模块模板：

- 注意力模块。
- 多尺度特征融合。
- 轻量化 neck/head。
- 数据增强。
- 损失函数替换。
- 小目标检测头。
- 边缘/纹理增强。
- 模型剪枝或蒸馏。

不应该：

- 不应该推荐无法做消融的模块。
- 不应该推荐需要额外硬件采集的模块。
- 不应该推荐与题目无关的复杂架构。
- 不应该推荐超过 4 个模块。

### M6：DirectionDecisionReport

建议文件：

```text
apps/api/app/services/graduation/decision_report.py
```

职责：

- 汇总方向、评分、证据、baseline、可加模块。
- 输出前端可直接渲染的结构化报告。
- 明确推荐一个主方向，一个备选降级方向。
- 停在“等待用户确认方向”。

不应该：

- 不应该生成开题报告正文。
- 不应该输出 12 节 proposal。
- 不应该自动进入报告导出。

## 6. API 设计

建议新增：

```text
apps/api/app/schemas_graduation_direction.py
apps/api/app/api/v1/graduation_direction.py
```
端点：

```text
POST /api/v1/projects/{project_id}/graduation-direction/plan
```

请求：

```json
{
  "topic": "基于三维成像的损伤智能检测",
  "use_last_retrieval": true,
  "use_local_rag": true,
  "max_directions": 3
}
```

响应最低结构：

```json
{
  "project_id": "ot_xxx",
  "topic": "...",
  "recommended_direction_id": "dir_1",
  "directions": [
    {
      "direction_id": "dir_1",
      "title": "基于公开裂缝数据集的轻量化检测",
      "why_graduation_friendly": ["公开数据较多", "baseline 成熟"],
      "risk_level": "low",
      "score": 82,
      "evidence_bundle": {
        "papers": [],
        "datasets": [],
        "repos": [],
        "rag_refs": [],
        "gaps": []
      },
      "recommended_baselines": [],
      "extension_modules": [],
      "fallback_route": "如果三维数据不足，降级为二维裂缝/缺陷检测"
    }
  ],
  "stop_reason": "已生成方向与 baseline 建议，等待用户确认，不生成开题报告"
}
```

不允许：

- 不允许返回纯字符串。
- 不允许 `directions` 为空还返回 200 成功且无解释。
- 不允许没有 evidence_bundle。

## 7. 前端接线

建议新增：

```text
apps/web-react/src/features/graduation-direction/DirectionDecisionPanel.tsx
apps/web-react/src/features/graduation-direction/directionTypes.ts
```

普通用户界面新增一个区域：

```text
方向建议
```

用户路径：

1. 输入题目。
2. 点击开始分析。
3. 点击让 AI 查证据。
4. 点击生成方向建议。
5. 页面展示 2-3 个方向卡。
6. 用户查看推荐方向的 baseline 和可加模块。
7. 页面停在这里。

方向卡必须显示：

- 方向标题。
- 好毕业理由。
- 分数与风险。
- 论文/数据集/工程证据数量。
- 建议 baseline。
- 可加模块。
- 降级路线。

不显示：

- 开题报告正文。
- 面试/测试内容。
- RAG Eval 指标。
- raw trace。

开发者窗口显示：

- scoring breakdown。
- evidence bundle raw ids。
- 使用了哪些 retrieval run。
- 使用了哪些 local RAG refs。

## 8. 测试要求

### 8.1 后端测试

新增：

```text
apps/api/tests/test_session62_graduation_direction.py
```

最低测试：

1. 输入题目能生成 2-3 个方向。
2. 每个方向都有 score / risk_level / evidence_bundle。
3. 推荐方向必须有 baseline。
4. baseline 至少包含名称、理由、复现难度。
5. extension_modules 数量在 2-4。
6. 数据集缺失时必须生成降级方向。
7. 无证据时不得给高分。
8. 响应必须包含 stop_reason，且说明不生成开题报告。
9. schema 拒绝多余字段。
10. 不调用外部 LLM 时 heuristic fallback 可跑通。

### 8.2 前端 Playwright

新增：

```text
apps/web-react/e2e/test_session62_graduation_direction.py
```

最低测试：

1. 输入题目。
2. 点击开始分析。
3. 点击让 AI 查证据。
4. 点击生成方向建议。
5. 页面出现方向卡。
6. 推荐方向显示 baseline。
7. baseline 显示可加模块。
8. 页面没有生成开题报告正文。
9. 开发者窗口能查看评分 breakdown。
10. 截图保存。

## 9. 真实点击验收

必须用真实浏览器测试：

```text
基于三维成像的损伤智能检测
```

点击链路：

1. 打开 `http://127.0.0.1:18183`。
2. 输入题目。
3. 点击 `开始分析`。
4. 点击 `让 AI 查证据`。
5. 等待 S61 检索结果。
6. 点击 `生成方向建议`。
7. 查看推荐方向、baseline、可加模块。
8. 停止，不生成开题报告。

必须保存：

```text
Plan/reports/session62-direction-flow.json
Plan/reports/session62-direction-flow.png
apps/web-react/e2e/screenshots/session62/s62_direction_cards.png
apps/web-react/e2e/screenshots/session62/s62_baseline_modules.png
apps/web-react/e2e/screenshots/session62/s62_dev_scoring_breakdown.png
```

截图分析必须回答：

- 用户能否看出哪个方向最推荐？
- 用户能否看出为什么好毕业？
- 用户能否看出 baseline 是什么？
- 用户能否看出 baseline 上加什么模块？
- 页面是否停在方向建议，而没有继续生成开题报告？

## 10. 验收报告

完成后输出：

```text
Plan/reports/Session_62_GraduationDirection_BaselineWorkPackage_验收报告.md
```

报告必须包含：

- S60/S61 是否已通过。
- 新增模块清单。
- 每个模块职责和禁止事项是否遵守。
- AutoResearchClaw / 科研 Skill 参考如何小型化落地。
- 对测试题目的方向推荐结果。
- 推荐 baseline 与可加模块。
- 自动测试结果。
- 真实点击截图分析。
- 是否建议通过验收。

## 11. 通过标准

可以通过：

- 输入题目后能生成 2-3 个毕业友好方向。
- 推荐方向有真实证据支撑。
- 推荐方向有 baseline。
- baseline 有 2-4 个可加模块。
- 数据集/工程缺失时有降级路线。
- 页面停止在方向建议，不进入开题报告生成。
- 后端测试、前端测试、真实点击截图均完成。

不通过：

- 只输出一个泛泛建议。
- 没有 evidence_bundle。
- 没有 baseline。
- 推荐过重或不可复现 baseline。
- 可加模块无法做消融。
- 数据集缺失仍给高分。
- 自动生成开题报告。
- 没有真实点击截图。

---

## 12. Self-audit 强约束（S62 修订）

后续每次实现必须包含 4 项 self-audit，否则不得过验收：

1. **方向生成走 LLM 路径，不能硬编码关键词模板。**
   - LLM-first: arXiv 抓 3-5 篇同领域参考论文 → LLM 基于论文 + 原题生成方向。
   - LLM/arXiv 失败 → 直接抛 `DirectionPlannerError` (HTTP 503)，**不做物理分词 fallback**。
   - 关键词模板硬编码会漏掉新方向（如 NLP / 多模态 / RAG），并且会把 3D 题错推 2D baseline。
2. **Baseline 按任务路径分组，不要硬塞 2D 模型。**
   - 3D 损伤检测 → PointNet++ / VoteNet / PointRCNN
   - 3D 重建 → MVSNet / NeRF / Occupancy Networks
   - NLP 预训练 → BERT / RoBERTa / DistilBERT
   - NLP 下游 → TextCNN / BiLSTM / BERT-finetune
   - 一个方向有"主任务 + 子任务"概念时（如"3D 重建 + 3D 检测"），必须每个路径分别给 baseline，**不能因为主任务命中就把子任务路径挤掉**。
3. **真实截图必须目视核对，不能只按测试断言收尾。**
   - 每个截图文件目视确认：方向卡标题、推荐徽章、baseline 名称、模块名称、stop_reason 是否可见。
   - 文件大小相同的截图大概率是 viewport 截窄，必须解除嵌套 overflow: auto 再 full_page。
4. **复用已有模块，不造新轮子。**
   - S60 retrieval_service.get_last_run (证据 backbone)
   - S60 local_rag.ask_local_rag (本地 RAG 片段)
   - S6 keyword_search_assistant 的 prompt 模板风格 (LLM-first + arXiv 引用)
   - 新建模块必须先说明"为什么已有模块不能复用"。

## 13. 文件引用规范（链接 vs 绝对路径）

所有报告、SOP、用户消息给文件路径时，必须用 markdown 链接 + 相对 workspace 根：

- ✅ `[direction_planner.py](apps/api/app/services/graduation/direction_planner.py)`
- ✅ `[UserWorkbenchPage.tsx](apps/web-react/src/features/user-workbench/UserWorkbenchPage.tsx)`
- ✅ `[session62/](apps/web-react/e2e/screenshots/session62/)`
- ❌ `g:/PaperAgent/apps/api/...` 单行绝对路径 (VSCode CopyLink 不能用)
- ❌ `apps/api/...` 裸文本 (IDE 无法跳转)

`Ctrl+点击` 链接直接打开文件；不要省略链接前缀的 `[]()`。


