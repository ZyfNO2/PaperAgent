# AutoResearchClaw 对标移植 ·收报告

> 日期：2026-06-22
> 性质：面试材料补强（思路向），不是 Phase / Session SOP。
> 口径：较小 MVP骨架 +试思路为主，未新增可执行代码，未伪造 Session编号。

---

## 1. 本轮做了什么

用户给定两个参考项目，要求把它对标移植到 TopicPilot-CN，但**思路为主、不强制具体实现**，且交付贴近求职/企业技能库口径：

1.考一：[AutoResearchClaw](https://github.com/aiming-lab/AutoResearchClaw)（aiming-lab，8.2k star，23段8相位全自动科研流水线）
2.考二：[scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills)（K-Dense-AI，147科研skill + Agent Skills开放标准）

产出一份对标设计文档：
- `docs/interview/AutoResearchClaw_对标与小型化移植.md`（扩到 §10后 457行）

并补一节面试材料交叉引用（§10）：对标后哪些试材料点讲得更好。

## 2.对标文档结构（§0-§10）

| | 内容 | 性质 |
|---|---|---|
| §0 | 为什么对标而不照搬（TopicPilot-CN是 ARC前置阶段：判断→开题报告，不跑实验/LaTeX） |路 |
| §1 |对标总表（16 ARC特性 →状/口径/企业技能库对标） |路 |
| §2 | **8 已对齐点**（只讲不补） |路 |
| §3 | **3可补强点**：§3.1 MetaClaw注入（最高）/ §3.2多层验证链（高）/ §3.3断降级（中） |路+最小可测单元 |
| §4 | 6不适用 +诚划界（不跑实验/LaTeX/ACP等） |界 |
| §5 |职深度一页表 +最值得讲3条 |路 |
| §6-8 |度/成本/不变式/落地优先级 |路 |
| §9 | scientific-agent-skills 与 S13 SkillRegistry对齐 |路 |
| §10 |试材料交叉引用（本轮新增） |路 |

## 3.三个补强点（思路为主，最小可测单元已写明，未落地）

- **P0 §3.1 MetaClaw注入**：run败留 lesson→下次注入该 stage prompt当"已知陷阱"小节。不接外部 MetaClaw、不 RLHF、可回放可回滚。对应缺口：试需清单"Agent忆从经验中学习"。对标 DSPy/promptfoo/RLAIF-lite。
- **P1 §3.2 多层引用验证链**：单层 URL Verified→可链接性/来源权威性/元数据完整性/内容相关性四层，LLM只判定不入 supports，产 verification_report.json。对应缺口：试需清单"RAG真 Hybrid/Eval闭环"。对标 Great Expectations/dbt tests/OpenLineage。
- **P2 §3.3显式熔断**：写死 try/except→closed/half_open/open +数退避 +诊断日志，复用已有 structured_log和 stale机制。对应缺口：试需清单"工具调用失败/路由错误"。对标 Resilience4j/Sentinel。

三档口径不破坏：P0 design-only、P1从 lightweight级、P2从 implicit fallback显式化；均不标 implemented除非真写测试。

## 4.诚实边界（守 Technical_Highlights三档）

- **不接外部 MetaClaw /不写 skills外部目录**
- **不引 Resilience4j/Hystrix/Sentinel**（自写极简版讲清原理）
- **不接真实向量库替代 lightweight索**
- **不做 RLHF/参数更新/微调**
- **不生成 LaTeX /不加 ACP多后端 /不做消息桥接**
- **不照搬 scientific-agent-skills 147个具体科研 skill**（蛋白对接/分子动力学不在开题范围）
- §10.3诚缺口：多模态解析、检索缓存、真实向量库对标无补强，保持现状回答不改口径

## 5.与 CLAUDE.md不变式对齐情况

- 设计不冒充已落地：本报告和§10都是思路设计，非验收强约束；落地与否以代码+pytest为准。
- LLM不直接写 supports /不参与真伪判定：§3.2 Layer4只判定相关性，不入池，守住证据规则不变式。
- pytest总数只增不减：本轮不新增/删除代码，无 pytest义务变动。
-据从.env读不引未列依赖：本轮无新依赖、无新代码。
- LLM路径配 heuristic fallback：未涉及，不变式保持。

## 6.试材料交叉引用要点（§10新增价值）

对标后试讲解的"3个最高性价比讲法"（建议新增到 Demo_Script）：

1.容错从"写死兜底"→"可观测容错链，对标 Resilience4j"（§3.3）
2.反幻觉从"单层 URL Verified"→"多层验证链+引用级血缘，对标 ARC四层验证"（§3.2）
3.自我改进从"Trace可回放"→"教训反哺prompt，对标 MetaClaw/Autoskill"（§3.1）

覆盖试材料：Interview_QA_Cards（30，6类）、Resume_Bullets、Failure_Cases、试需清单短板表。

## 7.后续可选落地（不强约束，用户定）

| 优先级 |路点 | 最小单元 |估工作量 |
|---|---|---|---|
| P0 | §3.1训注入 | lesson_extractor + build_prompt_overlay + 2 pytest | 半天 |
| P1 | §3.2多层验证链 | LayerChain + verification_report.json + 2 pytest | 半天-1天 |
| P2 | §3.3显式熔断 | CircuitBreaker +多源检索接入 + 1 pytest | 半天 |

落地后应在 acceptance report中写对照叙事（用 ARC哪个思路、小型化取舍、对应哪个企业技能库概念），并回写进试材料（Technical_Highlights / Deep_Dive_QA）。

## 8.本轮未涉及的关联事项（诚实记录）

- Session 41-43端改动（apps/web/{app.js,index.html,styles.css,step_workbench.js}）仍为未提交状态（git status M），属另一个 Phase收尾，本轮不动。
- 本轮不跑 pytest（无代码变更，无测试义务）；如后续落地 P0/P1/P2任一项，按 CLAUDE.md跑 pytest全绿后才能 commit。
- 本次commit范围仅限本轮两份文档（对标文档+本报告），不碰 apps/ / .claude/ /data 等。

---

## 附：产物清单

- 设计文档：`docs/interview/AutoResearchClaw_对标与小型化移植.md`（457行，§0-§10）
- 本报告：`Plan/reports/AutoResearchClaw_对标移植_验收报告.md`
-考项目：ARC (aiming-lab/AutoResearchClaw) +ientific-agent-skills (K-Dense-AI/scientific-agent-skills)
- 关联面试材料：docs/interview/Technical_Highlights.md / Interview_QA_Cards.md / Resume_Bullets.md / Failure_Cases.md / Deep_Dive_QA_*.md / Agent_Memory_Explainer.md / RAG_Design_Explainer.md
