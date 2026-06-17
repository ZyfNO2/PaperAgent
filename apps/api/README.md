# OneTopic MVP 框架

只用一题输入：用户只输入一个题目，系统完成关键词拆解 → 三线检索 → 可行性判断 → 开题建议 → 轻审核。

不再需要完整的 8 Phase 建档；后端是无状态服务（不写 DB，刷新页面就重新算）。
LLM 路径可走 MiniMax M3（从 `.env` 读 `MINIMAX_API_KEY`），失败时回退到启发式。
arXiv 真实检索走公开 API（httpx，无 LLM 依赖）。

## 目录

```
apps/api/
  app/
    main.py                # FastAPI 入口
    api/v1/one_topic.py    # POST /analyze + POST /analyze/stream
    services/one_topic.py  # 业务: 拆解 + 检索 + 评级 + 推荐 + 审核
    services/arxiv.py      # arXiv 公开 API 客户端
    services/llm.py        # MiniMax M3 LLM 客户端 (heuristic fallback)
    schemas.py             # Pydantic 模型
apps/web/
  index.html
  app.js                  # fetch + ReadableStream
  styles.css
  dev_server.py
  e2e/                    # Playwright tests
```
