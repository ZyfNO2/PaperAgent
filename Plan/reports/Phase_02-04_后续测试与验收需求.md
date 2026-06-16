# Phase 02-04 后续测试与验收需求

> 目的：明确 TopicPilot-CN 在 Phase 02-04 与界面 MVP 阶段还需要补哪些测试，以及最终达到什么验收状态。  
> 范围：不要求当前立即执行 Playwright。当前无浏览器页面，因此 Playwright 只作为界面 MVP 出现后的验收计划。

---

## 1. 当前判断

Phase 01 已通过工程验收，后端已经出现 Phase 02-04 的模型、节点、API、仓储和测试文件。

当前阶段最适合的验收方式是：

- API 集成测试
- Pydantic 模型校验测试
- LangGraph / 节点逻辑测试
- demo smoke 测试
- 结构化产物检查

当前不适合立即执行 Playwright，因为还没有 `apps/web` 浏览器页面。

---

## 2. 最终要达到的 MVP 需求

界面 MVP 最终要能让用户完成以下闭环：

```text
创建项目 / 填写建档信息
→ Phase 01 评级与阻断
→ Phase 02 生成 TopicSpec
→ Phase 03 生成 SearchQueryPlan
→ Phase 04 生成 EvidenceLedger
→ 页面展示每个阶段的产物、风险、阻断原因和下一步按钮
```

最低可验收状态：

1. 用户能创建一个 A/B 级项目，并看到允许进入 Phase 02。
2. 用户能创建一个 C/D 级项目，并看到 Phase 02 被阻断。
3. 用户能点击完成 Phase 02，看到题目拆解、风险词、论文结构映射、工作包雏形。
4. 用户能点击完成 Phase 03，看到 L0-L6 检索计划、工作包检索映射、Pivot 备选方向。
5. 用户能点击完成 Phase 04，看到论文、数据集、baseline、指标、实验模板、学位论文模板和风险 flags。
6. 刷新页面后，已生成的阶段产物仍能通过 GET 接口恢复展示。

---

## 3. 当前应补的后端测试

### 3.1 Phase 02 测试需求

目标：保证只有 Phase 01 通过的项目才能进入题目拆解，并且 `TopicSpec` 能支撑后续 Phase。

建议补充或确认以下测试：

- `Phase 01 D/BLOCKED` 项目调用 `/topic/decompose` 返回 409。
- `Phase 01 C/NEED_CLARIFICATION` 项目调用 `/topic/decompose` 返回 409。
- A/B 项目调用 `/topic/decompose` 成功返回 `TopicSpec`。
- `TopicSpec` 至少包含：
  - `normalized_topic`
  - `task_type`
  - `evaluation_metrics`
  - `risk_terms`
  - `thesis_mapping`
  - `work_package_drafts`
- `work_package_drafts` 至少 2 个；若不足 2 个，必须有风险说明。
- `allow_proceed_to_phase03` 与 `decomposition_rating` 一致。
- 重复调用 `/topic/decompose` 不产生重复脏数据，应 upsert。
- `/topic/spec` 在未生成时返回 404，在生成后可恢复读取。

### 3.2 Phase 03 测试需求

目标：保证检索计划只基于有效 `TopicSpec` 生成，并覆盖毕业论文方法论要求。

建议补充或确认以下测试：

- 没有 `TopicSpec` 时调用 `/search/plan` 返回 404。
- `TopicSpec` 不允许进入 Phase 03 时调用 `/search/plan` 返回 409。
- 成功生成的 `SearchQueryPlan` 包含 L0-L6 七层检索。
- 英文检索词总数不少于 10。
- 中文检索词总数不少于 5。
- 检索计划覆盖：
  - 论文
  - 综述
  - 数据集
  - baseline / code
  - benchmark / metrics
  - 学位论文模板
- 每个工作包至少绑定 2 组检索词。
- 至少包含 1 个 Pivot 备选方向。
- `/search/plan` 重复调用可稳定 upsert。
- `/search/plan` GET 可恢复读取。

### 3.3 Phase 04 测试需求

目标：保证证据账本只基于有效检索计划生成，并能支撑开题报告与毕业论文工作量。

建议补充或确认以下测试：

- 没有 `TopicSpec` 时调用 `/evidence/build` 返回 404。
- 没有 `SearchQueryPlan` 时调用 `/evidence/build` 返回 409。
- 成功生成的 `EvidenceLedger` 至少包含：
  - 论文证据
  - 数据集候选
  - baseline / 代码候选
  - 指标证据
  - 实验模板
  - 学位论文模板
- baseline 候选必须包含复现难度字段。
- 每类关键证据必须有来源或明确标记“无法追溯”。
- 证据账本应能绑定到工作包。
- `/evidence/ledger` 未生成时返回 404，生成后可恢复读取。
- `/evidence/build` 重复调用可稳定 upsert。

---

## 4. Demo Smoke 测试需求

在界面出现前，建议先有一个完整后端 demo smoke：

```text
1. POST /projects 创建 A 级项目
2. POST /projects/{id}/intake/validate
3. POST /projects/{id}/topic/decompose
4. GET  /projects/{id}/topic/spec
5. POST /projects/{id}/search/plan
6. GET  /projects/{id}/search/plan
7. POST /projects/{id}/evidence/build
8. GET  /projects/{id}/evidence/ledger
9. 校验 counts 与 allow flags
```

同时需要一个阻断路径：

```text
1. POST /projects 创建 D 级占位项目
2. POST /projects/{id}/intake/validate
3. POST /projects/{id}/topic/decompose
4. 期望返回 409，且错误信息能说明 Phase 01 未通过
```

---

## 5. 界面 MVP 出现后的 Playwright 测试计划

Playwright 只有在 `apps/web` 存在并能打开页面后才需要执行。

### 5.1 MVP Happy Path

```text
创建 A/B 级项目
→ 页面显示 Phase 01 OK
→ 点击“题目拆解”
→ 页面显示 TopicSpec
→ 点击“生成检索计划”
→ 页面显示 SearchQueryPlan
→ 点击“生成证据账本”
→ 页面显示 EvidenceLedger
```

验收点：

- 页面无 500 错误。
- 页面无明显 console error。
- 每个阶段按钮状态正确。
- 每个阶段生成后都有可见结果。
- 刷新后结果仍存在。

### 5.2 Blocked Path

```text
创建 D 级占位项目
→ 页面显示 Phase 01 BLOCKED
→ “题目拆解”按钮禁用
→ 页面显示待补问题
```

验收点：

- 用户不会误进入 Phase 02。
- 阻断原因可读。
- 待补字段可见。

### 5.3 Phase 02 页面验收

- 显示标准化题目。
- 显示研究对象、任务、数据模态、方法族、评价指标。
- 显示高风险词表。
- 显示五章式论文结构映射。
- 显示工作包卡片。
- 显示是否允许进入 Phase 03。

### 5.4 Phase 03 页面验收

- 显示 L0-L6 检索层。
- 显示中英文检索词数量。
- 显示论文、综述、数据集、baseline、benchmark、学位论文模板检索入口。
- 显示工作包与检索词映射。
- 显示 Pivot 备选方向。
- 显示是否允许进入 Phase 04。

### 5.5 Phase 04 页面验收

- 显示 evidence_rating。
- 显示论文、数据集、baseline、指标数量。
- 显示 baseline 复现难度。
- 显示实验模板和学位论文模板。
- 显示风险 flags。
- 显示工作包与证据绑定关系。

---

## 6. 建议的最终验收标准

项目在进入 Phase 05-08 整改前，至少应达到：

```text
后端：
- Phase 01-04 API 全部可调用
- A/B 路径可走通到 EvidenceLedger
- C/D 路径能被阻断
- Pydantic 结构化对象均可校验
- 数据可入库并通过 GET 恢复

测试：
- Phase 01-04 pytest 全部通过
- demo smoke happy path 通过
- demo smoke blocked path 通过

界面：
- apps/web 可启动
- 用户可在浏览器完成 Phase 01-04 主流程
- 阻断状态、风险信息、阶段产物均可见

Playwright：
- happy path 通过
- blocked path 通过
- refresh persistence 通过
```

---

## 7. Phase 05-08 的整改前置条件

只有满足以下条件后，才建议正式整改 Phase 05-08：

- Phase 01-04 的数据对象稳定。
- 界面 MVP 已经证明用户能理解阶段产物。
- Phase 04 的证据账本已经能支撑风险评分、Pivot、工作包定稿和开题报告生成。
- Playwright 至少覆盖 happy path 与 blocked path。

若这些条件未满足，Phase 05-08 不宜过早细化，否则容易建立在不稳定的上游数据结构上。

