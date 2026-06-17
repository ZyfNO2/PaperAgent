# Legcy Code

> 旧的 8-Phase TopicPilot-CN 实现，已停止维护，仅供小参考。
> 不要恢复，不要把这里的内容直接复制到新代码里。

## 结构

```
old_code/
├── apps/api/        # 旧 FastAPI: 8 个 phase 端点 + 8 个 SSE 端点
├── apps/web/        # 旧前端: 8 step dot 进度条 + 一页一动作
├── packages/        # 旧 domain/agents/clients/llm 模块
├── scripts/         # 旧 demo_smoke / full_smoke / browser_self_test
└── data/            # 旧 demo_cases / projects
```

## 复用的旧模块（小参考）

- `packages/clients/arxiv.py` — arXiv 公开 API XML 解析（轻量、无依赖）
- `packages/llm/client.py` — MiniMax M3 LiteLLM 客户端 + JSON 模式

## 当前主线

见 `Plan/TopicPilot-CN_OneTopic_MVP_修改SOP.md`，新版只做「一题输入 → 关键词拆解 →
三线检索 → 可行性判断 → 推荐 + 轻审核」的 MVP 体验。
