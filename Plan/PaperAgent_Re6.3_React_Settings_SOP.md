# PaperAgent Re6.3：React Settings SOP

> **制定日期**：2026-07-11  
> **承接**：R6-2 Router Unification。  
> **周期**：3 个有效开发日。  
> **阶段门**：浏览器无 raw key + Wizard 全流程可用 + snapshot viewer 可显示。  
> **后继**：R6-4 Academic Tailor 2.0。

---

## 1. 目标与非目标

### 1.1 目标

新增 React Settings / Models 页面，包含 Provider Profiles 管理、Add Provider
Wizard、Role Routing Matrix 和 Run Snapshot Viewer。用户可在前端完成 provider
配置、模型发现、能力探测和角色绑定全流程。

### 1.2 非目标

- 不实现公网多租户密钥管理；
- 不做 provider 计费或用量统计；
- 不修改 LangGraph 节点业务逻辑；
- 不做移动端适配（桌面优先）。

---

## 2. 产物/输出清单

| 编号 | 产物 | 路径 | 格式 |
|---|---|---|---|
| D-01 | Settings 页面 | `apps/web-react/src/pages/Settings.tsx` | React + TS |
| D-02 | Provider Profiles 组件 | `apps/web-react/src/components/settings/ProviderProfiles.tsx` | React + TS |
| D-03 | Add Provider Wizard 组件 | `apps/web-react/src/components/settings/ProviderWizard.tsx` | React + TS |
| D-04 | Role Routing Matrix 组件 | `apps/web-react/src/components/settings/RoleRoutingMatrix.tsx` | React + TS |
| D-05 | Run Snapshot Viewer 组件 | `apps/web-react/src/components/settings/RunSnapshotViewer.tsx` | React + TS |
| D-06 | Security Notice 组件 | `apps/web-react/src/components/settings/SecurityNotice.tsx` | React + TS |
| D-07 | API client 扩展 | `apps/web-react/src/lib/api.ts` | TS functions |
| D-08 | TypeScript 类型定义 | `apps/web-react/src/types/providers.ts` | TS interfaces |
| D-09 | Playwright e2e 测试 | `apps/web-react/e2e/settings.spec.ts` | Playwright |
| D-10 | Navigation 集成 | `apps/web-react/src/components/Layout.tsx` | 改造现有代码 |

---

## 3. 规范

### 3.1 Provider Profiles 页

| 元素 | 内容 |
|---|---|
| 列表 | 每条显示 label、protocol、健康状态、模型数、secret 状态 |
| 操作 | 编辑、删除、切换 active |
| secret 状态 | 只显示 `api_key_set: bool`，不回显 key |
| 健康状态 | 上次 probe 结果摘要（chat/json_object/json_schema） |

### 3.2 Add Provider Wizard 流程

```
Step 1: 输入 label、protocol（dropdown: openai_compatible | anthropic_like）
Step 2: 输入 base_url、api_key
        → key 输入后立即从前端 state 清空，不回显
Step 3: 后端 validate URL（SSRF 检查）+ validate key
        → 失败时显示具体错误（invalid_auth / url_blocked / etc）
Step 4: 模型发现
        → auto: 显示发现的 model 列表，用户勾选
        → unsupported: 显示 "discovery unsupported"，允许手工填 model_id
Step 5: 能力探测
        → 对选定 model 逐项 probe（chat/json_object/json_schema/reasoning/streaming）
        → 按能力逐项展示 ✅ / ❌ / ⏳
Step 6: 角色绑定
        → 用户为每个 task role 选择 primary provider+model
        → 可选 fallback provider+model
        → 设置 temperature（默认 0.0，novelty_draft 允许 0.2）
Step 7: Save
        → 默认 session-only
        → "Save to local vault" 需额外确认
        → 生成 config_version
        → 提示：新 run 才使用新配置
```

### 3.3 Role Routing Matrix

| 列 | 内容 |
|---|---|
| Task Role | structured_extract / search_control / evidence_critic / novelty_draft / narrative_write / rag_answer / formatter |
| Primary | model dropdown：`deepseek-v4-flash` 或 `big-pickle`（仅此两项） |
| Fallback | model dropdown：`deepseek-v4-flash` 或 `big-pickle`（可选，仅此两项） |
| Temperature | number input |
| Heuristic Policy | allow / deny（默认 deny，formatter 允许） |
| Contract Version | 只读，显示当前 contract_id |

**模型白名单约束**：dropdown 只列出 `deepseek-v4-flash` 和 `big-pickle`，禁止输入其他 model_id。

### 3.4 Run Snapshot Viewer

- 从 case_id 查询其 RunModelSnapshot；
- 展示每个 task role 的实际 provider/model/contract/temperature；
- 展示 fallback 链；
- 展示 prompt hash 与 fixture hash；
- 只读，不可修改。

### 3.5 Security Notice

| 条目 | 显示内容 |
|---|---|
| 保存位置 | "Session only（浏览器关闭后失效）" 或 "Local vault（加密存储）" |
| Local mode | 若启用 localhost URL，显示 ⚠️ 警告 |
| 删除入口 | "删除 provider 将同时删除密钥，不可恢复" |
| 日志保护 | "API key 不会出现在日志、trace 或截图中" |
| 模型切换 | "切换 provider 只影响新的研究 case，不影响已完成的 case" |

### 3.6 体验规则

| 规则 | 实现 |
|---|---|
| key 不回显 | 输入后立即清空 state，后续步骤只显示 `api_key_set: true` |
| discovery 失败 ≠ 连接失败 | discovery_unsupported 时显示 "可手工填 model" |
| probe 逐项展示 | 每个能力独立显示 ✅/❌，不批量 loading |
| 模型切换只影响新 run | 切换后 toast 提示 |
| heuristic 标注 | 若 allow_heuristic=true，在 matrix 中显示 ⚠️ |
| reviewer independence | 若 novelty_draft 和 evidence_critic 使用相同 model，显示 "self-review" 警告 |

### 3.7 TypeScript 类型

```typescript
interface ProviderProfile {
  provider_id: string;
  label: string;
  protocol: "openai_compatible" | "anthropic_like";
  base_url: string;
  api_key_set: boolean;
  secret_type: "session" | "local_vault";
  models: ModelInfo[];
  status: "active" | "invalid" | "disabled";
  config_version: string;
}

interface ModelInfo {
  model_id: string;
  label: string | null;
  discovery_source: "auto" | "manual";
  probed_capabilities: ProbedCapabilities | null;
}

interface ProbedCapabilities {
  chat: boolean;
  json_object: boolean;
  json_schema: boolean;
  reasoning_envelope: boolean;
  streaming: boolean;
}

interface ModelPolicy {
  role: TaskRole;
  primary: { provider_id: string; model_id: string };
  fallbacks: Array<{ provider_id: string; model_id: string }>;
  contract_version: string;
  temperature: number;
  allow_heuristic: boolean;
  max_provider_attempts: number;
  max_format_repairs: number;
}

type TaskRole =
  | "structured_extract" | "search_control" | "evidence_critic"
  | "novelty_draft" | "narrative_write" | "rag_answer" | "formatter";
```

---

## 4. 验证

### 4.1 Playwright e2e 测试

| 测试 | 步骤 | 断言 |
|---|---|---|
| Wizard 全流程 | 输入 URL/key → discover → probe → role bind → save | profile 出现在列表中 |
| key 不回显 | 输入 key 后检查 DOM | 无 raw key 文本 |
| key 不在 React snapshot | 完成 wizard 后检查 React DevTools snapshot | 无 raw key |
| key 不在 network response | 拦截 API 响应 | 只有 `api_key_set: true` |
| discovery 失败 → 手工填 | emulator models endpoint 404 | 显示 "手工填 model"，可输入 |
| probe 逐项展示 | 等待 probe 完成 | 每个能力有 ✅/❌ |
| role binding 保存 | 选择 primary + fallback → save | matrix 更新 |
| 删除 provider | 点击删除 → 确认 | profile 消失，secret 被清除 |
| 切换只影响新 run | 切换 provider → 查看旧 case snapshot | 旧 snapshot 不变 |
| snapshot viewer | 打开旧 case snapshot | 显示 provider/model/contract |
| self-review 警告 | novelty_draft 和 evidence_critic 选同一 model | 显示 ⚠️ |
| local mode 警告 | 输入 localhost URL | 显示 ⚠️ 风险提示 |
| heuristic 警告 | 开启 allow_heuristic | matrix 显示 ⚠️ |

### 4.2 安全验证

| 验证项 | 方法 | 门槛 |
|---|---|---|
| 浏览器无 raw key | Playwright 拦截所有网络响应 | 0 匹配 key 模式 |
| localStorage 无 key | `localStorage.getItem(...)` | 无 key |
| React state 无 key | DevTools snapshot 检查 | 无 key |
| 截图无 key | Playwright screenshot | 无 key 文本 |
| Git 无 key | `git diff` 检查 | 无 key |

### 4.3 阶段门

- [ ] Wizard 可完成 validate → discover → probe → role bind → save 全流程；
- [ ] 浏览器端 0 raw key（L0 + Playwright 全绿）；
- [ ] Role Routing Matrix 可编辑并保存；
- [ ] Run Snapshot Viewer 可显示已有 case 的快照；
- [ ] 删除 provider 时 secret 同步删除；
- [ ] 切换只影响新 run 的提示可见。
