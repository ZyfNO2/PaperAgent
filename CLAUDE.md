# TopicPilot-CN 项目规约（自动加载）

## 阶段开发流程（强约束）

**每个 Phase 结束必须按下列顺序完成，不可省略：**

1. **测试通过** — `uv run pytest` 全绿（或解释为何有 skip/xfail）
2. **commit** — 一个独立 commit，message 以 `Phase XX: ...` 起头，列出关键产物
3. **验收报告** — `Plan/reports/Phase_XX_验收报告.md`（与代码 commit 分开，可同 commit 也可独立 commit）
4. **回复用户** — 短摘要：修了什么、数据流如何、修了哪些 bug、修了什么偏离

## 阶段产物契约

- Phase 01：Pydantic `ProjectIntake` + 评级 + FastAPI 3 端点 + LangGraph Intake/Validation
- Phase 02：Pydantic `TopicSpec` + LLM 拆解 + 2 端点
- Phase 03：Pydantic `SearchQueryPlan` + 7 检索层 + 2 端点
- Phase 04：Pydantic `EvidenceLedger` + LLM 生成 + 2 端点

## 关键不变式

- **每个阶段端点必须被前阶段 409 拦截**（D 评级 → Phase 02 拒；无 TopicSpec → Phase 03 拒；无 SearchQueryPlan → Phase 04 拒）
- **LLM 路径必须配 heuristic fallback**（不许让 LLM 挂掉服务）
- **所有 LLM 凭据从 `.env` 读取**（`MINIMAX_API_KEY` 等），`.env` 不进 git，`.env.example` 进 git
- **pytest 总数每次 commit 应当增长**（不准删除已通过的测试）
- **真实 uvicorn smoke 至少跑一次**（不能只靠单测就 commit）

## 不要做的事

- 不要把 `.env`、`data/topicpilot.db`、`tmp/pytest/`、`__pycache__/` 提交
- 不要引入未在 pyproject.toml 列出的依赖（要先加再装）
- 不要在 Pydantic v2 里用 `T | None = None` 默认参数（会触发 `not fully defined`）
- 不要在 lifespan 外依赖 ORM class 已被 import（lifespan 内显式 import 新加的 ORM class）

## 端到端命令

```bash
# 起服务（端口 18181 不会与 Windows 防火墙冲突）
.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 18181

# 跑测试
.venv/Scripts/python.exe -m pytest

# 跑 demo smoke（需 uvicorn 已起）
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/demo_smoke.py

# 跑完整 Phase 01-04 happy/blocked smoke
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/full_smoke.py
```
