# Gold Case 与 RAG 面试说明

## 项目定位

PaperAgent 不是“自动写论文工具”，而是一个受约束的科研工作流：

```text
研究问题
→ 文献与代码证据
→ Baseline 事实冻结
→ Gap 与可证伪假设
→ 模块和接口契约
→ 公平实验矩阵
→ canonical methodology audit
→ GO / REVISE / NO_GO
```

Gold Case 选用与研究计划直接相关的 NPC/Game AI 场景：行为克隆策略在分布偏移后出现无效或意图外动作，候选方法通过动作约束与不确定性触发的残差修正进行干预。

## 30 秒中文介绍

我开发了一个受约束的科研 Agent。它不会直接根据模型生成的文字判断研究方案可行，而是把文献证据、Baseline 复现事实、模块接口、实验对照和停止条件都保存为结构化契约，再由确定性的 methodology audit 给出 GO、REVISE 或 NO_GO。为了验证完整链路，我增加了一个与游戏 AI 研究计划一致的 NPC Gold Case，并把检索 Recall@K、证据精度、引用支持率、unsupported claim 和成本分别评测，避免只看最终文本是否合理。

## 日本語キーワード

- 研究契約（けんきゅうけいやく）
- 再現可能（さいげんかのう）なベースライン
- 反証可能（はんしょうかのう）な仮説（かせつ）
- 証拠（しょうこ）に基（もと）づく判定（はんてい）
- 検索再現率（けんさくさいげんりつ） / Recall@K
- 引用（いんよう）による主張（しゅちょう）の裏付（うらづ）け
- 分布（ぶんぷ）シフト
- 意図（いと）しない行動（こうどう）
- 模倣学習（もほうがくしゅう）
- 強化学習（きょうかがくしゅう）

## 高频追问

### 为什么不能只让 LLM 判断研究方案是否合理？

LLM 可以生成看起来合理的解释，但可能伪造文献属性、Baseline 结果或兼容性。因此系统把 stable identifier、license、verification state、Baseline reproduction、fingerprint 和 audit verdict 设为服务端拥有的字段。模型只能提出内容，不能自行把未验证信息升级为通过。

### Gold Case 为什么是 GO？

它满足以下工程契约：

1. Baseline 已声明复现，且记录数据集、划分、种子、环境和 parity；
2. 每个模块都有来源、许可证、输入输出语义、shape、normalization、mask、ordering、gradient 和 feature switch；
3. 动作约束和残差策略对应不同失败机制，不是无条件堆叠；
4. 有 Baseline、单模块、完整方法、leave-one-out、interaction 与强对照；
5. 预期结果仍标为 proposed，没有伪造 observed result。

### 为什么 Gold Case 不能证明科研能力已经通过？

因为它使用 synthetic fixture，没有真实论文核验、真实代码复现、训练实验或独立专家评审。它只证明：系统的结构化科研契约、审计规则和评测工具可以稳定运行。

### RAG 怎么评测？

不只看最终答案。系统分别计算：

- Recall@K 与 Precision@K；
- evidence precision；
- citation support rate；
- unsupported claim rate；
- critical unsupported claims；
- duplicate-source rate；
- context utilization；
- calls、tokens、cost；
- terminal 与 blocker reason 分布。

这样可以判断失败发生在检索、证据验证、合成、方法审核、预算还是 Provider，而不是全部归为“模型效果不好”。

### 和研究计划有什么关系？

研究计划关注规则方法、模仿学习和强化学习在游戏 Agent 中的适应性、意图外行为和调整成本。Gold Case 把同一问题表达为可验证链路：

```text
熟悉场景下行为克隆有效
→ 分布偏移提高策略不确定性
→ 无约束动作头产生无效动作
→ 高不确定状态才启用受约束残差修正
→ 比较任务成功、无效动作率、人工调整量与延迟
```

## 演示命令

```bash
python scripts/run_gold_case_readiness.py --output build/gold-case/report.json
python scripts/build_interview_readiness.py \
  --input build/gold-case/report.json \
  --output build/gold-case/interview-readiness.md
```

演示时必须明确说：

```text
This is deterministic engineering evidence using synthetic fixtures.
Scientific acceptance is not claimed.
```
