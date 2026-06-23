# PaperAgent Session 45 SOP：两档画像重构 + RealityCheck 现实约束

## 0. 对 Session 44 的审阅结论

Session 44 通过。ACP 协议互操作设计、Interview Mode UI、E2E 测试均已落地。

仍需补强点：

- 产品画像仍停留在旧三档，不贴近真实毕业路线。
- 可行性评估缺少"资源可达性"和"实验周期"两个现实约束维度。

因此下一步进入：

```text
Session 45：两档画像重构 + RealityCheck 现实约束
```

## 1. 本轮目标

两块改动，一个 Session 完成：

1. **目标档位两档化**：`保毕业 / 稳中求新 / 冲高水平` → `保毕业 / 已有小论文`
2. **RealityCheck 独立模块**：资源可达性四层 + 实验周期三档，与现有可行性评估并列融合

核心原则：

```text
画像从"你想做到什么水平"改为"你现在处于哪种毕业状态"；
可行性评估加入"现有环境能做/需租算力/需自采数据/真做不到"现实约束。
```

## 2. 改动一：目标档位两档化

### 2.1 数据模型

```python
# 旧
GoalLevel = Literal["保毕业", "稳中求新", "冲高水平"]
# 新
GoalLevel = Literal["保毕业", "已有小论文"]
```

### 2.2 旧值兼容映射

```text
稳中求新 → 保毕业
冲高水平 → 已有小论文
```

在 `OneTopicRequest` 的 model_validator 中做兼容映射。

### 2.3 影响范围

| 文件 | 改动 |
|------|------|
| `apps/api/app/schemas.py` | GoalLevel 枚举 + validator |
| `apps/web/index.html` | 下拉选项两档 |
| `apps/api/app/services/llm_content.py` | prompt 文案适配 |
| `apps/api/app/services/one_topic.py` | intent 文案适配 |
| 测试文件 | 旧值替换 |

## 3. 改动二：RealityCheck 独立模块

### 3.1 Schema（schemas_reality.py）

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

### 3.2 资源四层判断逻辑

| 资源层 | 判断条件 | 实验周期 |
|--------|---------|---------|
| `existing_env` | 有公开数据集 + 可复现baseline + 非大模型 | week |
| `rent_compute` | 有公开数据集但需大算力 | month |
| `self_collect_data` | 无公开数据集 | month~year |
| `infeasible` | 无数据集 + 无baseline + 极小众 | year |

### 3.3 实验轮数与毕业风险

| goal_level | week | month | year |
|------------|------|-------|------|
| 保毕业 | 5轮/low | 2轮/medium | 1轮/high |
| 已有小论文 | 5轮/low | 3轮/low | 1轮/medium |

### 3.4 融合降级规则

- `graduation_risk == high` → verdict 至少降一级（可做→收缩后可做）
- `graduation_risk == high + infeasible` → 直接 STOP
- `FeasibilitySummary` 新增 `reality_check: RealityCheck` 字段

## 4. 实现步骤

### Step 1: Schema 层
1. 改 `schemas.py` GoalLevel 两档 + validator
2. 新建 `schemas_reality.py`
3. `FeasibilitySummary` 加 `reality_check` 字段

### Step 2: Service 层
1. 新建 `services/reality_check.py`
2. 改 `judge_feasibility` 整合 reality_check
3. 改 `llm_content.py` prompt 适配

### Step 3: 前端
1. 改 `index.html` 下拉选项

### Step 4: 测试
1. 改旧测试 goal_level 值
2. 新增 reality_check 测试
3. pytest 全绿

### Step 5: E2E + 验收
1. Playwright 批量跑（子代理）
2. commit
3. 验收报告

## 5. 验收标准

- [ ] GoalLevel 两档，旧值兼容
- [ ] RealityCheck 模块产出 resource_tier + experiment_cycle + graduation_risk
- [ ] 融合降级：year+保毕业 → verdict 降级
- [ ] pytest 全绿，测试总数增长
- [ ] Playwright E2E 通过
- [ ] 验收报告完成

## 6. 参考文档

- `Plan/design/PaperAgent_A_项目调研报告_优化版.md`
- `Plan/design/PaperAgent_B_用户画像与流程重构建议_保毕业_已有小论文.md`
