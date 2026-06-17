# TopicPilot-CN 项目设计稿

> 本文档从原方案中提取设计相关内容（第1～16节），不修改原文。

***

# TopicPilot-CN：面向中国研究生开题的选题可行性与工作量规划 Agent

> 调研与方案版本：2026-06-15\
> 项目定位：计算机、人工智能及工科方向硕士研究生开题辅助\
> 核心任务：判断题目是否“在造航母”、给出有文献依据的降级/泛化路线，并规划可支撑毕业论文的 2～3 个独立工作包

***

## 1. 项目概述

### 1.1 项目名称



TopicPilot-CN：开题选题助手



内部也可以使用一个更容易传播的功能名：

>   “航母检测器”——研究生选题范围与可行性审查 Agent  

### 1.2 一句话描述

> 系统根据拟定题目、研究约束和检索到的论文、数据集、开源代码及评价基准，判断选题是否过大、过新、过窄或资源不足；若风险过高，则沿“研究对象—任务—模态—方法—数据—评价”维度生成有文献支撑的降级路线，并进一步规划 2～3 个可验证、可消融、可写成论文章节的工作包。

### 1.3 目标用户

- 需要准备开题报告的硕士研究生
- 需要初步筛选学生选题的导师
- 计算机、人工智能、自动化、土木信息化等工科方向学生
- 有实际工程对象，但缺少公开数据和成熟算法链路的学生
- 有一个宽泛想法，但不知道如何拆成论文工作量的学生

### 1.4 项目边界

系统负责：

- 检索真实论文、数据集、代码和评价基准
- 评估题目范围、成熟度和资源适配性
- 给出选题收缩、抽象、迁移和降级建议
- 生成 2～3 个研究工作包
- 形成开题报告所需的研究问题、技术路线和实验矩阵
- 标明每项建议的证据来源和风险

系统不负责：

- 伪造创新点
- 编造不存在的论文、数据集或实验结果
- 仅靠替换模块名称宣称原创
- 保证选题一定通过开题或盲审
- 未经核验地生成“国内外尚无研究”等绝对化结论

***

# 2. 核心问题：什么叫“在造航母”

## 2.1 直观定义

研究生口语中的“造航母”，通常不是指题目本身没有价值，而是指：

> 在有限时间、算力、数据、代码能力和导师资源下，选题需要同时解决过多前置问题，无法在毕业周期内形成可验证、可复现、可答辩的成果。

典型表现包括：

- 研究对象极其特殊，几乎没有公开数据
- 任务定义不清，没有公认指标
- 没有成熟 Baseline，需要从零构建完整算法
- 同时要求采集数据、标注数据、设计模型、部署系统和工程验证
- 依赖昂贵硬件、特殊传感器或难以获得的现场
- 研究范围同时跨越多个学科
- 题目中包含多个高风险创新假设
- 任一前置环节失败，后续全部无法进行
- 最终成果难以拆成 2～3 个可独立验证的工作包

***

## 2.2 不能只用“论文数量”判断

最初思路是：

```text
相关论文很多
→ 说明已有成熟研究基础
→ 不属于造航母

相关论文很少
→ 说明相关研究不足
→ 可能是在造航母
```

这个思路可以作为第一层启发式规则，但不能直接作为最终结论。

论文数量少可能有多种原因：

1. 检索词过于具体
2. 中文术语和英文术语没有对齐
3. 研究对象名称不同，但底层任务相同
4. 该领域较新，但已有数据集和开源代码
5. 论文集中在相邻领域
6. 数据集以工程名称而非学术名称发布
7. 论文不多，但问题简单、资源充分
8. 论文很多，但研究对象的数据根本无法获得
9. 论文很多，但全部依赖大型算力或机构级资源

因此，系统需要从“论文数量判断”升级为：

>   文献成熟度 + 数据成熟度 + 基线成熟度 + 评价成熟度 + 资源适配度 + 工作包可拆分性  的综合判断。

***

# 3. 相关 GitHub 项目调研

## 3.1 项目总览

| 项目                                                                                            | 项目类型              | 与本项目的关系                             | 推荐借鉴模块              |
| --------------------------------------------------------------------------------------------- | ----------------- | ----------------------------------- | ------------------- |
| [ResearchAgent](https://github.com/JinheonBaek/ResearchAgent)                                 | 文献驱动研究问题生成        | 从核心论文出发检索相关论文，生成并迭代研究问题             | 问题生成、五维评审、迭代改进      |
| [IRIS](https://github.com/Anikethh/IRIS-Interactive-Research-Ideation-System)                 | 交互式科研构思系统         | 基于 Semantic Scholar 和 LLM 进行交互式假设生成 | 人机交互式选题、假设迭代        |
| [Idea2Proposal](https://github.com/NuoJohnChen/Idea2Proposal)                                 | 多 Agent 开题/研究方案生成 | 多角色学术讨论后生成带真实引用的研究方案                | 多导师讨论、开题方案结构化生成     |
| [research-companion](https://github.com/andrehuang/research-companion)                        | 研究选题战略评估          | 对想法做新颖性、影响、时机、可行性等压力测试              | Idea Critic、否决与暂停机制 |
| [idea-evaluation-pipeline](https://github.com/alejandroll10/idea-evaluation-pipeline)         | 研究想法评估与转向         | 低分想法进入 Pivot，直到达到阈值或被否决             | 评估—复核—转向—终审状态机      |
| [DatasetResearch](https://github.com/GAIR-NLP/DatasetResearch)                                | 数据集发现 Agent 基准    | 衡量 Agent 是否能根据需求发现合适数据集             | 数据集搜索与可用性评价         |
| [ResearchMCP](https://github.com/DaniManas/ResearchMCP)                                       | OpenAlex 科研 MCP   | 搜论文、提取论点、比较论文、寻找研究空白                | 文献检索工具接口、Gap Finder |
| [RAG Research Paper Gap Finder](https://github.com/bistadinank/RAG_Research_Paper_Gap_Finder) | 本地论文研究空白发现        | 从 limitation、future work 等位置提取研究空白  | 论文局限与未来工作结构化提取      |
| [ARIS](https://github.com/wanshuiyin/auto-claude-code-research-in-sleep)                      | 自动科研 Skill 工作流    | 文献调研、创新性检查、想法筛选、实验规划                | 多源检索、跨模型审查、人类门禁     |
| [AutoResearchClaw](https://github.com/aiming-lab/AutoResearchClaw)                            | 端到端自动科研           | 包含检索、Gap、假设、实验设计和引用校验               | 多阶段管线、文献真实性校验       |
| [ResearchRubrics](https://github.com/scaleapi/researchrubrics)                                | 研究报告 Rubric 评估    | 使用结构化 Rubric 对研究报告评分                | 开题评分规则与加权评估         |
| [academic-ai-prompt](https://github.com/bohyy/academic-ai-prompt)                             | 中文学术 Prompt 库     | 包含中文论文选题生成、评估和论证方法                  | 中文交互、选题五维评价         |
| [thesis\_work\_flow](https://github.com/bikeread/thesis_work_flow)                            | Dify 论文工作流        | 覆盖构思、开题、大纲和论文写作                     | Dify 工作流、中文开题输出     |
| [Professor\_skill](https://github.com/Azurboy/Professor_skill)                                | 导师/答辩委员会模拟        | 支持开题、中期、答辩三种委员会审查                   | 多导师质询、开题批准意见        |
| [nsfc-agent-skills](https://github.com/njzjz/nsfc-agent-skills)                               | 中文项目申请 Skills     | 选题、研究内容、技术路线、创新性与文献检索               | 立项依据和技术路线表达         |

***

## 3.2 ResearchAgent

ResearchAgent 是与本项目“文献驱动选题”最接近的研究型项目之一。

其主要流程是：

```text
输入核心论文
→ Semantic Scholar 检索参考文献和相关实体
→ 生成候选研究问题
→ 多个 Reviewer 从多个维度评分
→ 针对低分维度迭代修改
→ 生成方法与实验设计
```

可直接借鉴：

- 以真实论文作为选题起点
- 研究问题不是一次性生成，而是多轮迭代
- 问题生成与问题评审分离
- 使用不同 Reviewer 并行打分
- 保留每轮修改历史
- 研究问题、方法和实验需要连续对应

不宜直接照搬：

- ResearchAgent 更关注“生成新想法”
- 本项目优先关注“研究生能否完成”
- 本项目还需要数据、代码、算力、毕业周期等工程约束

***

## 3.3 IRIS

IRIS 是 ACL 2025 System Demonstration 项目，强调交互式研究构思。

可借鉴：

- 学生与 Agent 共同推进，而不是系统一次性给出答案
- 使用 Semantic Scholar 查找相关文献
- 对想法进行多轮修改
- 用户可以保留、删除或合并候选方向
- 将研究构思做成可视化交互界面

适合映射到：

```text
学生提出初始题目
→ 系统拆解题目
→ 学生确认研究对象和核心任务
→ 系统展示证据地图
→ 学生选择收缩或泛化路线
→ 系统生成工作包
```

***

## 3.4 Idea2Proposal

Idea2Proposal 通过多个具有不同学术角色的 Agent 讨论研究想法，并生成结构化、可引用的研究方案。

其可借鉴点包括：

- 多 Agent 学术讨论
- 横向讨论、纵向指导、跨学科讨论和领导者主导模式
- Semantic Scholar 真实论文集成
- YAML 配置不同讨论角色
- 从讨论记录生成研究方案

在 TopicPilot-CN 中可对应：

| Idea2Proposal 角色 | TopicPilot-CN 角色   |
| ---------------- | ------------------ |
| 领域专家             | Domain Expert      |
| 资深研究者            | Supervisor Agent   |
| 方法专家             | Method Agent       |
| 批判者              | Feasibility Critic |
| 方案整合者            | Proposal Planner   |

***

## 3.5 research-companion

该项目不是帮用户写论文，而是帮助用户决定：

> 哪些研究值得做，哪些应该暂停，哪些应该尽早放弃。

其 Idea Critic 使用的评价维度包括：

- Novelty
- Impact
- Timing
- Feasibility
- Competitive Landscape
- Core Nugget
- Narrative Potential

对本项目最有价值的是：

- 不强迫所有题目进入“继续做”
- 支持 `GO / PIVOT / PARK / KILL`
- 先验证最可能让项目失败的假设
- 保存过去被否决的想法
- 设置“重新考虑条件”

TopicPilot-CN 可以采用以下裁决：

```text
GO
题目范围和资源基本合理，可以进入工作量设计

NARROW
方向可行，但范围过大，需要缩小对象、任务或模态

PIVOT
原方向资源不足，需要转向有数据、有基线的相邻问题

PARK
当前条件不具备，但未来获得数据或设备后可以重启

STOP
核心任务无法验证，或不适合作为当前学位论文
```

***

## 3.6 idea-evaluation-pipeline

该项目提供一个“评估—复核—转向—终审”的循环。

可借鉴状态机：

```text
EVALUATE
   ↓
REVIEW_EVALUATION
   ↓
分数不足？
   ├── 是 → PIVOT_IDEA → 重新评估
   └── 否 → LITERATURE_REVIEW
                     ↓
               VERIFY_REVIEW
                     ↓
                FINAL_VERDICT
```

TopicPilot-CN 可增加：

```text
题目可行性评分 < 60
→ 必须进入收缩或转向

60 ≤ 评分 < 75
→ 有条件通过，必须完成最小可行实验

评分 ≥ 75
→ 可进入工作包设计

任一硬性条件失败
→ 不得直接通过
```

***

## 3.7 DatasetResearch

DatasetResearch 专门研究 Agent 能否根据真实需求找到合适的数据集。

它的重要启示是：

> “找到数据集”本身是一个困难任务，不能让 LLM 仅凭记忆生成数据集名称。

TopicPilot-CN 的 Dataset Scout 应检查：

- 数据集是否真实存在
- 下载地址是否有效
- 许可是否允许学术使用
- 数据规模是否足够
- 标注类型是否与任务匹配
- 训练集、验证集、测试集是否明确
- 是否有论文使用该数据集
- 是否有成熟 Baseline
- 是否需要额外清洗或转换
- 是否存在类别不平衡
- 是否需要申请权限
- 是否依赖医院、企业或实验室内部数据

***

## 3.8 ResearchMCP 与 RAG Gap Finder

ResearchMCP 提供：

- OpenAlex 论文搜索
- 论点提取
- 论文比较
- 引用网络分析
- Research Gap 检测

RAG Gap Finder 则重点从以下章节抽取研究空白：

- Limitations
- Future Work
- Discussion
- Conclusion

可借鉴为：

```text
候选研究空白
=
多篇论文重复出现的局限
+
已有论文明确提出的未来工作
+
不同论文结果之间的矛盾
+
已有方法在新场景下缺少验证
```

需要注意：

> 论文写了 Future Work，并不等于该工作一定适合硕士生，也不等于该问题尚未被后续论文解决。

所以所有 Gap 都必须再次进行时间范围检索和可行性检查。

***

## 3.9 中文项目的作用

### academic-ai-prompt

适合借鉴：

- 中文选题访谈
- 选题生成、评估和论证
- 研究现状到研究问题的转换
- 中文表格化输出

### thesis\_work\_flow

适合借鉴：

- Dify 工作流实现
- 开题报告模板
- 分阶段生成
- 中文论文大纲

### Professor\_skill

适合借鉴：

- 模拟开题委员会
- “是否值得做、方案是否可行”的质询
- 输出批准、有条件批准或不批准
- 模拟不同导师风格

### nsfc-agent-skills

虽然面向 NSFC，但其以下模块可迁移到开题：

- 立项依据
- 研究目标
- 研究内容
- 技术路线
- 创新性分析
- 文献检索
- 图表生成

***

# 4. 相关数据源与工具接口

## 4.1 文献检索

### OpenAlex

适合：

- 关键词检索
- 论文数量统计
- 年份趋势分析
- 主题、作者、机构和期刊分析
- 引用关系
- 学位论文和数据集类型检索

官方文档：

- [OpenAlex API](https://developers.openalex.org/api-reference/introduction)
- [OpenAlex Works](https://developers.openalex.org/api-reference/works)
- [OpenAlex Search](https://developers.openalex.org/guides/searching)

### Semantic Scholar

适合：

- 论文搜索
- 参考文献和被引文献
- 相似论文推荐
- SPECTER2 Embedding
- 论文影响和引用网络

官方文档：

- [Semantic Scholar Academic Graph API](https://www.semanticscholar.org/product/api)
- [Semantic Scholar API Docs](https://api.semanticscholar.org/api-docs/)

### 中文文献

中文学位开题通常需要中文研究现状。

建议支持：

```text
用户从知网、万方、维普或学校数据库导出：
- RIS
- BibTeX
- EndNote
- NoteExpress
- CSV

系统负责解析和分析
```

不建议：

- 绕过权限批量抓取付费数据库
- 使用不稳定的非官方爬虫作为核心依赖

***

## 4.2 数据集检索

### Hugging Face Hub

适合：

- NLP、CV、语音和多模态数据集搜索
- Dataset Card 解析
- 数据规模、语言、任务和许可提取
- 数据预览

官方文档：

- [Hugging Face Hub](https://huggingface.co/docs/hub/en/index)
- [Search the Hub](https://huggingface.co/docs/huggingface_hub/en/guides/search)
- [Datasets](https://huggingface.co/docs/datasets/en/index)

### 其他数据源

可选接入：

- Kaggle API
- UCI Machine Learning Repository
- OpenML
- Zenodo
- Figshare
- GitHub Release
- 论文附录或项目主页
- 用户上传的自有数据说明

***

## 4.3 开源代码与 Baseline

建议接入：

- GitHub Search API
- Semantic Scholar 论文项目链接
- arXiv HTML / Papers 页面中的代码链接
- Hugging Face Models / Spaces
- 历史 Papers with Code 数据快照

需要注意：

> Papers with Code 的历史数据仍可参考，但不应把它作为唯一且实时维护的数据源。

Baseline 检查内容：

- 仓库是否存在
- 是否有 License
- 是否有 README
- 是否有环境文件
- 是否提供预训练权重
- 是否提供训练脚本
- 是否提供评价脚本
- 是否能定位论文对应 Commit
- 最近是否仍有人维护
- Issue 是否显示大量无法复现问题
- 预计显存和训练时长
- 数据预处理是否完整

***

# 5. 选题拆解模型

系统收到题目后，首先不能直接搜索完整句子，而应拆成结构化组件。

## 5.1 Topic Schema

```python
class TopicSpec:
    title: str
    research_object: str
    scenario: str
    task: str
    modality: list[str]
    method_family: list[str]
    target_problem: list[str]
    data_requirement: list[str]
    expected_output: list[str]
    evaluation_metrics: list[str]
    engineering_constraints: list[str]
```

示例题目：

> 基于多模态深度学习的特殊桥梁混凝土裂缝三维智能检测方法研究

拆解结果：

```yaml
research_object: 特殊桥梁混凝土表面
scenario: 工程现场巡检
task:
  - 裂缝检测
  - 裂缝分割
  - 三维定位
modality:
  - RGB
  - 深度
  - 点云
method_family:
  - 深度学习
  - 多模态融合
target_problem:
  - 小目标
  - 跨域
  - 三维映射
data_requirement:
  - 裂缝图像
  - 深度或双目数据
  - 点云
  - 二维/三维标注
expected_output:
  - 损伤类别
  - 掩膜
  - 三维位置
  - 几何量
```

***

## 5.2 检索词扩展

每个题目生成四级检索词。

### L0：原始精确题目

```text
"特殊桥梁混凝土裂缝三维智能检测"
```

### L1：同义词和中英文对齐

```text
bridge concrete crack
structural damage detection
3D crack mapping
concrete surface defect
multi-view damage inspection
```

### L2：去除特殊场景约束

```text
concrete crack detection
surface defect segmentation
2D-to-3D damage mapping
```

### L3：抽象到底层任务

```text
object detection
semantic segmentation
domain adaptation
multi-modal fusion
point cloud projection
```

通过对 L0～L3 的检索结果进行对比，可以区分：

- 真正没有研究基础
- 只是术语过窄
- 场景特定但任务成熟
- 底层任务成熟但场景数据缺失

***

# 6. “航母风险”判定模型

## 6.1 双轴模型

单纯使用一个“航母分数”会混淆两种不同风险：

1.   资源不成熟风险  
2.   方向过度拥挤风险  

因此采用两个主轴：

### 研究基础成熟度 Maturity

衡量：

- 是否有足够相关论文
- 是否有公开数据集
- 是否有可复现 Baseline
- 是否有明确指标
- 是否有相邻领域迁移案例

### 差异空间 Differentiation

衡量：

- 是否存在未解决问题
- 是否有明确场景差异
- 是否有尚未验证的数据域
- 是否存在性能、效率、鲁棒性或工程化缺口
- 是否可以提出可证伪的研究假设

形成四象限：

| 成熟度 | 差异空间 | 判定                        |
| --- | ---- | ------------------------- |
| 高   | 中高   |   研究生安全区  ：有基础、有空间        |
| 高   | 低    |   红海重复区  ：容易变成简单复现        |
| 低   | 高    |   造航母高风险区  ：问题有价值，但基础设施不足 |
| 低   | 低    |   死区  ：既难做，也缺乏明确贡献        |

***

## 6.2 综合风险维度

### 1. 文献基础风险 `R_lit`

检查：

- 精确主题论文数量
- 相邻主题论文数量
- 最近五年趋势
- 是否存在综述
- 是否存在多个独立团队
- 是否仅有概念论文而无实验论文

### 2. 数据风险 `R_data`

检查：

- 有无公开数据
- 数据是否可下载
- 标注是否匹配任务
- 样本规模
- 使用许可
- 是否必须自采
- 自采成本
- 是否需要伦理审批
- 是否有测试集和评价协议

### 3. Baseline 风险 `R_base`

检查：

- 是否有成熟模型
- 是否有代码
- 是否可复现
- 是否有预训练权重
- 是否支持目标数据类型
- 是否有可用评价脚本

### 4. 评价风险 `R_eval`

检查：

- 是否有公认指标
- 是否有对照组
- 是否可以构建消融实验
- 是否能获得 Ground Truth
- 是否只能依靠主观可视化

### 5. 资源风险 `R_resource`

检查：

- GPU 显存
- 训练时间
- 采集设备
- 标注人力
- 软件栈
- 学生已有技能
- 导师/课题组支持

### 6. 范围风险 `R_scope`

检查：

- 任务数量
- 模态数量
- 数据来源数量
- 新模块数量
- 是否同时涉及算法、硬件、系统和理论
- 关键依赖链长度

### 7. 工作包风险 `R_wp`

检查：

- 能否拆成 2～3 个独立工作包
- 每个工作包是否有单独实验
- 工作包之间是否只是重复换模块
- 前一个失败后，后一个是否还能继续
- 是否能映射到论文第三、第四、第五章

***

## 6.3 航母风险分数

建议初始版本采用可解释加权评分：

```text
CarrierRisk =
    0.15 × R_lit
  + 0.20 × R_data
  + 0.15 × R_base
  + 0.10 × R_eval
  + 0.15 × R_resource
  + 0.15 × R_scope
  + 0.10 × R_wp
```

各项风险取值范围：

```text
0   = 风险极低
25  = 风险较低
50  = 中等风险
75  = 高风险
100 = 当前条件下基本不可行
```

建议判定：

|     分数 | 判定      | 系统动作          |
| -----: | ------- | ------------- |
|   0～29 | 风险较低    | 进入工作量规划       |
|  30～49 | 可控风险    | 给出风险清单和最小验证实验 |
|  50～69 | 高风险     | 必须收缩或泛化       |
|  70～84 | 造航母倾向明显 | 进入强制 Pivot    |
| 85～100 | 当前不可行   | STOP 或更换方向    |

***

## 6.4 硬性否决条件

即使综合分数不高，出现以下情况也不能直接判定通过：

```text
无可获得数据
且毕业周期内无法完成自采与标注

无可执行评价方法
且无法获得任何 Ground Truth

必须依赖无法获得的设备或企业数据

核心 Baseline 无代码
且学生不具备从零复现条件

两个以上核心前置假设均未验证

题目要求同时提出新数据、新模型、新硬件和新系统

工作包完全串行
任何一步失败都会导致整篇论文失效
```

***

# 7. 退化与泛化功能

## 7.1 功能定义

当题目风险过高时，系统不应只说“不要做”，而应生成：

> 从原始高风险题目逐级退化到有论文、有数据、有代码、有评价基准的可行研究区域。

这里的“退化”不是降低学术诚信要求，而是：

- 缩小研究对象
- 简化输入模态
- 降低目标难度
- 复用成熟 Baseline
- 优先使用公开数据
- 将理论突破改成工程验证
- 将端到端创新改成局部可验证改进

***

## 7.2 题目泛化图

对题目从六个维度建立可操作的父子图：

```text
研究对象 Object
场景 Scenario
任务 Task
模态 Modality
方法 Method
数据 Data
```

示例：

```text
某特殊桥型裂缝三维智能测量
        │
        ├── 对象泛化
        │   某特殊桥型 → 桥梁 → 混凝土结构 → 工业表面
        │
        ├── 任务降级
        │   三维精确测量 → 三维定位 → 二维分割 → 二维检测
        │
        ├── 模态降级
        │   RGB+Depth+PointCloud → RGB-D → 双目 → 单目 RGB
        │
        ├── 数据降级
        │   自建完整3D标注 → 公开2D数据 + 少量自采验证
        │
        ├── 方法降级
        │   新型端到端模型 → 成熟模型适配 → 轻量模块改进
        │
        └── 结论降级
            精确测量 → 估计量测 → 定性定位 → 可视化验证
```

***

## 7.3 常用退化策略

### 策略 A：从特定场景退到通用任务

```text
特定隧道病害识别
→ 混凝土表面损伤识别
→ 裂缝/剥落分割
```

适用：

- 特定场景数据不足
- 但底层视觉任务已有公开数据集

***

### 策略 B：从新数据集退到公开数据迁移

```text
从零构建大规模专用数据集
→ 使用公开数据训练
→ 少量自采数据验证
→ 做跨域差异分析或小样本适配
```

可形成的贡献：

- 数据域差异分析
- 跨域性能边界
- 小样本微调
- 数据增强
- 域适应

***

### 策略 C：从三维精确测量退到二维识别或估计

```text
真实毫米级三维裂缝测量
→ 深度辅助估计
→ 二维到三维定位
→ 二维分割
```

系统必须明确证据等级：

```text
measured
有人工真值和完整标定

estimated
有深度或点云，但无人工真值

visual_only
仅有图像结果
```

***

### 策略 D：从新模型退到成熟 Baseline + 问题驱动改进

```text
从零设计一个全新网络
→ 选择 YOLO / U-Net / DeepLab / Transformer Baseline
→ 找出一个明确失败场景
→ 添加一个有依据的改进模块
→ 做消融实验
```

***

### 策略 E：从多模态端到端退到模块化系统

```text
端到端统一处理图像、深度、点云和文本
→ 各模态使用成熟工具
→ Agent 负责路由与证据融合
```

这种路线更适合作为工程硕士工作量：

- 算法基础模块
- 跨模态集成
- 工程系统与验证

***

### 策略 F：从追求 SOTA 退到适用性与边界研究

```text
在所有数据集达到最高精度
→ 验证现有方法在目标场景是否适用
→ 找出失效条件
→ 提出轻量适配
```

这类工作可以合法、清晰地写成：

- 复现
- 跨域测试
- 失败分析
- 轻量优化
- 工程闭环

***

## 7.4 每条退化路线必须满足的证据条件

系统不能仅凭 LLM 猜测路线。

每个 Pivot 节点至少需要：

```text
2～5 篇真实相关论文
至少 1 个可获得数据集
至少 1 个可运行 Baseline 或成熟实现
明确的评价指标
明确的实验对照组
与学生资源匹配的算力估算
```

输出示例：

```json
{
  "from": "特殊桥梁裂缝三维精确测量",
  "to": "公开混凝土裂缝数据上的分割与跨域适配",
  "pivot_type": "data_and_task_degradation",
  "evidence_papers": ["paper_01", "paper_07", "paper_12"],
  "datasets": ["CFD", "CRACK500"],
  "baselines": ["U-Net", "DeepLabV3+"],
  "metrics": ["F1", "IoU", "Recall"],
  "carrier_risk_before": 82,
  "carrier_risk_after": 38,
  "tradeoff": "无法声称真实毫米级三维测量，但可形成跨域适配和工程验证结论"
}
```

***

# 8. 2～3 个论文工作量生成器

## 8.1 工作包的定义

一个有效工作包必须满足：

1. 对应一个明确研究问题
2. 有独立输入与输出
3. 有明确 Baseline
4. 有可运行实验
5. 有可量化指标
6. 有对照组或消融
7. 可以形成独立章节
8. 失败后不导致整篇论文完全失效
9. 与其他工作包存在递进关系，而不是简单重复

***

## 8.2 推荐的两工作包结构

适合时间较紧、工程型较强的硕士论文。

### WP1：基线复现与目标域适配

目标：

- 复现成熟 Baseline
- 在目标数据上验证
- 分析域差异和失败模式
- 建立可靠实验入口

可写内容：

- 数据整理
- Baseline 复现
- 跨域实验
- 失败案例
- 指标体系
- 轻量数据侧优化

### WP2：问题驱动的方法改进与系统验证

目标：

- 针对 WP1 发现的一个主要问题提出改进
- 完成消融和对比
- 集成到可展示系统

可写内容：

- 模块设计
- 损失函数或训练策略
- 消融实验
- 泛化实验
- 系统演示
- 工程可行性

论文映射：

```text
第三章：基线与目标域适配
第四章：改进方法与系统验证
```

***

## 8.3 推荐的三工作包结构

### WP1：数据与基线工作包

```text
数据集筛选
→ 数据清洗和统一
→ Baseline 复现
→ 目标域测试
→ 失败模式分析
```

贡献类型：

- 系统复现
- 数据域分析
- 性能边界
- 评价协议

### WP2：方法改进工作包

```text
从 WP1 选取一个主要失败问题
→ 搜索已有解决路线
→ 选择一个低耦合模块
→ 提出适配方案
→ 做对比和消融
```

贡献类型：

- 轻量模块
- 训练策略
- 置信度
- 注意力
- 小样本
- 域适应
- 多尺度

### WP3：泛化或工程系统工作包

候选方向：

```text
跨数据集泛化
真实场景测试
多模态路由
可视化系统
推理效率优化
Agent 工具编排
报告生成
失败与降级机制
```

论文映射：

```text
第三章：数据、基线与性能边界
第四章：问题驱动的改进方法
第五章：系统集成、泛化与工程验证
```

***

## 8.4 工作包组合模板

### 模板 1：数据 + 方法

```text
WP1：数据域差异和基线验证
WP2：面向域差异的模型适配
```

### 模板 2：方法 + 方法

仅在两个方法解决不同问题时使用：

```text
WP1：解决可靠性问题
WP2：解决时序稳定问题
```

不允许：

```text
WP1：加注意力模块
WP2：换另一个注意力模块
```

### 模板 3：方法 + 系统

```text
WP1：目标任务算法改进
WP2：多输入工具路由和工程系统
```

### 模板 4：数据 + 方法 + 泛化

```text
WP1：公开数据与目标域差异分析
WP2：小样本/跨域适配
WP3：真实场景泛化和系统展示
```

### 模板 5：二维 + 三维 + Agent

```text
WP1：二维识别与分割
WP2：二维到三维映射或几何估计
WP3：多模态 Agent 路由与报告
```

***

## 8.5 工作包评分

```text
WorkPackageScore =
    0.20 × EvidenceSupport
  + 0.15 × DataAvailability
  + 0.15 × BaselineReadiness
  + 0.15 × ExperimentalClarity
  + 0.10 × Independence
  + 0.10 × ChapterFit
  + 0.10 × ResourceFit
  + 0.05 × Demonstrability
```

硬性条件：

- 没有数据不能通过
- 没有评价指标不能通过
- 没有对照组不能通过
- 仅有文字叙述、无实验不能通过
- 两个工作包解决同一问题且实验重复，不能同时通过

***

# 9. 开题助手总体架构

```text
用户输入
├── 初始题目
├── 专业与学位类型
├── 导师方向
├── 毕业期限
├── GPU 与设备
├── 可获得数据
├── 已有代码
└── 学校开题模板
        │
        ▼
Topic Parser
题目结构化拆解
        │
        ▼
Query Expansion Agent
中英文术语、同义词和抽象层级扩展
        │
        ▼
Evidence Collection Graph
├── Literature Scout
├── Dataset Scout
├── Baseline Scout
├── Benchmark Scout
└── GitHub Scout
        │
        ▼
Evidence Landscape
文献、数据、代码、指标和趋势地图
        │
        ▼
Carrier Risk Judge
航母风险判定
        │
        ├── GO
        │      ↓
        │  Work Package Designer
        │
        ├── NARROW / PIVOT
        │      ↓
        │  Generalization Graph
        │      ↓
        │  重新检索与重新评分
        │
        ├── PARK
        │
        └── STOP
               │
               ▼
Proposal Planner
├── 选题依据
├── 研究现状
├── 研究问题
├── 研究内容
├── 技术路线
├── 实验方案
├── 进度计划
└── 风险与备选方案
        │
        ▼
Opening Committee
多导师开题质询
        │
        ▼
最终开题评估报告
```

***

# 10. Agent 角色设计

## 10.1 Topic Parser

职责：

- 拆解题目
- 识别任务、对象、模态和方法
- 识别题目中模糊和夸大的词

重点拦截：

```text
智能
高精度
实时
全场景
多模态
自适应
端到端
通用
精确测量
大模型
数字孪生
```

这些词不是不能使用，但必须给出可验证定义。

***

## 10.2 Query Planner

职责：

- 生成中英文关键词
- 生成精确查询和宽泛查询
- 生成排除词
- 生成时间范围
- 生成领域、任务和方法组合查询

输出：

```json
{
  "exact_queries": [],
  "synonym_queries": [],
  "parent_task_queries": [],
  "dataset_queries": [],
  "baseline_queries": [],
  "gap_queries": []
}
```

***

## 10.3 Literature Scout

职责：

- 搜索论文
- 去重
- 识别综述
- 统计发表趋势
- 聚类研究主题
- 抽取研究问题、方法、数据和结论
- 建立论文关系图

***

## 10.4 Dataset Scout

职责：

- 搜索公开数据集
- 验证下载地址
- 提取 Dataset Card
- 检查许可
- 判断标签和任务是否匹配
- 输出数据使用成本

***

## 10.5 Baseline Scout

职责：

- 寻找可复现模型
- 关联论文与 GitHub
- 判断代码完整度
- 估算复现成本
- 推荐最小 Baseline

***

## 10.6 Carrier Risk Judge

职责：

- 计算航母风险
- 给出硬性否决项
- 输出可解释判定
- 选择 GO、NARROW、PIVOT、PARK 或 STOP

要求：

> 每一个风险判断必须引用对应证据，不允许只给出模型主观意见。

***

## 10.7 Pivot Planner

职责：

- 生成题目泛化图
- 对每条路线重新搜索
- 计算转向后的风险
- 标明损失和收益
- 推荐 3 条不同保守程度的路线

输出：

```text
路线 A：最保守，优先毕业
路线 B：平衡，保留一定方法创新
路线 C：较激进，保留原场景特色
```

***

## 10.8 Work Package Designer

职责：

- 生成 2～3 个工作包
- 检查工作包独立性
- 生成问题—方法—实验矩阵
- 映射到论文章节
- 输出时间和算力预算

***

## 10.9 Proposal Planner

职责：

生成开题报告骨架：

```text
1. 选题背景与意义
2. 国内外研究现状
3. 现有研究不足
4. 研究目标
5. 研究问题
6. 研究内容
7. 技术路线
8. 实验方案
9. 创新点与工作量
10. 进度安排
11. 风险与备选方案
12. 参考文献
```

***

## 10.10 Opening Committee

模拟不同委员：

- 领域专家
- 方法专家
- 工程应用专家
- 数据与实验专家
- 严格型导师

重点提问：

```text
为什么必须做这个题目？
为什么是这个研究对象？
数据从哪里来？
没有自有数据怎么办？
Baseline 能否复现？
两个工作包是否真的不同？
创新点如何通过实验验证？
如果主要模块无效，论文是否还能完成？
预计什么时候得到第一张结果表？
题目是否超出硕士毕业周期？
```

***

# 11. LangGraph 状态设计

```python
class TopicPilotState:
    user_profile: dict
    raw_topic: str
    topic_spec: dict
    query_plan: dict

    papers: list
    datasets: list
    baselines: list
    benchmarks: list

    maturity_score: float
    differentiation_score: float
    carrier_risk: float
    hard_blockers: list

    verdict: str
    pivot_candidates: list
    selected_pivot: dict | None

    work_packages: list
    experiment_matrix: list
    proposal_outline: dict

    committee_reviews: list
    evidence_ledger: list
```

状态图：

```text
START
  ↓
parse_topic
  ↓
expand_queries
  ↓
collect_literature
  ├── collect_datasets
  ├── collect_baselines
  └── collect_benchmarks
  ↓
build_evidence_landscape
  ↓
judge_carrier_risk
  ├── GO → design_work_packages
  ├── NARROW → generate_pivots
  ├── PIVOT → generate_pivots
  ├── PARK → generate_revisit_conditions
  └── STOP → generate_stop_report
                ↓
         human_select_pivot
                ↓
         rerun_evidence_search
                ↓
         judge_carrier_risk
                ↓
         design_work_packages
                ↓
         generate_proposal
                ↓
         committee_review
                ↓
         revise_proposal
                ↓
               END
```

***

# 12. 关键数据结构

## 12.1 Evidence Item

```python
class EvidenceItem:
    evidence_id: str
    evidence_type: str
    title: str
    source_url: str
    source_database: str
    publication_year: int | None
    related_topic_component: str
    supports_claim: str
    confidence: float
    verified: bool
```

## 12.2 Dataset Candidate

```python
class DatasetCandidate:
    name: str
    task: list[str]
    modality: list[str]
    size: str
    annotation: list[str]
    license: str | None
    download_status: str
    related_papers: list[str]
    known_baselines: list[str]
    adaptation_cost: str
    risk: str
```

## 12.3 Baseline Candidate

```python
class BaselineCandidate:
    name: str
    paper_id: str
    repository: str
    license: str | None
    pretrained_weights: bool
    train_script: bool
    eval_script: bool
    estimated_vram: str | None
    estimated_training_time: str | None
    reproducibility_score: float
```

## 12.4 Work Package

```python
class WorkPackage:
    wp_id: str
    title: str
    research_question: str
    baseline: str
    proposed_change: str
    datasets: list[str]
    metrics: list[str]
    comparisons: list[str]
    ablations: list[str]
    deliverables: list[str]
    chapter_mapping: str
    risks: list[str]
    fallback: str
```

***

# 13. 系统输出

最终生成 `Topic Feasibility Report`。

## 13.1 报告结构

```text
1. 题目结构化拆解
2. 检索策略和关键词
3. 文献地图
4. 数据集地图
5. Baseline 与代码地图
6. 研究成熟度
7. 差异空间
8. 航母风险评分
9. 硬性风险
10. GO / NARROW / PIVOT / PARK / STOP 判定
11. 三条退化或泛化路线
12. 推荐题目
13. 2～3 个工作包
14. 问题—方法—实验矩阵
15. 论文目录映射
16. 开题报告骨架
17. 开题委员会问题
18. 风险与备选方案
19. 证据清单
```

***

## 13.2 示例判定摘要

```markdown
## 选题判定

原题目：
基于多模态大模型的特殊桥梁裂缝三维精确测量方法研究

航母风险：82/100
判定：PIVOT

主要原因：

1. 缺少可直接使用的裂缝级三维标注数据
2. “精确测量”需要人工真值和完整标定
3. 多模态大模型、三维重建和裂缝测量同时存在高风险
4. 当前算力和时间不足以完成端到端模型训练
5. 三个主要环节完全串行，前端失败会导致后续全部失效

推荐方向：

面向混凝土裂缝场景的二维分割、跨域适配与三维映射系统研究

转向后风险：39/100
判定：有条件 GO
```

***

# 14. MVP 设计

## 14.1 第一版支持范围

先只支持：

- 计算机、人工智能和工科视觉方向
- 硕士研究生
- 题目文本输入
- OpenAlex、Semantic Scholar、GitHub 和 Hugging Face
- 用户上传中文文献 RIS/BibTeX
- 2～3 个工作包生成
- Markdown 开题评估报告
- LangGraph 状态图
- 人工选择 Pivot

暂不支持：

- 自动完成完整开题报告正文
- 自动训练大模型
- 自动抓取受限中文数据库
- 所有学科通用
- 自动保证创新性
- 自动保证通过开题

***

## 14.2 MVP 页面

### 页面 1：用户约束

填写：

- 初始题目
- 专业
- 学位类型
- 开题时间
- 预计毕业时间
- GPU
- 是否有自有数据
- 是否有采集设备
- 当前编程水平
- 导师主要方向
- 希望形成几个工作包

### 页面 2：题目拆解

展示：

- 研究对象
- 任务
- 模态
- 方法
- 数据
- 评价目标
- 模糊词和高风险词

### 页面 3：证据地图

展示：

- 论文年份趋势
- 研究主题聚类
- 数据集
- Baseline
- GitHub 项目
- 相关综述

### 页面 4：航母风险

展示雷达图：

- 文献
- 数据
- Baseline
- 评价
- 资源
- 范围
- 工作包

### 页面 5：退化路线

展示三条路线：

- 保守
- 平衡
- 激进

### 页面 6：工作量规划

展示：

- WP1
- WP2
- WP3
- 实验矩阵
- 章节映射
- 时间计划

### 页面 7：开题报告

输出：

- 选题论证
- 研究问题
- 技术路线
- 创新点
- 风险
- 参考文献

***

# 15. 建议技术栈

| 层级       | 技术                          |
| -------- | --------------------------- |
| Agent 编排 | LangGraph                   |
| API 后端   | FastAPI                     |
| 数据模型     | Pydantic                    |
| 关系数据库    | PostgreSQL                  |
| 向量数据库    | pgvector / Qdrant           |
| 缓存       | Redis                       |
| 异步任务     | Celery / Dramatiq           |
| 文献检索     | OpenAlex / Semantic Scholar |
| 数据集检索    | Hugging Face Hub / Kaggle   |
| 代码检索     | GitHub API                  |
| 文献解析     | GROBID / Docling / PyMuPDF  |
| 图谱       | Neo4j 或 PostgreSQL 关系表      |
| 前端       | Next.js / Vue               |
| 状态可视化    | React Flow                  |
| 日志与追踪    | LangSmith / OpenTelemetry   |
| 报告输出     | Markdown / DOCX             |

***

# 16. 项目创新点

## 创新点 1：从“新颖性判断”转为“毕业可行性判断”

现有研究构思 Agent 更关注：

- 新不新
- 有没有研究价值
- 能否生成更复杂的方法

本项目增加：

- 学生能不能完成
- 数据是否真实可得
- Baseline 是否能复现
- 能否拆成 2～3 个工作包
- 是否符合硕士毕业周期

***

## 创新点 2：文献—数据—代码—指标联合证据

选题不是只看论文。

系统同时建立：

```text
Research Question
      ↓
Papers
      ↓
Datasets
      ↓
Baselines
      ↓
Metrics
      ↓
Experiments
```

只有证据链完整时，题目才可以进入 GO。

***

## 创新点 3：可解释的“航母风险”模型

风险不是 LLM 主观评价，而是由以下事实共同构成：

- 文献密度
- 数据可用性
- 代码成熟度
- 评价协议
- 算力与时间
- 工作包依赖关系

***

## 创新点 4：Topic Generalization Graph

系统不是简单推荐另一个题目，而是展示：

```text
原题目
→ 放松哪个约束
→ 对应哪些论文
→ 获得哪些数据集
→ 可以使用哪些 Baseline
→ 风险降低多少
→ 损失了什么结论
```

***

## 创新点 5：工作包级论文规划

系统直接生成：

```text
研究问题
→ 工作包
→ 方法
→ 数据
→ 实验
→ 章节
→ 备选方案
```

这比一般的“创新点生成器”更接近真实毕业论文需求。

***

