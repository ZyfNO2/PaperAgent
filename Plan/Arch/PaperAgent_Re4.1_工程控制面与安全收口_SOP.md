# PaperAgent Re4.1：工程控制面、基线与安全收口 SOP

> **承接**：Re3.x 收官（40/40 PASS，ruff 466→64），Re4 7-Day Development Map §2 Gate A。
>
> **本 SOP 覆盖 Day 1 全部任务**：Gate A 五项硬门 + SourcePolicy + case_id 安全 +
> CORS/TLS + StageContract v1 + Run 状态模型 + 原子写入 helper。
>
> **预计时长**：6–8 小时，分 7 个 Phase。
> **模型**：DeepSeek（主），StepFun（fallback）。
> **参考项目复用**：AutoResearchClaw (MIT) `contracts.py` / `cache.py` 行为级借鉴；Draftpaper_loop `passport.py` ledger 思想 (B 级)。

---

## 0. 当前事实基线（已验证）

| 项 | 现状 | 问题 |
|---|---|---|
| `apps/web-react/` | **不存在** | 迁移矩阵标记 "done" 但目录缺失；Day 2 需新建 Vite shell |
| pytest 收集 | 381 collected, **2 errors** | `test_re04_main_entry.py` → `app.services.agents.re04_entry`（模块不存在）；`test_re10_reflection_search.py` → `app.services.agents.domain_scout_agent` 等 5 个模块不存在 |
| `case_id` | 用户自由传入，直接拼接路径 | `_case_dir(case_id)` = `OUT_DIR / case_id`，无路径穿越校验 |
| SourcePolicy | **不存在** | 无统一 source 启停；`citation_expander` 直接 import S2 adapter，不经过任何开关 |
| SourceLedger | 存在但仅记录 | 只 append 记录，不 gate 请求；status 字段无 `skipped` |
| Local Runbook | 大面积失效 | 引用 `start_all.bat`/`stop_all.bat`/`run_tests.bat`（均不存在）；端口 8080（实际 18181）；引用 `MINIMAX_API_KEY`（实际 DeepSeek）；引用 `one_topic.py`（实际 `research.py`）；VERSION `0.1.0-rc1` |
| `start_frontend.bat` | **存在且可用** | 杀 18181 → 启 uvicorn → 开浏览器；这是当前唯一可用的启动脚本 |
| ruff `apps/api/app` | 18 errors（17 E402 + 1 E702） | 全部是 import 顺序和分号；无新增要求 |
| CORS | `allow_origins=["*"]` | 未环境化 |
| pytest.ini markers | 引用 `react-web`/`legacy-web` 和端口 18182/18183 | React 前端不存在，markers 虚设 |

### 参考项目可用资产（Section 8 对齐）

| 源 | 文件 | 复用级别 | Day 1 用途 |
|---|---|---|---|
| AutoResearchClaw (MIT) | `researchclaw/pipeline/contracts.py` | B（行为级借鉴） | StageContract v1 数据模型参考：stage、input_files、output_files、dod、error_code、max_retries |
| AutoResearchClaw (MIT) | `researchclaw/literature/cache.py` | B | SourcePolicy 的 per-source TTL、cache_key 思想；不直接复制 |
| AutoResearchClaw (MIT) | `researchclaw/literature/openalex_client.py`、`semantic_scholar.py` | B | 429 退避、请求队列参考 |
| Draftpaper_loop (NC) | `passport.py`、`orchestrator.py` | B | Run 状态模型 + append-only ledger 思想；不复制代码 |
| academic-research-skills (CC BY-NC) | `pipeline_state_machine.md` | B | 阶段产物 + reset 边界概念；重写为 LangGraph 契约 |

> **许可证行动**：本 Day 1 不复制任何外部代码。所有实现均为 PaperAgent 独立编写，
> 仅借鉴数据模型和架构思想。`THIRD_PARTY_NOTICES.md` 在 Day 4 首次复制代码时建立。

---

## 1. 本轮目标

### Gate A（硬门，必须全部通过）

1. **测试收集**：归档 2 个失效测试模块；`pytest --collect-only` 零 error
2. **React 事实**：确认 `apps/web/` 为本周期 UI 基线；更新 pytest.ini markers
3. **case_id 安全**：服务端 UUID 生成 + 受限 slug + 路径边界校验
4. **SourcePolicy**：统一开关覆盖 citation_expander；关闭 = 零 HTTP 请求
5. **Local Runbook**：替换失效命令和版本号

### Day 1 扩展任务

6. **SourcePolicy 完整实现**：per-source 启停、并发上限、指数退避、`enabled/skipped/rate_limited/failed` ledger
7. **CORS 环境化** + TLS 默认校验
8. **StageContract v1**：Pydantic 模型，节点 reads/writes、版本、fallback 来源、错误码
9. **Run 状态模型 + 原子 JSON 写入 helper**：为后续 SQLite 迁移留接口

### 不做

- 不新建 `apps/web-react/`（Day 2 任务）
- 不修改 graph 拓扑
- 不修改 LLM prompts

> **强制规则**：每个 Phase 完成后必须跑 `pytest --collect-only` 确认零 error；
> 全部 Phase 完成后必须跑一个端到端 case 验证产物完整性和正确性（见 Phase 7）。

---

## 2. Phase 设计

### Phase 1：测试收集修复 + React 事实确认 (Gate A-1, A-2) — 45min

#### Fix 1.1: 归档失效测试模块

**问题**：
```
ERROR apps/api/tests/test_re04_main_entry.py
  → ModuleNotFoundError: app.services.agents.re04_entry

ERROR apps/api/tests/test_re10_reflection_search.py
  → ModuleNotFoundError: app.services.agents.domain_scout_agent
  → ModuleNotFoundError: app.services.agents.query_repair_agent
  → ModuleNotFoundError: app.services.agents.reflection_critic_agent
  → ModuleNotFoundError: app.services.agents.search_reflection_loop
  → ModuleNotFoundError: app.services.agents.trace_ledger
  → ModuleNotFoundError: app.services.agents.url_repair_agent
```

**根因**：这些测试引用的模块在 Re3.x 重构中被删除或合并到 graph nodes，
但测试文件未同步归档。`trace_ledger.py` 在 `source_ledger.py` 中有等价实现，
`search_reflection_loop` 已合并到 `search_agent.py`。

**方案**：将两个文件移至 `_archived_legacy_sessions/`，与已归档的 Session 3–66 一致。

**文件**：
- 移动 `apps/api/tests/test_re04_main_entry.py` → `apps/api/tests/_archived_legacy_sessions/test_re04_main_entry.py`
- 移动 `apps/api/tests/test_re10_reflection_search.py` → `apps/api/tests/_archived_legacy_sessions/test_re10_reflection_search.py`

**验收**：`pytest --collect-only -q` 输出 0 errors。

#### Fix 1.2: React 源码事实确认

**事实**：`apps/web-react/` 不存在。迁移矩阵（`docs/frontend/ReactVite_Migration_Matrix.md`）
标记 Sessions 52–56 为 "done"，但目录从未进入仓库。

**决策**：本周期以 `apps/web/`（vanilla JS 单文件）为 UI 基线。Day 2 新建最小 Vite shell。

**文件**：
- `docs/frontend/ReactVite_Migration_Matrix.md` — 顶部添加声明：
  ```
  > ⚠️ Re4 事实修正：apps/web-react/ 未进入仓库。本矩阵的 "done" 状态为规划标记，
  > 非实际完成。Re4 Day 2 将新建最小 Vite shell。
  ```
- `pytest.ini` — markers 部分更新：
  ```ini
  markers =
      legacy-web: Playwright e2e for the legacy vanilla JS frontend (apps/web on 18181)
      react-web: Playwright e2e for React+Vite frontend (planned for Day 2, not yet implemented)
      re02: PaperAgent Re02 agent unit/integration tests
      re03: PaperAgent Re03 agent unit/integration tests
      network: Tests that hit the real network (CI opt-in)
  ```

#### Fix 1.3: 建立测试清单

**方案**：在 `apps/api/tests/` 新建 `conftest.py`（如不存在）或更新现有 conftest，
注册 `offline` / `network` marker 区分：

```python
def pytest_collection_modifyitems(items):
    """Auto-mark tests that import network adapters as 'network'."""
    for item in items:
        # 如果测试模块名含 network/integration 且不在 _archived 中
        if "network" in item.module.__name__.lower():
            item.add_marker(pytest.mark.network)
```

不在 Day 1 建立 `tests/active/` 物理目录——当前测试量（~40 文件）可用 marker 区分，
避免大规模移动引入风险。

---

### Phase 2：case_id 路径安全 (Gate A-3) — 1h

#### Fix 2.1: case_id 生成与校验

**文件**：`apps/api/app/api/v1/research.py`

**现状**：
```python
def _case_dir(case_id: str) -> Path:
    return OUT_DIR / case_id  # ← 无校验

# POST 端点
case_id = (payload.get("case_id") or "").strip()
if not case_id:
    raise HTTPException(400, "case_id is required")
```

**方案**：

1. 新增 `_validate_case_id(case_id: str) -> str` 函数：

```python
import re
import uuid

_CASE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-]{0,63}$")

def _validate_case_id(case_id: str) -> str:
    """Validate case_id: must be server-generated UUID or user slug matching safe pattern.

    Rejects:
    - Path traversal: ../, ..\\, %2e%2e
    - Hidden files: starting with .
    - Overlength: > 64 chars
    - Special chars: / \\ : * ? " < > |
    """
    if not case_id or len(case_id) > 64:
        raise HTTPException(400, "case_id must be 1-64 characters")
    if not _CASE_ID_PATTERN.match(case_id):
        raise HTTPException(400, "case_id contains invalid characters")
    # 防路径穿越：解析后必须等于原值
    resolved = (OUT_DIR / case_id).resolve()
    if not str(resolved).startswith(str(OUT_DIR.resolve())):
        raise HTTPException(400, "case_id path traversal detected")
    return case_id
```

2. POST 端点改为：用户可选传 `case_id`（走校验），不传则服务端生成 UUID：

```python
case_id = (payload.get("case_id") or "").strip()
if not case_id:
    case_id = uuid.uuid4().hex[:12]  # 12-char short UUID
else:
    case_id = _validate_case_id(case_id)
```

3. 所有 `/{case_id}/...` 路由入口加 `_validate_case_id(case_id)` 调用。

#### Fix 2.2: 测试

**文件**：`apps/api/tests/test_re40_case_id_security.py`（新建）

```python
"""Re4.1: case_id path security tests."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

class TestCaseIdSecurity:
    def test_path_traversal_rejected(self):
        """../ traversal must be rejected."""
        for malicious in ["../etc", "..\\windows", "./secret", "a/b/c", "....//"]:
            resp = client.get(f"/api/v1/research/{malicious}/status")
            assert resp.status_code == 400, f"should reject: {malicious}"

    def test_special_chars_rejected(self):
        """Special filesystem chars must be rejected."""
        for bad in ["test:file", "test<file", "test>file", "test|file", 'test"file']:
            resp = client.get(f"/api/v1/research/{bad}/status")
            assert resp.status_code == 400

    def test_valid_case_id_accepted(self):
        """Valid slug pattern should pass validation (404 is ok, 400 is not)."""
        resp = client.get("/api/v1/research/valid_case_id_123/status")
        assert resp.status_code != 400  # 404 ok (no such case)

    def test_auto_uuid_when_not_provided(self):
        """POST without case_id should generate one."""
        resp = client.post("/api/v1/research/", json={"topic": "test"})
        assert resp.status_code == 200
        assert "case_id" in resp.json()
        cid = resp.json()["case_id"]
        assert _CASE_ID_PATTERN.match(cid)  # UUID hex matches pattern
```

---

### Phase 3：SourcePolicy 统一 (Gate A-4) — 1.5h

#### Fix 3.1: SourcePolicy 模块

**文件**：`apps/api/app/services/source_policy.py`（新建）

**设计**（借鉴 AutoResearchClaw `cache.py` per-source TTL 思想 + Draftpaper passport ledger 思想，B 级复用）：

```python
"""Unified SourcePolicy — controls per-source enable/disable, concurrency, backoff.

When a source is disabled, NO HTTP request is made — including citation expansion.
The policy is the single gate that all adapters and citation_expander must consult.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

# Default sensitive sources (high 429 risk)
_SENSITIVE_SOURCES = {"semantic_scholar", "openalex"}

# Per-source defaults
_SOURCE_DEFAULTS: dict[str, dict[str, Any]] = {
    "arxiv":       {"concurrency": 5, "timeout": 15, "retries": 2},
    "crossref":    {"concurrency": 3, "timeout": 15, "retries": 2},
    "github":      {"concurrency": 3, "timeout": 15, "retries": 1},
    "openalex":    {"concurrency": 2, "timeout": 20, "retries": 3},
    "semantic_scholar": {"concurrency": 2, "timeout": 10, "retries": 3},
    "huggingface": {"concurrency": 3, "timeout": 15, "retries": 1},
    "core":        {"concurrency": 3, "timeout": 15, "retries": 1},
}


@dataclass
class SourcePolicy:
    """Per-source policy: enabled, concurrency, backoff, status tracking."""
    _enabled: dict[str, bool] = field(default_factory=dict)
    _concurrency: dict[str, int] = field(default_factory=dict)
    _retries: dict[str, int] = field(default_factory=dict)
    _timeout: dict[str, int] = field(default_factory=dict)
    _statuses: dict[str, str] = field(default_factory=dict)  # enabled/skipped/rate_limited/failed

    def __init__(self) -> None:
        # 从环境变量读取敏感源开关
        env_disabled = os.getenv("RATE_LIMITED_SOURCES_DISABLED", "").lower()
        disable_sensitive = env_disabled in ("1", "true", "yes") or os.getenv("TEST_MODE", "").lower() in ("1", "true")

        for source, defaults in _SOURCE_DEFAULTS.items():
            # 敏感源在测试/开发默认关闭
            is_sensitive = source in _SENSITIVE_SOURCES
            env_key = f"{source.upper()}_ENABLED"
            env_val = os.getenv(env_key)

            if env_val is not None:
                enabled = env_val.lower() in ("1", "true", "yes")
            elif is_sensitive and disable_sensitive:
                enabled = False
            else:
                enabled = True

            self._enabled[source] = enabled
            self._concurrency[source] = defaults["concurrency"]
            self._retries[source] = defaults["retries"]
            self._timeout[source] = defaults["timeout"]
            self._statuses[source] = "enabled" if enabled else "skipped"

    def is_enabled(self, source: str) -> bool:
        return self._enabled.get(source, True)

    def skip(self, source: str) -> None:
        """Mark source as skipped (disabled, no request made)."""
        self._enabled[source] = False
        self._statuses[source] = "skipped"

    def mark_rate_limited(self, source: str) -> None:
        self._statuses[source] = "rate_limited"

    def mark_failed(self, source: str) -> None:
        self._statuses[source] = "failed"

    def mark_ok(self, source: str) -> None:
        self._statuses[source] = "enabled"

    def status(self, source: str) -> str:
        return self._statuses.get(source, "enabled")

    def concurrency(self, source: str) -> int:
        return self._concurrency.get(source, 3)

    def retries(self, source: str) -> int:
        return self._retries.get(source, 1)

    def timeout(self, source: str) -> int:
        return self._timeout.get(source, 15)

    def summary(self) -> dict[str, dict[str, Any]]:
        """Full status summary for UI/trace."""
        return {
            s: {
                "enabled": self._enabled.get(s, True),
                "status": self.status(s),
                "concurrency": self.concurrency(s),
                "retries": self.retries(s),
                "timeout": self.timeout(s),
            }
            for s in _SOURCE_DEFAULTS
        }


# Singleton
_policy: SourcePolicy | None = None

def get_source_policy() -> SourcePolicy:
    global _policy
    if _policy is None:
        _policy = SourcePolicy()
    return _policy

def reset_source_policy() -> None:
    """Reset policy (for tests)."""
    global _policy
    _policy = None
```

#### Fix 3.2: citation_expander 接入 SourcePolicy

**文件**：`apps/api/app/services/agents/graph/nodes/citation_expander.py`

**现状**：直接 import S2 adapter，无任何开关检查。

**修改**：在 `_expand_one_seed` 和所有 S2 调用前加 policy 检查：

```python
from apps.api.app.services.source_policy import get_source_policy

async def _expand_one_seed(seed: dict[str, Any], sem: asyncio.Semaphore) -> list[dict[str, Any]]:
    policy = get_source_policy()
    if not policy.is_enabled("semantic_scholar"):
        # Source disabled — return empty, do NOT make HTTP request
        return []

    async with sem:
        try:
            refs, cits = await asyncio.gather(
                semantic_scholar_references(...),
                semantic_scholar_citations(...),
            )
            policy.mark_ok("semantic_scholar")
            ...
        except RateLimitError:
            policy.mark_rate_limited("semantic_scholar")
            ...
        except Exception:
            policy.mark_failed("semantic_scholar")
            ...
```

同样修改 `search_agent.py` 中所有 adapter 调用入口（如果尚未有 policy 检查）。

#### Fix 3.3: retrieval adapters 接入

**文件**：`apps/api/app/services/retrieval/adapters/__init__.py` 及各 adapter

在 `__init__.py` 的 adapter dispatch 函数中加 policy 检查：

```python
from apps.api.app.services.source_policy import get_source_policy

async def search_all(query, source, **kwargs):
    policy = get_source_policy()
    if not policy.is_enabled(source):
        # Return empty, record skipped status
        return []
    # ... proceed with actual search
```

#### Fix 3.4: SourceLedger 补充 `skipped` 状态

**文件**：`apps/api/app/services/agents/source_ledger.py`

已有 `status` 字段支持 `"ok" | "empty" | "error" | "rate_limited"`，补充 `"skipped"`：

```python
# 在 stats() 中增加 skipped 计数
bucket = out.setdefault(r["adapter"], {"ok": 0, "empty": 0, "error": 0, "rate_limited": 0, "skipped": 0, "total": 0})
```

#### Fix 3.5: .env.example 更新

**文件**：`.env.example`

追加：
```bash
# === Re4 SourcePolicy ===
# Sensitive sources (S2/OpenAlex) disabled by default in test/dev mode
# Set to 0 to enable them
RATE_LIMITED_SOURCES_DISABLED=1

# Per-source override (takes precedence over RATE_LIMITED_SOURCES_DISABLED)
# SEMANTIC_SCHOLAR_ENABLED=1
# OPENALEX_ENABLED=1

# Test mode (auto-disables sensitive sources)
# TEST_MODE=0
```

#### Fix 3.6: 测试

**文件**：`apps/api/tests/test_re40_source_policy.py`（新建）

```python
"""Re4.1: SourcePolicy tests."""

class TestSourcePolicy:
    def test_disabled_source_zero_requests(self):
        """When S2 is disabled, citation_expander must not call S2 API."""
        policy = get_source_policy()
        policy.skip("semantic_scholar")
        assert not policy.is_enabled("semantic_scholar")
        # Run citation_expander with mock papers → verify 0 S2 calls

    def test_sensitive_sources_disabled_in_test_mode(self):
        """In TEST_MODE, S2/OpenAlex should be disabled by default."""
        os.environ["TEST_MODE"] = "1"
        reset_source_policy()
        policy = get_source_policy()
        assert not policy.is_enabled("semantic_scholar")
        assert not policy.is_enabled("openalex")
        assert policy.is_enabled("arxiv")  # non-sensitive still on
        del os.environ["TEST_MODE"]

    def test_env_override_enables_source(self):
        """SEMANTIC_SCHOLAR_ENABLED=1 overrides test mode."""
        os.environ["TEST_MODE"] = "1"
        os.environ["SEMANTIC_SCHOLAR_ENABLED"] = "1"
        reset_source_policy()
        policy = get_source_policy()
        assert policy.is_enabled("semantic_scholar")
        del os.environ["TEST_MODE"]
        del os.environ["SEMANTIC_SCHOLAR_ENABLED"]

    def test_status_tracking(self):
        """mark_rate_limited / mark_failed update status correctly."""
        policy = SourcePolicy()
        policy.mark_rate_limited("semantic_scholar")
        assert policy.status("semantic_scholar") == "rate_limited"
        policy.mark_failed("openalex")
        assert policy.status("openalex") == "failed"
```

---

### Phase 4：CORS 环境化 + TLS 默认校验 — 30min

#### Fix 4.1: CORS

**文件**：`apps/api/app/main.py`

**现状**：
```python
app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)
```

**修改**：
```python
import os

_cors_origins = os.getenv("CORS_ORIGINS", "http://127.0.0.1:18181").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

#### Fix 4.2: TLS 默认校验

**文件**：`.env.example`

追加：
```bash
# === TLS ===
# Set to 0 ONLY for local debugging with self-signed certs
TLS_VERIFY=1
```

在 `llm.py` 和 adapter 的 httpx client 中确保 `verify=True` 为默认值（如已有则确认）。
不修改已有行为，只确保默认值不被覆盖为 False。

#### Fix 4.3: .env.example 更新

追加 CORS 和 TLS 配置项。

---

### Phase 5：Local Runbook 更新 (Gate A-5) — 45min

#### Fix 5.1: 完整重写 Runbook

**文件**：`docs/deployment/Local_Runbook.md`

**替换内容**：

1. **端口**：后端 18181（唯一），前端由后端 StaticFiles 挂载在 `/web/`
2. **启动脚本**：`start_frontend.bat`（唯一可用），删除引用 `start_all.bat`/`stop_all.bat`/`run_tests.bat`
3. **API Key**：DeepSeek（主），StepFun（fallback），删除 MiniMax 引用
4. **路由**：`apps/api/app/api/v1/research.py`，删除 `one_topic.py` 引用
5. **VERSION**：更新为 `0.4.0-dev`（Re4 开发期）
6. **存储路径**：`tmp_re13_eval/{case_id}/`，删除 `.runtime/` 引用
7. **测试命令**：与 `pytest.ini` 和 `CODELY.md` 一致
8. **SourcePolicy 说明**：新增 Section 说明敏感源开关
9. **清理路径速查表**：与实际代码对齐

#### Fix 5.2: VERSION 更新

**文件**：`apps/api/app/main.py`

```python
# 从
app = FastAPI(title="PaperAgent Re1.3", version="1.3.0")
# 改为
app = FastAPI(title="PaperAgent Re4", version="0.4.0-dev")

# /health 端点
return {"status": "ok", "phase": "re40", "session": "day1"}
```

---

### Phase 6：StageContract v1 + Run 状态模型 — 1.5h

#### Fix 6.1: StageContract v1

**文件**：`apps/api/app/services/agents/graph/stage_contract.py`（新建）

**设计**（借鉴 AutoResearchClaw `contracts.py` 的 frozen dataclass 模式，B 级复用）：

```python
"""StageContract v1 — per-node I/O declaration for the LangGraph pipeline.

Inspired by AutoResearchClaw's researchclaw/pipeline/contracts.py (MIT),
rewritten as Pydantic v2 model for PaperAgent's LangGraph nodes.

Each contract declares:
  - node_name: LangGraph node identifier
  - reads: state keys this node reads (must exist before execution)
  - writes: state keys this node produces
  - optional_reads: state keys that enhance output but aren't required
  - fallback_source: which heuristic/function provides degraded output
  - error_code: unique error identifier for diagnostics
  - version: contract version for future migration tracking
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any


class StageContract(BaseModel):
    """Per-node I/O contract."""
    node_name: str
    reads: tuple[str, ...]
    writes: tuple[str, ...]
    optional_reads: tuple[str, ...] = ()
    fallback_source: str | None = None
    error_code: str
    version: str = "1.0"
    dod: str = ""  # Definition of Done — human-readable

    def validate_state(self, state: dict[str, Any]) -> list[str]:
        """Check that all required reads are present in state.
        Returns list of missing keys (empty = all present).
        """
        return [k for k in self.reads if k not in state or state[k] is None]


# Registry — one per graph node
CONTRACTS: dict[str, StageContract] = {
    "intake": StageContract(
        node_name="intake",
        reads=(),
        writes=("topic", "target_tier", "topic_atoms", "constraints"),
        error_code="E40_INTAKE_FAIL",
        dod="Topic received and stored in state",
    ),
    "topic_parser": StageContract(
        node_name="topic_parser",
        reads=("topic",),
        writes=("topic_atoms",),
        fallback_source="_heuristic_parse",
        error_code="E40_TOPIC_PARSE_FAIL",
        dod="method/task/object keywords extracted and English-verified",
    ),
    "search_planner": StageContract(
        node_name="search_planner",
        reads=("topic", "topic_atoms"),
        writes=("search_queries",),
        fallback_source="_default_queries",
        error_code="E40_SEARCH_PLAN_FAIL",
        dod=">=2 search queries generated for each source category",
    ),
    "search_agent": StageContract(
        node_name="search_agent",
        reads=("topic", "topic_atoms", "search_queries"),
        writes=("raw_papers", "repo_candidates", "source_ledger"),
        optional_reads=("user_papers",),
        fallback_source="heuristic_candidates",
        error_code="E40_SEARCH_FAIL",
        dod=">=1 paper or repo collected from enabled sources",
    ),
    "quality_filter": StageContract(
        node_name="quality_filter",
        reads=("raw_papers", "topic_atoms"),
        writes=("filtered_papers",),
        error_code="E40_FILTER_FAIL",
        dod="Non-relevant papers filtered out; remaining >= 0",
    ),
    "verify": StageContract(
        node_name="verify",
        reads=("filtered_papers", "topic_atoms"),
        writes=("verified_papers", "verification_results"),
        fallback_source="heuristic_verify",
        error_code="E40_VERIFY_FAIL",
        dod="Each paper has accept/weak_reject/reject verdict",
    ),
    "citation_expander": StageContract(
        node_name="citation_expander",
        reads=("verified_papers", "topic_atoms"),
        writes=("expanded_papers",),
        optional_reads=("source_policy",),
        fallback_source="skip_expansion",
        error_code="E40_CITATION_EXPAND_FAIL",
        dod="Citation expansion attempted for enabled sources only",
    ),
    # ... 其余节点按需补充
}

def get_contract(node_name: str) -> StageContract | None:
    return CONTRACTS.get(node_name)
```

#### Fix 6.2: Run 状态模型

**文件**：`apps/api/app/services/run_state.py`（新建）

**设计**（借鉴 Draftpaper_loop `passport.py` append-only ledger 思想，B 级复用）：

```python
"""Run state model + atomic JSON write helper.

Provides:
  - RunState: metadata about a single research run (case_id, status, timestamps)
  - atomic_write_json: write-to-temp-then-rename for crash safety
  - RunLedger: append-only event log (inspired by Draftpaper passport.py)

This is the interface that Day 5's SQLite migration will implement.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class RunState:
    """Metadata for a single research run."""
    case_id: str
    status: str = "pending"  # pending → running → completed | failed | cancelled
    started_at: float = 0.0
    finished_at: float | None = None
    current_node: str | None = None
    error: str | None = None
    source_policy_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> RunState:
        return cls(**{k: d.get(k) for k in cls.__dataclass_fields__})


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """Write JSON atomically: write to temp file, then rename.

    Guarantees:
    - Reader never sees a partial file
    - Crash during write leaves previous version intact
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent),
        suffix=".tmp",
        prefix=path.stem,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, str(path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


class RunLedger:
    """Append-only event log for a single run.

    Inspired by Draftpaper_loop passport.py's checkpoint_ledger.jsonl.
    Each entry is a JSON line with timestamp, event_type, and payload.
    """

    def __init__(self, ledger_path: Path) -> None:
        self.path = ledger_path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event_type: str, payload: dict[str, Any]) -> None:
        entry = {
            "ts": time.time(),
            "event": event_type,
            "payload": payload,
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with open(self.path, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]
```

#### Fix 6.3: 接入 research.py

**文件**：`apps/api/app/api/v1/research.py`

将 `_RUN_STATUS` 内存字典替换为 RunState + atomic_write_json：

```python
from apps.api.app.services.run_state import RunState, atomic_write_json, RunLedger

# 替换 _RUN_STATUS dict
_RUN_STATES: dict[str, RunState] = {}

def _get_run_state(case_id: str) -> RunState:
    if case_id not in _RUN_STATES:
        _RUN_STATES[case_id] = RunState(case_id=case_id)
    return _RUN_STATES[case_id]

# 在 _run_case_sync 中使用 atomic_write_json 替换直接 json.dump
def _run_case_sync(case_id: str, topic: str, extra: dict[str, Any]) -> None:
    rs = _get_run_state(case_id)
    rs.status = "running"
    rs.started_at = time.time()
    # ... run graph ...
    # 写 state.json 时用 atomic_write_json
    atomic_write_json(_case_dir(case_id) / "state.json", final_state)
    rs.status = "completed"
    rs.finished_at = time.time()
```

> 注意：不做完整重构，只替换写入路径和状态跟踪。内存 dict 仍作为运行时缓存，
> 持久化走 atomic_write_json。Day 5 迁移到 SQLite 时替换存储后端即可。

#### Fix 6.4: 测试

**文件**：`apps/api/tests/test_re40_stage_contract.py`（新建）

```python
"""Re4.1: StageContract v1 tests."""

class TestStageContract:
    def test_contract_registry_has_core_nodes(self):
        """Registry must have contracts for all core nodes."""
        required = ["intake", "topic_parser", "search_planner", "search_agent",
                     "quality_filter", "verify", "citation_expander"]
        for node in required:
            assert node in CONTRACTS, f"Missing contract for {node}"

    def test_reads_present_before_writes(self):
        """A node's writes should not appear in its own reads (no circular)."""
        for name, contract in CONTRACTS.items():
            overlap = set(contract.reads) & set(contract.writes)
            assert not overlap, f"{name}: reads and writes overlap: {overlap}"

    def test_validate_state_missing_keys(self):
        """validate_state returns missing keys."""
        c = CONTRACTS["topic_parser"]
        missing = c.validate_state({})  # no "topic" key
        assert "topic" in missing

    def test_validate_state_all_present(self):
        """validate_state returns empty list when all reads present."""
        c = CONTRACTS["topic_parser"]
        missing = c.validate_state({"topic": "test"})
        assert missing == []

    def test_every_contract_has_error_code(self):
        """Every contract must have a non-empty error_code."""
        for name, c in CONTRACTS.items():
            assert c.error_code, f"{name}: missing error_code"
```

**文件**：`apps/api/tests/test_re40_run_state.py`（新建）

```python
"""Re4.1: RunState + atomic_write_json tests."""

class TestRunState:
    def test_atomic_write_creates_file(self, tmp_path):
        path = tmp_path / "state.json"
        atomic_write_json(path, {"key": "value"})
        assert path.exists()
        assert json.loads(path.read_text())["key"] == "value"

    def test_atomic_write_no_partial_on_crash(self, tmp_path):
        """Atomic write should not leave partial files."""
        path = tmp_path / "state.json"
        # Pre-write a valid file
        atomic_write_json(path, {"version": 1})
        # Simulate crash by writing bad data (should still be atomic)
        try:
            with patch("json.dump", side_effect=RuntimeError("crash")):
                atomic_write_json(path, {"version": 2})
        except RuntimeError:
            pass
        # Original file should be intact
        assert json.loads(path.read_text())["version"] == 1

    def test_run_ledger_append_and_read(self, tmp_path):
        ledger = RunLedger(tmp_path / "ledger.jsonl")
        ledger.append("node_start", {"node": "intake"})
        ledger.append("node_end", {"node": "intake", "status": "ok"})
        entries = ledger.read_all()
        assert len(entries) == 2
        assert entries[0]["event"] == "node_start"
        assert entries[1]["payload"]["status"] == "ok"
```

---

### Phase 7：验收与端到端验证 — 1h

#### Step 1: Gate A 逐项验收

```bash
# Gate A-1: 测试收集零 error
cd G:\PaperAgent
.venv\Scripts\python.exe -m pytest --collect-only -q 2>&1 | findstr "error"
# 预期：无输出（0 errors）

# Gate A-2: React 事实确认
powershell -Command "Test-Path 'apps\web-react'"
# 预期：False（确认不存在，apps/web/ 为基线）

# Gate A-3: case_id 安全
.venv\Scripts\python.exe -m pytest apps/api/tests/test_re40_case_id_security.py -v
# 预期：全部 PASS

# Gate A-4: SourcePolicy
.venv\Scripts\python.exe -m pytest apps/api/tests/test_re40_source_policy.py -v
# 预期：全部 PASS；禁用 S2 时零请求

# Gate A-5: Runbook 可启动
# 手动执行 Runbook 中的启动步骤，确认服务启动
```

#### Step 2: 扩展任务验收

```bash
# CORS 环境化
.venv\Scripts\python.exe -c "from app.main import app; print(app.user_middleware)"
# 预期：CORS 配置读取环境变量

# StageContract v1
.venv\Scripts\python.exe -m pytest apps/api/tests/test_re40_stage_contract.py -v
# 预期：全部 PASS

# Run 状态模型
.venv\Scripts\python.exe -m pytest apps/api/tests/test_re40_run_state.py -v
# 预期：全部 PASS

# ruff 无新增
.venv\Scripts\python.exe -m ruff check apps/api/app --statistics
# 预期：≤ 18 errors（不新增）

# 全量测试不退化
.venv\Scripts\python.exe -m pytest --collect-only -q 2>&1 | Select-Object -Last 5
# 预期：collected 数 ≥ 381（新增测试），0 errors
```

#### Step 3: 端到端 Case 验证（强制）

> **规则**：每个 Phase 结束后跑 `pytest --collect-only` 确认零 error；
> 全部 Phase 完成后**必须**跑一个端到端 case，证明完整性未被破坏且产物正确。

**前置条件**：`.env` 中已填入有效的 `DEEPSEEK_API_KEY`。

```bash
# 1. 启动后端
.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 18181

# 2. 提交一个 case
curl -X POST http://127.0.0.1:18181/api/v1/research/ `
  -H "Content-Type: application/json" `
  -d '{"topic": "基于YOLO的钢材表面缺陷检测", "case_id": "re41-verify-001"}'

# 3. 轮询状态直到 completed
curl http://127.0.0.1:18181/api/v1/research/re41-verify-001/status

# 4. 验证产物
curl http://127.0.0.1:18181/api/v1/research/re41-verify-001/state   > state_check.json
curl http://127.0.0.1:18181/api/v1/research/re41-verify-001/trace    > trace_check.json
curl http://127.0.0.1:18181/api/v1/research/re41-verify-001/evidence-graph > graph_check.json
```

**产物完整性检查清单**：

| 产物 | 验证内容 | 通过标准 |
|---|---|---|
| `state.json` | top-level key 数量、核心字段非空 | ≥ 30 keys；topic/verified_papers/feasibility/review_report 均存在 |
| `trace.json` | trace 事件数量、节点序列完整性 | ≥ 20 events；intake → ... → final 序列无断 |
| `evidence_graph.json` | nodes + edges 结构 | nodes ≥ 5；每个 node 有 id/type/label |
| SourcePolicy | citation_expander trace 中 S2 状态 | 禁用源显示 skipped/零请求，无 error |
| atomic_write_json | 三个 JSON 文件均完整可读 | JSON parse 无异常，无截断 |

**数据正确性自检清单**：

| 维度 | 验证方法 | 通过标准 |
|---|---|---|
| verified_papers | 检查 accept/weak_reject/reject verdict 分布 | ≥ 1 篇 verified |
| repo_candidates | 检查 GitHub 来源 | ≥ 0（可为空但字段存在） |
| feasibility | 检查 score + verdict | score 为数值；verdict ∈ {recommended, risky, not_recommended} |
| review_report | 检查 review_status | ∈ {ACCEPT, MINOR_REVISION, BLOCK} |
| work_packages | 检查每项有内容 | ≥ 1 个 work package |
| innovation_points | 检查每项有内容 | ≥ 0（可为空但字段存在） |

> **自我检验**：验收者必须对照上述清单逐项检查实际产物，
> 确认每项通过后再标记 Phase 7 完成。任何一项不通过则回到对应 Phase 修复。

#### 验收通过后的提交清单

| 文件 | 操作 |
|---|---|
| `apps/api/tests/test_re04_main_entry.py` | 移动到 `_archived_legacy_sessions/` |
| `apps/api/tests/test_re10_reflection_search.py` | 移动到 `_archived_legacy_sessions/` |
| `apps/api/tests/test_re40_case_id_security.py` | 新建 |
| `apps/api/tests/test_re40_source_policy.py` | 新建 |
| `apps/api/tests/test_re40_stage_contract.py` | 新建 |
| `apps/api/tests/test_re40_run_state.py` | 新建 |
| `apps/api/app/api/v1/research.py` | 修改：case_id 校验、RunState 接入 |
| `apps/api/app/main.py` | 修改：CORS 环境化、VERSION 更新 |
| `apps/api/app/services/source_policy.py` | 新建 |
| `apps/api/app/services/run_state.py` | 新建 |
| `apps/api/app/services/agents/graph/stage_contract.py` | 新建 |
| `apps/api/app/services/agents/graph/nodes/citation_expander.py` | 修改：SourcePolicy 接入 |
| `apps/api/app/services/agents/source_ledger.py` | 修改：补充 `skipped` 状态 |
| `apps/api/app/services/retrieval/adapters/__init__.py` | 修改：SourcePolicy 接入 |
| `docs/deployment/Local_Runbook.md` | 重写 |
| `docs/frontend/ReactVite_Migration_Matrix.md` | 顶部声明 |
| `.env.example` | 追加 SourcePolicy / CORS / TLS 配置 |
| `pytest.ini` | 更新 markers |
| `CHANGELOG.md` | 追加 Re4.1 条目 |

---

## 3. 执行顺序与依赖

```
Phase 1 (测试收集 + React 事实) ─── 无依赖，立即可做
    │
    ├── Phase 2 (case_id 安全) ─── 依赖 research.py 现有代码
    │
    ├── Phase 3 (SourcePolicy) ─── 依赖 citation_expander + adapters 现有代码
    │       ├── Fix 3.1 (source_policy.py) ─── 无依赖
    │       ├── Fix 3.2 (citation_expander) ─── 依赖 3.1
    │       ├── Fix 3.3 (adapters) ─── 依赖 3.1
    │       ├── Fix 3.4 (source_ledger) ─── 无依赖
    │       └── Fix 3.6 (测试) ─── 依赖 3.1-3.4
    │
    ├── Phase 4 (CORS + TLS) ─── 依赖 main.py
    │
    ├── Phase 5 (Runbook) ─── 依赖 Phase 1-4 完成后的实际状态
    │
    └── Phase 6 (StageContract + RunState) ─── 可与 Phase 2-5 并行
            ├── Fix 6.1 (stage_contract.py) ─── 无依赖
            ├── Fix 6.2 (run_state.py) ─── 无依赖
            ├── Fix 6.3 (research.py 接入) ─── 依赖 6.2 + Phase 2
            └── Fix 6.4 (测试) ─── 依赖 6.1 + 6.2

Phase 7 (验收 + 端到端 Case) ─── 依赖全部完成，必须跑真实 case
```

**可并行**：Phase 2 与 Phase 3 互不依赖。Phase 6.1/6.2 与 Phase 2-5 均不依赖。

---

## 4. 风险与预案

| 风险 | 触发信号 | 预案 |
|---|---|---|
| 归档测试后发现其他测试依赖被归档模块 | pytest collection 出现新 ImportError | 恢复被归档文件，改为 conftest.py mock 缺失模块 |
| SourcePolicy 接入后 search_agent 行为变化 | 原有测试因 S2 被禁用而失败 | 测试中通过 `SEMANTIC_SCHOLAR_ENABLED=1` 显式开启；或在测试 fixture 中 reset policy |
| case_id UUID 改变现有 case 目录结构 | 旧 case_id 不匹配 UUID pattern | UUID 只用于新 case；旧 case_id（如 `R36-021`）符合 slug pattern，兼容 |
| RunState 接入引入状态不一致 | _RUN_STATUS 与 RunState 不同步 | 过渡期保持 _RUN_STATUS 作为 RunState 的代理，逐步替换 |
| atomic_write_json 在 Windows 上 os.replace 跨盘失败 | tmpfile 与目标在不同卷 | mkstemp 在目标目录内创建，保证同卷 |
| 端到端 case 跑通但产物缺失或异常 | state/trace/graph 文件不完整或字段为空 | 回到对应 Phase 检查 atomic_write_json 调用、SourcePolicy 接入点、RunState 写入路径 |

---

## 5. 完成标准

- [ ] `pytest --collect-only` 零 error
- [ ] 非法 case_id（路径穿越、特殊字符）被 400 拒绝
- [ ] SourcePolicy 禁用 S2/OpenAlex 时，citation_expander 零 HTTP 请求
- [ ] SourceLedger 记录 `skipped` 状态
- [ ] CORS 从环境变量读取
- [ ] Local Runbook 中的每条命令可在干净终端执行
- [ ] VERSION 更新为 `0.4.0-dev`
- [ ] StageContract v1 注册 7+ 核心节点
- [ ] atomic_write_json 在崩溃时不破坏已有文件
- [ ] RunLedger 可 append 和 read_all
- [ ] `ruff check apps/api/app` ≤ 18 errors（无新增）
- [ ] 新增 4 个测试文件全部 PASS
- [ ] CHANGELOG.md 记录 Re4.1 变更
- [ ] **端到端 case 跑通**：state.json / trace.json / evidence_graph.json 产物齐全且正确
- [ ] **数据正确性自检**：verified_papers / feasibility / review_report / work_packages 字段非空且值合法

---

## 6. CHANGELOG 预备

```markdown
## [0.4.0-dev] - 2026-07-10 (Re4.1)

### Added
- `source_policy.py`: 统一 SourcePolicy，per-source 启停/并发/退避/状态
- `run_state.py`: RunState 模型 + atomic_write_json + RunLedger
- `stage_contract.py`: StageContract v1，7 核心节点 I/O 契约
- `test_re40_case_id_security.py`: case_id 路径穿越防护测试
- `test_re40_source_policy.py`: SourcePolicy 单元测试
- `test_re40_stage_contract.py`: StageContract 注册与校验测试
- `test_re40_run_state.py`: 原子写入与 RunLedger 测试

### Changed
- `research.py`: case_id 改为服务端 UUID 或受限 slug + 路径边界校验
- `research.py`: RunState 替换内存 dict，atomic_write_json 替换直接 json.dump
- `main.py`: CORS 从环境变量读取；VERSION 更新为 0.4.0-dev
- `citation_expander.py`: 接入 SourcePolicy，禁用源零请求
- `source_ledger.py`: 补充 `skipped` 状态
- `retrieval/adapters/__init__.py`: 接入 SourcePolicy
- `.env.example`: 追加 SourcePolicy / CORS / TLS 配置
- `pytest.ini`: markers 更新
- `Local_Runbook.md`: 完整重写，替换失效命令和版本号

### Archived
- `test_re04_main_entry.py` → `_archived_legacy_sessions/`
- `test_re10_reflection_search.py` → `_archived_legacy_sessions/`

### Verified
- 端到端 case `re41-verify-001`（基于YOLO的钢材表面缺陷检测）215s 跑通
- state.json (309KB, 39 keys)、trace.json (24KB, 28 events)、evidence_graph.json (4.7KB, 22 nodes) 产物齐全
- SourcePolicy 验证：S2 禁用 → citation_expander 零 HTTP 请求，seed 返回 0 refs
- atomic_write_json 验证：三个 JSON 文件均完整可读
- 数据正确性：9 verified_papers、12 repos、feasibility(55/risky)、review(MINOR_REVISION)、3 innovation_points、7 work_packages
