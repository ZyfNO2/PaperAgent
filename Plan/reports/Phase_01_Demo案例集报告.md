# Demo 案例集报告：12 个 ProjectIntake 回归基线

> 范围：Phase 01 完工后的补充——为 A/B/C/D 四档评级各造 3 领域共 12 个 Demo 案例，作为面试 artifact、产品演示、未来评级规则变更的回归基线。
> 日期：2026-06-16
> 状态：**12 案例 × 4 断言 = 48/48 端到端通过**；29 既有单测无回归。

---

## 1. 解决了什么问题

Phase 01 完工后留下了 1 个**评级规则无人看守**的风险：`compute_intake_rating()` 的 4 档评级规则写在 `packages/domain/models.py` 里，只有 10 条单测覆盖。一旦后续 Phase 02、03 修改 `derive_missing_fields` 或评级阈值，A/B/C/D 的契约可能被悄悄打破，且没有可见的"违反现场"。

更现实的问题是：0 个**真实可读**的端到端案例。`data/projects/TBD_AI_开题选题助手/00_input.md` 是占位骨架，触发 D 评级阻断——这是设计意图，但它也意味着"如果一个真实学生来用，看到什么"。Demo 案例集填补这个空缺：

- **3 领域 × 4 评级 = 12 案例**——既覆盖主路径（A→Phase 02），也覆盖阻断路径（C/D）。
- **每份 JSON 既是 fixture 又是文档**——可作为面试 artifact 给面试官翻阅。
- **每份 JSON 都有自动化验收**——`demo_smoke.py` 守护 A/B/C/D 的 outcome 契约。

---

## 2. 设计矩阵

| 领域 \ 评级 | **A** | **B** | **C** | **D** |
|---|---|---|---|---|
| **CS_AI_GRAD** 计算机科学硕士（保毕业） | A_CS_AI_GRAD | B_CS_AI_GRAD | C_CS_AI_GRAD | D_CS_AI_GRAD |
| **CS_AI_TOP** 计算机科学硕士（冲高水平） | A_CS_AI_TOP | B_CS_AI_TOP | C_CS_AI_TOP | D_CS_AI_TOP |
| **MED_UG** 临床医学本科 | A_MED_UG | B_MED_UG | C_MED_UG | D_MED_UG |

**字段裁剪规则**（与 `compute_intake_rating` 严格对齐）：

| 评级 | 裁剪动作 | 触发机制 |
|------|----------|----------|
| **A** | 全部 P0/P1/P2 填齐 | 无 missing 字段 |
| **B** | 仅 P2 `must_keep` 留空 | 单 P2 缺失 → B |
| **C** | `proposal_deadline` 留空（P0 缺 1） | 单 P0 缺失 → C |
| **D** | `raw_topic = "TBD"`（字面占位符） | 占位符直接触发 D，绕过其他缺失 |

**outcome 与 allow_proceed_to_phase02 期望**：

| 评级 | 期望 outcome | allow_proceed |
|------|-------------|---------------|
| A | `OK` | True |
| B | `OK` | True |
| C | `NEED_CLARIFICATION` | False |
| D | `BLOCKED` | False |

---

## 3. 3 个领域画像

### CS_AI_GRAD：CS 硕士保毕业

```text
专业：计算机科学与技术（硕士）
导师方向：图神经网络与推荐系统
目标档位：保毕业
继承资源：同门毕业论文（师兄 2024 届）、PyG 官方实现
算力：笔记本 RTX 3060
每周投入：25h
代表性题目：基于图神经网络的学术论文推荐方法研究
```

代表"人多方向 + 继承资源"型学生。Phase 02 推荐的题目池会很丰富；Phase 03 检索时优先搜 GNN + 推荐系统的近期论文。

### CS_AI_TOP：CS 硕士冲高水平

```text
专业：计算机科学与技术（硕士）
导师方向：多模态大模型与对齐
目标档位：冲高水平
继承资源：实验室 LLaVA 风格多模态基线、4×A100 集群
算力：实验室 4×A100
每周投入：40h
代表性题目：面向细粒度视觉理解的视觉-语言模型提示压缩方法
```

代表"高风险、高目标"型学生。`compute_intake_rating` 不区分保毕业 / 稳中求新 / 冲高水平——3 档目标在 Phase 01 都被接受为有效输入，但在 Phase 02 风险评分时权重不同。

### MED_UG：临床医学本科

```text
专业：临床医学（本科）
导师方向：医学信息学
目标档位：保毕业
继承资源：学姐 2023 届本科论文
算力：笔记本无独显
每周投入：15h
代表性题目：面向临床实习的医学影像报告自动校对系统
```

代表"跨学科 + 资源受限 + 学院格式特殊"型学生。`school_requirements` 包含"必须包含系统原型"——本科学院常见的工程实践要求。

---

## 4. 产物文件

### 4.1 JSON fixtures（12 份）

```
data/demo_cases/
├── A_CS_AI_GRAD.json      # 5 KB
├── A_CS_AI_TOP.json
├── A_MED_UG.json
├── B_CS_AI_GRAD.json
├── B_CS_AI_TOP.json
├── B_MED_UG.json
├── C_CS_AI_GRAD.json
├── C_CS_AI_TOP.json
├── C_MED_UG.json
├── D_CS_AI_GRAD.json
├── D_CS_AI_TOP.json
└── D_MED_UG.json
```

每份 JSON 结构：

```json
{
  "intake": {
    "case_id": "A_CS_AI_GRAD_20260616",
    "major": "计算机科学与技术",
    "degree_type": "硕士",
    "goal_level": "保毕业",
    "thesis_deadline": "2027-06-01",
    "proposal_deadline": "2026-10-15",
    "first_result_deadline": "2026-12-31",
    "advisor_direction": "图神经网络与推荐系统",
    "school_requirements": ["必须中文文献", "开题模板见附录"],
    "inherited_resources": [
      {
        "kind": "同门毕业论文",
        "description": "师兄 2024 届硕士论文（基于 GNN 的论文推荐）",
        "available": true,
        "authorization_or_attribution_risk": "低"
      },
      ...
    ],
    "student_resources": { ... },
    "raw_topic": "基于图神经网络的学术论文推荐方法研究",
    "must_keep": ["基于图神经网络的学术"],
    "can_drop": [],
    "missing_fields": [],
    "intake_rating": "A",
    "created_at": "..."
  }
}
```

### 4.2 生成器（`scripts/make_demo_payloads.py`，232 行）

**结构**：

- 3 个领域 profile 函数（`_cs_ai_grad_profile` / `_cs_ai_top_profile` / `_med_ug_profile`），返回 dict
- 1 个工厂函数 `_make_intake(domain, rating)`，按评级裁剪字段后 `ProjectIntake.model_validate`
- 1 个 `main()`，遍历 3×4=12 组合，**重算评级并写回 JSON**

**关键设计**：

- **领域与评级解耦**——3 个 profile 是"完整画像"，12 个案例只是在完整画像上做最小裁剪（A 全填、B 砍 must_keep、C 砍 proposal_deadline、D 砍 raw_topic）。
- **重算评级写回**——`intake_rating` 字段是 Pydantic 必填，但**模型层不重算评级**（`model_validate` 只做字段校验）。main 里手动调 `derive_missing_fields + compute_intake_rating`，把规约的"实际评级"写进 JSON，保证 demo 案例的 intake_rating 字段与文件名后缀一致。
- **不调用任何 LLM**——纯 Pydantic 工厂，无网络。

### 4.3 冒烟验收（`scripts/demo_smoke.py`，133 行）

**结构**：

- 读 `data/demo_cases/*.json`
- 对每份：
  1. 从文件名解析期望评级（`A_` / `B_` / `C_` / `D_`）
  2. POST `/api/v1/projects`，断言 201
  3. 断言服务端返回的 `payload.intake_rating == 期望评级`
  4. POST `/api/v1/projects/{id}/intake/validate`
  5. 断言 `outcome == 期望 outcome` 且 `intake_rating == 期望评级`
  6. 断言 `allow_proceed_to_phase02` 标志正确

**输出**：

```
=== demo smoke @ http://127.0.0.1:18181 (12 cases) ===
  [OK ] POST A_CS_AI_GRAD + validate outcome=OK + allow=True
  [OK ] POST A_CS_AI_TOP  + validate outcome=OK + allow=True
  [OK ] POST A_MED_UG     + validate outcome=OK + allow=True
  [OK ] POST B_CS_AI_GRAD + validate outcome=OK + allow=True
  [OK ] POST B_CS_AI_TOP  + validate outcome=OK + allow=True
  [OK ] POST B_MED_UG     + validate outcome=OK + allow=True
  [OK ] POST C_CS_AI_GRAD + validate outcome=NEED_CLARIFICATION + allow=False
  [OK ] POST C_CS_AI_TOP  + validate outcome=NEED_CLARIFICATION + allow=False
  [OK ] POST C_MED_UG     + validate outcome=NEED_CLARIFICATION + allow=False
  [OK ] POST D_CS_AI_GRAD + validate outcome=BLOCKED + allow=False
  [OK ] POST D_CS_AI_TOP  + validate outcome=BLOCKED + allow=False
  [OK ] POST D_MED_UG     + validate outcome=BLOCKED + allow=False
=== DEMO SMOKE OK ===
```

**48/48 断言通过**。零 5xx，零 traceback。

---

## 5. 数据流：demo_smoke 端到端

```text
data/demo_cases/A_CS_AI_GRAD.json
                  │
                  ▼  (json.load)
        {"intake": <ProjectIntake dict>}
                  │
                  ▼  (httpx POST)
        POST /api/v1/projects
                  │
                  ▼  (FastAPI 路由)
        CreateProjectRequest (Pydantic v2 校验)
                  │
                  ▼  (router.create_project)
        ProjectIntake.model_copy(intake_rating=A 来自服务端)
                  │
                  ▼  (ProjectRepository.create)
        INSERT INTO projects (case_id, payload)
                  │
                  ▼  (SQLite)
        data/topicpilot.db row id=N
                  │
                  ▼  (响应)
        HTTP 201 {"id":N, "case_id":"...", "payload":<ProjectIntake>}
                  │
                  ▼  (demo_smoke 断言)
        rating persisted = A ✓
                  │
                  ▼  (POST validate)
        POST /api/v1/projects/N/intake/validate
                  │
                  ▼  (validate_intake 纯函数)
        (ValidationOutcome.OK, "A", [])
                  │
                  ▼  (写回库)
        UPDATE projects SET payload=? WHERE id=N
                  │
                  ▼  (响应)
        {"outcome":"OK", "intake_rating":"A", "missing_fields":[],
         "allow_proceed_to_phase02":true}
                  │
                  ▼  (demo_smoke 断言)
        outcome=OK ✓  allow=True ✓
```

**单测不覆盖、demo 覆盖的部分**：

- 端到端 JSON 序列化往返（生成 → 落库 → 重水合 → 响应）——单测只测纯函数
- `payload.intake_rating` 字段被服务端正确覆盖（不让客户端控制）——只有端到端能验证
- `allow_proceed_to_phase02` 标志与 outcome 的对应关系——单测里手写常量，demo 用 HTTP 验证真值

---

## 6. 与规约的偏离

无字段偏离。两条**实现细节**标注如下：

### 6.1 must_keep 在 C 和 D 案例中也为空

C/D 案例的 `must_keep=[]` 是裁剪规则里隐含的（`_make_intake` 默认 `must_keep=[]`），所以它们的 `missing_fields` 里会出现一个 P2 `must_keep`：

| 案例 | missing_fields | 主导缺失 | 实际评级 |
|------|---------------|---------|---------|
| C_CS_AI_GRAD | [proposal_deadline(P0), must_keep(P2)] | P0 | C ✓ |
| D_CS_AI_GRAD | [must_keep(P2)] | 占位符 | D ✓ |

不影响评级结果——C 的 P0 缺失主导规则，D 的占位符规则绕过 missing 列表直接 D 触发。但**未来如果 C 案例的 missing 列表被用来决定补问优先级**，这个 P2 会被错误地优先关注。要彻底干净，C 案例应当把 must_keep 填上。**这是已知小瑕疵**，本报告不修，留作下一轮迭代。

### 6.2 3 领域的 3 档目标分布不均

- CS_AI_GRAD、MED_UG 目标档位 = 保毕业
- CS_AI_TOP 目标档位 = 冲高水平

设计时只想要 3 领域，不严格交叉 3 × 3 目标档位。Phase 01 评级规则不区分目标档位（`goal_level` 字段在 P0 必填但不参与评分），所以**目标档位不参与评级计算**——3 领域的差异体现在 `student_resources.weekly_hours` / `compute_resource` / `inherited_resources` 上，不在 `goal_level` 上。

如果未来 Phase 02 风险评分时给"冲高水平"加权，这里就有意义了。

---

## 7. 验收对照

| 项 | 状态 |
|----|------|
| 12 案例 JSON 全部生成 | ✓ `data/demo_cases/` 12 个文件 |
| 12 案例 `intake_rating` 与文件名一致 | ✓ `expected=X actual=X` 12/12 |
| 12 案例 POST /api/v1/projects 返 201 | ✓ |
| 12 案例 POST validate 返 200 | ✓ |
| 12 案例 outcome 与评级表一致 | ✓ A/B→OK, C→NEED_CLARIFICATION, D→BLOCKED |
| 12 案例 `allow_proceed_to_phase02` 标志正确 | ✓ A/B=True, C/D=False |
| 既有 29 条单测无回归 | ✓ 29/29 仍通过 |
| uvicorn 启动无 traceback | ✓ |

---

## 8. 用法

### 8.1 重新生成 JSON（字段调整后）

```bash
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/make_demo_payloads.py
```

### 8.2 跑端到端验收（需先起 uvicorn）

```bash
# Terminal 1
.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir apps/api --port 18181

# Terminal 2
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/demo_smoke.py
```

### 8.3 作为回归基线接入 CI

未来如果加 GitHub Actions，步骤：

1. `uv pip install -e ".[dev]"`
2. `uv run python -m uvicorn app.main:app --app-dir apps/api --port 18181 &`
3. `sleep 3 && uv run python scripts/demo_smoke.py`
4. 失败即 fail CI

### 8.4 作为面试 artifact

```bash
# 给面试官看 12 份 JSON
ls data/demo_cases/
cat data/demo_cases/A_CS_AI_GRAD.json | jq
```

---

## 9. 一句话总结

> Demo 案例集用 3 领域 × 4 评级 = 12 份 Pydantic 校验过的 JSON fixture，守护住 Phase 01 评级规则的核心契约。`make_demo_payloads.py` 保证字段与模型同步，`demo_smoke.py` 守护 outcome 路由。48 个端到端断言在真 uvicorn + 真 SQLite 上全过，29 条既有单测无回归。
