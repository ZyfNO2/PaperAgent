# Session 28 验收报告 — 可行性风险裁决与 PIVOT 路线

## 产物清单

### 新增文件
| 文件 | 说明 |
|------|------|
| `apps/api/app/schemas_feasibility.py` | 7 维风险评估 + 5 裁决 + 6 硬性否决 + 3 PIVOT 路线 |
| `apps/web/feasibility_card.js` | 前端 FeasibilityCard：维度渲染、否决展示、PIVOT 路线卡 |
| `apps/api/tests/test_session28_feasibility.py` | 13 个后端测试 |
| `apps/web/e2e/test_one_topic_session28_feasibility.py` | 7 个 Playwright e2e 测试 |

### 修改文件
| 文件 | 说明 |
|------|------|
| `apps/web/index.html` | 添加 `<script src="feasibility_card.js">` |

## 测试结果

| 类型 | 通过 | 总数 | 状态 |
|------|------|------|------|
| 后端 pytest | 13 | 13 | ✅ 全绿 |
| Playwright e2e | 7 | 7 | ✅ 全绿 |
| 全量回归 | 344 | 345 (1 skip) | ✅ 无回退 |

## 7 维风险评估

| 维度 | 含义 |
|------|------|
| EvidenceSupport | 证据数量是否达阈值 |
| DataAvailability | 是否有可访问数据集 |
| BaselineReadiness | 是否有 baseline/repo |
| ExperimentalClarity | 是否有实验方案 |
| ScopeControl | 范围是否可控 |
| ResourceFit | 资源是否可访问 |
| NoveltyDifferentiation | 创新度是否有区分 |

## 5 裁决

| 裁决 | 含义 |
|------|------|
| GO | 条件齐全，继续 |
| CONDITIONAL | 可做但需补资源 |
| PIVOT | 需收缩或换方向 |
| PARK | 条件不足，暂挂 |
| STOP | 核心条件不可验证 |

## 6 硬性否决规则

无数据集、无指标、无 baseline、无实验方案、URL 未验证、EvidenceRef 不足 → 均阻断 GO

## PIVOT 路线

每条 PIVOT/PARK/STOP 裁决自动生成 3 条路线：
- 🐢 保守：缩小范围
- ⚖️ 平衡：替换数据集
- 🚀 进取：补齐条件

## Bug 修复

- **PW-1 regex 误匹配**：`feasibility-dim` 正则匹配到容器类名 `feasibility-dimensions` → 改用 `class="feasibility-dim"` 精确匹配
