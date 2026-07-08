# PaperAgent Re3.2 真实 LLM 验证与缺口填补 SOP

> 承接：Re3.1 代码层面完成（32/32 集成测试通过），但**从未跑过真实 LLM 端到端测试**
> 本 SOP 聚焦：**真正跑通 + 修审计发现的 bug + 补缺失功能 + 推进 TODO**
> 预计总时长：5-7 小时，分 6 个 Phase。
> 模型：DeepSeek (主)，StepFun (fallback)。

## 0. 审计发现总结

Re3.1 完工报告声称 32/32 集成测试通过，但报告中 §7 已知限制明确承认：
- **"前端 E2E 未跑"**
- **"3-case 验证未跑"**
- **"需要真实 API 调用（DeepSeek + 搜索适配器），本轮通过集成测试覆盖关键功能点"**

代码审计还发现以下问题：

| # | 严重度 | 问题 | 位置 |
|---|---|---|---|
| 1 | **P0** | verify.py 缺 `import re` 和 `import json`，LLM 返回字符串时会 NameError | verify.py L112-118 |
| 2 | **P0** | 从未跑过真实 LLM 端到端测试 | — |
| 3 | P1 | test_re1_2_graph_nodes.py 2 个失败：引用已废弃的 `paper_retriever` | test_re1_2_graph_nodes.py |
| 4 | P1 | DataCite 适配器缺失（Re3.0 设计了但从未创建） | adapters/ |
| 5 | P1 | CORE 适配器已实现但未注册到 REGISTRY | adapters/__init__.py |
| 6 | P1 | search_agent 只暴露 5 个工具，huggingface 和 kaggle 不可达 | search_agent.py L390 |
| 7 | P1 | rules.md 缺失（SOP 反复引用但文件不存在） | 根目录 |
| 8 | P2 | MAX_REPAIR_ROUNDS 双重定义：graph router 读 env，targeted_repair.py 硬编码 2 | research_graph.py L160 vs targeted_repair.py L35 |
| 9 | P2 | CHANGELOG.md 停在 v0.1.0-rc1，不含任何 Re2/Re3 内容 | CHANGELOG.md |
| 10 | P2 | adapters/__init__.py docstring 乱码（UTF-8/GBK 编码问题） | adapters/__init__.py |
| 11 | P2 | LLM router docstring 说 "DeepSeek flash" 但默认是 StepFun | llm_router.py |
| 12 | P2 | 45 个 legacy session 测试 collection error（引用已删除的模块） | apps/api/tests/test_session*.py |

## 1. 本轮目标

1. **真正跑通 3-case 真实 LLM 验证**——启动 uvicorn，用 DeepSeek + 真实搜索适配器跑完整 graph
2. **修复审计发现的 P0/P1 bug**——verify.py imports、stale tests、缺失适配器
3. **补齐缺失功能**——DataCite 适配器、CORE 注册、search_agent 工具扩展
4. **一致性修复**——MAX_REPAIR_ROUNDS、CHANGELOG、乱码修复
5. **前端 E2E 验证**——通过浏览器提交题目，确认 SSE + 结果展示
6. **推进 TODO**——评估下一批可做项

不做：
- 新增分析节点
- 前端大改
- Docker / 部署
- 100 篇全量回归（Re3.3）

## 2. Phase 设计

### Phase 1：P0 Bug 修复 (30min)

#### Fix 1.1: verify.py 缺失 import

**文件**：`apps/api/app/services/agents/graph/nodes/verify.py`

**问题**：`_normalise_verifier_output` 函数在 L112-118 使用 `re.search()` 和 `json.loads()`，但文件头只有 `import logging, os, time`。当 LLM 返回字符串（JSON 修复回退路径）时会触发 `NameError: name 're' is not defined`。

**修复**：

```python
# verify.py 文件头，在 import logging 后添加
import json
import re
```

**验证**：
```bash
.venv/Scripts/python.exe -c "
from apps.api.app.services.agents.graph.nodes.verify import _normalise_verifier_output
# 模拟 LLM 返回字符串
result = _normalise_verifier_output('[{\"title\":\"test\",\"verdict\":\"accept\"}]')
assert len(result) == 1
print('OK:', result)
"
```

#### Fix 1.2: test_re1_2_graph_nodes.py 更新

**文件**：`apps/api/tests/test_re1_2_graph_nodes.py`

**问题**：2 个测试失败：
- `test_graph_compiles_and_smoke_runs` (L116): 期望 `paper_retriever` 出现在 fire_names 中，但 Re3.0 将节点改名为 `search_agent`
- `test_node_modules_expose_expected_node_funcs` (L129): 期望 `paper_retriever` 模块属性，但实际是 `search_agent`

**修复**：

1. L116: `"paper_retriever"` → `"search_agent"`
2. L129: `"paper_retriever": "retrieve_node"` → `"search_agent": "search_agent_node"`
3. L82: `"paper_retriever"` → `"search_agent"` （14 节点列表中也更新）

**验证**：
```bash
.venv/Scripts/python.exe -m pytest apps/api/tests/test_re1_2_graph_nodes.py -v
# 期望：4 passed
```

#### Fix 1.3: rules.md 恢复

**文件**：`G:\PaperAgent\rules.md`（新建）

**问题**：SOP 反复引用 "遵循 rules.md 的全部规则"，但文件不存在。需从 git 历史恢复或重新创建。

**修复**：先检查 git 历史：
```bash
git log --all --oneline -- rules.md
```

如果 git 中有历史版本，`git show <commit>:rules.md > rules.md` 恢复。
如果没有，根据 CODELY.md 中的规则汇总重新创建最小版本，包含：
- 禁止硬编码 domain fallback
- 禁止硬编码 domain_map
- 禁止短关键词长度过滤
- 禁止 prompt 示例中的领域偏差
- 禁止硬编码 regex/blacklist 自检
- 搜索链规则（空查询用 topic、429 不阻塞、GitHub→repo_candidates）
- JSON 解析鲁棒性规则
- 异步并发规则
- 测试策略规则
- API 兼容性规则
- 合规边界

**验证**：`Test-Path G:\PaperAgent\rules.md` → True

### Phase 2：缺失功能补齐 (1h)

#### Fix 2.1: CORE 适配器注册

**文件**：`apps/api/app/services/retrieval/adapters/__init__.py`

**问题**：`core_search.py` 已完整实现（CORE.ac.uk v3，无需 API key），但未注册到 REGISTRY。

**修复**：

```python
# __init__.py imports 中添加
from .core_search import core_search

# REGISTRY 中添加
REGISTRY: dict[SearchSource, SourceFn] = {
    ...
    "core": _make_runner(core_search),
}
```

同时修复 `__init__.py` 的乱码 docstring（重写为可读中文或英文）。

**验证**：
```bash
.venv/Scripts/python.exe -c "
from apps.api.app.services.retrieval.adapters import REGISTRY
assert 'core' in REGISTRY
print('OK: core registered')
"
```

#### Fix 2.2: DataCite 适配器创建

**新文件**：`apps/api/app/services/retrieval/adapters/datacite_search.py`

DataCite Search API: `https://api.datacite.org/dois` — 无需 API key，返回 DOI 注册的 dataset 记录。

```python
"""DataCite DOI search adapter — searches datasets registered with DataCite."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

DATACITE_API = "https://api.datacite.org/dois"


async def datacite_search(
    queries: list[str],
    top_k: int = 8,
    *,
    client: Any | None = None,
) -> list[dict]:
    """Search DataCite for datasets. No API key required.

    Returns normalized dicts with title/abstract/year/doi/source='datacite'
    /evidence_type='dataset'. 429/5xx → return [] (don't raise).
    """
    qs = [q for q in (queries or []) if q and q.strip()][:1]
    if not qs:
        return []
    q = qs[0]

    try:
        import httpx

        params = {
            "query": q,
            "page[size]": min(top_k, 10),
            "page[number]": 1,
        }
        headers = {"Accept": "application/json"}

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as c:
            resp = await c.get(DATACITE_API, params=params, headers=headers)

        if resp.status_code >= 400:
            logger.info("datacite http %s | q=%s", resp.status_code, q)
            return []

        data = resp.json()
        results = []
        for item in (data.get("data") or [])[:top_k]:
            attrs = item.get("attributes") or {}
            titles = attrs.get("titles") or []
            title = titles[0].get("title", "") if titles else ""
            if not title:
                continue
            descriptions = attrs.get("descriptions") or []
            abstract = descriptions[0].get("description", "") if descriptions else ""
            year_raw = attrs.get("publicationYear")
            doi = attrs.get("doi", "")
            url = attrs.get("url") or (f"https://doi.org/{doi}" if doi else "")
            results.append({
                "title": str(title),
                "abstract": str(abstract)[:500] if abstract else "",
                "year": int(year_raw) if year_raw else None,
                "doi": doi,
                "url": url,
                "source": "datacite",
                "evidence_type": "dataset",
                "source_query": q,
            })
        return results
    except Exception as exc:
        logger.info("datacite fetch error: %s | q=%s", exc, q)
        return []
```

注册到 `adapters/__init__.py`：
```python
from .datacite_search import datacite_search
REGISTRY["datacite"] = _make_runner(datacite_search)
```

**验证**：
```bash
.venv/Scripts/python.exe -c "
import asyncio
from apps.api.app.services.retrieval.adapters.datacite_search import datacite_search
results = asyncio.run(datacite_search(['YOLO crop detection'], 5))
print(f'OK: datacite returned {len(results)} results')
for r in results[:2]:
    print(f'  - {r[\"title\"][:80]}')
"
```

#### Fix 2.3: search_agent 工具扩展

**文件**：`apps/api/app/services/agents/graph/nodes/search_agent.py`

**问题**：`available_tools` 硬编码为 5 个：`{arxiv, openalex, crossref, github, semantic_scholar}`。HuggingFace、Kaggle、CORE、DataCite 适配器虽已注册但 search_agent 无法调用。

**修复**：

1. 扩展 `available_tools`：
```python
# L390 附近
available_tools = {"arxiv", "openalex", "crossref", "github", "semantic_scholar",
                   "huggingface", "core", "datacite"}
```

2. 扩展 `_SYSTEM_PROMPT` 可用工具列表：
```
可用工具:
- arxiv: 搜预印本论文
- openalex: 搜学术期刊论文
- crossref: 搜DOI注册论文
- github: 搜代码仓库
- semantic_scholar: 搜高被引论文
- huggingface: 搜模型和数据集
- core: 搜开放获取论文
- datacite: 搜注册数据集
```

3. 扩展 `all_tool_order`（L425 附近）：
```python
all_tool_order = [tool for tool in (
    "arxiv", "openalex", "crossref", "github", "semantic_scholar",
    "huggingface", "core", "datacite"
) if tool in raw]
```

4. 扩展 `_fallback_decide` 中的适配器列表（如果存在硬编码列表也要更新）。

**验证**：
```bash
.venv/Scripts/python.exe -c "
from apps.api.app.services.agents.graph.nodes.search_agent import _SYSTEM_PROMPT
assert 'huggingface' in _SYSTEM_PROMPT
assert 'core' in _SYSTEM_PROMPT
assert 'datacite' in _SYSTEM_PROMPT
print('OK: all 8 tools in system prompt')
"
```

### Phase 3：一致性修复 (30min)

#### Fix 3.1: MAX_REPAIR_ROUNDS 统一

**文件**：`apps/api/app/services/agents/graph/nodes/targeted_repair.py`

**问题**：`targeted_repair.py` L35 硬编码 `MAX_REPAIR_ROUNDS = 2`，而 `research_graph.py` L160 读 `os.environ.get("PAPERAGENT_MAX_REPAIR_ROUNDS", "2")`。如果用户通过环境变量调大修复轮数，router 会继续路由但 node 会提前退出。

**修复**：

```python
# targeted_repair.py L35
# 修改前: MAX_REPAIR_ROUNDS = 2
# 修改后:
MAX_REPAIR_ROUNDS = int(os.environ.get("PAPERAGENT_MAX_REPAIR_ROUNDS", "2"))
```

**验证**：
```bash
.venv/Scripts/python.exe -c "
import os
os.environ['PAPERAGENT_MAX_REPAIR_ROUNDS'] = '5'
# 重新导入
import importlib
from apps.api.app.services.agents.graph.nodes import targeted_repair
importlib.reload(targeted_repair)
assert targeted_repair.MAX_REPAIR_ROUNDS == 5
print('OK: reads env var')
"
```

#### Fix 3.2: adapters/__init__.py 乱码修复

**文件**：`apps/api/app/services/retrieval/adapters/__init__.py`

**问题**：docstring 是乱码（UTF-8 文件被 GBK 解码）：`"""妫€绱妫€绱㈤€傞厤鍣ㄥ叆鍙? + 娉ㄥ唽琛?"""`

**修复**：重写 docstring 为英文（避免编码问题）：

```python
"""Search adapter registry. Each adapter has signature:
async def (queries: list[str], top_k: int, *, client) -> list[dict]
"""
```

`_make_runner` docstring 同样重写。

#### Fix 3.3: CHANGELOG.md 更新

**文件**：`G:\PaperAgent\CHANGELOG.md`

添加 `## [Unreleased]` 段落，记录 Re2.0-Re3.2 的所有变更：

```markdown
## [Unreleased]

### Added (Re3.0)
- React search agent: LLM-driven 8-step think→call→observe loop
- Reflection strategy switch: synonym/broaden/switch_tool for repair
- Search agent async-safe (_run_tool_sync for FastAPI BackgroundThreads)

### Added (Re3.1)
- User paper upload API (POST/GET /{case_id}/papers)
- arXiv full-text PDF retrieval + pypdf text extraction
- Crossref component type filtering in quality_filter
- Enhanced cross-adapter dedup (_dedup_key with DOI priority)
- Heuristic dataset extraction from paper titles (45+ known datasets)
- Frontend upload UI

### Added (Re3.2)
- CORE adapter registered to REGISTRY
- DataCite adapter for dataset DOI search
- search_agent expanded to 8 tools (added huggingface, core, datacite)
- rules.md restored

### Fixed (Re3.0)
- Removed hardcoded "deep learning" domain fallback
- Removed len(q) > 5 short keyword filtering (YOLO, SLAM, GAN now pass)
- Removed hardcoded domain_map
- Unified research_narrative field name (singular) across 4 files
- Fixed revision_count double increment (narrative_builder + optimization_advisor)
- recursion_limit=100 (was default 25, caused graph truncation)
- search_agent _run_tool_sync replaces asyncio.run() (no event loop crash)

### Fixed (Re3.2)
- verify.py missing import re, import json (NameError on string LLM output)
- test_re1_2_graph_nodes.py updated for search_agent (was paper_retriever)
- MAX_REPAIR_ROUNDS reads env var in targeted_repair.py (was hardcoded)
- adapters/__init__.py mojibake docstring fixed
```

#### Fix 3.4: LLM router docstring 修正

**文件**：`apps/api/app/services/llm_router.py`

**问题**：docstring 说 "fast_json → DeepSeek flash" 但实际默认是 StepFun。

**修复**：更新 docstring 反映实际配置：

```python
# docstring 修改为：
# fast_json: DeepSeek (env FAST_JSON_PRIMARY=deepseek) or StepFun (default)
```

### Phase 4：真实 LLM 端到端验证 (2-3h)

#### 4.1 环境准备

1. 确认 `.env` 有真实 API key：
```bash
# 检查关键变量
grep -E "DEEPSEEK_API_KEY|FAST_JSON_PRIMARY|LLM_PROFILE" .env
# 确认 DEEPSEEK_API_KEY 不是 YOUR_DEEPSEEK_KEY
```

2. 确认 pypdf 已安装：
```bash
.venv/Scripts/python.exe -c "import pypdf; print(pypdf.__version__)"
```

3. 启动 uvicorn：
```bash
.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 18181
```

4. 确认 health：
```bash
curl http://127.0.0.1:18181/health
```

#### 4.2 三案例验证

通过 API 提交 3 个题目，每个等待完成后检查 state.json + trace.json：

| Case ID | 题目 | 重点验证 |
|---|---|---|
| V-SLAM-32 | 基于深度学习的视觉SLAM语义地图的研究 | recursion_limit + search_agent React 循环 + dataset (KITTI) |
| V-MED-32 | 基于大语言模型的医学问答可信度评估方法研究 | devils_advocate + arXiv 全文 + feasibility |
| V-YOLO-32 | 基于yolo的农作物识别 | dataset (COCO/PlantVillage) + 短关键词 pass + repo |

**提交命令**（每个 case）：
```bash
# 提交
curl -X POST http://127.0.0.1:18181/api/v1/research/ \
  -H "Content-Type: application/json" \
  -d '{"topic": "基于深度学习的视觉SLAM语义地图的研究", "target_tier": "SCI-Q2"}'

# 记下返回的 case_id，然后轮询状态
curl http://127.0.0.1:18181/api/v1/research/{case_id}/status

# 完成后检查 state
curl http://127.0.0.1:18181/api/v1/research/{case_id}/state > tmp_re32_eval/V-SLAM-32_state.json

# 检查 trace
curl http://127.0.0.1:18181/api/v1/research/{case_id}/trace > tmp_re32_eval/V-SLAM-32_trace.json
```

#### 4.3 验证检查清单

对每个 case，检查以下项：

**P0 — 必须通过**：

| # | 检查项 | 验证方式 | 通过标准 |
|---|---|---|---|
| 1 | graph 完成无 RecursionError | trace.json 中无 RecursionError | ✅ |
| 2 | search_agent React 循环执行 | state.search_steps 非空 | ≥2 步 |
| 3 | search_agent 无 asyncio 崩溃 | trace.json 中无 "event loop is already running" | ✅ |
| 4 | verify_node 无 NameError | trace.json 中无 "name 're' is not defined" | ✅ |
| 5 | verified_papers 非空 | state.verified_papers | ≥3 篇 |
| 6 | research_narrative 非空 | state.research_narrative 有 ≥3 个 key | ✅ |
| 7 | devils_advocate 收到 narrative | review_report.dimension_scores 非空 | ✅ |
| 8 | 无 "deep learning" 硬编码 fallback | search_steps 中的 query 不含 "deep learning"（除非题目本身是） | ✅ |

**P1 — 应该通过**：

| # | 检查项 | 验证方式 | 通过标准 |
|---|---|---|---|
| 9 | dataset_candidates 非空 | state.dataset_candidates | ≥1（V-SLAM/V-YOLO） |
| 10 | repo_candidates 非空 | state.repo_candidates | ≥1（V-SLAM/V-YOLO） |
| 11 | GitHub 结果不在 verified_papers | verified_papers 中无 source=github | ✅ |
| 12 | 无重复论文 | verified_papers 标题去重 | 0 重复 |
| 13 | 无 Crossref 表格标题 | verified_papers 中无 "Table N:" / "Figure N:" | ✅ |
| 14 | review verdict 不是全 BLOCK | review_report.overall_verdict | 有区分度 |
| 15 | feasibility 有区分度 | feasibility_report.tier | 不是全 not_recommended |

**P2 — 加分项**：

| # | 检查项 | 验证方式 | 通过标准 |
|---|---|---|---|
| 16 | huggingface/core/datacite 被调用 | search_steps 中出现这些工具 | ≥1 次 |
| 17 | arXiv 全文获取成功 | trace.json 中有 fulltext 相关事件 | ✅ |
| 18 | 短关键词不被过滤 | V-YOLO 的 query 包含 "YOLO" | ✅ |

#### 4.4 失败处理

如果任何 P0 项失败：
1. 记录失败现象 + 完整 trace
2. 分析根因
3. 修复代码
4. 重跑该 case
5. 直到 P0 全部通过

如果 P1 项失败：
1. 记录但不阻塞
2. 在完工报告中标注
3. 列入 Re3.3 TODO

#### 4.5 标答对比

读取 `tmp_re30_eval/ground_truth/verified_ground_truth.json`，对每个 case：
- 关键词覆盖率 ≥ 0.3
- 论文方向相关度 ≥ 0.5
- feasibility 方向一致

### Phase 5：前端 E2E 验证 (30min)

#### 5.1 浏览器提交

1. 启动 uvicorn（如 Phase 4 已启动则跳过）
2. 打开浏览器：`http://127.0.0.1:18181/web/`
3. 在输入框输入：`基于yolo的农作物识别`
4. 点击提交
5. 观察 SSE 流式更新

#### 5.2 前端验证检查清单

| # | 检查项 | 通过标准 |
|---|---|---|
| 1 | 提交后显示 loading/progress | ✅ |
| 2 | SSE 事件流式更新 trace | 节点逐步出现 |
| 3 | 完成后显示论文列表 | ≥1 篇 |
| 4 | 完成后显示 repo 候选 | 可选（有就显示） |
| 5 | 完成后显示候选计数 | ✅ |
| 6 | 上传论文 UI 可用 | 能输入标题并添加 |
| 7 | 无 JS 控制台错误 | F12 → Console 无红色 |

#### 5.3 截图

截取以下画面（保存到 `tmp_re32_eval/screenshots/`）：
1. 提交后 loading 状态
2. SSE 流式更新中
3. 完成后论文列表
4. 上传论文 UI

### Phase 6：TODO 评估与推进 (30min)

#### 6.1 当前 TODO 清单

| # | TODO | 来源 | 评估 |
|---|---|---|---|
| 1 | PubMed E-utilities 接入 | Re3.1 §6 | 适合 Re3.3，医学领域补充 |
| 2 | Unpaywall 接入 | Re3.1 §6 | 适合 Re3.3，开放获取 PDF |
| 3 | ScienceDirect/Elsevier API | Re3.1 §6 | 适合 Re3.4，需 institutional key |
| 4 | 100 篇全量回归 | Re3.1 §6 | Re3.3，3-case 通过后 |
| 5 | 前端美化 | Re3.1 §6 | Re3.4 |
| 6 | LangSmith 集成 | Re3.0 草稿 | Re3.4，可观测性 |
| 7 | StageContract 机制 | Re3.0 对照 | Re4.0，架构级 |
| 8 | 45 个 legacy session 测试清理 | 本次审计 | Re3.3，技术债 |
| 9 | retrieve.py 死代码清理 | 本次审计 | Re3.3，legacy retrieve_node 已不使用 |

#### 6.2 推荐下一步（Re3.3 方向）

**方向 A：100 篇全量回归**（如果 3-case 全通过）
- 用 `re30_batch_run.py` 跑 20 篇（Batch20）
- 扩展到 50 篇、100 篇
- 按领域矩阵分析

**方向 B：搜索源补强**（如果搜索结果不足）
- PubMed（医学）
- Unpaywall（开放获取 PDF）
- CORE 已注册，但需验证实际返回结果质量

**方向 C：可观测性**（如果需要调试）
- LangSmith 集成
- 每个 node 的输入/输出日志
- 搜索决策可解释性

#### 6.3 技术债清单

需要在 Re3.2 中处理的：
- ✅ verify.py imports（Phase 1）
- ✅ test_re1_2_graph_nodes.py（Phase 1）
- ✅ rules.md（Phase 1）
- ✅ CORE 注册（Phase 2）
- ✅ DataCite 创建（Phase 2）
- ✅ search_agent 工具扩展（Phase 2）
- ✅ MAX_REPAIR_ROUNDS（Phase 3）
- ✅ CHANGELOG（Phase 3）
- ✅ 乱码修复（Phase 3）

推迟到 Re3.3 的：
- 45 个 legacy session 测试清理
- retrieve.py 死代码清理
- LLM router docstring drift（已修，但需确认所有 docstring）

## 3. 执行者规则

1. **Phase 1-3 必须在 Phase 4 之前完成**——先修 bug 再跑真实测试
2. **Phase 4 每个 case 独立提交**——一个完成后再提交下一个
3. **Phase 4 失败不跳过**——P0 项失败必须修复后重跑
4. **每 Phase 完成后写 changelog**
5. **遵循 CODELY.md 中的所有开发约定**
6. **禁止跳过 Phase**
7. **禁止修改已有 API 接口签名**（backward-compatible only）
8. **VOAPI/MiniMax = 0**（全程 DeepSeek/StepFun）
9. **所有 LLM 凭证从 .env 读取**

## 4. 验证方式

### 单元/集成测试
```bash
# Phase 1 完成后
.venv/Scripts/python.exe -m pytest apps/api/tests/test_re1_2_graph_nodes.py -v

# Phase 2 完成后
.venv/Scripts/python.exe -m pytest apps/api/tests -v --tb=line -k "re1_2 or re1_3 or quality_filter or dataset_repo"
```

### 真实 LLM 端到端
```bash
# Phase 4
# 启动 uvicorn，提交 3 个 case，检查 state.json + trace.json
```

### 前端 E2E
```bash
# Phase 5
# 浏览器提交 + 截图
```

### 标答对比
```bash
# Phase 4.5
# 读取 ground_truth.json，对比关键词/论文/feasibility 方向
```

## 5. 交付物

### 代码
| 文件 | 改动类型 | Phase |
|---|---|---|
| `apps/api/app/services/agents/graph/nodes/verify.py` | 🔧 补 import re, json | 1 |
| `apps/api/tests/test_re1_2_graph_nodes.py` | 🔧 paper_retriever→search_agent | 1 |
| `G:\PaperAgent\rules.md` | 🆕 恢复或重建 | 1 |
| `apps/api/app/services/retrieval/adapters/__init__.py` | 🔧 注册 core+datacite+修乱码 | 2 |
| `apps/api/app/services/retrieval/adapters/datacite_search.py` | 🆕 DataCite 适配器 | 2 |
| `apps/api/app/services/agents/graph/nodes/search_agent.py` | 🔧 扩展到 8 工具 | 2 |
| `apps/api/app/services/agents/graph/nodes/targeted_repair.py` | 🔧 MAX_REPAIR_ROUNDS 读 env | 3 |
| `G:\PaperAgent\CHANGELOG.md` | 🔧 添加 Unreleased 段落 | 3 |
| `apps/api/app/services/llm_router.py` | 🔧 docstring 修正 | 3 |

### 数据
| 文件 | 内容 |
|---|---|
| `tmp_re32_eval/V-SLAM-32_state.json` | V-SLAM 完整 state |
| `tmp_re32_eval/V-SLAM-32_trace.json` | V-SLAM trace |
| `tmp_re32_eval/V-MED-32_state.json` | V-MED 完整 state |
| `tmp_re32_eval/V-MED-32_trace.json` | V-MED trace |
| `tmp_re32_eval/V-YOLO-32_state.json` | V-YOLO 完整 state |
| `tmp_re32_eval/V-YOLO-32_trace.json` | V-YOLO trace |
| `tmp_re32_eval/changelog.md` | 本轮 changelog |
| `tmp_re32_eval/screenshots/` | 前端截图 |

### 报告
| 文件 | 内容 |
|---|---|
| `Plan/PaperAgent_Re3.2_完工报告.md` | 完工报告 |

## 6. 最终验收条件

| # | 条件 | 验证方式 | 优先级 |
|---|---|---|---|
| 1 | verify.py 有 import re 和 import json | 代码检查 | P0 |
| 2 | test_re1_2_graph_nodes.py 4/4 passed | pytest | P0 |
| 3 | rules.md 存在 | 文件检查 | P0 |
| 4 | CORE 在 REGISTRY 中 | 代码检查 | P1 |
| 5 | DataCite 适配器创建并注册 | 代码检查 + 功能测试 | P1 |
| 6 | search_agent 暴露 8 个工具 | 代码检查 | P1 |
| 7 | targeted_repair 读 env MAX_REPAIR_ROUNDS | 代码检查 | P1 |
| 8 | CHANGELOG 含 Re3.0-Re3.2 内容 | 文件检查 | P1 |
| 9 | adapters/__init__.py 无乱码 | 代码检查 | P2 |
| 10 | **3-case 真实 LLM 全部完成** | state.json 存在 | **P0** |
| 11 | **3-case 无 RecursionError** | trace.json 检查 | **P0** |
| 12 | **3-case verified_papers ≥3** | state.json 检查 | **P0** |
| 13 | **3-case research_narrative 非空** | state.json 检查 | **P0** |
| 14 | **3-case devils_advocate 收到 narrative** | state.json 检查 | **P0** |
| 15 | **3-case 无 "deep learning" 硬编码** | search_steps 检查 | **P0** |
| 16 | dataset_candidates 非空（V-SLAM/V-YOLO） | state.json | P1 |
| 17 | 前端提交显示结果 | 截图 | P1 |
| 18 | 前端上传论文 UI 可用 | 截图 | P2 |
| 19 | VOAPI/MiniMax = 0 | 全程 | P0 |
| 20 | changelog 完整 | 文件检查 | P1 |

## 7. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| DeepSeek API 限流 (429) | 中 | case 无法完成 | 等待重试，或切 StepFun |
| OpenAlex 429 | 高 | 搜索结果少 | search_agent 会跳过失败工具，用 Crossref/arXiv 替代 |
| S2 API 429 | 高 | 搜索结果少 | 同上，不阻塞 |
| graph 超时 (>5min) | 中 | case 未完成 | 检查 trace 定位卡在哪个 node |
| verify.py NameError 仍触发 | 低 | verify 崩溃 | Phase 1 已修复，Phase 4 验证 |
| 前端 JS 报错 | 低 | 显示异常 | F12 控制台检查，修复 |
| pypdf 未安装 | 低 | arXiv 全文获取失败 | Phase 4.1 已检查 |

## 8. 执行顺序

```
Phase 1 (30min): Fix verify.py + test + rules.md
       ↓
Phase 2 (60min): CORE + DataCite + search_agent tools
       ↓
Phase 3 (30min): MAX_REPAIR_ROUNDS + CHANGELOG + docstrings
       ↓
Phase 4 (2-3h):  真实 LLM 3-case 验证 ← 核心阶段
       ↓
Phase 5 (30min): 前端 E2E + 截图
       ↓
Phase 6 (30min): TODO 评估 + 完工报告
```

Phase 1-3 必须在 Phase 4 之前完成。Phase 4 是本轮的核心——之前的所有 SOP 从未真正跑通过完整 pipeline。如果 Phase 4 发现新 bug，回到 Phase 1 修复后重跑。
