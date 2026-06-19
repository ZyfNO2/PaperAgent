# Local Runbook（本地运行手册）

> PaperAgent 在 Windows 11 上的本地开发 / 演示 / 测试运行手册。
> 端口：后端 18181 / 前端 8080（避开 Windows 防火墙冲突）。

---

## 1. 环境要求

| 项 | 要求 |
|---|---|
| OS | Windows 11 / macOS / Linux 均可 |
| Python | 3.12+ |
| 浏览器 | Chromium（Playwright 自动安装） |
| 磁盘 | 至少 2GB 可用（含 `.venv`） |
| 网络 | 可选 —— 无网络时所有 LLM / 外部 API 走 fallback |

---

## 2. 安装依赖

```bash
# 1) 克隆 & 进入
git clone <repo> PaperAgent
cd PaperAgent

# 2) 创建虚拟环境
python -m venv .venv

# 3) 激活（Windows Git Bash）
.venv/Scripts/python.exe -m pip install -e ".[dev]"

# 4) 安装 Playwright 浏览器
.venv/Scripts/python.exe -m playwright install chromium

# 5)（可选）复制 .env
cp .env.example .env
# 编辑 .env，把 MINIMAX_API_KEY=... 替换为你的真实 key
# 不填也能跑，heuristic fallback 兜底
```

### 依赖说明

```text
fastapi>=0.115        # 后端 web 框架
uvicorn[standard]>=0.32  # ASGI 服务器
pydantic>=2.9         # 数据模型 + 校验
httpx>=0.27           # 异步 HTTP 客户端（外部 API）
python-dotenv>=1.0    # 读 .env

# dev
pytest>=8.3           # 后端测试
pytest-asyncio>=0.24  # 异步测试
ruff>=0.7             # lint
playwright>=1.40      # 浏览器测试
```

---

## 3. 启动服务

### 3.1 一键启动（Windows）

```bash
start_all.bat
```

会先后启动：

- **后端**：`uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 18181`
- **前端**：`python apps/web/dev_server.py`（端口 8080）

### 3.2 手动启动

```bash
# Terminal 1：后端
.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 18181 --log-level info

# Terminal 2：前端
.venv/Scripts/python.exe apps/web/dev_server.py
```

### 3.3 停止服务

```bash
stop_all.bat
```

或手动：

```bash
# Windows
taskkill /F /IM python.exe /T
```

### 3.4 健康检查

```bash
# 后端
curl http://127.0.0.1:18181/docs

# 前端
curl http://127.0.0.1:8080
```

---

## 4. 跑测试

### 4.1 全量回归（推荐）

```bash
run_tests.bat
```

自动：

1. 杀掉残留的 uvicorn / dev_server；
2. 重新启动后端 + 前端；
3. 跑全量 pytest；
4. 留下服务在 18181 / 8080。

### 4.2 仅后端

```bash
.venv/Scripts/python.exe -m pytest apps/api/tests -v
```

### 4.3 仅前端

```bash
.venv/Scripts/python.exe -m pytest apps/web/e2e -v
```

### 4.4 单 Session

```bash
# 后端
.venv/Scripts/python.exe -m pytest apps/api/tests/test_session15_material_card_intake.py -v

# 前端
.venv/Scripts/python.exe -m pytest apps/web/e2e/test_one_topic_session15_material_cards.py -v
```

---

## 5. 常见问题

### 5.1 端口被占

```text
ERROR: [Errno 10048] Only one usage of each socket address ...
```

解决：

```bash
# 找出占用 18181 的进程
netstat -ano | findstr :18181
# 杀掉
taskkill /F /PID <pid>
```

### 5.2 Playwright 启动失败

```text
playwright._impl._errors.Error: BrowserType.launch ...
```

解决：

```bash
.venv/Scripts/python.exe -m playwright install chromium
.venv/Scripts/python.exe -m playwright install-deps chromium   # Linux/macOS
```

### 5.3 LLM 调用失败

```text
[ERROR] LLM call failed: ...
```

解决：

- 确认 `.env` 是否填了 `MINIMAX_API_KEY`；
- 不填也能跑，只是 LLM 路径返回 heuristic fallback；
- 测试中默认 mock LLM；如要真跑测试需明确 `LITELLM_LIVE=1`。

### 5.4 外部 API 失败

```text
[ERROR] OpenAlex / arXiv / GitHub / HuggingFace call failed
```

解决：

- 网络抖动 → 等 30s 重试；
- 接口限流 → 切换 `refresh=False` 复用上次结果；
- 服务主动 fallback：单源失败不影响其他源。

### 5.5 pytest 全红

```text
collected X items
...
FAILED ...
```

排查顺序：

1. 看后端是否在 18181 起：`curl http://127.0.0.1:18181/docs`
2. 看前端 dev_server 是否在 8080 起
3. 看 `.runtime/` 权限 / 剩余空间
4. 看 `apps/api/tests/conftest.py` 是否要重置环境

---

## 6. 清理 .runtime

`.runtime/` 目录保存：

- `traces/{project_id}.jsonl`：所有 trace 事件；
- `materials/{project_id}/`：上传的 PDF / 图片；
- `retrieval/`：多源检索缓存；
- `skills_cache/`：Skill 注册缓存。

清理：

```bash
# 清空所有
rm -rf .runtime/traces/* .runtime/materials/* .runtime/retrieval/* .runtime/skills_cache/*

# 完全删除（会丢所有历史）
rm -rf .runtime/
```

清理不影响代码与测试。

---

## 7. 外部 API 降级说明

| 源 | 失败表现 | 降级 |
|---|---|---|
| OpenAlex | papers 列表为空 | 走 arXiv 单独检索 |
| arXiv | papers 列表为空 | 走 OpenAlex 单独检索 |
| GitHub | repos 列表为空 | 走 heuristic 候选 |
| HuggingFace | datasets 列表为空 | 走 heuristic 候选 |
| MiniMax LLM | intent_zh 返回兜底文本 | heuristic fallback |
| 资料 OCR | parse_confidence 0.4 + warning | 用户需手动确认 |

**测试默认 mock 外部 API**，保证离线 CI 可跑。

---

## 8. Demo 演示

```bash
# 1. 启动
start_all.bat

# 2. 浏览器
open http://127.0.0.1:8080

# 3. 按脚本走
# 详见 docs/demo/OneTopic_Demo_Script.md
```

主 Demo 题目已默认填好：**基于 YOLO 的钢材表面缺陷检测**。

---

## 9. 调试技巧

### 9.1 后端日志

```bash
# 改 log-level
.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 18181 --log-level debug
```

### 9.2 前端日志

- F12 → Console：看 app.js 输出
- F12 → Network：看 API 调用

### 9.3 Trace 调试

```bash
# 查某个 project 的所有 trace
cat .runtime/traces/<project_id>.jsonl | jq .
```

### 9.4 pytest 调试

```bash
# 失败时进入 pdb
.venv/Scripts/python.exe -m pytest apps/api/tests/test_session15_material_card_intake.py -v --pdb

# 只跑某个 test
.venv/Scripts/python.exe -m pytest apps/api/tests/test_session15_material_card_intake.py::test_upload_pdf -v
```

---

## 10. CI / 离线运行

```bash
# 不依赖网络
.venv/Scripts/python.exe -m pytest apps/api/tests -v -m "not llm_live"

# 不依赖真实浏览器
.venv/Scripts/python.exe -m pytest apps/api/tests -v --ignore=apps/web/e2e
```

---

## 11. 常见路径速查

| 用途 | 路径 |
|---|---|
| 后端入口 | `apps/api/app/main.py` |
| 后端路由 | `apps/api/app/api/v1/one_topic.py` |
| 后端服务 | `apps/api/app/services/` |
| 前端入口 | `apps/web/index.html` |
| 前端逻辑 | `apps/web/app.js` |
| Skill 注册 | `skills/registry.json` |
| Trace 持久化 | `.runtime/traces/` |
| 材料存储 | `.runtime/materials/` |
| 测试配置 | `pytest.ini` + `pyproject.toml` |
| 一键启动 | `start_all.bat` |
| 一键停止 | `stop_all.bat` |
| 一键测试 | `run_tests.bat` |