# Re1.1 坑坑洼洼（踩坑记录）

记录 Re1.1 落地过程中遇到的"与环境/依赖/Windows/LLM 接口"相关的坑。格式：**标题 → 现象 → 根因 → 修复**。

原则：积累后不反复踩；修了代码的在 SOP 修复清单里也要记。

---

## 1. Windows + bash 脚本批量 git mv 时 UTF-8 文件名被拆散成八进制字节子目录

**现象**：运行 `git ls-files Plan/ | while read p; do git mv "$p" Legcy/Plan/...`，结果 Plan 下许多中文文件名（如 `FIX-2_Validator输出.md`）在 Legcy/Plan 下变成许多 346/220/345... 等数字文件名的目录，原始文件还在 Plan 里但 git status 显示 `D`。

**根因**：`git ls-files` 在 bash/Cygwin 下输出八进制转义（`\345\256\214\345\267\245`），`read p` 读到的就是八进制字符串，git 当字面路径 → 找不到源文件 → 失败。

**修复**：用 Python 脚本（文件列表走 `os.listdir()` 而非 bash pipe），subprocess.run 传 list 参数（避免 shell 引号转义）。

**避免**：禁止批量 git mv 用 bash pipe；改用 Python。

---

## 2. 误删 `_chat_openai_compat_once` 中的 `return content`

**现象**：直接调用 `_chat_stepfun` 返回 `None`，导致所有 LLM 响应为空，进而整个 LLM-consuming graph 节点（verify / dataset_repo / work_package）全部报 `LLMUnavailable: stepfun returned empty content`。

**根因**：增加 reasoning-model content fallback 时把手误写没 `return content` 行。

**修复**：在 `apps/api/app/services/llm.py:_chat_openai_compat_once` 末尾补 `return content`。

**避免**：改该函数前后跑 `test_llm_router_re11.py::test_call_json_routes_to_adapter`。

---

## 3. StepFun step-3.7-flash 是推理模型，不会把结构化 JSON content 放 `content` 字段

**现象**：长 prompt 调用 step-3.7-flash，返回合法 HTTP 但 `content` 为空，思考内容在 `message.reasoning` 里。直接带 reasoning-fallback 会把 reasoning 当 result — 返回的是 thinking-out-loud 文字而非 JSON，整个 graph 失败。

**根因**：SOP 里没有区分 reasoning model / instruct model — StepFun 提供的 model 列表里 step-3.7-flash 是 reasoning 模型，默认输出到 `reasoning` 字段。

**修复**：`STEPFUN_MODEL` 改为 `step-1v-32k`（非推理，直接把 JSON 放 `content`）。

**避免**：新增 LLM 供应商时，第一步 probe 长 prompt（>500 字符）+ complex JSON schema 看 model 是否把结构放 `content`。不要用 reasoning 模型做 JSON 输出场景；预留执行路径用 instruct 模型。

---

## 4. StepFun base URL 分两个平面且会随时间切换

**现象**：`https://api.stepfun.com/step_plan`、`/step_plan/v1`、`/v1` 都曾在不同时段返回 200；过几分钟后 `/step_plan` 变 404，只有 `https://api.stepfun.com/v1`（bare）稳 200。

**根因**：StepFun 有多个 API surface（`/step_plan` 是"计划"管理，稳定 endpoint 是 `/v1/chat/completions`）；他们的内部路由会抖动或路径结构会变。

**修复**：默认 `base_url=https://api.stepfun.com`，legacy adapter 拼接 `/v1/chat/completions`，最终 URL 正好是 `https://api.stepfun.com/v1/chat/completions` — 实测最稳。`STEPFUN_MODEL` 走 user 给的 `step-1v-32k`。

**避免**：LLM 服务 URL 不要迷信文档；跑之前先 `curl -s <base>/models` 验证路径。

---

## 5. `.env` + `load_dotenv()` 的缓存陷阱

**现象**：手动修改 `.env`（比如把 `STEPFUN_BASE_URL` 从 `step_plan/v1` 改为 `https://api.stepfun.com`）后，正在运行的 Python 进程仍然读到旧值。

**根因**：`load_dotenv()` 只在首次导入 `apps.api.app.services.llm` 时调用一次；之后改 .env 不影响已加载值。

**修复**：脚本需要 live-read 时用 `dotenv_values(".env")`（每次都从盘读）。

**避免**：修改 `.env` 后重启 `.venv/Scripts/python.exe` 进程。

---

## 6. LangGraph 1.x `StateGraph` 没有 `.edges` 属性

**现象**：测试里写`G.edges` 抛 AttributeError。

**根因**：`CompiledStateGraph` 只有 `.nodes` 和 `.channels`；边是 channels 的数据。

**避免**：inspection 用 `G.nodes` + `G.channels`。

---

## 7. pytest 运行目录与 `__file__` 不一致 — 相对路径要用 `.` 定位

**现象**：脚本里`ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")` 在 Windows pytest 上报 missing dir。

**根因**：Windows 下 pytest invocation 时 `__file__` 可能相对化；os.path.dirname 逐级 up 的层级不对（Windows 上我当 4 levels up 结果当了 5）。

**修复**：用 `Path(__file__).resolve().parent.parent.parent.parent`（按需加 `.parent`）。

**避免**：路径一律 `Path(...).resolve()`，避免 `os.path.abspath` 与 `__file__` 混合。

---

## 8. 在 Multi-line Python print() 里用中文 + emoji + Windows 默认 GBK stdout

**现象**：GBK codec can't encode 错误，脚本被中断。

**根因**：Windows 默认 console 是 GBK，print 含 emoji/U+1Fxxx 或多字节中文时崩溃。

**修复**：用 `PYTHONIOENCODING=utf-8` 或 `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")`。

**避免**：bash template 里隐式设置 `PYTHONIOENCODING=utf-8`。

---

## 9. `generic_repos` 黑名单被修过但上游 `search_reflection_helpers.py` 缺 exports

**现象**：`import apps.api.app.services.agents.search_reflection_loop` 失败：`ImportError: cannot import name 'build_axis_bound_queries'`。

**根因**：Re10 FIX 系列重构期间 `search_reflection_helpers.py` 改了函数名，但 loop 的 import 没同步更新；旧 `_research_agent_compat.py` 里可能也有残留。这是上游遗留问题，不是 Re1.1 应该修的。

**修复**：Re1.1 retrieve adapter try/except 包裹，import 失败 fall through 到 `_FALLBACK_SEED`（确定性 placeholder 候选）— pipeline 其余部分继续可跑。

**避免**：不直接 import 遗留 loop；隔离在 adapter 层。

---

## 10. `.env` 中没有显式的 mode switch 时，legacy fallback 常会走错

**现象**：Hard-coded provider（如"DeepSeek 走 /v1/chat/completions"）在不同时间因服务端升级失败。

**修复**：保留 `DEEPSEEK_BASE_URL` 允许用户覆盖（不要硬 base）。

## 10. `.env` 中没有显式的 mode switch 时，legacy fallback 常会走错

**现象**：Hard-coded provider（如"DeepSeek 走 /v1/chat/completions"）在不同时间因服务端升级失败。

**修复**：保留 `DEEPSEEK_BASE_URL` 允许用户覆盖（不要硬 base）。

---

## 11. StepFun step-3.7-flash 是 reasoner 模型，max_tokens 必须给大

**现象**：小 max_tokens (≤1000) 调用 step-3.7-flash 时 `content` 字段被截断为 `{}` 或空字符串，thinking 在 `reasoning` 字段里。

**修复**：verify/dataset_repo/work_package 的 max_tokens 给到 6000-8000（reasoning 占 1-2k，JSON 占 1-3k）。

**避免**：reasoner 模型调用前检查 `LLM_THINKING_BUDGET` env；instruct 模型 (step-1v-32k) 不需要。

---

## 12. verify fallback 转发 vs 隔离 — 选了隔离

**现象**：verify_node 失败时，初版代码把候选全部 forward (verdict=`forwarded_no_verify`) — 违反 SOP §15。

**修复**：改为隔离全部候选 (verified=[])，错误写入 trace。

**代价**：拒真率上升。**P0 修复**：3 阶段稳健提取 (regex → schema normalize → fallback LLM)。

---

## 13. 上游 `search_reflection_helpers.build_axis_bound_queries` 缺失

**现象**：`import search_reflection_loop` 失败 → retrieve_node 走 fallback seed。

**修复**：Re1.1 已补 `build_axis_bound_queries` + `flatten_axis_terms` 两个 helper。

**避免**：上游重构时 grep 所有 import 点。

---

## 14. 模型适配不应绑死

**现象**：step-1v-32k 能力差 (verify accept=0)；step-3.7-flash 是 reasoner 需大 max_tokens。

**修复**：通过 env (`STEPFUN_MODEL`, `FAST_JSON_PRIMARY`, `LLM_THINKING_BUDGET`) 切换，不改代码。

**避免**：新增模型时只加 adapter + 默认 profile；不要写死 max_tokens。

---

> 更新时间：2026-07-05 Re1.1 完工。每次遇到新的环境坑都追加。
