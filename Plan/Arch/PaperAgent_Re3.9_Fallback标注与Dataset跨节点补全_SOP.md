# PaperAgent Re3.9 Fallback 标注 + Dataset 跨节点补全 + 新搜索链路验证 SOP

> 承接：Re3.8 系统性问题修复（进行中）。深度分析 48+ 个 eval case 发现：
> - 零 heuristic 触发——所有节点全部走 LLM 路径，`known_dataset_names` 是死代码
> - 20/20 Batch20 cases datasets=0，但 4 个 case 的 innovation_points 提到了数据集名——graph 顺序问题
> - "表现好"全部是 LLM 驱动，不是 heuristic fallback——但 heuristic 代码未标注、未追踪、无法区分
> - S2/OpenAlex 429 限流持续影响多个 case（R36-003 耗时 878s，R34-066 仅 3 篇论文）
> 
> **本 SOP 聚焦：fallback 路径标注 + dataset 跨节点补全 + topic_parser 英文修复 + PubMed 按需调用 + 不依赖 429 API 的新搜索链路验证**
> 预计总时长：5-6 小时，分 6 个 Phase。
> 模型：DeepSeek (主)，StepFun (fallback)。

## 0. 审计发现总结

### Fallback 透明度问题

| 问题 | 证据 | 影响 |
|---|---|---|
| `known_dataset_names` 未标注为 fallback | L257-273 直接定义，无注释说明是 heuristic-only | 误以为是主路径逻辑 |
| heuristic 提取的 dataset 无 `source` 区分 | L288: `"source": "innovation_plan_heuristic"` 有标注，但 L312: `"source": "paper_title_heuristic"` 也有——但 `dataset_repo_extractor` LLM 路径提取的 dataset source 是什么？未追踪 | 无法区分 LLM 提取 vs heuristic 提取 |
| 48+ case 全部走 LLM，heuristic 从未触发 | trace 中 `provider` 字段无 "heuristic" | heuristic 代码是死代码——但不可删除（LLM 不可用时是安全网） |
| 表现好的 case 是否依赖 heuristic？ | **否**——全部 LLM 驱动 | 但如果 LLM 降级，heuristic 质量未知 |

### Dataset 跨节点丢失问题

| 问题 | 证据 |
|---|---|
| dataset_repo_extractor 在 innovation_extractor 之前运行 | graph 顺序：dataset_repo → ... → innovation_extractor → narrative_builder |
| innovation_extractor 识别到数据集但无法回传 | ENG-THESIS-027: innovation_points 提到 TJU-DHD，但 dataset_candidates=0 |
| 4/20 Batch20 cases 有此问题 | 016(SLAM/COCO)、022(steel/NEU-DET)、027(YOLOv5/TJU-DHD)、093(insulator/DOTA) |

### Graph 节点顺序

```
当前: dataset_repo → evidence_auditor → feasibility → work_package → innovation → narrative
问题: innovation 发现的数据集无法反馈给 dataset_repo
```

## 1. 本轮目标

1. **Fallback 全链路标注**——`known_dataset_names` 标注为 fallback-only + 所有 heuristic 产物加 `source="heuristic_fallback"` 标记 + trace 中 `provider="heuristic"` 的节点在前端时间线中标记
2. **Dataset 跨节点补全**——在 innovation_extractor 之后补跑一次 dataset 启发式扫描，将 innovation_points 文本中提到的数据集追加到 dataset_candidates
3. **产物可溯源分析**——为 Batch20 全部 20 case 生成溯源报告，标注每个 dataset/repo/baseline 的来源
4. **topic_parser 强制英文输出**（Re3.8 遗漏修复）——在 prompt 中明确要求 ALL keywords MUST be in English
5. **PubMed E-utilities 适配器（按需调用）**——接入 PubMed，但仅在 topic_parser 识别到医学/生物领域时才启用，非医学题目不调用 PubMed
6. **不依赖 S2/OpenAlex 的搜索链路验证**——禁用 S2 + OpenAlex，仅用 arXiv + Crossref + GitHub + PubMed（医学时）+ CORE + DataCite + HuggingFace 跑 2 个 case，对比论文质量

不做：
- 删除 `known_dataset_names`（保留作为安全网，但标注）
- 修改 graph 拓扑顺序（用补跑方案，不改 LangGraph 边）
- 100 篇回归
- Google Scholar 爬虫（合规风险）
- Google Scholar 爬虫（合规风险，需代理/反检测，不适合学术项目）

## 2. Phase 设计

### Phase 0：topic_parser 强制英文输出 (5min)

#### Fix 0.1: prompt 添加英文强制指令

**文件**：`apps/api/app/services/agents/prompts/re11_topic_parser.py`

**问题**：Re3.8 SOP Fix 2.4 要求添加 "ALL keywords MUST be in English" 指令，但实际未修改。中文题目仍可能输出中文关键词（如 "伪深度图误差过滤方法"），导致 arXiv/Crossref 返回 0 结果。

**修复**：在 SYSTEM 和 USER_TEMPLATE 中添加强制英文指令：

```python
# SYSTEM 修改为:
SYSTEM = """You parse raw Chinese or English thesis topics into structured atoms.
ALL keywords in method/object/task/scenario/domain MUST be in English.
If the topic is in Chinese, you MUST translate all terms to English.
For example: "目标检测" -> "object detection", "语义分割" -> "semantic segmentation",
"深度学习" -> "deep learning", "机械臂" -> "robotic arm".
Chinese keywords in the output will cause search adapters to return zero results.
Output STRICT JSON. Do not invent methods, datasets, or baselines that the
topic does not imply. Avoid generic method names (e.g. "deep learning",
"neural network") unless the topic truly is generic.

Do NOT bias toward any specific domain. Parse what the topic says, not what
examples suggest. If the topic says <object_X>, every alias must refer to
<object_X> or its direct synonyms — never to <object_Y> from an adjacent
field that happens to share a keyword.
"""

# USER_TEMPLATE 中 method/object/task 行修改为:
# - method: list[str] — techniques the topic implies, ALL IN ENGLISH (translate Chinese)
# - object: list[str] — physical/behavioral target, ALL IN ENGLISH (translate Chinese)
# - task: list[str] — what to do, ALL IN ENGLISH (translate Chinese)
```

**验证**：
```bash
.venv/Scripts/python.exe -c "
src = open('apps/api/app/services/agents/prompts/re11_topic_parser.py', encoding='utf-8').read()
assert 'ALL' in src and 'ENGLISH' in src, 'Missing English requirement!'
assert 'translate' in src.lower(), 'Missing translate instruction!'
print('OK: topic_parser enforces English output')
"
```

### Phase 1：Fallback 标注 (1h)

#### Fix 1.1: known_dataset_names 标注为 fallback-only

**文件**：`apps/api/app/services/agents/graph/nodes/dataset_repo_extractor.py` L255-273

```python
# 修改前:
# Re2.2-fix: heuristic dataset extraction from innovation_points stitching_plan
innovation_points = state.get("innovation_points") or []
known_dataset_names = [
    "NEU-DET", "GC10-DET", ...
]

# 修改后:
# ---------------------------------------------------------------------------
# FALLBACK ONLY: This list is used ONLY when the LLM dataset_extractor fails
# or returns empty results. It performs a simple string-match scan of paper
# titles/abstracts and innovation_points text for known dataset names.
#
# This is NOT the primary extraction path — the LLM path (above) is.
# In 48+ eval cases, this heuristic NEVER fired because LLM was always available.
#
# Rules (rules.md §1): This is a flat string-match list, NOT a domain→dataset
# mapping. It does not route by domain. It is equivalent to _STOPWORDS in
# evidence_consistency.py — a tokenization aid for the fallback path.
# -------------------------------------------------------------------------
known_dataset_names_fallback = [  # FALLBACK ONLY — see comment above
    "NEU-DET", "GC10-DET", ...
]
```

#### Fix 1.2: heuristic 产物 source 标记统一

**文件**：同上，L282-297 和 L306-321

当前 heuristic 产物已有 `"source": "innovation_plan_heuristic"` 和 `"source": "paper_title_heuristic"`，但格式不统一。统一为：

```python
# L288:
"source": "heuristic_fallback:innovation_plan",
# L312:
"source": "heuristic_fallback:paper_title",
```

同时，LLM 路径提取的 dataset 需要标注 source：

```python
# _extract_one 函数中，LLM 返回的 dataset:
"source": "llm:dataset_repo_extractor",
```

#### Fix 1.3: trace 中标注 fallback 节点

**文件**：`apps/api/app/services/agents/graph/nodes/dataset_repo_extractor.py`

在 trace 的 output_summary 中添加 `used_fallback` 标志：

```python
# 在 _emit 调用中:
trace = _emit("dataset_repo", t0,
              {"n_papers": len(papers), "limit": limit},
              {"n_datasets": len(merged_ds), "n_repos": len(merged_repo),
               "used_fallback": ok_count < tried,  # True if any paper used heuristic
               "llm_success_rate": f"{ok_count}/{tried}" if tried else "n/a"},
              ...)
```

#### Fix 1.4: 前端时间线标注 fallback 节点

**文件**：`apps/web/index.html`

在 `selectTimelineNode` 函数中，如果 `output_summary.used_fallback` 为 true，在详情面板显示警告：

```javascript
// 在 renderTimeline detail 中添加:
var fallbackHtml = '';
if (ev.output_summary && ev.output_summary.used_fallback) {
    fallbackHtml = '<div style="color:#f59e0b;font-size:11px;">⚠ This node used heuristic fallback (LLM may have failed for some papers)</div>';
}
document.getElementById('tlDetailErrors').innerHTML = errHtml + fallbackHtml;
```

### Phase 2：Dataset 跨节点补全 (1h)

#### Fix 2.1: innovation_extractor 后补跑 dataset 扫描

**文件**：`apps/api/app/services/agents/graph/nodes/innovation_extractor.py`

**问题**：innovation_extractor 在 dataset_repo_extractor 之后运行，但它能识别到后者遗漏的数据集（如 TJU-DHD）。当前这些信息停留在 innovation_points 文本中，不会回传到 dataset_candidates。

**修复**：在 innovation_extractor_node 的返回中，扫描 innovation_points 文本，将提到的数据集追加到 dataset_candidates：

```python
def innovation_extractor_node(state: ResearchState) -> dict[str, Any]:
    # ... 现有 LLM 调用逻辑 ...
    
    # Re3.9: 跨节点 dataset 补全——扫描 innovation_points 文本中的数据集名
    # 这不是 heuristic fallback，而是跨节点信息传递：
    # innovation_extractor 的 LLM 能识别 dataset_repo_extractor 遗漏的数据集
    existing_ds = list(state.get("dataset_candidates") or [])
    existing_names = {str(d.get("name", "")).lower() for d in existing_ds}
    
    # 扫描 innovation_points + stitching_plan 文本
    scan_text = " ".join([
        str(ip.get("description", "")) + " " + str(ip.get("stitching_plan", ""))
        for ip in result_inn
    ] + [
        str(result_plan.get("baseline_model", "")) + " " +
        str(result_plan.get("module_b", "")) + " " +
        str(result_plan.get("module_c", "")) + " " +
        " ".join(result_plan.get("stitching_steps", []))
    ])
    
    # 使用与 dataset_repo_extractor 相同的 fallback 列表
    # 但标注 source 为 "cross_node:innovation_extractor"
    from apps.api.app.services.agents.graph.nodes.dataset_repo_extractor import (
        known_dataset_names_fallback as _ds_names,
    )
    
    new_ds = []
    for ds_name in _ds_names:
        if ds_name.lower() in scan_text.lower() and ds_name.lower() not in existing_names:
            new_ds.append({
                "from_paper": "innovation_extractor_cross_scan",
                "kind": "dataset",
                "name": ds_name,
                "url": None,
                "source": "cross_node:innovation_extractor",
                "availability": "named",
                "status": "found",
                "reproducibility_hint": "",
                "risk": "",
            })
            existing_names.add(ds_name.lower())
    
    trace = _emit("innovation_extractor", t0,
                  {"n_baseline": len(baselines), "n_parallel": len(parallels)},
                  {"n_innovation": len(result_inn), "n_datasets_found": len(new_ds)},
                  [{"tool": "innovation_extractor.llm" if prov != "heuristic" else "heuristic"}],
                  prov, [],
                  state_keys=["innovation_points", "stitching_plan",
                              "dataset_candidates", "trace_events"])
    
    return {
        "innovation_points": result_inn,
        "stitching_plan": result_plan,
        "dataset_candidates": existing_ds + new_ds,  # 合并
        "trace_events": [trace],
    }
```

**关键设计**：
- `source: "cross_node:innovation_extractor"` —— 与 `heuristic_fallback:xxx` 区分
- 复用 `known_dataset_names_fallback` 列表（不重复定义）
- 不修改 graph 拓扑——只在 innovation_extractor 的返回 patch 中追加 dataset_candidates
- LangGraph 的 state merge 会自动合并 dataset_candidates（列表追加）

**注意**：需要确认 ResearchState 的 `dataset_candidates` 字段在 LangGraph merge 中的行为。如果是 `Operator.add`（列表追加），则直接返回新列表即可；如果是覆盖，需要返回 `existing_ds + new_ds`。

#### Fix 2.2: ResearchState 确认 dataset_candidates merge 行为

**文件**：`apps/api/app/services/agents/graph/state.py`

检查 `dataset_candidates` 是否有 `Annotated[list, operator.add]` 注解。如果没有，innovation_extractor 返回的 `dataset_candidates` 会覆盖之前 dataset_repo_extractor 的结果——需要返回合并后的完整列表。

```python
# state.py 中确认:
# 如果是 Annotated[list[dict], operator.add]:
#   只需返回 new_ds（LangGraph 自动追加）
# 如果是普通 list:
#   需返回 existing_ds + new_ds（手动合并）
```

### Phase 3：产物溯源分析 (1h)

#### 3.1 溯源分析脚本

**新文件**：`scripts/re39_provenance_analysis.py`

```python
"""Re3.9: Analyze the source of every dataset/repo/baseline across all eval data.

For each case, outputs:
- Which datasets came from LLM extraction vs heuristic vs cross_node scan
- Which repos came from search_agent vs citation_expander
- Which baselines came from LLM classification vs heuristic
- Whether any node used heuristic fallback (provider="heuristic")
"""

import json, os, sys
from collections import Counter

EVAL_DIRS = [
    "tmp_re30_eval/batch20",
    "tmp_re34_eval",
    "tmp_re35_eval",
    "tmp_re36_eval",
]

def analyze_case(case_path: str) -> dict:
    state_path = os.path.join(case_path, "state.json")
    trace_path = os.path.join(case_path, "trace.json")
    if not os.path.exists(state_path):
        return None
    
    state = json.load(open(state_path, encoding="utf-8"))
    trace = json.load(open(trace_path, encoding="utf-8")) if os.path.exists(trace_path) else []
    
    # Dataset sources
    datasets = state.get("dataset_candidates") or []
    ds_sources = Counter(d.get("source", "unknown") for d in datasets)
    
    # Repo sources
    repos = state.get("repo_candidates") or []
    repo_sources = Counter(r.get("source", "unknown") for r in repos)
    
    # Heuristic nodes
    heuristic_nodes = []
    for ev in trace:
        if ev.get("provider") == "heuristic":
            heuristic_nodes.append(ev.get("node", "?"))
    
    # Fallback flag in dataset_repo trace
    ds_used_fallback = False
    for ev in trace:
        if ev.get("node") in ("dataset_repo", "dataset_repo_extractor"):
            out = ev.get("output_summary", {})
            if out.get("used_fallback"):
                ds_used_fallback = True
            break
    
    # Innovation mentions datasets?
    inn = state.get("innovation_points") or []
    inn_text = " ".join([str(i.get("description","")) + str(i.get("stitching_plan","")) for i in inn])
    
    return {
        "n_datasets": len(datasets),
        "ds_sources": dict(ds_sources),
        "n_repos": len(repos),
        "repo_sources": dict(repo_sources),
        "heuristic_nodes": heuristic_nodes,
        "ds_used_fallback": ds_used_fallback,
        "inn_mentions_dataset": len(inn_text) > 0 and any(
            kw in inn_text.lower() for kw in ["dataset", "benchmark", "数据集"]
        ),
    }

# Main
results = {}
for eval_dir in EVAL_DIRS:
    if not os.path.exists(eval_dir):
        continue
    for case_dir in sorted(os.listdir(eval_dir)):
        case_path = os.path.join(eval_dir, case_dir)
        if not os.path.isdir(case_path):
            continue
        analysis = analyze_case(case_path)
        if analysis:
            results[f"{eval_dir}/{case_dir}"] = analysis

# Summary
print("=" * 80)
print("Re3.9 Provenance Analysis")
print("=" * 80)

all_heuristic = []
all_ds_sources = Counter()
all_fallback = 0

for case_id, a in results.items():
    if a["heuristic_nodes"]:
        all_heuristic.append((case_id, a["heuristic_nodes"]))
    for src, cnt in a["ds_sources"].items():
        all_ds_sources[src] += cnt
    if a["ds_used_fallback"]:
        all_fallback += 1

print(f"\nTotal cases: {len(results)}")
print(f"Cases with heuristic fallback: {len(all_heuristic)}")
if all_heuristic:
    for case, nodes in all_heuristic:
        print(f"  {case}: {nodes}")
else:
    print("  (none — all LLM-driven)")

print(f"\nDataset sources across all cases:")
for src, cnt in all_ds_sources.most_common():
    print(f"  {src}: {cnt}")

print(f"\nCases where dataset_repo used fallback: {all_fallback}")
```

#### 3.2 Batch20 溯源报告

对 Batch20 全部 20 case 运行溯源脚本，生成 `tmp_re39_eval/batch20_provenance.json`，包含：
- 每个 case 的 dataset/repo/baseline 来源
- heuristic fallback 触发记录
- innovation_extractor 提到的数据集（但 dataset_repo_extractor 遗漏的）

#### 3.3 验证

跑 1 个 case（ENG-THESIS-027 或类似有 innovation 提到数据集的题目），确认：
- dataset_candidates 中出现 TJU-DHD，source=`cross_node:innovation_extractor`
- trace 中 innovation_extractor 的 output_summary 有 `n_datasets_found: 1`
- 前端时间线中 innovation_extractor 节点的详情面板显示找到的数据集

### Phase 4：PubMed E-utilities 适配器 (1h)

#### 背景

当前 8 个搜索适配器中，Semantic Scholar (S2) 和 OpenAlex 是 429 限流重灾区：
- S2：免费 tier 100 req/2h，批量回归时 citation_expander 会快速耗尽
- OpenAlex：免费 tier 有 rate limit，高峰期 429

现有替代方案分析：

| API | 免费？ | 需 key？ | Rate limit | 论文覆盖 | 适配度 |
|---|---|---|---|---|---|
| **PubMed E-utilities** | ✅ | 可选（无 key 3 req/s） | 3 req/s 无 key | 医学/生物/化学 | 医学论文首选 |
| Crossref | ✅ | 不需要 | 无硬限制 | 全领域 DOI | 已有 |
| arXiv | ✅ | 不需要 | 1 req/3s | 预印本 | 已有 |
| GitHub | ✅ | 不需要 | 60 req/h | 代码仓库 | 已有 |
| CORE | ✅ | 可选 | 有限制 | 开放获取 | 已有 |
| DataCite | ✅ | 不需要 | 有限制 | 数据集 DOI | 已有 |
| HuggingFace | ✅ | 不需要 | 有限制 | 模型/数据集 | 已有 |
| S2 | ✅ | 可选 | 100 req/2h（无 key 更低） | 高被引论文 | **429 重灾区** |
| OpenAlex | ✅ | 可选 | 有限制 | 全领域 | **429 重灾区** |
| Lens.org | ✅ | 需注册 | 14 天 trial | 专利+学术 | 合规复杂 |
| Google Scholar | ✅ | 无 API | 需爬虫 | 全领域 | **合规风险** |

**结论**：PubMed E-utilities 是最值得接入的新适配器——免费、无 key 可用（3 req/s）、医学论文覆盖好。但**不应默认加入所有搜索链路**——PubMed 只收录医学/生物/化学论文，对机械臂/裂缝/SLAM 等非医学题目搜索是浪费。应在 search_agent 中根据 topic_atoms.domain 按需启用。

#### Fix 4.1: PubMed 适配器实现

**新文件**：`apps/api/app/services/retrieval/adapters/pubmed_search.py`

```python
"""PubMed E-utilities search adapter — searches NCBI PubMed database.

Free, no API key required (3 req/s without key, 10 req/s with key).
429/5xx → return [] (don't raise).

NOTE: PubMed only indexes medical/life science papers. For non-medical topics
(robotics, civil engineering, etc.) it will return 0 results. This adapter
should only be called for medical/biological/chemical topics — see
search_agent's domain-gated tool selection.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

async def pubmed_search(
    queries: list[str],
    top_k: int = 8,
    *,
    client: Any | None = None,
) -> list[dict]:
    """Search PubMed for medical/life science papers.
    
    Two-step: esearch (get PMIDs) → esummary (get metadata).
    No API key required. 429/5xx → return [].
    """
    qs = [q for q in (queries or []) if q and q.strip()][:2]
    if not qs:
        return []
    
    try:
        import httpx
        
        all_results = []
        for q in qs:
            # Step 1: esearch → get PMIDs
            params = {
                "db": "pubmed",
                "term": q,
                "retmax": min(top_k, 10),
                "retmode": "json",
            }
            
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as c:
                resp = await c.get(PUBMED_ESEARCH, params=params)
            
            if resp.status_code >= 400:
                logger.info("pubmed esearch http %s | q=%s", resp.status_code, q[:50])
                continue
            
            data = resp.json()
            id_list = data.get("esearchresult", {}).get("idlist", [])
            if not id_list:
                continue
            
            # Step 2: esummary → get paper metadata
            summary_params = {
                "db": "pubmed",
                "id": ",".join(id_list),
                "retmode": "json",
            }
            
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as c:
                resp = await c.get(PUBMED_ESUMMARY, params=summary_params)
            
            if resp.status_code >= 400:
                logger.info("pubmed esummary http %s | q=%s", resp.status_code, q[:50])
                continue
            
            sdata = resp.json()
            result = sdata.get("result", {})
            
            for pmid in id_list:
                item = result.get(pmid, {})
                if not item:
                    continue
                title = item.get("title", "")
                if not title:
                    continue
                
                authors = [a.get("name", "") for a in item.get("authors", []) if a.get("name")]
                
                doi = ""
                for aid in item.get("articleids", []):
                    if aid.get("idtype") == "doi":
                        doi = aid.get("value", "")
                        break
                
                pubdate = item.get("pubdate", "")
                year = None
                for part in pubdate.split():
                    if part.isdigit() and 1900 < int(part) < 2100:
                        year = int(part)
                        break
                
                all_results.append({
                    "title": str(title),
                    "abstract": "",
                    "authors": authors[:5],
                    "year": year,
                    "doi": doi,
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
                    "pmid": pmid,
                    "source": "pubmed",
                    "evidence_type": "paper",
                    "source_query": q,
                })
        
        return all_results[:top_k]
    except Exception as exc:
        logger.info("pubmed fetch error: %s | q=%s", exc, qs[0][:50] if qs else "")
        return []
```

#### Fix 4.2: 注册到 REGISTRY

**文件**：`apps/api/app/services/retrieval/adapters/__init__.py`

```python
from .pubmed_search import pubmed_search

REGISTRY: dict[SearchSource, SourceFn] = {
    ...
    "pubmed": pubmed_search,
}
```

#### Fix 4.3: search_agent 按需启用 PubMed（领域门控）

**文件**：`apps/api/app/services/agents/graph/nodes/search_agent.py`

**设计**：PubMed 不默认加入 `available_tools`，而是根据 `topic_atoms.domain` 动态启用。只有当 domain 包含医学/生物相关关键词时才加入 PubMed。

```python
# 在 search_agent_node 中，构建 available_tools 时:
def _get_domain_tools(domain: str) -> set[str]:
    """Return domain-specific tools based on topic domain."""
    domain_lower = (domain or "").lower()
    medical_keywords = {"medical", "medicine", "biomedical", "health", "clinical",
                        "bioinformatic", "biological", "lifestream", "medical_ai"}
    if any(kw in domain_lower for kw in medical_keywords):
        return {"pubmed"}
    return set()

# 在构建 available_tools 时:
domain = (atoms.get("domain") or ["unknown"])[0] if isinstance(atoms.get("domain"), list) else str(atoms.get("domain", "unknown"))
domain_tools = _get_domain_tools(domain)

# 基础工具（所有领域）:
base_tools = {"arxiv", "openalex", "crossref", "github", "semantic_scholar",
              "huggingface", "core", "datacite"}
available_tools = base_tools | domain_tools  # 医学领域额外加 pubmed
```

**_SYSTEM_PROMPT 中添加领域门控说明**：
```python
# 在 _SYSTEM_PROMPT 中添加:
"""
注意: pubmed 工具仅对医学/生物领域可用。如果 pubmed 不在可用工具列表中，
不要尝试使用它。
"""
```

**_fallback_decide 中也需要同步**——当 `available_tools` 不含 pubmed 时，fallback 不会选 pubmed（已天然支持，因为 fallback 遍历的是 search_plan 中的工具，而 search_plan 由 search_planner 生成）。

**search_planner.py 和 targeted_repair.py 的 `_TOOLS`**：

```python
# search_planner.py — _TOOLS 改为动态:
# 不在模块级别硬编码 pubmed，而是在 build() 时根据 domain 添加
# 或保持 _TOOLS 不含 pubmed，由 search_agent 的 domain_tools 在运行时追加

# 最简方案: _TOOLS 保持 8 个（不含 pubmed），search_agent 运行时追加
_TOOLS = frozenset({"arxiv", "openalex", "crossref", "github", "semantic_scholar",
                     "huggingface", "core", "datacite"})
# pubmed 由 search_agent 的 _get_domain_tools 动态添加
```

这样 PubMed 只在医学领域被 LLM 看到，非医学题目不会尝试调用。
) -> list[dict]:
    """Search PubMed for medical/life science papers.
    
    Two-step: esearch (get PMIDs) → esummary (get metadata).
    No API key required. 429/5xx → return [].
    """
    qs = [q for q in (queries or []) if q and q.strip()][:2]
    if not qs:
        return []
    
    try:
        import httpx
        
        all_results = []
        for q in qs:
            # Step 1: esearch → get PMIDs
            params = {
                "db": "pubmed",
                "term": q,
                "retmax": min(top_k, 10),
                "retmode": "json",
            }
            
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as c:
                resp = await c.get(PUBMED_ESEARCH, params=params)
            
            if resp.status_code >= 400:
                logger.info("pubmed esearch http %s | q=%s", resp.status_code, q[:50])
                continue
            
            data = resp.json()
            id_list = data.get("esearchresult", {}).get("idlist", [])
            if not id_list:
                continue
            
            # Step 2: esummary → get paper metadata
            summary_params = {
                "db": "pubmed",
                "id": ",".join(id_list),
                "retmode": "json",
            }
            
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as c:
                resp = await c.get(PUBMED_ESUMMARY, params=summary_params)
            
            if resp.status_code >= 400:
                logger.info("pubmed esummary http %s | q=%s", resp.status_code, q[:50])
                continue
            
            sdata = resp.json()
            result = sdata.get("result", {})
            
            for pmid in id_list:
                item = result.get(pmid, {})
                if not item:
                    continue
                title = item.get("title", "")
                if not title:
                    continue
                
                # Extract authors
                authors = [a.get("name", "") for a in item.get("authors", []) if a.get("name")]
                
                # Extract DOI from articleids
                doi = ""
                for aid in item.get("articleids", []):
                    if aid.get("idtype") == "doi":
                        doi = aid.get("value", "")
                        break
                
                # Extract year
                pubdate = item.get("pubdate", "")
                year = None
                for part in pubdate.split():
                    if part.isdigit() and 1900 < int(part) < 2100:
                        year = int(part)
                        break
                
                all_results.append({
                    "title": str(title),
                    "abstract": "",  # esummary doesn't return abstract; use efetch for that
                    "authors": authors[:5],
                    "year": year,
                    "doi": doi,
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
                    "pmid": pmid,
                    "source": "pubmed",
                    "evidence_type": "paper",
                    "source_query": q,
                })
        
        return all_results[:top_k]
    except Exception as exc:
        logger.info("pubmed fetch error: %s | q=%s", exc, qs[0][:50] if qs else "")
        return []
```

#### Fix 4.2: 注册到 REGISTRY

**文件**：`apps/api/app/services/retrieval/adapters/__init__.py`

```python
from .pubmed_search import pubmed_search

REGISTRY: dict[SearchSource, SourceFn] = {
    ...
    "pubmed": pubmed_search,
}
```

#### Fix 4.4: PubMed 适配器验证

```bash
# 1. 功能验证
.venv/Scripts/python.exe -c "
import asyncio
from apps.api.app.services.retrieval.adapters.pubmed_search import pubmed_search
results = asyncio.run(pubmed_search(['lung nodule detection YOLO'], 5))
print(f'PubMed returned {len(results)} results')
for r in results[:3]:
    print(f'  - {r[\"title\"][:80]}')
    print(f'    PMID: {r.get(\"pmid\",\"?\")} DOI: {r.get(\"doi\",\"?\")} Year: {r.get(\"year\",\"?\")}')
"

# 2. 领域门控验证——非医学题目不应看到 pubmed 工具
.venv/Scripts/python.exe -c "
from apps.api.app.services.agents.graph.nodes.search_agent import _get_domain_tools
assert _get_domain_tools('medical_ai') == {'pubmed'}, 'medical domain should include pubmed'
assert _get_domain_tools('vision_2d') == set(), 'non-medical domain should NOT include pubmed'
assert _get_domain_tools('civil_infra') == set(), 'civil domain should NOT include pubmed'
assert _get_domain_tools('energy_power') == set(), 'energy domain should NOT include pubmed'
print('OK: domain gating works correctly')
"
```

### Phase 5：不依赖 S2/OpenAlex 的搜索链路验证 (1.5h)

#### 5.1 验证设计

禁用 S2 + OpenAlex，仅用 7 个适配器（arXiv + Crossref + GitHub + PubMed + CORE + DataCite + HuggingFace）跑 2 个 case：

| Case | 题目 | 之前 S2/OpenAlex 贡献 | 验证重点 |
|---|---|---|---|
| R39-MED | 基于大语言模型的医学问答可信度评估方法研究 | V-MED-33: S2 贡献了大部分论文 | PubMed 能否替代 S2 的医学论文覆盖 |
| R34-066 | 面向自动驾驶中多模态融合感知算法的攻击和防御 | R34-066: S2 429 导致仅 3 篇论文 | 无 S2 后 Crossref+arXiv 是否能补充 |

#### 5.2 禁用方式

通过环境变量禁用 S2 + OpenAlex，不修改代码：

```bash
# 设置环境变量标记禁用
set PAPERAGENT_DISABLE_S2=1
set PAPERAGENT_DISABLE_OPENALEX=1

# 启动 server
.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 18181
```

**代码修改**（`search_agent.py`）：

```python
# 在 _run_tool 函数开头添加:
import os
_DISABLED_TOOLS = set()
if os.environ.get("PAPERAGENT_DISABLE_S2"):
    _DISABLED_TOOLS.add("semantic_scholar")
if os.environ.get("PAPERAGENT_DISABLE_OPENALEX"):
    _DISABLED_TOOLS.add("openalex")

# 在 _run_tool 中:
if tool in _DISABLED_TOOLS:
    logger.info("search_agent: tool %s disabled by env var", tool)
    return []
```

同样在 `citation_expander` 中禁用 S2 引用展开。

#### 5.3 对比验证

对每个 case，对比两次运行结果：

| 指标 | 正常链路（8 工具） | 禁用链路（7 工具，无 S2/OA） | 差异 |
|---|---|---|---|
| verified_papers 数量 | ? | ? | 期望 ≤20% 下降 |
| 论文质量（accept 比例） | ? | ? | 期望不降 |
| 搜索耗时 | ? | ? | 期望更快（无 429 重试） |
| feasibility verdict | ? | ? | 期望一致 |
| dataset_candidates | ? | ? | 期望一致或更好（PubMed 补充） |

#### 5.4 验收标准

**P0**：

| # | 检查项 | 通过标准 |
|---|---|---|
| 1 | PubMed 适配器返回结果 | ≥3 篇论文 |
| 2 | 禁用链路 2 case 完成 | state.json 存在 |
| 3 | 禁用链路无 RecursionError | trace.json |
| 4 | 禁用链路 verified_papers ≥ 3 | state.json |
| 5 | 禁用链路 search_agent 无 S2/OpenAlex 调用 | trace search_steps |

**P1**：

| # | 检查项 | 通过标准 |
|---|---|---|
| 6 | R39-MED 论文数 vs V-MED-33 | ≤20% 下降 |
| 7 | 禁用链路 search_agent 耗时 < 正常链路 | trace elapsed_s |
| 8 | PubMed 出现在 search_steps 中 | trace.json |
| 9 | 禁用链路 feasibility 有区分度 | 不全是同一 verdict |

## 3. 执行者规则

1. **Phase 0 最先完成**——topic_parser 英文指令影响后续所有 case 的搜索质量
2. **Phase 1 可以独立完成**——标注不影响功能
3. **Phase 2 需要确认 state merge 行为**——先读 state.py
4. **Phase 3 在 Phase 1-2 完成后执行**
5. **Phase 4 可以独立完成**——新适配器 + 领域门控不影响现有链路
6. **Phase 5 在 Phase 0 + Phase 4 完成后执行**——需要 PubMed 适配器 + 英文 topic_parser
7. **每个 Phase 完成后 commit**

### Commit 规范

| Phase | Commit message |
|---|---|
| 0 | `fix(re3.9-phase0): topic_parser强制英文输出 — Re3.8遗漏修复` |
| 1 | `fix(re3.9-phase1): fallback标注 — known_dataset_names标注为fallback-only + source统一 + trace used_fallback标志` |
| 2 | `feat(re3.9-phase2): dataset跨节点补全 — innovation_extractor后补跑dataset扫描` |
| 3 | `docs(re3.9-phase3): 产物溯源分析 — Batch20全部case来源标注` |
| 4 | `feat(re3.9-phase4): PubMed适配器+领域门控 — 仅医学领域按需调用` |
| 5 | `test(re3.9-phase5): 禁用S2+OpenAlex搜索链路验证 — 2case对比` |

## 4. 交付物

### 代码
| 文件 | 改动类型 | Phase |
|---|---|---|
| `prompts/re11_topic_parser.py` | 🔧 强制英文指令 | 0 |
| `dataset_repo_extractor.py` | 🔧 标注 + source 统一 + trace used_fallback | 1 |
| `innovation_extractor.py` | 🔧 跨节点 dataset 补全 | 2 |
| `state.py` | 🔧 确认 dataset_candidates merge 行为 | 2 |
| `index.html` | 🔧 时间线 fallback 警告 | 1 |
| `scripts/re39_provenance_analysis.py` | 🆕 溯源脚本 | 3 |
| `apps/api/app/services/retrieval/adapters/pubmed_search.py` | 🆕 PubMed 适配器 | 4 |
| `apps/api/app/services/retrieval/adapters/__init__.py` | 🔧 注册 pubmed | 4 |
| `search_agent.py` | 🔧 领域门控 _get_domain_tools + 禁用 env var | 4+5 |

### 数据
| 文件 | 内容 |
|---|---|
| `tmp_re39_eval/batch20_provenance.json` | Batch20 溯源报告 |
| `tmp_re39_eval/R39-027/` | 跨节点补全验证 case |
| `tmp_re39_eval/R39-MED/` | 禁用链路医学 case（PubMed 替代 S2） |
| `tmp_re39_eval/R39-066/` | 禁用链路多模态 case（无 PubMed，纯 Crossref+arXiv） |

### 报告
| 文件 | 内容 |
|---|---|
| `Plan/PaperAgent_Re3.9_完工报告.md` | 完工报告 + 禁用链路对比表 |

## 5. 最终验收条件

| # | 条件 | 验证方式 | 优先级 |
|---|---|---|---|
| 1 | topic_parser prompt 含 "ALL" + "ENGLISH" + "translate" | 代码检查 | P0 |
| 2 | known_dataset_names 标注为 fallback-only | 代码检查 | P0 |
| 3 | 所有 heuristic 产物 source 含 "heuristic_fallback" | 代码检查 | P0 |
| 4 | LLM 产物 source 含 "llm:" | 代码检查 | P0 |
| 5 | trace output_summary 含 used_fallback 字段 | trace.json | P0 |
| 6 | innovation_extractor 返回 dataset_candidates | 代码检查 | P0 |
| 7 | 跨节点补全的 dataset source = "cross_node:innovation_extractor" | trace.json | P0 |
| 8 | 验证 case dataset_candidates > 0（之前为 0） | state.json | P0 |
| 9 | PubMed 适配器返回 ≥3 结果 | 功能测试 | P0 |
| 10 | PubMed 注册到 REGISTRY | 代码检查 | P0 |
| 11 | _get_domain_tools 医学→pubmed，非医学→空 | 代码检查 | P0 |
| 12 | 非医学题目 search_steps 无 pubmed 调用 | trace.json | P0 |
| 13 | 禁用链路 2 case 完成 | state.json | P0 |
| 14 | 禁用链路无 RecursionError | trace.json | P0 |
| 15 | 禁用链路 verified_papers ≥ 3 | state.json | P0 |
| 16 | 禁用链路 search_steps 无 S2/OpenAlex | trace.json | P0 |
| 17 | R39-MED 论文数 vs V-MED-33 ≤20% 下降 | state.json | P1 |
| 18 | 禁用链路 search_agent 耗时 < 正常链路 | trace.json | P1 |
| 19 | R39-MED search_steps 含 pubmed 调用 | trace.json | P1 |
| 20 | R39-066 search_steps 不含 pubmed | trace.json | P1 |
| 21 | Batch20 溯源报告生成 | 文件检查 | P1 |
| 22 | 前端时间线显示 fallback 警告 | 截图 | P1 |
| 23 | commit per phase | git log | P1 |

## 6. 执行顺序

```
Phase 0 (5min): topic_parser 强制英文 (Re3.8 遗漏修复)
       ↓
Phase 1 (1h):   Fallback 标注 (代码注释 + source 统一 + trace 标志 + 前端)
       ↓
Phase 2 (1h):   Dataset 跨节点补全 (innovation_extractor 后补跑)
       ↓                     ↑ 可并行
Phase 4 (1h):   PubMed 适配器 + 领域门控 (新文件 + 注册 + _get_domain_tools)
       ↓
Phase 3 (1h):   产物溯源分析 (Batch20 全量 + 验证 case)
       ↓
Phase 5 (1.5h): 禁用 S2+OpenAlex 链路验证 (2 case 对比)
```

## 7. 风险与缓解

| 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|
| topic_parser 英文指令导致 LLM 过度翻译 | 低 | 专有名词被错误翻译 | 指令中保留 "do not invent" 约束 |
| state merge 覆盖 dataset_candidates | 中 | 跨节点补全的 dataset 丢失 | 返回 existing_ds + new_ds 而非仅 new_ds |
| known_dataset_names_fallback import 循环 | 低 | import 失败 | 改为在 innovation_extractor 内部定义引用 |
| 跨节点补全引入误报 | 中 | 不相关的数据集名被匹配 | 扫描范围限制在 innovation_points + stitching_plan 文本 |
| PubMed E-utilities 无 abstract | 中 | quality_filter 无法判断 | esummary 不返回 abstract，需后续 efetch 补充；或接受无 abstract |
| 领域门控误判——非医学题目被加入 pubmed | 低 | PubMed 返回 0 结果，浪费一个搜索步 | 门控关键词列表保守（仅 medical/biomedical/health/clinical） |
| 领域门控漏判——医学题目未加入 pubmed | 中 | 医学论文覆盖不足 | topic_parser 的 domain 输出需覆盖 medical_ai 等标签 |
| 禁用链路论文数大幅下降 | 中 | 系统鲁棒性不足 | 记录差异，分析是否需要增加更多适配器 |
| 禁用 env var 影响非预期路径 | 低 | citation_expander 也需要禁用 S2 | 在 citation_expander 中也检查 env var |
