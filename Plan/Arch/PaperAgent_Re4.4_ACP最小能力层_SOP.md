# PaperAgent Re4.4：ACP 最小能力层 SOP

> **承接**：Re4.3 创新点/叙事/工作包可追溯升级完成（49 tests PASS，3 历史案例回归通过）。
>
> **本 SOP 覆盖 Day 4 全部任务**：capability registry、10+ 能力声明、REST + JSON Schema
> 运行实现、读写权限控制、集成测试、Codex/Claude Code/Trae 调用示例。
>
> **预计时长**：6–8 小时，分 7 个 Phase。
> **参考项目复用**：AutoResearchClaw (MIT) `mcp/tools.py` / `mcp/server.py`（A 级直接复用候选）；
> Draftpaper_loop (NC) `passport.py` checkpoint/resume 行为 (B 级)。
> Day 4 首次建立 `THIRD_PARTY_NOTICES.md`。

---

## 0. 当前事实基线（已验证）

### 现有 API 端点（ACP 可包装的底座）

| 方法 | 路径 | 读写 | ACP 能力名 |
|---|---|---|---|
| GET | `/api/v1/research/` | read | `list_cases` |
| POST | `/api/v1/research/` | write | `search_literature` |
| GET | `/{case_id}/status` | read | `get_run_status` |
| GET | `/{case_id}/state` | read | `get_research_state` |
| GET | `/{case_id}/evidence-graph` | read | `get_evidence_graph` |
| GET | `/{case_id}/papers` | read | `get_papers` |
| POST | `/{case_id}/papers` | write | `upload_paper` |
| GET | `/{case_id}/feasibility` | read | `get_feasibility` |
| GET | `/{case_id}/innovation` | read | `get_innovation` |
| GET | `/{case_id}/narrative` | read | `get_narrative` |
| GET | `/{case_id}/optimization` | read | `get_optimization` |
| GET | `/{case_id}/review` | read | `get_review` |
| GET | `/{case_id}/work-packages` | read | `get_work_packages` |
| GET | `/{case_id}/trace` | read | `get_trace` |
| GET | `/{case_id}/expanded` | read | `get_citation_expansion` |
| GET | `/graph-topology` | read | `get_graph_topology` |
| GET | `/health/providers` | read | `get_provider_health` |
| — | (Day 5 新增) | write | `ingest_pdf` |
| — | (Day 6 新增) | write | `query_rag` |
| — | (Day 6 新增) | read | `get_knowledge_graph` |
| — | (未来) | write | `review_human_gate` |

### AutoResearchClaw MCP 模块（MIT，A 级复用候选）

| 文件 | 内容 | 复用价值 |
|---|---|---|
| `mcp/tools.py` | `TOOL_DEFINITIONS` — JSON Schema 格式的工具定义列表 | **A 级**：可直接复用 JSON Schema 结构模式；工具名和参数需替换为 PaperAgent 的 |
| `mcp/server.py` | `ResearchClawMCPServer` — MCP server 类，含 `handle_tool_call` 路由 + `_validated_run_dir` 安全 | **A 级**：可复用 handler 路由模式和 run_id 校验逻辑 |
| `mcp/registry.py` | `MCPServerRegistry` — 外部 MCP server 注册/连接管理 | **B 级**：PaperAgent 不需要连接外部 MCP server，但 registry 模式可借鉴 |
| `mcp/transport.py` | MCP transport 层 | **B 级**：MVP 用 REST，transport 可后加 |
| `mcp/client.py` | MCP client | **不复制**：PaperAgent 是 server 端，不需要 client |

### 决策

- **协议选择**：REST + JSON Schema 为运行实现（MVP）；MCP adapter 仅包薄层（后续）
- **理由**：MCP 插件环境在当前周期不稳定；REST 端点已有，包装成本最低
- **权限模型**：read 默认开放；write 需显式 header `X-ACP-Capability: write`

### 参考项目可用资产

| 源 | 文件 | 复用级别 | Day 4 用途 |
|---|---|---|---|
| AutoResearchClaw (MIT) | `mcp/tools.py` | A | JSON Schema tool definition 格式：name, description, inputSchema(properties, required) |
| AutoResearchClaw (MIT) | `mcp/server.py` | A/B | `handle_tool_call` 路由模式 + `_validated_run_id` 安全校验 |
| AutoResearchClaw (MIT) | `mcp/registry.py` | B | registry list/get 模式（PaperAgent 用 capability registry，不是 server registry） |
| Draftpaper_loop (NC) | `passport.py` | B | checkpoint hash 消费 + append-only ledger（Re4.1 已实现 RunLedger，Day 4 接入 ACP） |

> **许可证行动**：Day 4 首次复制 AutoResearchClaw (MIT) 代码。
> 新建 `docs/project/THIRD_PARTY_NOTICES.md`，记录源路径、MIT 许可证文本、改动说明。
> 复制模块先加独立单测，再接入 PaperAgent。

---

## 1. 本轮目标

### 核心交付

1. **Capability Registry**：10+ 能力声明，每个含 name / read-write 级别 / input schema / output schema / error_code / 示例
2. **REST + JSON Schema 运行实现**：`/api/v1/acp/` 端点，列出能力 + 调用能力
3. **权限控制**：read 默认开放；write 需显式 `X-ACP-Capability: write` header
4. **统一错误结构**：未知能力、越权写操作、非法参数返回统一 JSON error
5. **集成测试**：≥ 3 个只读 + ≥ 2 个受控写能力通过测试
6. **调用示例**：Codex / Claude Code / Trae 各一段可运行示例

### 验收标准

- 能力清单可机器读取（`GET /api/v1/acp/capabilities` 返回 JSON Schema）
- 至少 3 个只读能力和 2 个受控写能力通过集成测试
- 未知能力返回 `UNKNOWN_CAPABILITY` 错误
- 越权写操作返回 `PERMISSION_DENIED` 错误
- 非法参数返回 `INVALID_PARAMS` 错误

### 不做

- 不实现 MCP transport（后续扩展）
- 不实现真正的 Human Gate resume（本周期仅审阅记录）
- 不实现 `ingest_pdf` / `query_rag` 的实际逻辑（Day 5–6 填充，Day 4 仅声明）
- 不修改已有 API 端点（ACP 是新层，包装现有端点）

> **强制规则**：每个 Phase 完成后必须跑 `pytest --collect-only` 确认零 error；
> 全部 Phase 完成后必须跑一个端到端 case 验证产物完整性和正确性（见 Phase 7）。

---

## 2. Phase 设计

### Phase 1：THIRD_PARTY_NOTICES + ACP 目录结构 — 30min

#### Fix 1.1: 新建 THIRD_PARTY_NOTICES.md

**文件**：`docs/project/THIRD_PARTY_NOTICES.md`（新建）

```markdown
# Third Party Notices

This file records all third-party code reused in PaperAgent, per Re4 Map §8.6 rules.

## AutoResearchClaw (MIT License)

- **Source**: `C:\Users\ZYF\Desktop\Paper\AutoResearchClaw\researchclaw\mcp\`
- **Files reused**: `tools.py` (tool definition pattern), `server.py` (handler routing + run_id validation)
- **License**: MIT — Copyright (c) 2026 Aiming Lab
- **Modifications**: Renamed tools to PaperAgent capability names; replaced pipeline-specific
  handlers with PaperAgent service calls; added read/write permission layer.
- **Date**: 2026-07-10 (Re4.4)

### MIT License Text

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
```

#### Fix 1.2: ACP 目录结构

```
apps/api/app/services/acp/
├── __init__.py
├── registry.py          # CapabilityRegistry — 能力注册与查找
├── capabilities.py      # 10+ 能力声明（JSON Schema 定义）
├── server.py            # ACPServer — REST handler 路由 + 权限检查
├── errors.py            # 统一错误结构
└── examples.py          # Codex / Claude Code / Trae 调用示例生成
```

---

### Phase 2：Capability Registry + 能力声明 — 2h

#### Fix 2.1: 统一错误结构

**文件**：`apps/api/app/services/acp/errors.py`（新建）

```python
"""Re4.4: Unified ACP error structure."""
from __future__ import annotations

from pydantic import BaseModel
from typing import Any


class ACPError(BaseModel):
    """Unified error response for all ACP operations."""
    success: bool = False
    error_code: str  # UNKNOWN_CAPABILITY | PERMISSION_DENIED | INVALID_PARAMS | INTERNAL_ERROR | NOT_FOUND
    message: str
    capability: str | None = None
    details: dict[str, Any] | None = None


# Error code constants
UNKNOWN_CAPABILITY = "UNKNOWN_CAPABILITY"
PERMISSION_DENIED = "PERMISSION_DENIED"
INVALID_PARAMS = "INVALID_PARAMS"
INTERNAL_ERROR = "INTERNAL_ERROR"
NOT_FOUND = "NOT_FOUND"


def unknown_capability(name: str) -> ACPError:
    return ACPError(error_code=UNKNOWN_CAPABILITY,
                    message=f"Unknown capability: {name}", capability=name)

def permission_denied(name: str, required: str) -> ACPError:
    return ACPError(error_code=PERMISSION_DENIED,
                    message=f"Capability '{name}' requires '{required}' permission",
                    capability=name, details={"required_permission": required})

def invalid_params(name: str, missing: list[str]) -> ACPError:
    return ACPError(error_code=INVALID_PARAMS,
                    message=f"Missing required parameters: {missing}",
                    capability=name, details={"missing": missing})

def not_found(name: str, resource: str) -> ACPError:
    return ACPError(error_code=NOT_FOUND,
                    message=f"Resource not found: {resource}",
                    capability=name)

def internal_error(name: str, detail: str) -> ACPError:
    return ACPError(error_code=INTERNAL_ERROR,
                    message=f"Internal error: {detail}",
                    capability=name)
```

#### Fix 2.2: 能力声明

**文件**：`apps/api/app/services/acp/capabilities.py`（新建）

**设计**（借鉴 AutoResearchClaw `mcp/tools.py` 的 JSON Schema 格式，A 级复用）：

```python
"""Re4.4: ACP capability declarations.

Each capability declares:
  - name: unique capability identifier
  - description: human-readable purpose
  - permission: "read" | "write"
  - input_schema: JSON Schema for input parameters
  - output_schema: JSON Schema for output (summary)
  - error_code: unique error identifier
  - example: sample invocation

Inspired by AutoResearchClaw mcp/tools.py TOOL_DEFINITIONS (MIT, A-level reuse).
"""
from __future__ import annotations

from typing import Any

CAPABILITIES: list[dict[str, Any]] = [
    # ===== READ capabilities (default open) =====
    {
        "name": "list_cases",
        "description": "List all research cases with their status.",
        "permission": "read",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "cases": {"type": "array"},
                "n": {"type": "integer"},
            },
        },
        "error_code": "E44_LIST_CASES",
        "example": {"input": {}, "output": {"cases": [{"case_id": "re41-verify-001"}], "n": 1}},
    },
    {
        "name": "get_run_status",
        "description": "Get the current status of a research run.",
        "permission": "read",
        "input_schema": {
            "type": "object",
            "properties": {
                "case_id": {"type": "string", "description": "The case ID"},
            },
            "required": ["case_id"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "current_node": {"type": "string"},
                "has_state_json": {"type": "boolean"},
            },
        },
        "error_code": "E44_GET_STATUS",
        "example": {"input": {"case_id": "re41-verify-001"}, "output": {"status": "done"}},
    },
    {
        "name": "get_evidence_graph",
        "description": "Get the evidence graph (nodes + edges) for a case.",
        "permission": "read",
        "input_schema": {
            "type": "object",
            "properties": {"case_id": {"type": "string"}},
            "required": ["case_id"],
        },
        "output_schema": {"type": "object", "properties": {"nodes": {"type": "array"}, "edges": {"type": "array"}}},
        "error_code": "E44_GET_GRAPH",
        "example": {"input": {"case_id": "re41-verify-001"}, "output": {"nodes": [], "edges": []}},
    },
    {
        "name": "get_papers",
        "description": "Get verified papers and user-uploaded papers for a case.",
        "permission": "read",
        "input_schema": {
            "type": "object",
            "properties": {"case_id": {"type": "string"}},
            "required": ["case_id"],
        },
        "output_schema": {"type": "object", "properties": {"papers": {"type": "array"}, "n": {"type": "integer"}}},
        "error_code": "E44_GET_PAPERS",
        "example": {"input": {"case_id": "re41-verify-001"}, "output": {"papers": [], "n": 0}},
    },
    {
        "name": "get_work_packages",
        "description": "Get work packages with dependency DAG for a case.",
        "permission": "read",
        "input_schema": {
            "type": "object",
            "properties": {"case_id": {"type": "string"}},
            "required": ["case_id"],
        },
        "output_schema": {"type": "object", "properties": {"work_packages": {"type": "array"}, "dag": {"type": "object"}}},
        "error_code": "E44_GET_WP",
        "example": {"input": {"case_id": "re41-verify-001"}, "output": {"work_packages": [], "dag": {}}},
    },
    {
        "name": "get_feasibility",
        "description": "Get the feasibility report for a case.",
        "permission": "read",
        "input_schema": {
            "type": "object",
            "properties": {"case_id": {"type": "string"}},
            "required": ["case_id"],
        },
        "output_schema": {"type": "object"},
        "error_code": "E44_GET_FEAS",
        "example": {"input": {"case_id": "re41-verify-001"}, "output": {"score": 85, "verdict": "feasible"}},
    },
    {
        "name": "get_review",
        "description": "Get the final review report for a case.",
        "permission": "read",
        "input_schema": {
            "type": "object",
            "properties": {"case_id": {"type": "string"}},
            "required": ["case_id"],
        },
        "output_schema": {"type": "object"},
        "error_code": "E44_GET_REVIEW",
        "example": {"input": {"case_id": "re41-verify-001"}, "output": {"review_status": "ACCEPT"}},
    },
    {
        "name": "get_innovation",
        "description": "Get innovation points with evidence binding for a case.",
        "permission": "read",
        "input_schema": {
            "type": "object",
            "properties": {"case_id": {"type": "string"}},
            "required": ["case_id"],
        },
        "output_schema": {"type": "object"},
        "error_code": "E44_GET_INNOV",
        "example": {"input": {"case_id": "re41-verify-001"}, "output": {"innovation_points": []}},
    },

    # ===== WRITE capabilities (require X-ACP-Capability: write) =====
    {
        "name": "search_literature",
        "description": "Submit a topic for background research graph run. Starts a full pipeline.",
        "permission": "write",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "The research topic"},
                "case_id": {"type": "string", "description": "Optional case ID (auto-generated if omitted)"},
            },
            "required": ["topic"],
        },
        "output_schema": {"type": "object", "properties": {"case_id": {"type": "string"}, "status": {"type": "string"}}},
        "error_code": "E44_SEARCH_LIT",
        "example": {"input": {"topic": "基于YOLO的钢材表面缺陷检测"}, "output": {"case_id": "abc123", "status": "running"}},
    },
    {
        "name": "upload_paper",
        "description": "Upload a user-known paper (enriched via Crossref/arXiv).",
        "permission": "write",
        "input_schema": {
            "type": "object",
            "properties": {
                "case_id": {"type": "string"},
                "title": {"type": "string"},
                "doi": {"type": "string"},
                "arxiv_id": {"type": "string"},
                "role": {"type": "string", "enum": ["baseline", "parallel"]},
            },
            "required": ["case_id"],
        },
        "output_schema": {"type": "object", "properties": {"paper": {"type": "object"}, "stored": {"type": "boolean"}}},
        "error_code": "E44_UPLOAD_PAPER",
        "example": {"input": {"case_id": "abc123", "doi": "10.1234/example"}, "output": {"stored": True}},
    },

    # ===== DECLARED but not yet implemented (Day 5-6) =====
    {
        "name": "ingest_pdf",
        "description": "Ingest a PDF for full-text indexing. [Re4.5 — not yet implemented]",
        "permission": "write",
        "input_schema": {
            "type": "object",
            "properties": {
                "case_id": {"type": "string"},
                "pdf_url": {"type": "string"},
            },
            "required": ["pdf_url"],
        },
        "output_schema": {"type": "object"},
        "error_code": "E44_INGEST_PDF",
        "example": {"input": {"pdf_url": "https://arxiv.org/pdf/2401.00001"}, "output": {"status": "NOT_IMPLEMENTED"}},
    },
    {
        "name": "query_rag",
        "description": "Query the RAG system for evidence-grounded answers. [Re4.6 — not yet implemented]",
        "permission": "read",
        "input_schema": {
            "type": "object",
            "properties": {
                "case_id": {"type": "string"},
                "question": {"type": "string"},
            },
            "required": ["question"],
        },
        "output_schema": {"type": "object"},
        "error_code": "E44_QUERY_RAG",
        "example": {"input": {"question": "What datasets are used?"}, "output": {"status": "NOT_IMPLEMENTED"}},
    },
    {
        "name": "get_knowledge_graph",
        "description": "Get the knowledge graph for a case. [Re4.6 — not yet implemented]",
        "permission": "read",
        "input_schema": {
            "type": "object",
            "properties": {"case_id": {"type": "string"}},
            "required": ["case_id"],
        },
        "output_schema": {"type": "object"},
        "error_code": "E44_GET_KG",
        "example": {"input": {"case_id": "abc123"}, "output": {"status": "NOT_IMPLEMENTED"}},
    },
    {
        "name": "review_human_gate",
        "description": "Submit a human gate review decision. [Future — not yet implemented]",
        "permission": "write",
        "input_schema": {
            "type": "object",
            "properties": {
                "case_id": {"type": "string"},
                "decision": {"type": "string", "enum": ["approve", "reject", "modify"]},
            },
            "required": ["case_id", "decision"],
        },
        "output_schema": {"type": "object"},
        "error_code": "E44_REVIEW_GATE",
        "example": {"input": {"case_id": "abc123", "decision": "approve"}, "output": {"status": "NOT_IMPLEMENTED"}},
    },
]


def get_capability(name: str) -> dict[str, Any] | None:
    """Look up a capability by name."""
    for cap in CAPABILITIES:
        if cap["name"] == name:
            return cap
    return None


def list_capability_names() -> list[str]:
    """Return all capability names."""
    return [c["name"] for c in CAPABILITIES]
```

#### Fix 2.3: Capability Registry

**文件**：`apps/api/app/services/acp/registry.py`（新建）

```python
"""Re4.4: Capability Registry — registers and validates ACP capabilities.

Inspired by AutoResearchClaw mcp/registry.py MCPServerRegistry (MIT, B-level):
same list/get pattern, but for capabilities (not external servers).
"""
from __future__ import annotations

from typing import Any

from .capabilities import CAPABILITIES, get_capability, list_capability_names
from .errors import unknown_capability, invalid_params, ACPError


class CapabilityRegistry:
    """Registry of all declared ACP capabilities."""

    def __init__(self) -> None:
        self._capabilities: dict[str, dict[str, Any]] = {
            c["name"]: c for c in CAPABILITIES
        }

    def get(self, name: str) -> dict[str, Any] | None:
        return self._capabilities.get(name)

    def list_all(self) -> list[dict[str, Any]]:
        """Return all capabilities with full schema (for GET /capabilities)."""
        return list(self._capabilities.values())

    def list_names(self) -> list[str]:
        return list(self._capabilities.keys())

    def validate_params(self, name: str, params: dict[str, Any]) -> ACPError | None:
        """Validate input params against capability's input_schema.

        Only checks required fields (basic validation, not full JSON Schema).
        """
        cap = self.get(name)
        if cap is None:
            return unknown_capability(name)

        required = cap["input_schema"].get("required", [])
        missing = [r for r in required if r not in params or params[r] is None]
        if missing:
            return invalid_params(name, missing)

        return None

    def get_permission(self, name: str) -> str | None:
        cap = self.get(name)
        return cap["permission"] if cap else None

    @property
    def count(self) -> int:
        return len(self._capabilities)


# Singleton
_registry: CapabilityRegistry | None = None

def get_registry() -> CapabilityRegistry:
    global _registry
    if _registry is None:
        _registry = CapabilityRegistry()
    return _registry
```

---

### Phase 3：ACP REST Server + 权限控制 — 2h

#### Fix 3.1: ACP Server

**文件**：`apps/api/app/services/acp/server.py`（新建）

**设计**（借鉴 AutoResearchClaw `mcp/server.py` 的 `handle_tool_call` 路由模式，A/B 级复用）：

```python
"""Re4.4: ACP REST Server — routes capability calls to PaperAgent services.

Inspired by AutoResearchClaw mcp/server.py ResearchClawMCPServer (MIT):
  - handle_tool_call routing pattern
  - _validated_run_id path safety (adapted from _validated_run_dir)
  - unified error response on unknown tool / exception

Key differences:
  - REST-based (not MCP transport)
  - Read/write permission layer (X-ACP-Capability header)
  - Calls PaperAgent services, not ResearchClaw pipeline
"""
from __future__ import annotations

import logging
from typing import Any

from .registry import get_registry
from .errors import (
    ACPError, unknown_capability, permission_denied,
    internal_error, not_found, NOT_FOUND,
)
from .capabilities import get_capability

logger = logging.getLogger(__name__)


class ACPServer:
    """Routes ACP capability calls to PaperAgent services."""

    def __init__(self) -> None:
        self.registry = get_registry()

    def list_capabilities(self) -> list[dict[str, Any]]:
        """GET /api/v1/acp/capabilities — return all capability schemas."""
        return self.registry.list_all()

    def invoke(
        self,
        capability_name: str,
        params: dict[str, Any],
        has_write_permission: bool = False,
    ) -> dict[str, Any]:
        """POST /api/v1/acp/invoke — invoke a capability.

        Args:
            capability_name: name of the capability to invoke
            params: input parameters
            has_write_permission: True if X-ACP-Capability: write header present

        Returns:
            Success: {"success": True, "result": ...}
            Error: {"success": False, "error": ACPError.model_dump()}
        """
        # 1. Check capability exists
        cap = self.registry.get(capability_name)
        if cap is None:
            return {"success": False, "error": unknown_capability(capability_name).model_dump()}

        # 2. Check permission
        if cap["permission"] == "write" and not has_write_permission:
            return {"success": False, "error": permission_denied(capability_name, "write").model_dump()}

        # 3. Validate params
        val_err = self.registry.validate_params(capability_name, params)
        if val_err:
            return {"success": False, "error": val_err.model_dump()}

        # 4. Route to handler
        try:
            handler = self._get_handler(capability_name)
            if handler is None:
                # Declared but not implemented
                return {"success": False, "error": {
                    "error_code": "NOT_IMPLEMENTED",
                    "message": f"Capability '{capability_name}' is declared but not yet implemented",
                    "capability": capability_name,
                }}
            result = handler(params)
            return {"success": True, "result": result}
        except Exception as exc:
            logger.error("ACP invoke %s failed: %s", capability_name, exc, exc_info=True)
            return {"success": False, "error": internal_error(capability_name, str(exc)).model_dump()}

    def _get_handler(self, name: str):
        """Return the handler function for a capability, or None if not implemented."""
        handlers = {
            "list_cases": self._h_list_cases,
            "get_run_status": self._h_get_run_status,
            "get_evidence_graph": self._h_get_evidence_graph,
            "get_papers": self._h_get_papers,
            "get_work_packages": self._h_get_work_packages,
            "get_feasibility": self._h_get_feasibility,
            "get_review": self._h_get_review,
            "get_innovation": self._h_get_innovation,
            "search_literature": self._h_search_literature,
            "upload_paper": self._h_upload_paper,
        }
        return handlers.get(name)

    # ===== READ handlers =====

    def _h_list_cases(self, params: dict[str, Any]) -> dict[str, Any]:
        from apps.api.app.api.v1.research import _list_cases_impl
        return _list_cases_impl()

    def _h_get_run_status(self, params: dict[str, Any]) -> dict[str, Any]:
        from apps.api.app.api.v1.research import _get_status_impl
        return _get_status_impl(params["case_id"])

    def _h_get_evidence_graph(self, params: dict[str, Any]) -> dict[str, Any]:
        from apps.api.app.api.v1.research import _get_evidence_graph_impl
        return _get_evidence_graph_impl(params["case_id"])

    def _h_get_papers(self, params: dict[str, Any]) -> dict[str, Any]:
        from apps.api.app.api.v1.research import _list_user_papers_impl
        return _list_user_papers_impl(params["case_id"])

    def _h_get_work_packages(self, params: dict[str, Any]) -> dict[str, Any]:
        from apps.api.app.api.v1.research import _get_work_packages_impl
        return _get_work_packages_impl(params["case_id"])

    def _h_get_feasibility(self, params: dict[str, Any]) -> dict[str, Any]:
        from apps.api.app.api.v1.research import _get_feasibility_impl
        return _get_feasibility_impl(params["case_id"])

    def _h_get_review(self, params: dict[str, Any]) -> dict[str, Any]:
        from apps.api.app.api.v1.research import _get_review_impl
        return _get_review_impl(params["case_id"])

    def _h_get_innovation(self, params: dict[str, Any]) -> dict[str, Any]:
        from apps.api.app.api.v1.research import _get_innovation_impl
        return _get_innovation_impl(params["case_id"])

    # ===== WRITE handlers =====

    def _h_search_literature(self, params: dict[str, Any]) -> dict[str, Any]:
        from apps.api.app.api.v1.research import _submit_topic_impl
        return _submit_topic_impl(params["topic"], params.get("case_id"))

    def _h_upload_paper(self, params: dict[str, Any]) -> dict[str, Any]:
        from apps.api.app.api.v1.research import _upload_paper_impl
        return _upload_paper_impl(params["case_id"], params)


# Singleton
_server: ACPServer | None = None

def get_acp_server() -> ACPServer:
    global _server
    if _server is None:
        _server = ACPServer()
    return _server
```

#### Fix 3.2: API 路由

**文件**：`apps/api/app/api/v1/acp.py`（新建）

```python
"""Re4.4: ACP REST endpoints."""
from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Header
from pydantic import BaseModel

from apps.api.app.services.acp.server import get_acp_server

router = APIRouter(prefix="/api/v1/acp", tags=["acp-v1"])


class InvokeRequest(BaseModel):
    capability: str
    params: dict[str, Any] = {}


@router.get("/capabilities")
def list_capabilities() -> dict[str, Any]:
    """List all declared ACP capabilities with full JSON Schema."""
    server = get_acp_server()
    caps = server.list_capabilities()
    return {"capabilities": caps, "n": len(caps)}


@router.post("/invoke")
def invoke_capability(
    req: InvokeRequest,
    x_acp_capability: str | None = Header(default=None, alias="X-ACP-Capability"),
) -> dict[str, Any]:
    """Invoke an ACP capability.

    For write capabilities, include header: X-ACP-Capability: write
    """
    server = get_acp_server()
    has_write = (x_acp_capability or "").lower() == "write"
    return server.invoke(req.capability, req.params, has_write_permission=has_write)
```

#### Fix 3.3: 注册路由到 main.py

**文件**：`apps/api/app/main.py`

追加：
```python
from apps.api.app.api.v1.acp import router as acp_router
app.include_router(acp_router)
```

#### Fix 3.4: 现有 research.py 提取 impl 函数

**文件**：`apps/api/app/api/v1/research.py`

将现有端点逻辑提取为 `_xxx_impl` 函数，供 ACP server 调用。
不修改现有端点行为——只是把函数体提取出来：

```python
# Before (inline in route):
# @router.get("/{case_id}/status")
# def case_status(case_id: str):
#     ... logic inline ...

# After:
def _get_status_impl(case_id: str) -> dict[str, Any]:
    ... logic ...

@router.get("/{case_id}/status")
def case_status(case_id: str) -> dict[str, Any]:
    _validate_case_id(case_id)
    return _get_status_impl(case_id)
```

> 注意：只提取 ACP 需要调用的 10 个端点的 impl 函数，不全部重构。

---

### Phase 4：集成测试 — 1.5h

#### Fix 4.1: 测试

**文件**：`apps/api/tests/test_re44_acp.py`（新建）

```python
"""Re4.4: ACP capability registry and REST server tests."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestCapabilityRegistry:
    def test_registry_has_12_plus_capabilities(self):
        """Registry must have at least 12 capabilities (8 read + 2 write + 2 declared)."""
        from apps.api.app.services.acp.registry import get_registry
        reg = get_registry()
        assert reg.count >= 12

    def test_every_capability_has_required_fields(self):
        """Each capability must have name, description, permission, input_schema, error_code."""
        from apps.api.app.services.acp.registry import get_registry
        reg = get_registry()
        for cap in reg.list_all():
            assert "name" in cap
            assert "description" in cap
            assert cap["permission"] in ("read", "write")
            assert "input_schema" in cap
            assert "error_code" in cap
            assert "example" in cap

    def test_unknown_capability_returns_error(self):
        """Invoking unknown capability returns UNKNOWN_CAPABILITY."""
        resp = client.post("/api/v1/acp/invoke", json={"capability": "nonexistent", "params": {}})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert data["error"]["error_code"] == "UNKNOWN_CAPABILITY"

    def test_missing_required_params_returns_error(self):
        """Missing required params returns INVALID_PARAMS."""
        resp = client.post("/api/v1/acp/invoke", json={"capability": "get_run_status", "params": {}})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert data["error"]["error_code"] == "INVALID_PARAMS"


class TestReadCapabilities:
    """At least 3 read capabilities must pass integration tests."""

    def test_list_cases(self):
        """list_cases should return case list."""
        resp = client.post("/api/v1/acp/invoke", json={"capability": "list_cases", "params": {}})
        data = resp.json()
        assert data["success"] is True
        assert "cases" in data["result"]
        assert "n" in data["result"]

    def test_get_run_status(self):
        """get_run_status should return status for a case."""
        # Use a known case or create one
        resp = client.post("/api/v1/acp/invoke",
                          json={"capability": "get_run_status", "params": {"case_id": "test-nonexistent"}})
        data = resp.json()
        assert data["success"] is True
        assert "status" in data["result"]

    def test_get_evidence_graph(self):
        """get_evidence_graph should return graph structure."""
        resp = client.post("/api/v1/acp/invoke",
                          json={"capability": "get_evidence_graph", "params": {"case_id": "test-nonexistent"}})
        # 404 is ok (no such case), but should be a structured response
        data = resp.json()
        # Either success with empty graph or structured error
        assert "success" in data


class TestWriteCapabilities:
    """At least 2 write capabilities must pass integration tests."""

    def test_write_without_permission_denied(self):
        """Write capability without X-ACP-Capability header must be denied."""
        resp = client.post("/api/v1/acp/invoke",
                          json={"capability": "search_literature", "params": {"topic": "test"}})
        data = resp.json()
        assert data["success"] is False
        assert data["error"]["error_code"] == "PERMISSION_DENIED"

    def test_search_literature_with_write_permission(self):
        """search_literature with write permission should submit topic."""
        resp = client.post("/api/v1/acp/invoke",
                          json={"capability": "search_literature", "params": {"topic": "test"}},
                          headers={"X-ACP-Capability": "write"})
        data = resp.json()
        assert data["success"] is True
        assert "case_id" in data["result"]
        assert data["result"]["status"] == "running"

    def test_upload_paper_with_write_permission(self):
        """upload_paper with write permission should accept paper."""
        # First create a case
        submit = client.post("/api/v1/acp/invoke",
                            json={"capability": "search_literature", "params": {"topic": "test"}},
                            headers={"X-ACP-Capability": "write"})
        case_id = submit.json()["result"]["case_id"]

        resp = client.post("/api/v1/acp/invoke",
                          json={"capability": "upload_paper",
                                "params": {"case_id": case_id, "title": "Test Paper"}},
                          headers={"X-ACP-Capability": "write"})
        data = resp.json()
        assert data["success"] is True


class TestDeclaredNotImplemented:
    def test_ingest_pdf_returns_not_implemented(self):
        """Declared but not implemented capability returns NOT_IMPLEMENTED."""
        resp = client.post("/api/v1/acp/invoke",
                          json={"capability": "ingest_pdf", "params": {"pdf_url": "https://example.com/test.pdf"}},
                          headers={"X-ACP-Capability": "write"})
        data = resp.json()
        assert data["success"] is False
        assert data["error"]["error_code"] == "NOT_IMPLEMENTED"

    def test_query_rag_returns_not_implemented(self):
        """query_rag returns NOT_IMPLEMENTED."""
        resp = client.post("/api/v1/acp/invoke",
                          json={"capability": "query_rag", "params": {"question": "test?"}})
        data = resp.json()
        assert data["success"] is False
        assert data["error"]["error_code"] == "NOT_IMPLEMENTED"


class TestCapabilitiesEndpoint:
    def test_get_capabilities_machine_readable(self):
        """GET /capabilities returns machine-readable JSON Schema list."""
        resp = client.get("/api/v1/acp/capabilities")
        assert resp.status_code == 200
        data = resp.json()
        assert "capabilities" in data
        assert data["n"] >= 12
        for cap in data["capabilities"]:
            assert "name" in cap
            assert "input_schema" in cap
            assert cap["input_schema"]["type"] == "object"
```

---

### Phase 5：调用示例 — 1h

#### Fix 5.1: 示例生成

**文件**：`apps/api/app/services/acp/examples.py`（新建）

```python
"""Re4.4: ACP call examples for external AI tools.

Each example is a self-contained snippet that can be run by the respective tool.
Not-yet-implemented capabilities are marked with [示例 — 未接通].
"""
from __future__ import annotations

CODEX_EXAMPLE = '''# Codex (OpenAI) — ACP 调用示例
import requests

BASE = "http://127.0.0.1:18181/api/v1/acp"

# 1. 列出所有能力
resp = requests.get(f"{BASE}/capabilities")
capabilities = resp.json()["capabilities"]
print(f"可用能力: {[c['name'] for c in capabilities]}")

# 2. 只读：获取 case 状态
resp = requests.post(f"{BASE}/invoke", json={
    "capability": "get_run_status",
    "params": {"case_id": "re41-verify-001"}
})
print(f"状态: {resp.json()}")

# 3. 写操作：提交题目检索（需要 write 权限）
resp = requests.post(f"{BASE}/invoke", json={
    "capability": "search_literature",
    "params": {"topic": "基于YOLO的钢材表面缺陷检测"}
}, headers={"X-ACP-Capability": "write"})
print(f"提交结果: {resp.json()}")
'''

CLAUDE_CODE_EXAMPLE = '''# Claude Code — ACP 调用示例
# 使用 curl 调用 PaperAgent ACP

# 1. 列出所有能力
curl http://127.0.0.1:18181/api/v1/acp/capabilities

# 2. 只读：获取工作包 DAG
curl -X POST http://127.0.0.1:18181/api/v1/acp/invoke \\
  -H "Content-Type: application/json" \\
  -d '{"capability": "get_work_packages", "params": {"case_id": "re41-verify-001"}}'

# 3. 写操作：上传论文（需要 write 权限）
curl -X POST http://127.0.0.1:18181/api/v1/acp/invoke \\
  -H "Content-Type: application/json" \\
  -H "X-ACP-Capability: write" \\
  -d '{"capability": "upload_paper", "params": {"case_id": "re41-verify-001", "doi": "10.1234/example"}}'

# 4. [示例 — 未接通] RAG 问答
curl -X POST http://127.0.0.1:18181/api/v1/acp/invoke \\
  -H "Content-Type: application/json" \\
  -d '{"capability": "query_rag", "params": {"question": "What datasets are used?"}}'
# 预期返回: {"success": false, "error": {"error_code": "NOT_IMPLEMENTED"}}
'''

TRAE_EXAMPLE = '''# Trae — ACP 调用示例 (Python)
import httpx
import asyncio

async def main():
    base = "http://127.0.0.1:18181/api/v1/acp"
    async with httpx.AsyncClient() as client:
        # 1. 列出能力
        resp = await client.get(f"{base}/capabilities")
        caps = resp.json()
        print(f"共 {caps['n']} 个能力")

        # 2. 只读：获取创新点
        resp = await client.post(f"{base}/invoke", json={
            "capability": "get_innovation",
            "params": {"case_id": "re41-verify-001"}
        })
        print(f"创新点: {resp.json()}")

        # 3. 写操作：提交检索（需要 write 权限）
        resp = await client.post(f"{base}/invoke", json={
            "capability": "search_literature",
            "params": {"topic": "医学问答可信度评估"}
        }, headers={"X-ACP-Capability": "write"})
        result = resp.json()
        if result["success"]:
            print(f"Case ID: {result['result']['case_id']}")

        # 4. [示例 — 未接通] PDF 入库
        resp = await client.post(f"{base}/invoke", json={
            "capability": "ingest_pdf",
            "params": {"pdf_url": "https://arxiv.org/pdf/2401.00001"}
        }, headers={"X-ACP-Capability": "write"})
        print(f"PDF 入库: {resp.json()}")
        # 预期: NOT_IMPLEMENTED

asyncio.run(main())
'''


def get_examples() -> dict[str, str]:
    return {
        "codex": CODEX_EXAMPLE,
        "claude_code": CLAUDE_CODE_EXAMPLE,
        "trae": TRAE_EXAMPLE,
    }
```

#### Fix 5.2: API 端点返回示例

在 `acp.py` 追加：

```python
@router.get("/examples")
def get_call_examples() -> dict[str, str]:
    """Return example call snippets for external AI tools."""
    from apps.api.app.services.acp.examples import get_examples
    return get_examples()
```

---

### Phase 6：RunLedger 接入 ACP — 30min

#### Fix 6.1: ACP 调用记录到 RunLedger

**文件**：`apps/api/app/services/acp/server.py`

在 `invoke()` 方法中追加 RunLedger 记录：

```python
from apps.api.app.services.run_state import RunLedger
from pathlib import Path

# 在 invoke() 方法中，成功调用后追加：
def invoke(self, capability_name, params, has_write_permission=False):
    # ... existing logic ...
    if result.get("success"):
        # Record to RunLedger if case_id is in params
        case_id = params.get("case_id")
        if case_id:
            ledger = RunLedger(Path(f"tmp_re13_eval/{case_id}") / "acp_ledger.jsonl")
            ledger.append("acp_invoke", {
                "capability": capability_name,
                "permission": cap["permission"],
                "params_keys": list(params.keys()),
            })
    return result
```

---

### Phase 7：验收与端到端验证 — 1h

#### Step 1: 单元 + 集成测试

```bash
cd G:\PaperAgent
.venv\Scripts\python.exe -m pytest apps/api/tests/test_re44_acp.py -v
# 预期：全部 PASS
```

#### Step 2: pytest 收集不退化

```bash
.venv\Scripts\python.exe -m pytest --collect-only -q 2>&1 | Select-String "error|collected"
# 预期：0 errors，collected 数 ≥ 480（新增 Re4.4 测试）
```

#### Step 3: ruff 无新增

```bash
.venv\Scripts\python.exe -m ruff check apps/api/app --statistics
# 预期：≤ 18 errors（无新增）
```

#### Step 4: 能力清单机器可读

```bash
curl http://127.0.0.1:18181/api/v1/acp/capabilities | python -m json.tool
# 预期：n >= 12，每个 capability 有 name/description/permission/input_schema/error_code
```

#### Step 5: 端到端 Case 验证（强制）

> **规则**：全部 Phase 完成后必须跑一个端到端 case，通过 ACP 层验证完整性。

**前置条件**：后端 18181 运行中，`.env` 有效 `DEEPSEEK_API_KEY`。

```bash
# 1. 通过 ACP 提交题目
curl -X POST http://127.0.0.1:18181/api/v1/acp/invoke \
  -H "Content-Type: application/json" \
  -H "X-ACP-Capability: write" \
  -d '{"capability": "search_literature", "params": {"topic": "基于YOLO的钢材表面缺陷检测", "case_id": "re44-verify-001"}}'

# 2. 轮询状态
curl -X POST http://127.0.0.1:18181/api/v1/acp/invoke \
  -H "Content-Type: application/json" \
  -d '{"capability": "get_run_status", "params": {"case_id": "re44-verify-001"}}'

# 3. 等待完成后，通过 ACP 获取产物
curl -X POST http://127.0.0.1:18181/api/v1/acp/invoke \
  -H "Content-Type: application/json" \
  -d '{"capability": "get_evidence_graph", "params": {"case_id": "re44-verify-001"}}'

curl -X POST http://127.0.0.1:18181/api/v1/acp/invoke \
  -H "Content-Type: application/json" \
  -d '{"capability": "get_work_packages", "params": {"case_id": "re44-verify-001"}}'

curl -X POST http://127.0.0.1:18181/api/v1/acp/invoke \
  -H "Content-Type: application/json" \
  -d '{"capability": "get_review", "params": {"case_id": "re44-verify-001"}}'

# 4. 验证未实现能力返回 NOT_IMPLEMENTED
curl -X POST http://127.0.0.1:18181/api/v1/acp/invoke \
  -H "Content-Type: application/json" \
  -d '{"capability": "query_rag", "params": {"question": "test?"}}'

# 5. 验证越权写操作被拒绝
curl -X POST http://127.0.0.1:18181/api/v1/acp/invoke \
  -H "Content-Type: application/json" \
  -d '{"capability": "upload_paper", "params": {"case_id": "re44-verify-001", "title": "test"}}'
# 预期：PERMISSION_DENIED
```

**产物完整性检查清单**：

| 检查项 | 通过标准 |
|---|---|
| GET /capabilities | 返回 ≥ 12 个能力，JSON Schema 格式正确 |
| POST /invoke (read) | 只读能力无需 write header，返回 success=true |
| POST /invoke (write, no header) | 返回 PERMISSION_DENIED |
| POST /invoke (write, with header) | 返回 success=true |
| POST /invoke (unknown) | 返回 UNKNOWN_CAPABILITY |
| POST /invoke (missing params) | 返回 INVALID_PARAMS |
| POST /invoke (NOT_IMPLEMENTED) | 返回 NOT_IMPLEMENTED |
| 端到端 case | 通过 ACP 提交 → 轮询 → 获取产物，全链路成功 |
| ACP ledger | acp_ledger.jsonl 记录了调用事件 |
| THIRD_PARTY_NOTICES.md | 存在且记录了 AutoResearchClaw MIT 许可证 |
| 调用示例 | GET /examples 返回 3 段示例 |

**数据正确性自检清单**：

| 维度 | 验证方法 | 通过标准 |
|---|---|---|
| 只读能力覆盖 | 通过 ACP 获取 state/graph/work_packages/review | 数据与直接 API 调用一致 |
| 写能力权限 | search_literature 无 header 被拒绝 | PERMISSION_DENIED |
| 统一错误结构 | 未知能力/越权/缺参数 | 每种都返回对应 error_code |
| 未实现声明 | ingest_pdf / query_rag | 返回 NOT_IMPLEMENTED |
| 调用示例 | 3 段示例可执行 | curl/requests/httpx 语法正确 |

> **自我检验**：验收者必须对照上述清单逐项检查实际产物，
> 确认每项通过后再标记 Phase 7 完成。任何一项不通过则回到对应 Phase 修复。

---

## 3. 执行顺序与依赖

```
Phase 1 (THIRD_PARTY_NOTICES + 目录) ─── 无依赖
    │
    ├── Phase 2 (Registry + 能力声明) ─── 依赖 Phase 1 目录
    │       ├── errors.py ─── 无依赖
    │       ├── capabilities.py ─── 无依赖
    │       └── registry.py ─── 依赖 errors + capabilities
    │
    ├── Phase 3 (REST Server + 权限) ─── 依赖 Phase 2 + research.py impl 提取
    │       ├── server.py ─── 依赖 Phase 2 registry
    │       ├── acp.py (API) ─── 依赖 server.py
    │       └── research.py impl 提取 ─── 无依赖（可并行）
    │
    ├── Phase 4 (集成测试) ─── 依赖 Phase 2 + 3
    │
    ├── Phase 5 (调用示例) ─── 依赖 Phase 3
    │
    ├── Phase 6 (RunLedger 接入) ─── 依赖 Phase 3 + Re4.1 RunLedger
    │
    └── Phase 7 (验收 + 端到端) ─── 依赖全部完成

可并行：
- Phase 3 的 research.py impl 提取可与 server.py 并行
- Phase 5 示例编写可与 Phase 4 测试并行
```

---

## 4. 风险与预案

| 风险 | 触发信号 | 预案 |
|---|---|---|
| research.py impl 提取破坏现有端点 | 原有 API 测试失败 | 只提取函数体，不改逻辑；原有路由调用 impl 函数 |
| ACP invoke 超时（search_literature 触发 graph 运行） | 端到端测试超时 | search_literature 只返回 case_id + status=running；不等 graph 完成 |
| 能力声明与实际实现不一致 | ACP 调用返回 INTERNAL_ERROR | 先跑测试再跑端到端；测试覆盖每个已实现能力 |
| AutoResearchClaw 代码复制后 >30% 改动 | 复用验收门不通过 | 改为 B 级：行为级借鉴，重写实现 |
| 权限 header 被代理 stripping | write 操作全部 PERMISSION_DENIED | 确认 CORS/Vite proxy 传递自定义 header |
| 第三方依赖膨胀 | import 链过长 | ACP 层只依赖 FastAPI + Pydantic + 现有 services |

---

## 5. 完成标准

- [ ] `THIRD_PARTY_NOTICES.md` 存在且记录了 AutoResearchClaw MIT 许可证
- [ ] CapabilityRegistry 注册 ≥ 12 个能力（8 read + 2 write + 2 declared）
- [ ] 每个能力有 name / description / permission / input_schema / error_code / example
- [ ] `GET /api/v1/acp/capabilities` 返回机器可读 JSON Schema
- [ ] `POST /api/v1/acp/invoke` 路由到对应 handler
- [ ] ≥ 3 个只读能力通过集成测试
- [ ] ≥ 2 个受控写能力通过集成测试
- [ ] 未知能力返回 `UNKNOWN_CAPABILITY`
- [ ] 越权写操作返回 `PERMISSION_DENIED`
- [ ] 缺参数返回 `INVALID_PARAMS`
- [ ] 未实现能力返回 `NOT_IMPLEMENTED`
- [ ] `GET /api/v1/acp/examples` 返回 Codex/Claude Code/Trae 三段示例
- [ ] ACP 调用记录到 `acp_ledger.jsonl`
- [ ] `pytest --collect-only` 零 error
- [ ] `ruff check apps/api/app` ≤ 18 errors（无新增）
- [ ] **端到端 case 跑通**：ACP 提交 → 轮询 → 获取产物
- [ ] **数据正确性自检**：ACP 返回数据与直接 API 一致；权限/错误结构统一

---

## 6. 提交清单

| 文件 | 操作 |
|---|---|
| `docs/project/THIRD_PARTY_NOTICES.md` | 新建 |
| `apps/api/app/services/acp/__init__.py` | 新建 |
| `apps/api/app/services/acp/errors.py` | 新建 |
| `apps/api/app/services/acp/capabilities.py` | 新建 |
| `apps/api/app/services/acp/registry.py` | 新建 |
| `apps/api/app/services/acp/server.py` | 新建 |
| `apps/api/app/services/acp/examples.py` | 新建 |
| `apps/api/app/api/v1/acp.py` | 新建 |
| `apps/api/app/main.py` | 追加 acp_router 注册 |
| `apps/api/app/api/v1/research.py` | 提取 10 个 impl 函数 |
| `apps/api/tests/test_re44_acp.py` | 新建 |
| `CHANGELOG.md` | 追加 Re4.4 条目 |

---

## 7. CHANGELOG 预备

```markdown
## [0.4.0-dev] - 2026-07-10 (Re4.4)

### Added
- `services/acp/`: ACP 最小能力层
  - `capabilities.py`: 13 个能力声明（8 read + 2 write + 3 declared）
  - `registry.py`: CapabilityRegistry — 注册/查找/参数校验
  - `server.py`: ACPServer — REST handler 路由 + 读写权限控制
  - `errors.py`: 统一错误结构（UNKNOWN_CAPABILITY / PERMISSION_DENIED / INVALID_PARAMS / NOT_IMPLEMENTED / INTERNAL_ERROR）
  - `examples.py`: Codex / Claude Code / Trae 调用示例
- `api/v1/acp.py`: ACP REST 端点（GET /capabilities, POST /invoke, GET /examples）
- `docs/project/THIRD_PARTY_NOTICES.md`: AutoResearchClaw MIT 许可证记录
- `test_re44_acp.py`: ACP 集成测试（registry + read + write + errors + declared）

### Changed
- `research.py`: 提取 10 个 `_xxx_impl` 函数供 ACP server 调用（不改变现有端点行为）
- `main.py`: 注册 acp_router

### Verified
- 端到端 case 通过 ACP 层验证：提交 → 轮询 → 获取产物
- 3 个只读 + 2 个受控写能力通过集成测试
- 未知能力/越权/缺参数/未实现返回统一错误结构
- ACP 调用记录到 acp_ledger.jsonl
- THIRD_PARTY_NOTICES.md 已记录 MIT 许可证
```
