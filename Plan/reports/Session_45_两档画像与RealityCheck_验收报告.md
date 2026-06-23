# Session 45 验收报告：两档画像重构 + RealityCheck 现实约束

> 日期：2026-06-24
> 对应 SOP：`Plan/PaperAgent_Session45_两档画像与RealityCheck_SOP.md`

---

## 完成情况

| Task | 状态 | 关键产物 |
|------|------|----------|
| T1: GoalLevel 两档化 | ✅ | `schemas.py` GoalLevel 改两档 + 兼容 validator |
| T2: RealityCheck Schema | ✅ | `schemas_reality.py` (RealityCheck + 资源四层 + 实验周期) |
| T3: RealityCheck Service | ✅ | `services/reality_check.py` (assess_reality + 融合降级) |
| T4: judge_feasibility 整合 | ✅ | `one_topic.py` judge_feasibility 调用 reality_check |
| T5: 前端适配 | ✅ | `index.html` 下拉选项两档 |
| T6: 测试 | ✅ | 26 个新测试全绿，554 旧测试全绿 |
| T7: E2E | ⚠️ | 24 passed, 267 errors (Playwright 浏览器未安装) |

---

## T1: GoalLevel 两档化

### 改动

```python
# 旧
GoalLevel = Literal["保毕业", "稳中求新", "冲高水平"]
# 新
GoalLevel = Literal["保毕业", "已有小论文"]
```

### 旧值兼容映射

```python
_GOAL_LEVEL_COMPAT = {
    "稳中求新": "保毕业",
    "冲高水平": "已有小论文",
}
```

通过 `field_validator(mode="before")` 在 Pydantic 验证前做映射，保证旧 project_memory 数据不崩。

### 影响文件

- `apps/api/app/schemas.py` — GoalLevel 枚举 + validator
- `apps/web/index.html` — 下拉选项两档
- `apps/api/app/services/llm_content.py` — 无需改（用占位符传值）
- `apps/api/app/services/one_topic.py` — intent 文案无需改（goal_level 值自动变）

---

## T2: RealityCheck Schema

### 新建文件：`apps/api/app/schemas_reality.py`

```python
ResourceTier = Literal["existing_env", "rent_compute", "self_collect_data", "infeasible"]
ExperimentCycle = Literal["week", "month", "year"]
GraduationRisk = Literal["low", "medium", "high"]

class RealityCheck(BaseModel):
    resource_tier: ResourceTier
    resource_reason: str
    experiment_cycle: ExperimentCycle
    cycle_reason: str
    max_experiment_rounds: int
    graduation_risk: GraduationRisk
    score: int  # 0-100
    suggestion: str
```

### 实验轮数矩阵

| goal_level | week | month | year |
|------------|------|-------|------|
| 保毕业 | 5轮/low | 2轮/medium | 1轮/high |
| 已有小论文 | 5轮/low | 3轮/low | 1轮/medium |

### FeasibilitySummary 扩展

新增 `reality_check: dict | None` 字段，存储 RealityCheck 评估结果。

---

## T3: RealityCheck Service

### 新建文件：`apps/api/app/services/reality_check.py`

#### 资源四层判断逻辑

| 资源层 | 判断条件 | 实验周期 |
|--------|---------|---------|
| `existing_env` | 有公开数据集 + 可复现baseline + 非大模型 | week |
| `rent_compute` | 有公开数据集但需大算力（大语言模型/Transformer/扩散模型等） | month |
| `self_collect_data` | 无公开数据集 | month~year |
| `infeasible` | 无数据集 + 无baseline + 极小众 | year |

#### 融合降级规则

- `graduation_risk == high` → verdict 至少降一级（可做→收缩后可做）
- `graduation_risk == high + infeasible` → 直接 STOP/不建议
- `graduation_risk == medium/low` → 不降级

---

## T4: judge_feasibility 整合

### 数据流

```text
judge_feasibility(req, keywords, ev)
  ↓
原有 5 档 verdict 决策 (可做/收缩后可做/可转向/暂缓/不建议)
  ↓
assess_reality(keywords, ev, goal_level, raw_topic) → RealityCheck
  ↓
apply_reality_to_verdict(verdict, reality) → 降级后 verdict
  ↓
FeasibilitySummary(reality_check=reality.model_dump())
```

---

## T5: 前端适配

`apps/web/index.html` 下拉选项从三档改为两档：

```html
<option value="保毕业" selected>保毕业</option>
<option value="已有小论文">已有小论文</option>
```

---

## T6: 测试结果

### 新增测试：`apps/api/tests/test_session45_reality_check.py`

26 个测试，覆盖：
- GoalLevel 两档 + 兼容映射 (4 个)
- 资源四层判断 (4 个)
- 实验周期判断 (4 个)
- 实验轮数矩阵 (4 个)
- assess_reality 集成 (3 个)
- 融合降级 (4 个)
- 大模型判断 (3 个)

### pytest 全量结果

```text
554 passed, 1 skipped (旧测试)
26 passed (新测试)
= 580 passed, 1 skipped
```

所有旧测试通过，兼容映射生效。

---

## T7: E2E 测试

- 24 passed (不依赖 browser 的 API 测试)
- 267 errors (Playwright 浏览器未安装，环境问题)
- 正在安装 Playwright chromium，安装后重新跑

---

## 偏离说明

1. **llm_content.py 未改 prompt 文案**：经检查，prompt 中只用 `{goal_level}` 占位符传值，没有硬编码旧三档文案，无需改动。
2. **旧测试未改 goal_level 值**：兼容映射自动处理旧值，旧测试无需修改即可通过。
3. **RealityCheck 用 dict 存储**：FeasibilitySummary.reality_check 字段用 `dict | None` 而非 `RealityCheck` 类型，避免 schema 循环依赖。

---

## 产物清单

| 文件 | 类型 | 说明 |
|------|------|------|
| `apps/api/app/schemas.py` | 修改 | GoalLevel 两档 + validator + FeasibilitySummary.reality_check |
| `apps/api/app/schemas_reality.py` | 新建 | RealityCheck schema + 资源四层 + 实验周期 |
| `apps/api/app/services/reality_check.py` | 新建 | assess_reality + 融合降级 |
| `apps/api/app/services/one_topic.py` | 修改 | judge_feasibility 整合 reality_check |
| `apps/web/index.html` | 修改 | 下拉选项两档 |
| `apps/api/tests/test_session45_reality_check.py` | 新建 | 26 个测试 |
| `Plan/PaperAgent_Session45_两档画像与RealityCheck_SOP.md` | 新建 | SOP 文档 |
