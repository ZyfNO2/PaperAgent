# PaperAgent / TopicPilot-CN 科研 Skill 内置清单与下载链接汇总

> 目标：为 PaperAgent 内置一组“科研 Skill”，用于增强开题选题、文献检索、证据审查、数据集检索、论文写作、答辩材料生成等能力。  
> 调研范围：Claude Skills Marketplace / SkillsLLM / MCPMarket / AwesomeSkill / GitHub。  
> 使用建议：不要一次性内置所有 Skill，先做“精选 + 本地改写 + 安全审查”。

---

## 0. 结论

建议 PaperAgent 第一批内置 **8 个核心科研 Skill**，其余作为可选插件。

### 第一批必须内置

| 序号 | Skill / 项目 | 用途 | 推荐处理 |
|---:|---|---|---|
| 1 | Academic Research Skills | 全流程科研写作 Skill | 核心参考，拆分吸收 |
| 2 | Agent Research Skills | 论文生命周期 + GitHub 研究主题分析 | 核心参考，拆分吸收 |
| 3 | Deep Research Skills | 分阶段 Deep Research + Human-in-the-loop | 直接参考你的交互式检索流程 |
| 4 | Research Paper Writing Skills | ML/CV/NLP 论文写作规范 | 用于方法、实验、相关工作写作 |
| 5 | Claude Scholar | 证据 → 实验 → 分析 → Claim → Writing | 用于证据链设计 |
| 6 | Scientific Agent Skills | 科研数据库、科学分析、文献 review | 选取 literature-review / analysis 类 |
| 7 | Academic Paper Skills | 论文规划与写作质量检查 | 用于开题报告和论文大纲 |
| 8 | Literature Review Skill | 系统综述、PRISMA/PICO、引用整理 | 用于开题“国内外研究现状” |

### 第二批可选内置

| 序号 | Skill / 项目 | 用途 |
|---:|---|---|
| 9 | AI Research SKILLs | AI 研究自动化、实验、写作 |
| 10 | paper-craft-skills | 论文图解、PPT、文章可视化 |
| 11 | claude-deep-research-skill | 企业级 Deep Research 流程 |
| 12 | claude-skills-journalism | 验证、事实核查、学术写作 |
| 13 | awesome-claude-skills | Skill 索引 |
| 14 | Claude Skills Marketplace | Skill 搜索入口 |
| 15 | SkillsLLM | Skill 市场与下载入口 |

---

# 1. PaperAgent 内置 Skill 目录建议

建议不要直接把第三方 Skill 原封不动丢进项目，而是转成 PaperAgent 自己的 Skill 规范。

```text
PaperAgent/
└── skills/
    ├── research/
    │   ├── literature-review/
    │   ├── evidence-search/
    │   ├── paper-card/
    │   ├── research-gap/
    │   └── citation-check/
    │
    ├── topic/
    │   ├── topic-decompose/
    │   ├── carrier-risk/
    │   ├── topic-pivot/
    │   └── work-package-design/
    │
    ├── dataset/
    │   ├── dataset-discovery/
    │   ├── dataset-validation/
    │   └── dataset-risk-check/
    │
    ├── engineering/
    │   ├── github-baseline-search/
    │   ├── repo-reproducibility-check/
    │   └── experiment-plan/
    │
    ├── writing/
    │   ├── proposal-outline/
    │   ├── related-work/
    │   ├── method-writing/
    │   ├── experiment-analysis/
    │   └── academic-revision/
    │
    └── defense/
        ├── committee-review/
        ├── defense-qa/
        └── defense-slides/
```

每个 Skill 建议包含：

```text
SKILL.md
schema.json
examples/
prompts/
tests/
README.md
```

---

# 2. 下载链接总表

## 2.1 核心推荐 Skill

| 名称 | 来源 | 下载/仓库链接 | 适配优先级 | 适合内置模块 |
|---|---|---|---:|---|
| Academic Research Skills | GitHub / SkillsLLM | https://github.com/imbad0202/academic-research-skills | P0 | literature-review、citation、writing、defense |
| Academic Research Skills 市场页 | SkillsLLM | https://skillsllm.com/skill/academic-research-skills | P0 | 查看介绍、下载 ZIP |
| Agent Research Skills | GitHub | https://github.com/lingzhi227/agent-research-skills | P0 | research lifecycle、GitHub topic analysis |
| Research Paper Writing Skills | GitHub | https://github.com/Master-cai/Research-Paper-Writing-Skills | P0 | ML/CV/NLP 论文写作 |
| Deep Research Skills | GitHub | https://github.com/Weizhena/Deep-Research-skills | P0 | 分阶段研究、人机交互 |
| Deep Research Skills 市场页 | SkillsLLM | https://skillsllm.com/skill/deep-research-skills | P0 | 查看说明和下载 |
| Claude Scholar | GitHub | https://github.com/Galaxy-Dawn/claude-scholar | P0 | question-evidence-experiment-analysis-claim-writing |
| Claude Scholar 市场页 | SkillsLLM | https://skillsllm.com/skill/claude-scholar | P1 | 查看说明和下载 |
| Claude Scholar 另一个实现 | GitHub | https://github.com/yy/claude-scholar | P2 | citation、LaTeX、math verification |
| Scientific Agent Skills | GitHub | https://github.com/K-Dense-AI/scientific-agent-skills | P1 | literature review、scientific tools |
| Scientific Agent Skills 镜像页 | SourceForge | https://sourceforge.net/projects/claude-science-skills.mirror/ | P2 | 备用下载 |
| Literature Review Skill | MCPMarket | https://mcpmarket.com/tools/skills/academic-literature-review | P1 | systematic review、PRISMA、citation |
| Literature Review Skill | AwesomeSkill | https://awesomeskill.ai/skill/claude-scientific-skills-literature-review | P1 | 下载单个 literature-review skill |
| Academic Paper Skills | GitHub | https://github.com/lishix520/academic-paper-skills | P1 | 论文 planning / composer |
| Academic Paper Skills 市场页 | SkillsLLM | https://skillsllm.com/skill/academic-paper-skills | P1 | 查看说明和 ZIP 下载 |
| AI Research SKILLs | GitHub | https://github.com/Orchestra-Research/AI-Research-SKILLs | P1 | AI research orchestration、engineering skills |
| Paper Craft Skills | GitHub | https://github.com/zsyggg/paper-craft-skills | P2 | 方法图、PPT、深度解读文章 |
| Claude Deep Research Skill | GitHub | https://github.com/199-biotechnologies/claude-deep-research-skill | P2 | source scoring、validation |
| Claude Skills Journalism | SkillsLLM | https://skillsllm.com/skill/claude-skills-journalism | P2 | verification、fact-check、academic writing |

---

## 2.2 Skill 市场与索引

| 名称 | 链接 | 用途 |
|---|---|---|
| Claude Skills Marketplace | https://claudeskills.info/ | 搜索 Claude Skills |
| SkillsLLM | https://skillsllm.com/ | 搜索 Claude Code / Codex / ChatGPT Skills |
| MCPMarket Skills | https://mcpmarket.com/tools/skills | 搜 MCP / Skills |
| Agent Skills Library | https://mcpservers.org/agent-skills | Agent Skill 索引 |
| AwesomeSkill | https://awesomeskill.ai/ | Skill 搜索与单 Skill 下载 |
| Awesome Claude Skills | https://github.com/travisvn/awesome-claude-skills | GitHub 精选索引 |
| BehiSecc Awesome Claude Skills | https://github.com/BehiSecc/awesome-claude-skills | 含 scientific / research 分类 |
| Composio Awesome Claude Skills | https://github.com/ComposioHQ/awesome-claude-skills | Claude.ai skill 使用说明与集合 |
| Claude Code Skills & Plugins | https://github.com/alirezarezvani/claude-skills | 大型跨领域 Skill 集合 |
| Claude 官方 Skills 文档 | https://code.claude.com/docs/en/skills | Claude Code Skills 机制说明 |

---

# 3. 按 PaperAgent 功能拆分的 Skill 选择

## 3.1 开题选题与“航母风险”模块

### 推荐参考

1. **Deep Research Skills**
   - 链接：https://github.com/Weizhena/Deep-Research-skills
   - 作用：分阶段研究，先生成 outline，再深入调查。
   - 适配点：PaperAgent 的 Human Gate 可借鉴其分阶段控制。

2. **Claude Scholar**
   - 链接：https://github.com/Galaxy-Dawn/claude-scholar
   - 作用：question → evidence → experiment → analysis → claim → writing。
   - 适配点：非常适合 PaperAgent 的 Evidence Ledger。

3. **Agent Research Skills**
   - 链接：https://github.com/lingzhi227/agent-research-skills
   - 作用：论文全生命周期 + GitHub 仓库分析。
   - 适配点：可拆出 topic-analysis、repo-analysis、proposal-planning Skill。

### 建议内置 Skill

```text
topic-decompose
carrier-risk-evaluator
topic-pivot-planner
work-package-designer
opening-committee-review
```

---

## 3.2 文献检索与综述模块

### 推荐参考

1. **Academic Research Skills**
   - 链接：https://github.com/imbad0202/academic-research-skills
   - 作用：从 research 到 publication 的完整技能。
   - 适配点：PaperAgent 可吸收其 literature-review、citation、writing skill。

2. **Literature Review Skill**
   - MCPMarket：https://mcpmarket.com/tools/skills/academic-literature-review
   - AwesomeSkill：https://awesomeskill.ai/skill/claude-scientific-skills-literature-review
   - 作用：systematic literature review，PRISMA / PICO / citation。
   - 适配点：开题报告“国内外研究现状”。

3. **Scientific Agent Skills**
   - 链接：https://github.com/K-Dense-AI/scientific-agent-skills
   - 作用：科研数据库、科学分析、领域工具。
   - 适配点：选择其中 literature-review / database-search 类 Skill，不要全量安装。

### 建议内置 Skill

```text
literature-review
paper-card
research-gap-finder
citation-check
evidence-synthesis
```

---

## 3.3 论文写作模块

### 推荐参考

1. **Research Paper Writing Skills**
   - 链接：https://github.com/Master-cai/Research-Paper-Writing-Skills
   - 作用：ML/CV/NLP paper writing skill package。
   - 适配点：适合你项目的 AI / CV / Agent 方向写作。

2. **Academic Paper Skills**
   - 链接：https://github.com/lishix520/academic-paper-skills
   - 作用：strategist + composer，论文规划和撰写质量关卡。
   - 适配点：开题报告、相关工作、方法章节结构化生成。

3. **Academic Research Skills**
   - 链接：https://github.com/imbad0202/academic-research-skills
   - 作用：支持多种论文结构和引用格式。
   - 适配点：中文学术写作和引用检查。

### 建议内置 Skill

```text
proposal-outline
related-work-writer
method-section-writer
experiment-analysis-writer
academic-revision
```

---

## 3.4 数据集与工程检索模块

### 推荐参考

1. **Agent Research Skills**
   - 链接：https://github.com/lingzhi227/agent-research-skills
   - 作用：含 GitHub repository analysis。
   - 适配点：数据集、Baseline、GitHub 仓库检索和复现风险评估。

2. **Claude Scholar**
   - 链接：https://github.com/Galaxy-Dawn/claude-scholar
   - 作用：连接 evidence、experiment、analysis。
   - 适配点：把数据集和实验设计纳入证据链。

3. **Scientific Agent Skills**
   - 链接：https://github.com/K-Dense-AI/scientific-agent-skills
   - 作用：有大量科学数据库相关能力。
   - 适配点：可参考其 database-oriented skill 组织方式。

### 建议内置 Skill

```text
dataset-discovery
dataset-validation
github-baseline-search
repo-reproducibility-check
experiment-plan
```

---

## 3.5 答辩与展示模块

### 推荐参考

1. **paper-craft-skills**
   - 链接：https://github.com/zsyggg/paper-craft-skills
   - 作用：将论文生成方法图、幻灯片、深度文章。
   - 适配点：开题 PPT、答辩 PPT、方法图。

2. **Academic Research Skills**
   - 链接：https://github.com/imbad0202/academic-research-skills
   - 作用：包含 defense / slide / writing 类能力。
   - 适配点：开题答辩材料生成。

### 建议内置 Skill

```text
defense-slides
committee-question-generator
defense-qa
method-figure-planner
```

---

# 4. 推荐内置 Skill 规范

为了避免第三方 Skill 风格不统一，PaperAgent 建议采用统一格式。

## 4.1 SKILL.md 模板

```markdown
---
name: literature-review
description: 用于围绕研究题目检索、筛选、组织文献，并输出开题报告中的国内外研究现状。
category: research
version: 0.1.0
source: adapted
risk_level: low
requires_tools:
  - openalex_search
  - semantic_scholar_search
  - local_paper_retrieval
---

# Literature Review Skill

## 触发条件

当用户需要：
- 查找相关论文
- 梳理研究现状
- 对比不同方法
- 支撑开题背景

## 输入

- TopicSpec
- SearchQueryPlan
- EvidenceLedger

## 输出

- LiteratureMap
- PaperCluster
- RelatedWorkDraft
- EvidenceList

## 操作步骤

1. 读取题目结构。
2. 生成中英文检索词。
3. 调用论文检索工具。
4. 去重并分类。
5. 标记综述、Baseline、应用论文和数据集论文。
6. 输出研究脉络。
7. 所有结论必须绑定 Evidence ID。

## 禁止事项

- 不得生成不存在的引用。
- 不得声称“国内外没有研究”，除非已有系统检索记录。
- 不得把无关论文作为核心证据。
```

---

## 4.2 schema.json 示例

```json
{
  "name": "literature-review",
  "input_schema": {
    "topic_spec": "TopicSpec",
    "query_plan": "SearchQueryPlan",
    "evidence_ledger": "EvidenceLedger"
  },
  "output_schema": {
    "literature_map": "LiteratureMap",
    "related_work_draft": "string",
    "evidence_ids": "list[string]"
  }
}
```

---

# 5. PaperAgent 第一批 Skill 清单

## 5.1 Research 类

| Skill | 说明 | 参考项目 |
|---|---|---|
| topic-decompose | 拆解题目中的对象、任务、方法、数据和评价 | Claude Scholar / Deep Research |
| query-expansion | 中英文关键词扩展 | Academic Research Skills |
| literature-review | 文献调研与国内外研究现状 | Literature Review Skill |
| paper-card | 单篇论文结构化卡片 | PaperQA2 思路 + Academic Research |
| research-gap | 从 limitation / future work 抽取 gap | Research Skills |

---

## 5.2 Evidence 类

| Skill | 说明 | 参考项目 |
|---|---|---|
| evidence-ledger | 管理论文、数据集、代码和指标证据 | Claude Scholar |
| citation-check | 检查引用是否支撑论断 | Claude Scholar / PaperQA2 |
| evidence-synthesis | 多篇论文证据合成 | Academic Research Skills |
| claim-grounding | 每个结论绑定 Evidence ID | Claude Scholar |

---

## 5.3 Topic 类

| Skill | 说明 | 参考项目 |
|---|---|---|
| carrier-risk | 判断题目是否“造航母” | 自研 |
| topic-pivot | 生成保守、平衡、激进路线 | Deep Research |
| work-package | 生成 2～3 个工作包 | ResearchAgent / Academic Paper Skills |
| committee-review | 模拟开题委员会追问 | Academic Paper Skills |

---

## 5.4 Dataset / Engineering 类

| Skill | 说明 | 参考项目 |
|---|---|---|
| dataset-discovery | 检索公开数据集 | Agent Research Skills |
| dataset-validation | 验证数据集下载、许可、标注 | Scientific Agent Skills |
| github-baseline | 检索 GitHub baseline | Agent Research Skills |
| repo-reproducibility | 评估仓库可复现性 | Agent Research Skills |

---

## 5.5 Writing / Defense 类

| Skill | 说明 | 参考项目 |
|---|---|---|
| proposal-outline | 生成开题报告骨架 | Academic Paper Skills |
| related-work | 生成相关工作草稿 | Research Paper Writing Skills |
| method-writing | 方法章节写作 | Research Paper Writing Skills |
| experiment-plan | 实验矩阵与消融设计 | Claude Scholar |
| defense-slides | 开题/答辩 PPT 大纲 | paper-craft-skills |

---

# 6. 安装和集成建议

## 6.1 Claude Code 直接安装方式

第三方 Skill 通常可直接放入：

```text
~/.claude/skills/
```

或项目目录：

```text
.claude/skills/
```

典型安装：

```bash
git clone https://github.com/Weizhena/Deep-Research-skills
mkdir -p ~/.claude/skills/
cp -r Deep-Research-skills/deep-research ~/.claude/skills/
```

具体路径需以各仓库 README 为准。

---

## 6.2 PaperAgent 推荐集成方式

不要依赖 Claude Code 才能运行。建议将 Skill 抽象为项目内部能力：

```text
third_party_skills/
    原始下载，不直接执行

skills/
    PaperAgent 改写后的可控 Skill

packages/agents/nodes/
    LangGraph 节点调用 Skill

packages/agents/tools/
    Skill 可用工具
```

流程：

```text
下载第三方 Skill
→ 阅读 SKILL.md
→ 提取可复用流程
→ 改写为 PaperAgent Skill
→ 写 schema.json
→ 写测试
→ 加入 SkillRegistry
```

---

# 7. 安全与合规审查

第三方 Skill 不能直接信任。每个 Skill 入库前必须检查：

```text
是否包含 shell 命令
是否会读写敏感文件
是否会上传数据
是否调用外部 API
是否要求密钥
是否修改 git 仓库
是否执行 pip/npm 安装
是否有未知二进制
是否含 prompt injection 风险
是否许可证允许改写
```

建议状态：

```text
candidate
reviewed
adapted
enabled
disabled
deprecated
```

每个 Skill 入库记录：

```yaml
name: deep-research
source_url: https://github.com/Weizhena/Deep-Research-skills
license: unknown
reviewed_at: 2026-06-17
reviewer: zyf
status: adapted
security_notes:
  - no direct shell execution retained
  - external API calls replaced by PaperAgent retrieval tools
```

---

# 8. 适配优先级

## P0：必须先做

```text
literature-review
paper-card
evidence-ledger
dataset-discovery
github-baseline
carrier-risk
topic-pivot
work-package
```

## P1：第二批

```text
citation-check
research-gap
experiment-plan
proposal-outline
related-work
committee-review
```

## P2：可选增强

```text
defense-slides
method-figure-planner
repo-reproducibility
academic-revision
claim-grounding
```

---

# 9. 推荐下载顺序

按优先级下载和阅读：

1. https://github.com/imbad0202/academic-research-skills
2. https://github.com/lingzhi227/agent-research-skills
3. https://github.com/Weizhena/Deep-Research-skills
4. https://github.com/Galaxy-Dawn/claude-scholar
5. https://github.com/Master-cai/Research-Paper-Writing-Skills
6. https://github.com/K-Dense-AI/scientific-agent-skills
7. https://github.com/lishix520/academic-paper-skills
8. https://github.com/zsyggg/paper-craft-skills
9. https://github.com/Orchestra-Research/AI-Research-SKILLs
10. https://github.com/199-biotechnologies/claude-deep-research-skill

---

# 10. 建议写进 PaperAgent README 的说明

```markdown
## Built-in Research Skills

PaperAgent 内置了一组面向开题选题场景的科研 Skill。不同于通用论文写作助手，这些 Skill 不直接生成“看起来合理”的结论，而是围绕 Evidence Ledger 工作：

1. 题目拆解 Skill：将题目拆成对象、任务、方法、数据和评价。
2. 文献调研 Skill：检索并筛选相关论文。
3. 数据集发现 Skill：验证公开数据集是否真实可用。
4. GitHub Baseline Skill：评估工程仓库是否可复现。
5. 航母风险 Skill：判断题目是否超过当前毕业资源。
6. 退化路线 Skill：生成保守、平衡、激进三条可行路径。
7. 工作包 Skill：将题目拆成 2～3 个可验证工作包。
8. 开题委员会 Skill：模拟导师和评审专家追问。

所有 Skill 输出都必须绑定 Evidence ID，避免虚假引用和无依据判断。
```

---

# 11. 后续可扩展方向

## 11.1 Skill Marketplace 同步器

后期可增加：

```text
输入 marketplace URL
→ 自动抓取 Skill 信息
→ 下载到 candidate_skills/
→ 生成安全审查报告
→ 用户确认是否启用
```

## 11.2 Skill 评分

```text
SkillScore =
    0.25 × relevance_to_topicpilot
  + 0.20 × clarity_of_instructions
  + 0.20 × safety
  + 0.15 × maintainability
  + 0.10 × license_clarity
  + 0.10 × testability
```

## 11.3 Skill Evaluation

每个 Skill 都需要评估任务：

```text
literature-review：能否找到核心论文
dataset-discovery：能否找到真实数据集
github-baseline：能否找到可运行仓库
carrier-risk：能否正确拦截高风险题目
work-package：能否生成可独立验证的工作包
```

---

# 12. 总结

PaperAgent 不应该简单“安装很多 Skills”。更合适的路线是：

```text
从 Claude market / GitHub 收集科研 Skill
→ 筛出适合开题场景的流程
→ 改写成 PaperAgent 内置 Skill
→ 用 Evidence Ledger 约束输出
→ 通过测试验证每个 Skill 的有效性
```

最终目标：

> 让 PaperAgent 从“一个会生成开题建议的 Agent”，变成“一个带科研 Skill 库、证据审查和交互式选题流程的开题工作台”。
