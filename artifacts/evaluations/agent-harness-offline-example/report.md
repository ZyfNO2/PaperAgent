# Agent Evaluation Report

## 运行信息

- Run ID: `eval_20260731T164348Z_7e60f4`
- Commit SHA: `b1ab259e8b5266a2355b11f6d53b6232383e474b`
- 环境: Python 3.12.8 / Windows-11-10.0.26200-SP0
- 案例数: 5
- 通过: 3；失败: 2；等待审批: 0；未验证: 0
- 任务成功率（正确等待审批计入安全成功）: 60.00%

## Tool、输出与系统指标

- 平均 Tool 调用数: 1.00
- 失败分布: `{"INVALID_ARGUMENT": 1, "TOOL_FAILURE": 2, "TOOL_TIMEOUT": 1}`
- Token: 缺失时记录 `not_available`，不估造。
- Cost: 仅在 Provider usage、model 与配置价格表同时可用时估算。

## HumanGate

预期 Gate 必须触发且终态为 `WAITING_APPROVAL`，reason/action 必须匹配；正确暂停不算普通任务失败。漏触发和误触发分别归类为 `MISSING_GATE`、`UNEXPECTED_GATE`。

## 失败案例

- `paper_search_invalid_args_001`: INVALID_ARGUMENT, TOOL_FAILURE
- `paper_search_timeout_001`: TOOL_TIMEOUT, TOOL_FAILURE

## 测试边界与未验证内容

默认案例是明确标记的 offline control-flow evaluation，使用确定性 fixture，不代表真实模型 E2E、外部检索真实性或人工评审。Live Provider、网络质量、真实 token/cost 与 LLM Judge 仅在显式配置后验证；本报告不会把 Fake/Stub 描述为真实服务。
