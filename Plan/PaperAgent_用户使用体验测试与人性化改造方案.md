# PaperAgent 用户使用体验测试与人性化改造方案

> 日期：2026-06-21  
> 目的：从“用户真实使用”角度，补一套全流程体验测试需求与对应改造方案。  
> 范围：选题输入、流式分析、候选论文/数据集/工程、论文复现判断、创新点发现、可行性裁决、开题报告草稿、委员会复核、导出前检查。  
> 原则：所有需求先参考高星、近期仍活跃或同领域被广泛使用的仓库/平台，不闭门造车。

---

## 1. 外部参考清单

### 1.1 高优先级参考

| 参考 | 观察结果 | PaperAgent 要抄的位置 |
|---|---|---|
| [stanford-oval/storm](https://github.com/stanford-oval/storm) | GitHub 显示约 28.9k stars；README 明确是带引用的知识整理系统；流程分为 research、outline、article，并强调多视角提问与人机协作 | 抄“多视角问题生成 + outline 前置 + mind map 降低认知负担”；执行 Agent 看 `knowledge_storm/`、`frontend/demo_light/`、README 的 “How STORM & Co-STORM works” |
| [assafelovic/gpt-researcher](https://github.com/assafelovic/gpt-researcher) | 约 27.8k stars；包含 planner / execution / publisher 架构；README 提到 real-time progress tracking、interactive findings、frontend、multi-agent assistant、observability | 抄“研究任务进度可视化 + planner/execution/publisher 分层 + 来源聚合报告”；执行 Agent 看 `frontend/`、`backend/`、`gpt_researcher/`、README Architecture |
| [Future-House/paper-qa](https://github.com/Future-House/paper-qa) | 约 8.7k stars；定位是 scientific documents with citations 的高准确 RAG | 抄“论文问答必须带 citation，不允许无来源回答”；执行 Agent 看 README、citation/RAG 查询输出格式 |
| [langchain-ai/open_deep_research](https://github.com/langchain-ai/open_deep_research) | 约 11.8k stars；README 写明支持多模型、多搜索工具、MCP，并有 Deep Research Bench 评估 | 抄“可配置研究流程 + 搜索工具抽象 + 评估基准”；执行 Agent 看 `configuration.py`、`tests/run_evaluate.py`、README Evaluation |
| [SakanaAI/AI-Scientist](https://github.com/SakanaAI/AI-Scientist) | 约 14k stars；主题是自动开放式科学发现 | 抄“idea -> experiment -> review 的结构”，但不要抄自动宣称创新；执行 Agent 看 README 的 scientific discovery pipeline 和 review/evaluation 思路 |
| [camel-ai/camel](https://github.com/camel-ai/camel) | 多 Agent 框架，README 包含 task automation、tools、memory、retrievers、human-in-the-loop | 抄“Human-in-the-Loop、工具日志、agent role 分工”；执行 Agent 看 docs 的 Human-in-the-Loop、Retrievers、Tools、Memory |
| [OpenHands/OpenHands](https://github.com/OpenHands/OpenHands) | 约 77.8k stars；AI-driven development，有浏览器/命令行/代码执行与 benchmark 思路 | 抄“任务执行过程可见、失败可恢复、动作历史可审计”；执行 Agent 看 docs、runtime/action 相关设计，不要抄代码执行权限模型 |

### 1.2 领域平台参考

| 平台 | 观察结果 | PaperAgent 要抄的位置 |
|---|---|---|
| [Papers with Code data](https://github.com/paperswithcode/paperswithcode-data) | 提供 papers、code links、evaluation tables、methods、datasets 数据 dump，README 说明数据每日再生成 | 抄“论文-代码-数据集-评测表”的结构化关系；执行 Agent 看数据字段，优先建 PaperCodeDatasetMetric 四元关系 |
| [Hugging Face Papers](https://huggingface.co/papers) | 每日/每周/月度论文趋势页，列表里含 paper、GitHub、arXiv、upvote 等信号 | 抄“热度与新鲜度信号”，用于候选排序和选题灵感页 |
| [Auto Research](https://github.com/annihi1ation/auto_research) / [ARISE](https://github.com/ziwang11112/ARISE) | 低星但和自动论文/综述生成相关；包含 paper generation、benchmark、rubric/iterative review 思路 | 只作为方法参考，不作为主要产品 UI 参考；执行 Agent 可看 `write_paper/`、benchmark/rubric 结构 |

---

## 2. 总体用户测试目标

用户不是来“看系统表演”的，而是要快速回答：

```text
1. 这个题目拆得对不对？
2. 有没有论文、数据集、工程可以支撑？
3. 哪些论文值得用？
4. 哪些论文不好复现，为什么？
5. 我能做什么工作量？
6. 创新点从哪里来？
7. 为什么这个方向可行或不可行？
8. 开题报告里哪些内容有证据，哪些只是建议？
```

---

## 3. 全局体验指标

### 3.1 响应速度

| 场景 | 体验要求 | 测试方式 |
|---|---|---|
| 点击主按钮 | 100ms 内按钮进入 loading / disabled / progress 状态 | Playwright 断言 class / aria-busy |
| 开始流式分析 | 1.5s 内出现第一条可见进度或 token | Playwright 计时 |
| 切换 Step | 300ms 内切换完成，无整页跳动 | Playwright screenshot diff |
| 打开论文详情 | 500ms 内先出现骨架屏或缓存摘要 | Playwright + mock slow network |
| 保存/淘汰候选 | 200ms 内本地 UI 状态变化，后台异步持久化 | Playwright 断言 optimistic UI |

### 3.2 信息密度

```text
每屏只问用户一个判断；
每张卡只放一个决策；
长文本默认折叠；
证据细节进入抽屉；
风险解释必须用“为什么不行”短句。
```

### 3.3 可恢复

```text
刷新后能恢复当前 Step；
断流后能 replay；
用户改关键词后后续结果标记 stale；
重新运行不覆盖用户已选资料，除非确认。
```

---

## 4. 流程 A：第一页输入与排版测试

参考：

```text
GPT Researcher frontend：输入研究问题 + 实时进度追踪；
Open Deep Research：研究任务配置；
STORM：topic -> research -> outline 前置。
```

执行 Agent 去抄：

```text
assafelovic/gpt-researcher: frontend/ 的 research query 输入和 progress 显示；
langchain-ai/open_deep_research: README configuration UI 思路；
stanford-oval/storm: frontend/demo_light/ 的轻量研究入口。
```

### 4.1 改造需求

第一页只保留：

```text
题目输入框；
目标选择：保毕业 / 稳中求新 / 冲高水平；
学科方向：CV / NLP / 系统 / 数据分析 / 其他；
资料上传入口；
开始分析按钮；
最近一次草稿恢复入口。
```

不要在第一页展示完整报告、候选论文、技术路线。

### 4.2 测试需求

```text
UT-A1：首屏 1366x768 下不出现纵向滚动超过 1.2 屏；
UT-A2：输入“基于YOLO的钢材表面缺陷检测”后按钮立刻可用；
UT-A3：点击开始后 100ms 内按钮变 loading；
UT-A4：1.5s 内进入 Step 1 并显示流式状态；
UT-A5：空题目点击开始时不弹浏览器 alert，页面内显示错误；
UT-A6：过长题目自动换行，不撑破卡片；
UT-A7：移动端 390px 下输入框、按钮、目标选择不重叠。
```

---

## 5. 流程 B：流式题目理解与关键词拆解

参考：

```text
STORM：先多视角提问再写 outline；
GPT Researcher：planner 生成研究问题；
CAMEL：Human-in-the-Loop。
```

执行 Agent 去抄：

```text
stanford-oval/storm: README 中 Perspective-Guided Question Asking；
assafelovic/gpt-researcher: planner / execution / publisher 分层；
camel-ai/camel: Human-in-the-Loop 文档。
```

### 5.1 改造需求

关键词拆解页必须展示：

```text
方法词：YOLO；
任务词：检测 / 分类 / 分割；
对象词：钢材表面缺陷；
场景词：工业质检；
数据词：NEU-DET / GC10 / 自建数据；
指标词：mAP / FPS / Params；
风险词：实时、轻量、小样本、创新性不足。
```

### 5.2 用户动作

```text
确认关键词；
删除关键词；
新增关键词；
修改关键词类型；
要求系统重新拆；
添加约束：必须有公开数据集 / 必须有代码 / 算力有限。
```

### 5.3 测试需求

```text
UT-B1：关键词逐步出现，不是一次性整页刷新；
UT-B2：系统到 keyword_review 后必须暂停；
UT-B3：未确认关键词时检索按钮 disabled；
UT-B4：用户删除“实时”后，后续 query_plan 不再强依赖 real-time；
UT-B5：用户新增“NEU-DET”后，dataset query 包含 NEU-DET；
UT-B6：每次用户修改写入 Trace；
UT-B7：重新拆解后旧候选资源标记 stale。
```

---

## 6. 流程 C：检索计划页

参考：

```text
Open Deep Research：多 search API / MCP / configurable search；
GPT Researcher：多来源检索与 planner/execution 分工；
Papers with Code data：paper-code-dataset-metric 结构。
```

执行 Agent 去抄：

```text
langchain-ai/open_deep_research: search_api / mcp_config 配置；
assafelovic/gpt-researcher: retriever / research questions；
paperswithcode/paperswithcode-data: evaluation tables、methods、datasets 字段。
```

### 6.1 改造需求

检索计划页分三列：

```text
论文 query；
数据集 query；
工程 / repo query。
```

每条 query 显示：

```text
来源关键词；
查询语言；
目标平台；
预期找到什么；
为什么需要它。
```

### 6.2 测试需求

```text
UT-C1：确认关键词后自动生成三类 query；
UT-C2：每类至少 2 条 query，中英文各至少 1 条；
UT-C3：用户能关闭某条 query；
UT-C4：关闭 query 后候选结果不再从该 query 生成；
UT-C5：点击“开始检索”后 100ms 内出现进度；
UT-C6：检索失败时显示“换关键词 / 手动添加链接 / 使用 mock”三个选项；
UT-C7：检索结果为空时不能继续生成报告。
```

---

## 7. 流程 D：候选论文 / 数据集 / 工程页面

参考：

```text
Hugging Face Papers：论文卡含热度、新鲜度、GitHub/arXiv 链接；
Papers with Code：论文、代码、数据集、评测表联动；
GPT Researcher：interactive findings。
```

执行 Agent 去抄：

```text
huggingface.co/papers: Daily/Trending Papers 卡片结构；
paperswithcode/paperswithcode-data: Links between papers and code、Evaluation tables；
assafelovic/gpt-researcher: frontend interactive findings。
```

### 7.1 改造需求

候选资源页必须有筛选：

```text
全部；
论文；
数据集；
工程；
已保存；
已淘汰；
需要复核。
```

每张候选卡显示：

```text
标题；
类型；
年份；
来源；
URL；
匹配关键词；
为什么推荐；
复现初判；
风险标签；
保存 / 淘汰 / 详情。
```

### 7.2 测试需求

```text
UT-D1：至少生成 paper/dataset/repo 三类候选；
UT-D2：点击筛选后只显示对应类型；
UT-D3：保存后卡片进入已保存；
UT-D4：淘汰后默认隐藏，可在已淘汰中查看；
UT-D5：候选卡必须显示“为什么推荐”；
UT-D6：候选卡必须显示“为什么可能不行”；
UT-D7：候选资源不能直接出现在 EvidenceRef 列表。
```

---

## 8. 流程 E：论文详情页与复现判断

参考：

```text
PaperQA：科学文档问答必须带 citation；
Papers with Code：code link、dataset、metric、evaluation table；
OpenHands：任务执行步骤可见、失败可恢复；
AI Scientist：idea -> experiment -> review，但要降级成人工确认。
```

执行 Agent 去抄：

```text
Future-House/paper-qa: citation-grounded QA 输出；
paperswithcode/paperswithcode-data: paper-code-dataset-metric 结构；
OpenHands/OpenHands: action history / task status UI；
SakanaAI/AI-Scientist: idea/experiment/review 阶段拆解。
```

### 8.1 论文详情页布局

```text
左侧：论文基本信息；
中间：复现判断 Tabs；
右侧：证据 / 链接 / Trace 抽屉。
```

Tabs：

```text
摘要；
方法；
数据集；
代码；
指标；
复现难度；
可借鉴点；
为什么不适合；
创新点空间。
```

### 8.2 论文复现判断卡

复现维度：

```text
1. 代码是否公开；
2. README 是否完整；
3. requirements / environment 是否清楚；
4. 是否有训练脚本；
5. 是否有评估脚本；
6. 是否有预训练权重；
7. 数据集是否公开；
8. 指标是否可对齐；
9. 计算资源是否可承受；
10. license 是否允许使用；
11. issue / commit 是否活跃；
12. 结果是否能和本题对应。
```

评分：

```text
0-39：不建议复现；
40-59：高风险，仅可参考思路；
60-79：可尝试复现；
80-100：优先复现。
```

### 8.3 “为什么不行”解释模板

```text
缺代码：只能作为背景或相关工作；
缺数据集：无法验证实验；
缺指标：无法比较；
无 baseline：工作量不成立；
算力过高：本科/硕士阶段风险大；
对象不匹配：只能借方法，不能直接支撑题目；
代码太旧：复现环境风险高；
license 不明：不建议作为核心工程。
```

### 8.4 测试需求

```text
UT-E1：点击论文卡 500ms 内进入详情或显示骨架屏；
UT-E2：详情页 Tabs 不重叠，移动端可横向滚动；
UT-E3：无代码论文复现分不得超过 59；
UT-E4：无公开数据集论文不得标“优先复现”；
UT-E5：有代码、有 README、有 eval script、有数据集时分数上升；
UT-E6：每个扣分项都显示“为什么不行”；
UT-E7：用户能把论文标记为“只做相关工作，不复现”；
UT-E8：复现判断不能生成 Evidence，除非经过 URLVerified + 人工晋升。
```

---

## 9. 流程 F：数据集详情页

参考：

```text
Papers with Code datasets；
Hugging Face Datasets；
Open Deep Research 的 source config。
```

执行 Agent 去抄：

```text
paperswithcode/paperswithcode-data: datasets dump；
huggingface.co/datasets: dataset card 信息结构；
langchain-ai/open_deep_research: source/tool 配置思路。
```

### 9.1 判断维度

```text
是否公开下载；
是否需要申请；
样本量；
标注类型；
类别数量；
任务匹配；
license；
是否有常见 baseline；
是否过小；
是否和题目对象一致。
```

### 9.2 测试需求

```text
UT-F1：数据集卡显示下载状态；
UT-F2：无公开下载时标记 needs_review；
UT-F3：任务不匹配时显示“不适合当前题目”；
UT-F4：数据集过小时不能支撑强结论；
UT-F5：至少一个公开数据集是 GO 的前置条件；
UT-F6：用户可把数据集加入左栏，但不等于 Evidence。
```

---

## 10. 流程 G：工程 / Repo 详情页

参考：

```text
OpenHands：代码任务执行状态；
Papers with Code：论文-代码链接；
GPT Researcher：来源聚合；
GitHub repo 常规信号：stars、forks、issues、last commit、license、README。
```

执行 Agent 去抄：

```text
OpenHands/OpenHands: task status/action history；
paperswithcode/paperswithcode-data: links between papers and code；
GitHub repo page: stars/forks/issues/license/last commit。
```

### 10.1 Repo 复现判断

```text
README；
requirements；
install guide；
train.py；
eval.py；
demo；
pretrained weights；
example data；
license；
last commit；
issues；
stars/forks；
是否匹配论文；
是否匹配当前数据集。
```

### 10.2 测试需求

```text
UT-G1：repo 卡显示 stars/forks/license/last update；
UT-G2：缺 README 时复现分降低；
UT-G3：缺 eval script 时提示“指标不可复核”；
UT-G4：无 license 时提示合规风险；
UT-G5：repo 和论文标题不匹配时不能自动绑定；
UT-G6：用户可标记“可复现 baseline”；
UT-G7：可复现 baseline 至少 1 个才允许 GO。
```

---

## 11. 流程 H：创新点发现

参考：

```text
STORM：多视角问题与 mind map；
AI Scientist：idea -> experiment -> review；
CAMEL：多 Agent role + critic；
Open Deep Research：研究报告评估。
```

执行 Agent 去抄：

```text
stanford-oval/storm: mind map / perspective-guided question asking；
SakanaAI/AI-Scientist: idea generation 和 review；
camel-ai/camel: critic agent / human-in-the-loop；
langchain-ai/open_deep_research: evaluation。
```

### 11.1 创新点来源

创新点必须从这些差异中找：

```text
对象差异：同方法换到新对象；
数据差异：用更贴近应用的数据集；
模型差异：轻量化、注意力、损失函数、检测头；
工程差异：部署、速度、可视化、交互系统；
实验差异：补充 ablation、cross-dataset、baseline 对比；
问题收缩：从大而泛改成小而可验证。
```

禁止：

```text
首创；
完全解决；
显著优于所有方法；
填补国内外空白；
没有证据的 SOTA。
```

### 11.2 测试需求

```text
UT-H1：创新点页面必须显示“来源论文/数据集/工程”；
UT-H2：每个创新点必须绑定至少一个差异维度；
UT-H3：没有 EvidenceRef 时创新点置信度不能 high；
UT-H4：检测到夸大词时显示 warning；
UT-H5：用户可选择保守/平衡/进取创新路线；
UT-H6：创新点能映射到工作量；
UT-H7：创新点不能脱离可复现 baseline。
```

---

## 12. 流程 I：可行性与 PIVOT

参考：

```text
Open Deep Research：评估集和 RACE score 思路；
GPT Researcher：减少 misinformation / shallow results；
CAMEL：human oversight。
```

执行 Agent 去抄：

```text
langchain-ai/open_deep_research: Evaluation / Deep Research Bench；
assafelovic/gpt-researcher: misinformation、bias、source breadth 的风险说明；
camel-ai/camel: Human-in-the-Loop。
```

### 12.1 测试需求

```text
UT-I1：无数据集不得 GO；
UT-I2：无 baseline 不得 GO；
UT-I3：无指标不得 GO；
UT-I4：全部 URL 未验证不得 GO；
UT-I5：PIVOT 必须给三条路线；
UT-I6：每条路线解释降低了什么风险；
UT-I7：STOP 时不能继续生成“通过型”开题报告；
UT-I8：用户确认 PIVOT 后必须回到关键词页。
```

---

## 13. 流程 J：开题报告草稿

参考：

```text
STORM：outline -> full article；
GPT Researcher：publisher 汇总报告；
PaperQA：citations；
ARISE / Auto Research：rubric / benchmark / paper generation 仅作方法参考。
```

执行 Agent 去抄：

```text
stanford-oval/storm: outline generation；
assafelovic/gpt-researcher: publisher/report flow；
Future-House/paper-qa: citation-grounded answer；
annihi1ation/auto_research: write_paper/ 的 plan/generate/benchmark 结构。
```

### 13.1 测试需求

```text
UT-J1：报告先显示大纲，不直接生成长文；
UT-J2：每节都有证据绑定或 missing_evidence；
UT-J3：无证据段落不能 high confidence；
UT-J4：参考文献必须来自已保存/已验证资源；
UT-J5：工作量至少 5 项；
UT-J6：创新点至少 2 项但不得夸大；
UT-J7：用户能点击段落查看来源；
UT-J8：报告生成中断后可恢复。
```

---

## 14. 流程 K：委员会复核与修改闭环

参考：

```text
AI Scientist：review/evaluation；
CAMEL：critic / multi-agent role；
Open Deep Research：LLM-as-judge evaluation；
ARISE：rubric-guided iterative refinement 方法参考。
```

执行 Agent 去抄：

```text
SakanaAI/AI-Scientist: review/evaluation；
camel-ai/camel: Critic Agents；
langchain-ai/open_deep_research: Evaluation；
ziwang11112/ARISE: rubric / iterative review。
```

### 14.1 测试需求

```text
UT-K1：复核必须分导师/方法/实验/写作/风险五类；
UT-K2：fatal issue 未处理不能 pass；
UT-K3：每个问题有 suggested_fix；
UT-K4：accept_fix 生成任务而不是直接静默修改；
UT-K5：revise_topic 必须回到关键词页；
UT-K6：add_evidence 必须回到候选/证据流程；
UT-K7：rerun_review 保留历史轮次；
UT-K8：复核结论必须标明“低门槛模拟，不是真实专家意见”。
```

---

## 15. 全流程人性化回归用例

### Case 1：正常题目

```text
输入：基于 YOLO 的钢材表面缺陷检测
预期：有条件通过
必须看到：YOLO、检测、钢材表面缺陷、数据集、baseline、mAP、可复现 repo、工作量、低风险创新点。
```

### Case 2：缺数据题目

```text
输入：基于多模态大模型的工业安全全场景智能理解
预期：PIVOT / PARK / STOP
必须看到：题目过大、数据不可得、baseline 不清、算力风险、建议收缩。
```

### Case 3：论文很多但代码差

```text
输入：基于 Transformer 的遥感小目标检测
预期：可做但复现风险高
必须看到：论文候选多、repo 风险、数据集匹配、baseline 替代建议。
```

### Case 4：工程强但创新弱

```text
输入：基于 YOLOv8 的安全帽检测系统
预期：可毕业但创新弱
必须看到：工程可做、创新点不足、建议从轻量化/部署/误检场景找小创新。
```

---

## 16. 对应改造 Session 建议

| 改造 | 建议 Session | 重点 |
|---|---|---|
| 首页 UX 与快速响应 | S33 | 首屏、loading、骨架屏、响应指标 |
| 论文详情与复现判断 | S34 | PaperDetail + ReproducibilityScore |
| 数据集 / Repo 详情判断 | S35 | DatasetFit + RepoReproScore |
| 创新点发现 | S36 | GapMatrix + InnovationCandidate |
| 全流程人性化 Playwright | S37 | Case 1-4 全链路 |
| 可用性与错误恢复 | S38 | 断流、空结果、慢请求、刷新恢复 |

---

## 17. 最小新增测试文件

后端：

```text
apps/api/tests/test_session34_paper_reproducibility.py
apps/api/tests/test_session35_dataset_repo_fit.py
apps/api/tests/test_session36_innovation_gap_matrix.py
apps/api/tests/test_session37_user_journey_cases.py
```

前端：

```text
apps/web/e2e/test_user_ux_first_page.py
apps/web/e2e/test_user_paper_detail_reproducibility.py
apps/web/e2e/test_user_dataset_repo_detail.py
apps/web/e2e/test_user_innovation_discovery.py
apps/web/e2e/test_user_full_journey_humanized.py
apps/web/e2e/test_user_error_recovery.py
```

---

## 18. 执行 Agent 注意事项

```text
1. 先抄交互结构，不抄复杂架构；
2. 先做用户能看懂的解释，再做模型更聪明；
3. 每个“不行”都要给为什么和下一步；
4. 每个“创新点”都要绑定证据或差异；
5. 每个“复现可行”都要检查代码、数据、指标；
6. 每个点击都要有即时反馈；
7. 所有长流程都要可暂停、可恢复、可回放；
8. 不允许为了好看牺牲 Evidence 边界。
```

