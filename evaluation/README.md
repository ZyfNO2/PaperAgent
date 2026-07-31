# PaperAgent Agent Evaluation Harness

该模块提供最小、可重复、默认无外部副作用的 Agent 自动评估。它不替代已有的专项科学 benchmark；它负责统一评估一次 Agent trajectory 的任务终态、Tool 使用、结构化输出、引用落地、循环/预算、系统开销与 HumanGate。

## 结构与集成

- `cases/`：版本控制的 JSONL 案例，当前 20 条，分为 paper search、summary、workflow、HumanGate。
- `adapters/agent_adapter.py`：唯一生产集成边界。`CallableAgentAdapter` 接收现有 Graph/API invoke callable，并把 `TraceEvent`、`ExecutionMeta` 和 `human_action_required` 归一化；核心 Agent 不导入 evaluation。
- `recorder.py`：递归 secret 脱敏和有界 payload 摘要。
- `judges/`：确定性 Rule Judge 与默认关闭的结构化 LLM Judge。
- `metrics/`：任务、Tool、输出、系统和 Gate 指标。
- `runner.py` / `report.py`：隔离单案例失败并生成 JSON、Markdown 和失败分类。

现有生产 Tool 没有统一全局 registry；adapter 可通过 `ToolSchemaRegistry` 注入生产 Pydantic/type schema，参数验证不会复制业务规则。现有 LangGraph 的 `waiting_human` 映射为 `WAITING_APPROVAL`，runner 从不调用 `Command(resume=...)`，也不会用 Mock 假装批准。

## Case Schema

必填字段为 `case_id`、`category`、`input`。其余字段具有安全默认值：offline、active、终态 `COMPLETED`、12 steps、8 tool calls、120 秒、LLM Judge 关闭。`extra` 字段、冲突的 Tool policy、required 不属于非空 allowlist、required Gate 却未期待 `WAITING_APPROVAL` 等问题均在运行前失败。

`required_tools` 必须至少调用；`allowed_tools` 是 allowlist（空表示不额外限制）；`forbidden_tools` 永远禁止。`metadata.offline_observation` 只用于确定性控制流测试，不能被描述为真实 E2E。

新增案例时，在相应 JSONL 中添加一行，先运行：

```powershell
python -c "from pathlib import Path; from evaluation.runner import load_cases; print(len(load_cases(Path('evaluation/cases/paper_search.jsonl'))))"
```

## 运行

安全的 offline 示例：

```powershell
python -m evaluation.runner --dataset evaluation/cases/paper_search.jsonl --offline --output artifacts/evaluations/example
```

可用 `--case-id`、`--category`、`--max-concurrency` 过滤/限流。单案例异常不会中断其他案例。CLI 在存在预期的负向案例时以非零状态退出。

Live 案例必须标记 `mode=live`，并显式使用 `--live`。当前版本提供 adapter seam，但未把凭据或特定部署装配硬编码进 harness；未配置 live adapter 的案例报告为 `unverified/pending`，不会回退到 Fake。CI 不运行付费 Provider。

LLM Judge 仅评估 relevance、completeness、faithfulness 和 instruction following：

```powershell
python -m evaluation.runner --dataset evaluation/cases/paper_search.jsonl --enable-llm-judge
```

该选项复用 `PAPERAGENT_LLM_*` Provider 配置和生产 `LLMProvider.generate_structured`，输出由 `LLMJudgeResult` 校验；调用失败只记录在对应案例，不丢失 Rule Judge 报告。它是 automated judge，不是人工评审，也不负责在无来源证据时断言论文事实真伪。

## 指标与判定

- Task：`task_success`、成功率、terminal、字段完成率、step/tool limit、loop、timeout。
- Tool：required coverage、forbidden/invalid/duplicate/unnecessary/failure counts、recovery、平均调用数。
- Output：non-empty、schema、字段完成、citation presence/grounding、unsupported citation。
- System：总/model/tool latency、调用/重试/超时、input/output/total tokens、estimated cost。
- Gate：trigger/count、expected/unexpected、reason/action match、waiting approval。

`task_success` 综合终态、Tool policy、输出/引用、Gate 与 Rule Judge，不信任 Agent 自报 `success=true`。引用 token 必须能在本次 Tool result summary 中匹配。Token 或费用缺失时写 `unknown/not_available`；成本只允许用现有可配置 `PriceTable` 与真实 usage 估计。

## 报告与限制

每次输出 `summary.json`、`report.md`、`cases/*.json` 和 `failures/<type>/*.json`。trajectory 保存脱敏后的输入、逐步事件、参数、结果摘要、原始错误类型/信息、重试、Gate、usage、latency 与 final output。

当前限制：通用 Tool schema registry 需要具体生产部署在 adapter 装配时注入；offline fixture 只验证控制流和评分器；真实网络检索质量、真实模型、真实 token/cost、外部写入以及人工批准均未由默认运行验证。
