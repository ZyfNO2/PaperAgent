# PaperAgent Re3.1 前端打通与质量打磨 SOP

> 承接：Re3.0 全链路重新设计完成（Batch20 报告显示后端结果良好）
> **本 SOP 聚焦：前端能跑出后端报告中的效果 + 遗留质量问题清理。**
> 预计总时长：4-6 小时，分 5 个 Phase。
> 模型：DeepSeek (主)。

## 0. 核心问题

Re3.0 的 Batch20 报告（`Plan/PaperAgent_Re3.0_Batch20_成功结果与标答.md`）显示后端结果很好：
- 13/14 case 有论文（2-21 篇 verified）
- 10/14 case 有 repo（1-12 个）
- 8/14 case 有创新点 + 缝合方案 + 研究叙事
- feasibility 有区分度：feasible(85) / risky(55) / not_recommended(25)
- review 有区分度：ACCEPT / MINOR_REVISION / BLOCK

**但前端测试时"啥也没显示"**。根因有三层：

### 问题 1：recursion_limit 未设

`research.py` 的 `_run_case_sync` 和 `re30_batch_run.py` 都没有设 `recursion_limit`。LangGraph 默认 25，但 20 节点 + repair loop + citation expansion 二次循环 + devils_advocate 回环，实际步数可能超 25 → graph 截断 → 前端空。

### 问题 2：search_agent_node 用 asyncio.run() 嵌套

`search_agent.py` 的 `search_agent_node` 内部用 `asyncio.run(_run_tool(tool, query, 12))`。但 `_run_case_sync` 已经在后台线程中运行（FastAPI BackgroundTasks），如果线程中已有 event loop，`asyncio.run()` 会报 `RuntimeError: This event loop is already running`。batch 脚本在纯 Python 进程中跑没问题，但通过 API 跑会崩。

### 问题 3：research_narratives 字段名仍不匹配

`state.py` 定义 `research_narratives`（复数），`__init__.py` NODE_FIELDS 也是 `research_narratives`（复数），`narrative_builder.py` 返回的 key 也是 `research_narratives`。但 `devils_advocate_node.py` 如果读的是 `research_narrative`（单数）就会拿到空值。需要确认所有文件统一。

## 1. 本轮目标

1. **前端能跑出 Batch20 报告中的效果**——修 recursion_limit + asyncio 嵌套
2. **dataset/repo 提取增强**——DataCite 接好 + LLM prompt 增强
3. **devils_advocate 调优**——确认字段名 + 降低 BLOCK
4. **用户上传论文功能**——API + 前端入口
5. **arXiv 全文获取**——从 PDF 提取更准确的 dataset/repo

不做：

- 新增分析节点
- 前端大改（只加上传入口 + 修 bug）
- Docker / 部署
- 100 篇全量

## 2. Phase 设计

### Phase 1：前端打通修复 (1h)

#### Fix 1.1: recursion_limit

**文件**：`apps/api/app/api/v1/research.py`

```python
# _run_case_sync 函数中
out = g.invoke(state_in, config={
    "configurable": {"thread_id": case_id},
    "recursion_limit": 100  # 默认 25 不够，20 节点 + repair + citation + devils 回环
})
```

**文件**：`apps/api/scripts/re30_batch_run.py`

```python
out = g.invoke(state_in, config={
    "configurable": {"thread_id": case_id},
    "recursion_limit": 100
})
```

#### Fix 1.2: search_agent asyncio 嵌套

**文件**：`apps/api/app/services/agents/graph/nodes/search_agent.py`

当前 `search_agent_node` 内部用 `asyncio.run(_run_tool(...))`。这在纯 Python 进程中没问题，但在 FastAPI 后台线程中会报 `RuntimeError: This event loop is already running`。

**方案 A（最简）**：改为同步调用适配器

适配器函数都是 `async def`，但在后台线程中可以用 `asyncio.run()`。问题是如果线程中已有 event loop 就会报错。

**方案 B（推荐）**：用 `asyncio.get_event_loop().run_until_complete()` 或 `nest_asyncio`

```python
# 在 search_agent_node 中，替换 asyncio.run(_run_tool(tool, query, 12))
import asyncio

def _run_tool_sync(tool: str, query: str, top_k: int = 12) -> list[dict[str, Any]]:
    """同步调用适配器，兼容已有 event loop 的环境。"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 已有 loop 运行中，用线程池跑
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _run_tool(tool, query, top_k))
                return future.result()
        else:
            return loop.run_until_complete(_run_tool(tool, query, top_k))
    except RuntimeError:
        # 没有 event loop，直接 asyncio.run
        return asyncio.run(_run_tool(tool, query, top_k))
```

然后调用改为 `results = _run_tool_sync(tool, query, 12)`。

#### Fix 1.3: 确认 research_narratives 字段名

检查以下文件中 `research_narrative` vs `research_narratives`：

- `state.py`：当前是 `research_narratives`（复数）
- `__init__.py` NODE_FIELDS：当前是 `research_narratives`（复数）
- `narrative_builder.py`：检查 return 中的 key
- `devils_advocate_node.py`：检查 `state.get("research_???")` 读的是哪个

**如果 narrative_builder 返回 `research_narratives` 且 state 定义也是 `research_narratives`，但 devils_advocate 读 `research_narrative`（单数）→ 数据丢失。**

统一为 `research_narratives`（复数，因为 state.py 已经是这个）。

#### 验证

启动 uvicorn，通过前端提交"基于深度学习的视觉SLAM语义地图的研究"：
- [ ] graph 完成无 RecursionError
- [ ] search_agent 不报 asyncio 错误
- [ ] 前端显示论文列表 + repo + 候选计数
- [ ] devils_advocate 收到非空 narrative

### Phase 2：dataset/repo 提取增强 (1h)

#### 问题

Batch20 报告显示 14 个 case 中 14/14 dataset_candidates 为空。虽然 repo 有 10/14 非空，但 dataset 全空。

根因：
1. `dataset_repo_extractor` 的 LLM prompt 只从论文摘要提取，但很多摘要不提数据集名
2. DataCite 适配器（Re3.0 Phase 3 设计了）可能没接好或没注册
3. GitHub 搜索结果的"摘要"是 repo 描述，不含数据集名

#### Fix 2.1: DataCite 适配器确认

检查 `apps/api/app/services/retrieval/adapters/__init__.py` 是否注册了 `datacite`。如果没有，创建 `datacite_search.py` 并注册。

检查 `search_agent.py` 的 `_SYSTEM_PROMPT` 是否列了 `datacite` 工具。如果没有，加上。

#### Fix 2.2: dataset_repo_extractor prompt 增强

**文件**：`apps/api/app/services/agents/prompts/re11_dataset_repo_extractor.py`

当前 prompt 只说"从论文摘要中提取"。改为"从论文标题和摘要中提取"：

```
Paper: {title}
Abstract: {abstract}

Extract dataset and code links that the PAPER itself mentions in its title or abstract.
Many papers mention datasets in the title (e.g., "NEU-DET dataset", "KITTI benchmark")
or in the abstract ("we evaluate on COCO dataset").
```

#### Fix 2.3: 从 verified_papers 的标题中 heuristic 提取数据集名

在 `dataset_repo_extractor.py` 中，LLM 提取后，heuristic 补充：

```python
# 从 verified_papers 的标题中识别已知数据集名
_KNOWN_DATASETS = [
    "NEU-DET", "GC10-DET", "COCO", "Pascal VOC", "ImageNet",
    "KITTI", "TUM RGB-D", "EuRoC", "Bonn", "ScanNet",
    "Cityscapes", "nuScenes", "DOTA", "GTSRB", "GTSDB",
    "PlantVillage", "PlantDoc", "IP102", "DeepCrack",
    "SDNET2018", "BDD100K", "TT100K", "LIDC-IDRI", "LUNA16",
    "VisDrone", "Matterport3D", "ETH3D", "Cornell Grasping",
]

for p in verified_papers:
    title = (p.get("title") or "").lower()
    for ds in _KNOWN_DATASETS:
        if ds.lower() in title:
            # 添加到 dataset_candidates
```

**注意**：这不是硬编码黑名单——这是已知数据集注册表，用于从论文标题中 heuristic 提取。LLM 仍然是主路径，heuristic 只是补充。

#### 验证

V-SLAM: dataset_candidates 应有 KITTI 或 TUM RGB-D（从 verified_papers 标题中提取）。
V-YOLO: dataset_candidates 应有 COCO 或 PlantVillage。

### Phase 3：devils_advocate 调优 (45min)

#### 问题

Batch20 报告显示 review verdict 分布：
- ACCEPT: 4/14
- MINOR_REVISION: 7/14
- BLOCK: 1/14
- 空: 2/14（graph 未完成）

这比之前好很多（之前全是 BLOCK）。但仍需确认：
1. Fix 1.3 的字段名修复是否生效（narrative 数据不丢失）
2. 有 baseline + 有创新点 + 有工作包时不应 BLOCK

#### Fix 3.1: 确认 devils_advocate_node 读的叙事字段

```python
# devils_advocate_node.py 中
# 确认读的是 state.get("research_narratives") 还是 state.get("research_narrative")
# 必须和 state.py 的字段名一致
```

#### Fix 3.2: devils_advocate prompt 微调

如果 Phase 1.3 修复后仍有过多 BLOCK，检查 prompt 是否需要进一步调整。

#### 验证

V-MED: review 应为 ACCEPT 或 MINOR_REVISION（不应 BLOCK，因为有 baseline + innovation + narrative）。

### Phase 4：用户上传论文功能 (1.5h)

#### 需求

用户知道自己 baseline 是哪篇论文，应该能通过 API/前端上传。上传后：
- 论文进入 verified_papers（直接 accept）
- 如果有 DOI，查 Crossref 补全元数据
- 作为引文扩展的种子论文

#### API 端点

**文件**：`apps/api/app/api/v1/research.py`

```python
_USER_PAPERS: dict[str, list[dict]] = {}

@router.post("/{case_id}/papers")
async def upload_paper(case_id: str, payload: dict) -> dict:
    """用户上传论文。

    payload:
    {
        "title": "YOLOv5: Real-time object detection",
        "doi": "10.xxx/yyy",       # 可选
        "arxiv_id": "2106.12345",  # 可选
        "url": "https://...",      # 可选
        "role": "baseline"         # 可选
    }
    """
    paper = {
        "title": payload.get("title", ""),
        "doi": payload.get("doi"),
        "arxiv_id": payload.get("arxiv_id"),
        "url": payload.get("url"),
        "verdict": "accept",
        "relation_to_topic": payload.get("role", "baseline"),
        "source": "user_upload",
    }
    _USER_PAPERS.setdefault(case_id, []).append(paper)
    return {"case_id": case_id, "n_papers": len(_USER_PAPERS[case_id])}
```

在 `_run_case_sync` 中注入（已有代码，确认生效）：

```python
user_papers = _USER_PAPERS.pop(case_id, None)
if user_papers:
    state_in["user_papers"] = user_papers
```

在 `intake_node` 中处理 `user_papers`：直接追加到 `verified_papers` 和 `seed_papers`。

#### 前端入口

在 `apps/web/index.html` 输入区下方加：
- 文本框：输入标题/DOI/arXiv ID
- 下拉：选择 role（baseline/parallel）
- 按钮：添加

#### 验证

上传 1 篇论文 → 提交题目 → 论文出现在 verified_papers 中 → 引文扩展用作种子。

### Phase 5：arXiv 全文获取 (1h)

#### 需求

从 arXiv 拿论文 PDF 全文，用于更准确的 dataset/repo 提取。

#### 新文件

**文件**：`apps/api/app/services/retrieval/arxiv_fulltext.py`

```python
"""arXiv full-text PDF fetcher. Downloads PDF, extracts text with pypdf."""

import httpx
import pypdf
import io

async def fetch_arxiv_fulltext(arxiv_id: str) -> str:
    url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    try:
        async with httpx.AsyncClient(timeout=30.0) as c:
            r = await c.get(url, follow_redirects=True)
            if r.status_code != 200:
                return ""
            pdf = pypdf.PdfReader(io.BytesIO(r.content))
            text = ""
            for page in pdf.pages[:10]:
                text += page.extract_text() or ""
            return text[:5000]
    except Exception:
        return ""
```

#### 接入

在 `dataset_repo_extractor.py` 中，对有 arxiv_id 的论文获取全文：

```python
# 在 _extract_one 函数中
arxiv_id = paper.get("arxiv_id")
if arxiv_id:
    fulltext = await fetch_arxiv_fulltext(arxiv_id)
    if fulltext:
        built = P.build(title, fulltext[:800])  # 传全文而非摘要
```

**注意**：pypdf 已在 pyproject.toml 依赖中。只对有 arXiv ID 的论文获取全文。超时不阻塞。

#### 验证

V-MED: 有 arXiv ID 的论文，检查 dataset/repo 提取是否改善。

## 3. 验证方式

### 3-case 验证

| Case | 题目 | 重点 |
|---|---|---|
| V-SLAM | 基于深度学习的视觉SLAM语义地图的研究 | recursion_limit + asyncio + dataset |
| V-MED | 基于大语言模型的医学问答可信度评估方法研究 | devils_advocate + 全文获取 |
| V-YOLO | 基于yolo的农作物识别 | dataset + 用户上传 |

### 前端验证

通过浏览器提交题目，确认：
- graph 完成无 RecursionError
- 前端显示论文列表 + repo + 候选计数
- devils_advocate 收到非空 narrative
- 上传论文功能可用

### 标答对比

读取 `tmp_re30_eval/ground_truth/verified_ground_truth.json`，按 rules.md §8 自查标准判断。

## 4. 执行者规则

遵循 `rules.md` 的全部规则。补充：
- 每次改动后跑 3-case 验证
- 验证失败回滚
- 禁止跳过 Phase

## 5. 交付物

代码：
- `apps/api/app/api/v1/research.py` 🔧 (Fix 1.1: recursion_limit + Phase 4: upload 端点)
- `apps/api/app/services/agents/graph/nodes/search_agent.py` 🔧 (Fix 1.2: asyncio 嵌套)
- `apps/api/app/services/agents/graph/nodes/devils_advocate_node.py` 🔧 (Fix 3.1: 字段名)
- `apps/api/app/services/agents/graph/nodes/dataset_repo_extractor.py` 🔧 (Phase 2 + 5)
- `apps/api/app/services/agents/prompts/re11_dataset_repo_extractor.py` 🔧 (Phase 2)
- `apps/api/app/services/retrieval/adapters/datacite_search.py` 🆕 (Phase 2: 如需)
- `apps/api/app/services/retrieval/adapters/__init__.py` 🔧 (Phase 2: 注册 datacite)
- `apps/api/app/services/retrieval/arxiv_fulltext.py` 🆕 (Phase 5)
- `apps/web/index.html` 🔧 (Phase 4: 上传 UI)
- `apps/api/scripts/re30_batch_run.py` 🔧 (Fix 1.1: recursion_limit)

数据：
- `tmp_re31_eval/verify/` (3-case 验证)
- `tmp_re31_eval/changelog.md`

报告：
- `Plan/PaperAgent_Re3.1_完工报告.md`

## 6. TODO（不在本轮做）

- PubMed E-utilities 接入
- Unpaywall 接入
- ScienceDirect/Elsevier API
- 100 篇全量回归
- 前端美化
- LangSmith 集成（Re3.0 草稿已设计）

## 7. 最终验收条件

| # | 条件 | 验证方式 |
|---|---|---|
| 1 | recursion_limit 设为 100 | 代码检查 |
| 2 | search_agent 无 asyncio 嵌套错误 | 前端提交不崩 |
| 3 | research_narratives 字段名统一 | devils_advocate 收到非空 |
| 4 | 前端显示论文/repo/候选 | 前端提交看到结果 |
| 5 | dataset_candidates 非空（V-SLAM/V-YOLO） | 3-case |
| 6 | devils_advocate 不全是 BLOCK | 3-case |
| 7 | 用户上传论文功能可用 | API 测试 |
| 8 | 上传论文出现在 verified_papers | API 测试 |
| 9 | arXiv 全文获取 | V-MED 有全文的论文 |
| 10 | changelog 完整 | 文件检查 |
| 11 | VOAPI/MiniMax = 0 | 全程 |
