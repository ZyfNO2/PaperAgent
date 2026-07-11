# PaperAgent Re6.4.1：学术裁缝方法落地门 SOP

> 决策：**需要更新 Re6.4，但不替换现有创新点评审链。**  
> 新参考：`academic-method-tailoring` skill。  
> 作用：把“创新点候选可辩护”进一步约束为“方法可复现、可集成、可公平验证”。

## 目录

1. 更新判断
2. 双层职责
3. 最小新增合同
4. 链路与门禁
5. 验收

## 1. 更新判断

Re6.4 已覆盖 Problem--Method--Insight、伪创新、可证伪、相邻工作差异和演化日志；但尚未把
`Method` 拆成可运行的 baseline/module/interface/experiment 合同。因此存在“创新叙事可过、
实际模块拼接不可复现或不公平”的风险。

本增量不改写 Re6.4 的创新审查 prompt；它在候选进入工作包、代码或论文方法章节前增加工程化
方法门。所有状态必须明确为 `verified|inferred|proposed|unknown`。

## 2. 双层职责

| 层 | 输入 | 核心问题 | 禁止越权 |
|---|---|---|---|
| Re6.4 NoveltyReviewAdapter | evidence + 创新候选 | 是否有 Problem--Method--Insight，是否伪创新、可证伪 | 不证明代码能跑或实验已完成 |
| Re6.4.1 Method Tailoring Gate | 已审查候选 + baseline/code/data 信息 | baseline 能否复现、模块是否语义兼容、实验能否证伪 | 不把计划写成结果，不替代文献真实性验证 |

## 3. 最小新增合同

- `BaselineCard`：paper/DOI、repo+commit、license、dataset/split、environment、reported 与 reproduced metric、状态；
- `ModuleCard`：来源/许可、原作用与新作用、输入输出语义、dtype/scale/order/mask、gradient/loss、算力、失败模式；
- `CompatibilityMatrix`：每个 producer->consumer 边的语义单位、shape、归一化、时空顺序、mask、梯度与测试；
- `MethodHypothesis`：条件 C、限制 L、机制 M、干预 B、观测 Y、guardrail G、falsifier；
- `ExperimentMatrix`：frozen baseline、单模块、leave-one-out、full、compute-matched control、固定 split/seeds/预算；
- `MethodDecision`：`GO|REVISE|NO_GO`，连同缺证据和 stop condition。

## 4. 链路与门禁

```text
verified evidence
  -> Re6.4 novelty candidate + pressure review
  -> baseline freeze -> module cards -> compatibility matrix
  -> falsifiable method hypothesis -> experiment matrix
  -> GO / REVISE / NO_GO -> work package / implementation
```

| Gate | 通过条件 | 失败处置 |
|---|---|---|
| G0 scope | 指标、约束、数据/算力与边界明确 | `REVISE`，不得选模块 |
| G1 evidence | 重要来源可定位，未知项显式标记 | `needs_evidence` |
| G2 baseline | 原路径可运行，或明确接受重实现风险 | 不进入模块组合 |
| G3 hypothesis | 机制、guardrail、falsifier 可观测 | 降级为 proposed idea |
| G4 integration | 不仅 shape，语义/scale/order/mask/gradient 皆有测试 | 禁止“reshape 修好” |
| G5 experiment | 有公平对比、消融和停止条件 | 不得声称贡献成立 |

## 5. 验收

- [ ] 所有借用模块、代码、数据和文本模式有来源与 license 字段；
- [ ] 未复现 baseline 的候选不能标 `GO`；
- [ ] 每个模块边界至少有一个语义兼容测试，而不只测 tensor shape；
- [ ] 每条机制主张都有可推翻的实验与 guardrail；
- [ ] 方法章节只能读取已验证 artifact，未跑实验用 `proposed/planned_not_verified` 表述；
- [ ] 负结果和已知限制保留在 evolution log。
