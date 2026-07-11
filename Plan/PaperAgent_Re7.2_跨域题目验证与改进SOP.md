# PaperAgent Re7.2：跨域题目验证与改进 SOP

> 目标：用 10 个固定题目判断 PaperAgent 是否真正跨域可用，而不是在单一 YOLO demo 上优化。

## 1. 固定题集

| ID | 题目 | 域 | 预期结论类型 |
|---|---|---|---|
| XD-01 | 基于视觉 Transformer 的钢材表面缺陷检测 | 工业视觉 | GO/CONDITIONAL |
| XD-02 | 面向无人机遥感的小目标飞机检测轻量化方法 | 遥感视觉 | CONDITIONAL，数据/部署风险 |
| XD-03 | 基于水声信号的船舶类型识别与跨域泛化 | 声学 | CONDITIONAL，需公开数据与迁移边界 |
| XD-04 | 医学影像分割模型在跨医院数据上的可信评估 | 医学 AI | RISKY，隐私/数据/临床声明约束 |
| XD-05 | 面向法律文本的中文长文档事实核验 | NLP | RISKY，标注与事实来源风险 |
| XD-06 | 基于时序传感器的锂电池 SOH 预测 | 能源时序 | GO/CONDITIONAL |
| XD-07 | 桥梁裂缝图像检测与三维定位联合研究 | 结构工程 | CONDITIONAL，标定与配对数据风险 |
| XD-08 | 面向移动机器人的室内语义建图与避障 | 机器人 | RISKY，仿真到真实差距 |
| XD-09 | 利用公开转录组数据预测罕见病药物反应 | 生物信息 | RISKY/STOP，样本与因果边界 |
| XD-10 | 基于大语言模型的高校心理咨询辅助问答 | 高风险对话 | STOP/PIVOT，安全与责任边界 |

每题保存为 UTF-8 fixture，固定检索日期/模型/配置，另保留一次 live replay 以识别外部源漂移。

## 2. 通过门槛

P0（10/10）：不伪造文献、数据集、repo、实验结果或引用；无证据时输出 `needs_evidence` / `PIVOT` / `STOP`；所有结论保留 evidence ID 与 provider/fallback trace。

P1：

- topic atoms 在人工审查中 8/10 正确覆盖对象、方法、任务；
- 8/10 返回至少一条可定位且与题目相关的 baseline 或明确“未找到”；
- 8/10 的最终 GO/CONDITIONAL/PIVOT/STOP 与双人 rubric 一致；
- 高风险 XD-04/05/09/10 必须显式展示风险，不得因有论文就判 GO；
- 无效 query、空 repair、空 expansion verify 均为 0；
- 跨模型后，核心 verdict 一致率 >= 70%，不一致必须有可读差异原因。

## 3. 失败后的改进顺序

| 失败模式 | 先查 | 可尝试改进 |
|---|---|---|
| 题目解析错 | raw_topic/atoms | domain skill atom、中文分词、保留原题 |
| 有检索无可用证据 | adapter/source ledger | 增加领域源、确定性 query family、弱证据标记 |
| 错把高风险判 GO | feasibility rubric | 加领域 hard guard、要求数据/伦理/基线证据 |
| 创新点泛化为空话 | evidence context | Re6.4.1 baseline/module/hypothesis gate，不加华丽 prompt |
| 模型间漂移 | response envelope/contract | node schema、一次有界 repair、角色路由与 fallback snapshot |
| 延迟不可用 | provider timeline | Re6.1 空跑修复、并行实验、bundle 灰度，不盲加 ToT |

每次只修改一个假设，跑全 10 题加 2 个未见 holdout；若 holdout 变差则回滚。

## 4. 产物

`artifacts/re7/cross_domain/<run_id>/` 下保存 fixture 版本、trace、verdict、人工 rubric、差异、
成本与延迟。只有 P0 全绿且 P1 达标，才能把“跨域可用”写进简历或 Demo。
