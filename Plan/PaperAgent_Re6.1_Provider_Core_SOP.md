# PaperAgent Re6.1：Provider Core SOP

> **制定日期**：2026-07-11  
> **承接**：R6-0 基线冻结。  
> **周期**：4 个有效开发日。  
> **阶段门**：无 raw key 泄露 + SSRF 全绿 + provider API v2 可用。  
> **后继**：R6-2 Router Unification。  
> **门失败时**：暂停 UI（R6-3）和学术裁缝（R6-4），优先修底座。

---

## 1. 目标与非目标

### 1.1 目标

实现用户自定义 provider 的安全接入：URL 验证（SSRF 防护）、API key 安全存储
（SecretStore）、协议适配器、模型发现（discovery）与能力探测（probe）。

### 1.2 非目标

- 不做公网多租户密钥托管；
- 不做计费、团队共享 vault；
- 不做前端 UI（R6-3 负责）；
- 不改变生产 router 的消费逻辑（R6-2 负责）；
- 不做 LLM 输出 schema 校验（R6-2 负责）。

---

## 2. 产物/输出清单

| 编号 | 产物 | 路径/模块 | 格式 |
|---|---|---|---|
| D-01 | URL 安全策略模块 | `app/services/security/url_safety.py` | Python module |
| D-02 | ProviderProfile Pydantic schema | `app/services/providers/profile.py` | Pydantic v2 model |
| D-03 | SecretStore 抽象与实现 | `app/services/providers/secret_store.py` | Python module |
| D-04 | 协议适配器（OpenAI-compatible + Anthropic-like） | `app/services/providers/adapters/` | Python modules |
| D-05 | 模型发现服务 | `app/services/providers/discovery.py` | Python module |
| D-06 | 能力探测服务 | `app/services/providers/probe.py` | Python module |
| D-07 | Provider 管理 API v2 | `app/api/v1/providers.py` | FastAPI router |
| D-08 | 错误类型枚举 | `app/services/providers/errors.py` | Enum + TypedError |
| D-09 | Provider Ledger | `app/services/providers/ledger.py` | JSONL append-only |
| D-10 | L0 单元测试 | `apps/api/tests/test_re6/provider/` | pytest |
| D-11 | L1 emulator 集成测试 | `apps/api/tests/test_re6/provider/emulator/` | pytest |

---

## 3. 规范

### 3.0 允许的模型（全局约束）

**只允许通过 OpenCode proxy 接入以下两个模型，禁止第三个模型：**

| model_id | 标识 | 典型角色 |
|---|---|---|
| `deepseek-v4-flash` | DeepSeek V4 Flash | structured_extract / search_control / formatter / rag_answer |
| `big-pickle` | Big Pickle | evidence_critic / novelty_draft / narrative_write / premium_review |

- ProviderProfile 的 `models` 列表只能包含这两个 model_id；
- 模型发现（discovery）仍需实现，但运行时只绑定这两个 model_id；
- 能力探测（probe）对这两个模型逐项执行；
- 禁止注册或切换到其他模型。

### 3.1 URL 安全（SSRF）规则

| 规则 | 实现 |
|---|---|
| 协议 | 仅接受 `http`/`https`；默认仅 `https`；`http` 需显式 `local_mode` |
| DNS 解析后检查 | 拒绝 loopback (127.0.0.0/8)、private (10/172.16/192.168)、link-local (169.254)、metadata (169.254.169.254) |
| 重定向 | 禁止重定向到内网 IP；最多跟随 3 跳，每跳重新校验目标 |
| 端口 | 默认仅 443/80；`local_mode` 放开 11434(Ollama) 等白名单端口 |
| 超时 | 连接 5s、读取 30s |
| 响应大小 | discovery 响应 ≤ 1MB |
| 并发 | 每 provider 最多 2 个并发请求 |
| 错误正文 | 截断至 200 字符并 redaction（移除可能含 key 的 header） |
| local_mode | 仅在显式启用时允许 localhost；UI/API 必须明示风险 |

### 3.2 ProviderProfile schema

```python
class ProviderProfile(BaseModel):
    provider_id: str           # uuid4 或用户 slug
    label: str                 # 显示名
    protocol: Literal["openai_compatible", "anthropic_like"]
    base_url: str
    secret_ref: SecretRef      # 不存 raw key
    models: list[ModelInfo]
    capabilities: ProviderCapabilities
    status: Literal["active", "invalid", "disabled"]
    config_version: str        # uuid4，每次修改递增
    created_at: datetime
    updated_at: datetime

class SecretRef(BaseModel):
    type: Literal["session", "local_vault"]
    key_id: str                # OS keyring key 或 session key
    api_key_set: bool          # GET API 只返回此字段

class ModelInfo(BaseModel):
    model_id: str
    label: str | None = None
    discovery_source: Literal["auto", "manual"]
    probed_capabilities: ProbedCapabilities | None = None

class ProbedCapabilities(BaseModel):
    chat: bool
    json_object: bool
    json_schema: bool
    reasoning_envelope: bool
    streaming: bool
    probed_at: datetime
```

### 3.3 SecretStore 规则

| 规则 | 实现 |
|---|---|
| 默认 session-only | key 存于进程内存 dict，浏览器关闭/显式删除后不可恢复 |
| Save to local vault | 使用 OS keyring（Windows Credential Manager）或加密文件 |
| 主密钥 | 不入仓库；加密文件主密钥由用户环境变量提供 |
| GET API | 只返回 `api_key_set: bool` 和 `secret_ref.type` |
| 删除 profile | 同时删除 secret；ledger 保留无密钥 tombstone |
| 禁止 | key 进入 URL、query string、localStorage、trace、日志、错误正文、截图 |
| 切换 provider | 只影响新 run；历史 run 保留 snapshot 但不可恢复 key |

### 3.4 协议适配器

| 适配器 | 输入 | 输出 |
|---|---|---|
| OpenAI-compatible | `{messages, model, temperature, ...}` | OpenAI chat response |
| Anthropic-like | `{messages, model, temperature, ...}` | Anthropic message response |

适配器只负责协议转换，不做业务逻辑。输出在 R6-2 中由 ResponseEnvelope 归一化。

### 3.5 模型发现

```
1. 尝试 GET {base_url}/v1/models（OpenAI-compatible）
2. 200 → 解析 model 列表
3. 404/405 → 标记 discovery_unsupported，允许手工填 model
4. 401 → invalid_auth，不继续
5. 其他错误 → typed error
```

### 3.6 能力探测

对用户选定的 model 逐项探测：

| 探测项 | 方法 | 判定 |
|---|---|---|
| chat | 发送 `{"role":"user","content":"ping"}` | 有 content 即通过 |
| json_object | 发送 `response_format={"type":"json_object"}` | 返回合法 JSON |
| json_schema | 发送 `response_format={"type":"json_schema","json_schema":{...}}` | 返回符合 schema 的 JSON |
| reasoning_envelope | 检查响应是否含 `reasoning`/`thinking` 字段 | 有即通过 |
| streaming | 发送 `stream=true` | 收到 SSE chunk 即通过 |

探测结果写入 `ProbedCapabilities`。能列出 models 不代表模型可用，必须通过
selected-model probe。

### 3.7 错误类型

```python
class ProviderErrorType(str, Enum):
    invalid_auth = "invalid_auth"           # 401, 无效 key
    permission_denied = "permission_denied" # 403
    model_not_found = "model_not_found"     # 404
    rate_limited = "rate_limited"           # 429
    transient_network = "transient_network" # timeout, 5xx
    context_too_large = "context_too_large" # token 超限
    malformed_output = "malformed_output"   # 无 JSON, schema fail
    semantic_contract_fail = "semantic_contract_fail"  # ID 不存在等
    unsupported_protocol = "unsupported_protocol"      # 非预期响应
    discovery_unsupported = "discovery_unsupported"    # models endpoint 404
```

### 3.8 Provider Ledger

每次 provider 操作追加一条 JSONL：

```json
{
  "event": "created|updated|deleted|probed|discovered|switched",
  "provider_id": "...",
  "config_version": "...",
  "timestamp": "ISO-8601",
  "actor": "user|system",
  "details": {"error_type": "...", "model_id": "..."}
}
```

Ledger 不含 raw key。删除事件保留 tombstone：`{"event":"deleted","provider_id":"...","secret_purged":true}`。

---

## 4. 验证

### 4.1 L0：静态合同与安全单测

| 测试项 | 方法 | 门槛 |
|---|---|---|
| ProviderProfile schema 验证 | 构造合法/非法 profile | 非法字段被拒绝 |
| key redaction | GET `/api/v1/providers` 响应 | 无 raw key，只有 `api_key_set` |
| 日志无 key | 触发 provider 操作后搜索日志 | 0 匹配 key 模式 |
| trace 无 key | trace.json 中搜索 | 0 匹配 |
| 错误正文 redaction | 触发 401 错误 | 错误正文不含 Authorization header |
| URL SSRF：loopback | `http://127.0.0.1/v1/models` | 拒绝 |
| URL SSRF：private | `http://10.0.0.1/v1/models` | 拒绝 |
| URL SSRF：metadata | `http://169.254.169.254/...` | 拒绝 |
| URL SSRF：redirect to private | 302 → 10.0.0.1 | 拒绝 |
| URL SSRF：non-http scheme | `ftp://...` | 拒绝 |
| URL SSRF：local_mode off + localhost | `http://localhost:11434` | 拒绝 |
| URL SSRF：local_mode on + localhost | `http://localhost:11434` | 允许 |
| discovery success | emulator 返回 model 列表 | 解析正确 |
| discovery 404 | emulator 返回 404 | `discovery_unsupported`，允许手工填 |
| discovery 401 | emulator 返回 401 | `invalid_auth`，停止 |
| discovery malformed | emulator 返回非 JSON | typed error |
| probe chat | emulator 返回正常 chat | `chat: true` |
| probe json_object | emulator 返回 JSON | `json_object: true` |
| probe json_schema | emulator 返回符合 schema 的 JSON | `json_schema: true` |
| probe 失败 | emulator 返回非 JSON | `json_object: false` |
| secret 删除 | 删除 profile 后查询 keyring | secret 不存在 |
| ledger tombstone | 删除后查 ledger | 有 deleted 事件，无 key |

### 4.2 L1：Provider emulator 集成

| Emulator | 响应 | 预期 |
|---|---|---|
| openai-models | `GET /v1/models` 返回列表 | discovery 成功 |
| models-404 | `GET /v1/models` 返回 404 | 允许手工填 model |
| models-405 | `GET /v1/models` 返回 405 | 允许手工填 model |
| openai-chat | 标准 chat completion | probe chat 通过 |
| anthropic-like | messages/content blocks | probe chat 通过 |
| auth-401 | 401 Unauthorized | `invalid_auth`，停止 |
| auth-403 | 403 Forbidden | `permission_denied` |
| rate-429 | 429 Too Many Requests | `rate_limited` |
| server-503 | 503 Service Unavailable | `transient_network` |
| timeout | 请求超时 | `transient_network` |
| context-too-large | 400 + token limit | `context_too_large` |

**P0：L0 必须 100% 全绿。L1 最终 provider/model、error class 与 trace 断言一致。**

### 4.3 阶段门

- [ ] 无 raw key 泄露（L0 全绿）；
- [ ] SSRF 全绿（L0 全绿）；
- [ ] provider API v2 可完成 validate → discover → probe 全流程；
- [ ] 删除 profile 时 secret 同步删除；
- [ ] ledger 记录完整且无 key。
