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

## 前端交互可用性契约 (Session 57 起强约束)

> 每个 Session 结束时，新前端 (`apps/web-react`, 18183) 的**每个可点击 / 可输入控件
> 必须有真实交互测试**，不能只断言"可见"。下列契约必须遵守。

**【强制规则】每次新增或修改前端控件后，必须执行并通过 Playwright 全流程点击测试 + 截图：**
- 测试文件: `apps/web-react/e2e/test_session<N>_topic_driven_retrieval.py`
- 截图目录: `apps/web-react/e2e/screenshots/session<N>/`
- 测试内容: 输入 3 个金样例题目 → 点击分析 → 验证关键词拆解 → 验证候选变化
- 断言: 3D题显示MVTec 3D-AD/COLMAP/3DGS, YOLO题不混3D, NLP题显示BERT/RoBERTa
- **禁止跳过此测试** — 任何以"scope限制"或"时间不足"跳过的理由无效，必须补做

**TopBar 5 nav (工作台 / RAG / ThesisEval / 面试 / 协议)**:

- 点击后路由必须跳转 (`#/` / `#/?mode=...` / `#/workbench` / `#/protocols`)
- 跳转后目标路由的 `data-testid` 必须可见
- 当前 nav item 必须带 `.pa-topbar__nav-item--active` 类
- 截图: 跳后页面 full_page

**TopBar CTA 与链接**:

- `加载 Demo` 点击后 hash 必须包含 `mode=interview&demo=case1`
- `旧前端 ↗` 链接 href 必须指向 `http://127.0.0.1:18182`

**SideNav docs rail**:

- 每个分组 (工作流 / 评估 / 协议 / 系统) 的子项点击后必须跳转 + 该项加 `.pa-sidenav__item--active`
- 当前路由 active 数量恰好为 1

**首页 hero CTA**:

- `进入工作台 →` 黑色主按钮: 点击后 hash 跳到 `#/` 或 `#/workbench`
- `加载面试 Demo` 次按钮: 点击后 hash 包含 `mode=interview&demo=case1`
- `/health` 次按钮: href 指向 `18183/health`
- 3 个能力数据区 (RAG / ThesisEval / Interview) 必须有 `图 1 / 图 2 / 图 3` 编号 caption

**ThoughtPanel TUI console**:

- 底部命令行 prompt (`data-testid="thought-input"`) 必须可输入
- Enter 后必须追加新行 (`.pa-thought-panel__line` 数量 +1)
- 新行文本必须包含用户输入
- **关键不变式**: 路由切换后 console 内容**不清空**

**RAG Eval 页面**:

- 点 `Seed Library` 后点 `Run Eval`, `.pa-metric-table` 必须出现
- metric row 数量 ≥ 11 (Recall@5 / MRR / NDCG / Hit Rate / Citation Precision / Evidence Coverage / Unsupported Claim / Faithfulness / Latency p50 / p95 / Fallback Rate)

**ThesisEval 页面**:

- 4 个 `.pa-subset-btn` 必须可见
- 点击 subset 后 active 数量恰好为 1

**Playwright 文件位置**:

- 主 spec (可见性 + 截图): `apps/web-react/e2e/test_session<N>_*.py`
- 点击真实交互 spec: `apps/web-react/e2e/test_session57_click_through.py`
- 截图: `apps/web-react/e2e/screenshots/session<N>/` (主截图) + `interactions/` (交互后截图)
- marker: `pytest.mark.react_web`

**运行命令**:

```bash
.venv/Scripts/python.exe -m pytest apps/web-react/e2e/test_session57_click_through.py -v -m react_web
.venv/Scripts/python.exe -m pytest apps/web-react/e2e -v -m react_web
```

**任何 session 提交时如果新增了交互控件, 必须同步扩展 `test_session57_click_through.py` 或新增同名 spec.**
