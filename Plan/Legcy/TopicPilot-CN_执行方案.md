# TopicPilot-CN 多阶段执行 SOP 总索引

> 版本：v0.3  
> 日期：2026-06-15  
> 说明：本文件为总索引。前四个 Phase 已结合“毕业论文合集”方法论优化；后续 Phase 暂不定稿，先保留为待定。

---

# 1. 执行目标

TopicPilot-CN 初版先解决开题/选题阶段的核心问题：把一个原始研究想法转化为“可毕业、可检索、可复现、可写成章节”的题目方案。

结合毕业论文合集中的经验，前四个 Phase 优先贯彻四条原则：

1. **目标先行**：先判断学生是保毕业、稳中求新，还是冲高水平。
2. **方向成熟度优先**：优先选择论文、数据、代码和模板都较多的方向。
3. **Baseline 优先**：先找可继承、可复现、可运行的基准，再谈创新。
4. **章节反推工作量**：开题阶段就要能映射到第三章、第四章或系统/泛化章节。

---

# 2. Phase 划分

| Phase | 文件 | 状态 | 核心目标 |
|---|---|---|---|
| Phase 1 | [Phase_01_任务建档与毕业目标确认.md](TopicPilot-CN_SOP_Phases/Phase_01_任务建档与毕业目标确认.md) | 已优化 | 明确学生目标、导师约束、毕业要求和资源边界 |
| Phase 2 | [Phase_02_题目拆解与论文结构映射.md](TopicPilot-CN_SOP_Phases/Phase_02_题目拆解与论文结构映射.md) | 已优化 | 将题目拆成研究组件，并预判能否形成论文章节 |
| Phase 3 | [Phase_03_方向成熟度与检索计划.md](TopicPilot-CN_SOP_Phases/Phase_03_方向成熟度与检索计划.md) | 已优化 | 按“人多方向/基准/综述/实验模板”生成检索计划 |
| Phase 4 | [Phase_04_证据采集与Baseline账本.md](TopicPilot-CN_SOP_Phases/Phase_04_证据采集与Baseline账本.md) | 已优化 | 收集论文、数据、代码、指标和可继承模板证据 |
| Phase 5 | [Phase_05_待定.md](TopicPilot-CN_SOP_Phases/Phase_05_待定.md) | 待定 | 后续根据前四阶段跑通情况确定 |
| Phase 6 | [Phase_06_待定.md](TopicPilot-CN_SOP_Phases/Phase_06_待定.md) | 待定 | 后续根据前四阶段跑通情况确定 |
| Phase 7 | [Phase_07_待定.md](TopicPilot-CN_SOP_Phases/Phase_07_待定.md) | 待定 | 后续根据前四阶段跑通情况确定 |
| Phase 8 | [Phase_08_待定.md](TopicPilot-CN_SOP_Phases/Phase_08_待定.md) | 待定 | 后续根据前四阶段跑通情况确定 |

---

# 3. 当前推荐执行顺序

```text
Phase 1 任务建档与毕业目标确认
→ Phase 2 题目拆解与论文结构映射
→ Phase 3 方向成熟度与检索计划
→ Phase 4 证据采集与 Baseline 账本
→ Phase 5-8 待定
```

---

# 4. 前四阶段门禁

- Phase 1 未确认毕业目标、时间、导师方向和资源条件，不进入 Phase 2。
- Phase 2 未拆出对象、任务、数据、方法、评价和章节映射，不进入 Phase 3。
- Phase 3 未覆盖论文、综述、数据集、Baseline、实验指标和同领域论文模板，不进入 Phase 4。
- Phase 4 未找到数据、Baseline 或明确证明缺失，不进入后续风险裁决。

---

# 5. 单个案例目录建议

```text
work/
└── topic_cases/
    └── YYYYMMDD_学生或题目简称/
        ├── 00_input.md
        ├── 01_topic_spec.md
        ├── 02_query_plan.md
        ├── 03_evidence_ledger.md
        └── 99_phase_review.md
```

