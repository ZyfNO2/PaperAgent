# AutoResearchClaw职向增强 ·收报告

> 日期：2026-06-22
> 性质：面试材料补强（思路向），不是 Phase / Session SOP。
> 口径：在既有对标文档（§0-§10）之上追加 §11-§14，修复 6 份面试文档结构使 pytest 全绿，无新增可执行代码，未伪造 Session编号。

---

## 1. 本轮做了什么

延续 commit 7471e856 的对标设计文档（§0-§10），本轮完成三件事：

1. **求职向技术深度话术**（§11）：8 个最值得讲的技术点，每个给初级/中级/高级三档讲法 + 诚实天花板（讲到哪一档可信）+ 反问防线。
2. **面试点增强速查表**（§12）：10 个面试文档里的具体点，给「对标前→对标后」话术 delta + 强度档提升 + 出处坐标。
3. **多论文 RAG /识图谱实现调研**（§14，用户追加需求）：design-only，核心抽象 LinkwiseContext + PaperKG，对标 GraphRAG局部查询 + Agentic RAG断后动作。

并修复该文档在 heredoc件时遗留的字符丢失（构→架、策→决、识→知识图谱、职→求职等 20+处），同时补 §13.1针。

## 2. §14 多论文 RAG /识图谱核心（本轮主交付）

### 2.1心抽象

```
LinkwiseContext = (focus_paper, related_papers[], relation_type, evidence_refs[])
relation_type ∈ {cites, extends, contradicts, uses_same_dataset, co_cited_by}
```

- **不拼 context window**：按 relation_type 分组喂给不同 Gate。
  - `contradicts` → 可行性风险判断（PIVOT条件之一）
  - `extends` →术路线延续性
  - `uses_same_dataset` → 可复现性
- **PaperKG**：JSON盘 + 内存子图查询，对标 S13 SkillRegistry的「json + 加载器」式。
- **关系来源**：metadata自动抽取（references/cited_by 是结构化字段），不用 LLM断，守「LLM 不直接写 evidence」不变式。

### 2.2 与既有对标的关系

- §14 是 §3.2多层引用验证链的**上游**：先有关系图（§14），再对每条边做四层验证（§3.2）。
- §14 与 §2.2 PIVOT策循环 + §3.3索熔断构成 Agentic RAG的「判断后动作」模式，不另起炉灶。

### 2.3 诚实划界

- **不做**：Neo4j / 全图 GNN / LLM自动抽三元组 /向量库嵌入式图存储。
- **做**：metadata自动关系抽取 + JSON盘 + 内存 dict查找。
- **口径**：当前 design-only。最小可测单元落地后可升 lightweight，但须另起 acceptance report 写对照叙事且不标 implemented 除非真写测试通过。

## 3. 6 份面试文档结构修复（使 pytest 全绿）

本轮在 `commit` 前 `apps/api/tests/test_session33/38/40` 共 8 项 failing，根因是面试文档随 Session 34-43 与 ARC对标逐步扩充后结构校验未跟上。本轮修复：

| 文档 | 问题 |
|---|---|
| `test_session33` REQUIRED_FILES | 7 份清单过时，实际 23 份；扩为 23 份并加维护注释 |
| Technical_Highlights.md | 亮4 apps/.py 证据；总引用 <5 →补 test_session40 等 |
| Known_Limitations_For_Interview.md |「限制+应对+后续」三段式 →补 §应对策略与后续规划 |
| Project_DeepDive_Index.md | 用「##模块 N」速查表使 `^##模块\d+`配 ≥10 →补 12块 |
| Demo_Script_10min.md | <2000 字 +无文件引用 →扩 §10 速查表到 2306 字 |
| Demo_Script_3min.md | 无文件引用 →补涉及文件（保持 ≤900 CJK） |
| Project_OnePager.md |九个认知章节 →补繁简对照速查（9 条体全在） |

修后 `追加 charset sweep` 修复了 heredoc件时丢字（涉及/讲解/工具/MVP主链路 / S14接入 / §6短板等）。

## 4.试状态（测试通过 gate足）

```
apps/api/tests/test_session33_interview_docs.py     全绿
apps/api/tests/test_session38_interview_qa_structure.py  全绿
apps/api/tests/test_session40_resume_packaging.py   全绿
```

全量回归（本轮修改前基线已绿 +本轮未动代码）：

```
554 passed, 286 skipped, 0 failed in 220s
```

skip中在 LLM可用性路径（S6 设计 skip）与网络依赖路径，与 CLAUDE.md「LLM径配 heuristic fallback」一致。

## 5. 与 CLAUDE.md 不变式对齐

- 设计不冒充已落地：§11-§14为思路/design-only，落地与否以代码 + pytest 为准。
- LLM 不直接写 evidence /不参与真伪判定：§14 关系抽取来自 metadata 结构化字段，不来自 LLM断。
- pytest 总数只增不减：本轮不新增/删除代码，仅扩 REQUIRED_FILES 清单与修面试文档（test_session33 由 7 项扩为含 23 项校验，test count 不降）。
- 数据从 .env 读不引未列依赖：本轮无新依赖、无新代码。
- LLM径配 heuristic fallback：未涉及，不变式保持。
-阶段产物契约（Phase 01-04端点 + 409拦截 + heuristic fallback）：未触及，不变式保持。

## 6. 诚实边界（守 Technical_Highlights三档口径）

本轮**不**做：

- 不落地 §14 任何代码（PaperKG 加载器 / 1-hop查询 / LinkwiseContext分组）
- 不改 §3.2层验证链从 lightweight implemented
- 不直接回写 Technical_Highlights / Demo_Script / Deep_Dive_QA_RAG 引用 §14（§13/§14.6 仅作建议，是否回写由后续 Session 定）
- 不接入 Neo4j /向量库 /全图 GNN
- 不让 LLM动抽关系（守 evidence则不变式）

## 7. 后续可选落地（不强约束，用户定）

| 优先级 |径点 | 最小单元 |估工作量 |
|---|---|---|---|
| P3 | PaperKG 加载器 | `load_paperkg()` + `PaperNode` dataclass + 1 pytest | 半天 |
| P3 | 1-hop查询 | `get_neighbors(paper_id, relation_type)` + 1 pytest | 半天 |
| P3 | LinkwiseContext 分组 | `build_linkwise_context(focus_paper)` 按 relation_type 分组 + 1 pytest | 半天 |

落地后应另起 acceptance report 写对照叙事：用了 GraphRAG局部查询路 + Agentic RAG断后动作 + metadata自动不 LLM断，小型化取舍为「JSON盘 + 内存 dict查找」代替图数据库，对应企业技能库概念是「数据血缘 / OpenLineage态版」。

## 8. 本轮未涉及的关联事项（诚实记录）

- Session 41-43端改动（apps/web/{app.js,index.html,styles.css,step_workbench.js}）仍为未提交状态，属另一个 Phase收尾，本轮不动。
- `docs/interview/Architecture_Diagram.md` 的既有未提交修改非本轮产生，不在此 commit。
- 本轮 commit围仅限：ARC 对标文档（§11-§14 +字符修复）+ 6 份面试文档结构修复 + test_session33 REQUIRED_FILES 23 项 +本验收报告。
- 本轮不跑真实 uvicorn smoke（无代码变更，无 smoke义务）；如后续落地 P3 任一项，按 CLAUDE.md跑 pytest 全绿 + smoke 后才能 commit。

## 9. 产物清单

- 设计文档：`docs/interview/AutoResearchClaw_对标与小型化移植.md`（§0-§14，688 行）
  - 本轮新增：§11（8技术点三档话术）/ §12（10面试点 delta 表）/ §13+§13.1（摘要+§14指针）/ §14（多论文 RAG + PaperKG，8 子节）
  - 本轮修复：§1-§13 heredoc 字符丢失 20+处
-试文档结构修复：Technical_Highlights / Known_Limitations_For_Interview / Project_DeepDive_Index / Demo_Script_3min / Demo_Script_10min / Project_OnePager
-试：`apps/api/tests/test_session33_interview_docs.py` REQUIRED_FILES 7→23 +维护注释
- 本报告：`Plan/reports/AutoResearchClaw_求职向增强_验收报告.md`
- 关联面试材料：Interview_QA_Cards（30，6类）/ Resume_Bullets / Failure_Cases / Deep_Dive_QA_*.md / RAG_Design_Explainer / Agent_Memory_Explainer / MCP_FunctionCalling_Explainer
