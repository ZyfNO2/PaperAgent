# PaperAgent Re6.5：鲁棒性实验室 SOP

> **制定日期**：2026-07-11  
> **承接**：R6-4 学术裁缝 2.0。  
> **周期**：5 个有效开发日。  
> **阶段门**：满足验收文档 P0/P1 + hidden 盲测对比报告完成 + 无 No-go 硬条件。  
> **后继**：R6-6 RAG 与上线前收口。

---

## 1. 目标与非目标

### 1.1 目标

构建可复现的鲁棒性评估体系：provider emulator、固定 replay、hidden 跨域盲测、
fallback chaos 注入。产出对比报告与失败分类，为上线决策提供证据。

### 1.2 非目标

- 不修改 R6-1/R6-2/R6-4 的实现代码（仅发现缺陷并记录）；
- 不逐题调 prompt 后宣称泛化（hidden 盲测禁止回看调参）；
- 不做 live smoke 以外的外网测试（L4 仅限低 token probe）；
- 不做上线部署。

---

## 2. 产物/输出清单

| 编号 | 产物 | 路径 | 格式 |
|---|---|---|---|
| D-01 | Provider emulator 套件 | `apps/api/tests/test_re6/emulators/` | Python fixtures |
| D-02 | 固定 replay fixture 集 | `apps/api/tests/test_re6/fixtures/` | JSON |
| D-03 | Hidden-OOD 跨域测试集 | `apps/api/tests/test_re6/hidden/` | JSON（冻结后解封） |
| D-04 | Failure 注入测试集 | `apps/api/tests/test_re6/failure/` | JSON + emulator config |
| D-05 | Novelty gold set | `apps/api/tests/test_re6/novelty/gold/` | JSON（R6-4 产出） |
| D-06 | RAG gold set | `apps/api/tests/test_re6/rag/gold/` | JSON |
| D-07 | 评估 harness | `scripts/re6_eval.py` | Python script |
| D-08 | L2 replay 对比报告 | `artifacts/re6/<run_id>/replay_report.md` | Markdown |
| D-09 | L3 hidden 盲测报告 | `artifacts/re6/<run_id>/hidden_report.md` | Markdown |
| D-10 | Fallback chaos 报告 | `artifacts/re6/<run_id>/chaos_report.md` | Markdown |
| D-11 | 聚合指标报告 | `artifacts/re6/<run_id>/aggregate_metrics.md` | Markdown |
| D-12 | 失败分类报告 | `artifacts/re6/<run_id>/failures.md` | Markdown |
| D-13 | 试验目录 manifest | `artifacts/re6/<run_id>/manifest.json` | JSON |

---

## 3. 规范

### 3.1 测试分层

| 层级 | 内容 | 前置条件 |
|---|---|---|
| L0 | 静态合同 / 安全单测 | R6-1/R6-2/R6-4 L0 全绿 |
| L1 | Provider emulator 集成 | R6-1/R6-2 L1 全绿 |
| L2 | 固定 replay 端到端 | 冻结 retrieval/RAG/provider fixture |
| L3 | 跨模型 / 跨域 hidden 盲测 | prompt/schema/router/阈值冻结 |
| L4 | 小规模 live smoke | L2/L3 通过后 |
| L5 | RAG + 上线前 readiness review | R6-6 负责 |

### 3.2 Provider Emulator 套件

| Emulator | 响应形态 | 用途 |
|---|---|---|
| openai-json | 标准 chat + content JSON | 直通测试 |
| reasoning-json | reasoning 有 JSON, content 有 prose | envelope 解析 |
| markdown-json | fence 包 JSON | parse 容错 |
| malformed-once | 首次缺字段, repair 后合法 | repair 测试 |
| malformed-always | 始终不合 schema | 有界失败 |
| auth-429-5xx | 401 / 429 / 503 | 错误分类 |
| models-unsupported | GET models 404/405 | 手工填 model |
| anthropic-like | messages/content blocks | adapter 归一化 |
| context-too-large | token 超限 | context 压缩 |
| semantic-fail | schema pass 但 ID 不存在 | semantic contract fail |
| all-fallback-fail | 全部 provider 失败 | typed failure |
| weak-instruction | 缺字段、枚举漂移 | 弱模型兼容 |
| streaming-chunked | SSE 分块 | streaming 支持 |

### 3.3 跨域与模型矩阵

#### Hidden-OOD 集（48 题）

至少覆盖：

| 领域/条件 | 数量 | 说明 |
|---|---|---|
| 医学 | 3 | 临床决策、医学影像 |
| 土木 | 3 | 结构健康、桥梁 |
| 遥感 | 3 | 卫星图像、地表变化 |
| 工业制造 | 3 | 缺陷检测、工艺优化 |
| 机器人 | 3 | 路径规划、抓取 |
| 材料 | 3 | 材料发现、性能预测 |
| 能源 | 3 | 负荷预测、可再生能源 |
| CV | 3 | 检测、分割、生成 |
| NLP | 3 | 理解、生成、多语言 |
| 时序 | 3 | 预测、异常检测 |
| 图学习 | 3 | 节点分类、链接预测 |
| 无 repo | 2 | 题域无公开代码 |
| 无数据集 | 2 | 题域无公开数据 |
| 中文长题 | 2 | 超长中文题目 |
| 英文缩写 | 2 | 缩写/同义词 |
| 跨域组合 | 2 | 跨学科交叉 |
| 不可行冷门题 | 2 | 证据极度稀疏 |

#### Failure 集（16 题）

| 类型 | 数量 |
|---|---|
| 无结果 | 2 |
| 429 全部 source | 2 |
| 鉴权失败 | 2 |
| 模型不存在 | 2 |
| 超长 context | 2 |
| 空 PDF | 2 |
| 全 fallback 失败 | 2 |
| SSRF 拒绝 | 2 |

#### Novelty gold set（24 题，R6-4 产出）

| 类型 | 数量 |
|---|---|
| 强候选 | 4 |
| 工程堆料 | 4 |
| 跨域移植 | 4 |
| 相邻工作重叠 | 4 |
| 证据薄弱 | 4 |
| 指标故事 | 4 |

#### RAG gold set（30 问题 / 10 个文档）

| 场景 | 问题数 |
|---|---|
| 强证据 | 8 |
| 冲突证据 | 5 |
| 无命中 | 5 |
| 扫描 PDF | 5 |
| 上下文注入文本 | 4 |
| 跨文档推理 | 3 |

人工标注：每个问题的正确页码/段落/拒绝理由。

#### 模型原型矩阵

**模型白名单**：`deepseek-v4-flash` 和 `big-pickle`（均通过 OpenCode proxy），禁止第三个模型。

| 原型 | 对应 model_id | 重点风险 | Emulator |
|---|---|---|---|
| DeepSeek V4 Flash | `deepseek-v4-flash` | 合同直通、JSON 格式服从 | openai-json / markdown-json / malformed-once |
| Big Pickle | `big-pickle` | reasoning/content 分离、审查能力 | reasoning-json / semantic-fail |

两个模型各由对应 emulator 覆盖。L4 live smoke 只对这两个 model_id 执行低 token probe。

### 3.4 L2 replay 规范

- 冻结同一批 adapter fixture、RAG index、provider emulator 配置；
- 分别运行 baseline（R6-0 冻结）和 candidate（R6-1~R6-4 完成后）；
- 每次只改变一个变量（provider/model/prompt/contract）；
- 输出 per-case ledger、route、coverage、成本、失败解释；
- 同一 fixture、预算和 prompt hash 下运行。

### 3.5 L3 hidden 盲测规范

1. 执行者先提交 prompt hash、schema hash、router config hash、阈值 hash；
2. hash 冻结后解封 hidden fixture；
3. 只允许运行，不允许调 prompt/schema/阈值；
4. 生成 aggregate report + failure taxonomy；
5. 未过门槛时回到 Dev 集，不可"修一下 hidden 的个例"。

### 3.6 L4 live smoke 规范

- 每 provider 最多两次低 token probe；
- source 限并发和成本；
- 只判断 success / degraded / typed failure；
- 外网偶然成功不能覆盖 L2/L3 的失败。

### 3.7 试验报告目录

```
artifacts/re6/<run_id>/
  manifest.json                  # run_id, timestamps, config versions
  provider_snapshot.json         # 不含 key
  model_policy.json              # 每个 role 的 ModelPolicy
  prompt_hashes.json             # 所有 prompt 的 SHA-256
  contract_versions.json         # 所有 contract 的版本
  fixture_hashes.json            # 所有 fixture 的 SHA-256
  per_case_results.jsonl         # 每 case 的结果
  fallback_ledger.jsonl          # 每次 fallback 事件
  security_redaction_report.json # key/SSRF/trace 审查结果
  novelty_review_report.json     # 学术裁缝 gold 结果
  rag_citation_report.json       # RAG gold 结果
  aggregate_metrics.md           # 聚合指标摘要
  failures.md                    # 失败案例分类
```

缺 manifest、版本快照或失败案例的报告，不得作为鲁棒性已验证的证据。

### 3.8 每项产物的元数据

每个测试产物必须包含：

| 字段 | 说明 |
|---|---|
| code_hash | git commit hash |
| provider_config_version | provider snapshot 版本 |
| model_id | 实际使用的 model |
| prompt_hash | prompt SHA-256 |
| contract_version | StructuredOutputContract 版本 |
| fixture_hash | fixture SHA-256 |
| run_id | 关联的 run ID |
| environment | local / ci / live |
| duration | 耗时 |
| conclusion | pass / fail / degraded |

记录不得含 key 或完整私密原文。

---

## 4. 验证

### 4.1 多模型输出与 fallback 验收

| 指标 | 定义 | 门槛 |
|---|---|---|
| Direct schema pass | 首次输出通过 schema | 按模型报告 |
| Repaired schema pass | 一次 repair 后通过 | 不得掩盖 semantic fail |
| Semantic contract pass | IDs/枚举/evidence/不变量通过 | P0：100% 或 typed failure |
| Silent degradation | 不合格输出仍被消费 | P0：0% |
| Repair recursion | repair depth 超限/循环 | P0：0% |
| Attribution completeness | trace 有 provider/model/contract/fallback | P0：100% |

### 4.2 故障注入验收

| 注入故障 | 期望 | 禁止 |
|---|---|---|
| 401 | invalid_auth，停止 profile | 换模型后仍用坏 key |
| 403 | permission_denied，提示无权 | 伪装 network error |
| model 404 | model_not_found，允许重选 | 自动猜模型名 |
| 429 | 有界退避或切 fallback | 无限 sleep |
| 5xx/timeout | 有界 retry 后 fallback | 无预算重试 |
| JSON 缺字段 | 单次 node-specific repair | verifier 字段污染其他节点 |
| semantic fail | validator feedback 或 typed failure | formatter 伪造 ID |
| context too large | 压缩并记录 evidence loss | 静默截断引用 |
| 全 fallback 失败 | typed_failure 或 heuristic_marked | success + 空对象 |

### 4.3 跨域验收

| 指标 | 门槛 |
|---|---|
| Hidden-OOD contract violation rate | 0% |
| Hidden-OOD role coverage@budget | 比 control 高 ≥ 10 个百分点 |
| Hidden-OOD false stop rate | 不高于 control |
| Hidden-OOD silent degradation | 0% |
| 不可行冷门题 | 正确 stop_with_explicit_gap |
| 无 repo/dataset 题 | 不因缺失 optional role 而 stop |

### 4.4 学术裁缝验收

| 指标 | 门槛 |
|---|---|
| P-M-I 完整且逻辑连通 | ≥ 85% |
| 伪创新风险召回 | ≥ 80% |
| 无证据强 claim 误放行 | 0% |
| first claim 正确降级 | 100% |
| 可证伪命题可执行率 | ≥ 85% |
| 相邻工作重叠识别 | 比 control 高 ≥ 10 个百分点 |
| reviewer independence 标注 | 100% |

### 4.5 RAG 验收

| 指标 | 门槛 |
|---|---|
| Citation validity | 100% |
| No-answer precision | ≥ 90% |
| Supporting chunk recall@5 | ≥ 80% |
| 模型切换后 citation validity 不下降 | 100% |
| 无证据强回答 | 0% |

### 4.6 阶段门

- [ ] L0–L3 通过（L0 100% 绿，L1 全绿，L2 replay 报告完成，L3 hidden 报告完成）；
- [ ] L4 仅有允许外网降级；
- [ ] 所有 P0 通过，P1 达标或有批准例外；
- [ ] hidden 对比报告、prompt/provider/fixture/contract 版本齐全；
- [ ] NoveltyReviewAdapter 对伪创新和 first claim 通过 gold；
- [ ] RAG citation validity 100%，无证据强回答为 0%；
- [ ] 失败案例有分类和根因分析。
