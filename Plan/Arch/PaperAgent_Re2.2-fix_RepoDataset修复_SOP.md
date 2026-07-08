# PaperAgent Re2.2-fix Repo/Dataset 提取修复 SOP

> 承接：Re2.2 完工报告（100 篇全量回归，91% 完成）
> **本 SOP 设计为全程无人值守执行。**
> 预计总时长：2-3 小时。
> 模型：DeepSeek (主)。

## 0. 执行者必读

### 0.1 问题总结

Re2.2 审核发现 5 个系统性问题，全部围绕"GitHub repo 被当论文 + dataset 提取全空"：

| # | 问题 | 根因 | 影响 |
|---|---|---|---|
| 1 | GitHub repo URL 是 `api.github.com/repos/...` | retrieve.py 存了 GitHub API 的原始 URL，没转成人类可访问的 `github.com/owner/repo` | repo URL 不可访问，`_owner_repo()` regex 匹配不到 |
| 2 | GitHub repo 在 evidence_graph 中标为 `type="paper"` | json_graph_builder 不检查 `source=github`，统一标 `type="paper"` | repo 和论文混在一起，前端无法区分 |
| 3 | verified_papers 有重复 | verify 第一轮完全不去重，第二轮只按 title 去重（不按 URL） | 同一篇论文/repo 出现 2-3 次 |
| 4 | quality_filter 漏 `Table 2:` / `Figure 3:` | `_NON_PAPER_PATTERNS` 有 `^table\s*\d+` 但没匹配带冒号的 | 22/100 篇有表格标题混入 |
| 5 | dataset_candidates 全空 | LLM 只从论文摘要提取，GitHub 结果无摘要；已知数据集名（NEU-DET/KITTI 等）在 innovation_points 的 stitching_plan 中出现但没被提取 | 0/100 case 有 dataset |

### 0.2 核心原则

1. **每改一处代码，必须立即重跑 3 个 case 验证。** ≥2/3 通过才保留，3 个全失败回滚。
2. **每次只改一个文件，验证通过后再改下一个。**
3. **验证失败必须 `git checkout` 回滚。**
4. **Phase 间不传染。**

### 0.3 验证 case 集

| 验证 case | 题目 | 领域 | 选原因 |
|---|---|---|---|
| V-SLAM | 基于深度学习的视觉SLAM语义地图的研究 | SLAM | Re2.2 有 9 个 source=github 的 verified_papers，repo 提取全空 |
| V-CRACK | 基于深度学习的混凝土桥梁裂缝检测研究 | 土木 | 无 GitHub，验证 dataset heuristic 提取 + Table/Figure 过滤 |
| V-MED | 基于大语言模型的医学问答可信度评估方法研究 | NLP/医学 | 验证去重 + 有创新链路（innovation_points 中可能有数据集名） |

### 0.4 验证通过标准

**对 3 个 case 的验证，以下每项需要 ≥2/3 通过：**

| 检查项 | 通过标准 |
|---|---|
| graph 完成 | ≥2/3 has_final=True |
| 无 crash | ≥2/3 无 InvalidUpdateError |
| 改动的目标指标改善 | ≥2/3 目标指标有改善（见各 Fix 定义） |

### 0.5 改动隔离

```bash
# 改前备份
git stash create > /tmp/re22fix_stash_<fix_name>

# 改后验证通过
echo "<file>: <改动> → 3 case 验证通过" >> tmp_re22fix_eval/changelog.md

# 改后验证失败
git checkout -- <file>
echo "<file>: <改动> → 3 case 验证失败, 已回滚" >> tmp_re22fix_eval/changelog.md
```

## 1. 前置条件

- Re2.2 审核完成，问题已确认。
- `tmp_re22_eval/all_100/ENG-THESIS-048/state.json` 有 baseline 数据（9 个 source=github 的 verified_papers）。
- DeepSeek API key 可用。

## 2. 模型策略

```text
FAST_JSON_PRIMARY=deepseek
LLM_PROFILE=deepseek
```

## 3. Fix 设计

### Fix 1: retrieve.py — GitHub URL 转换 (20min)

#### 问题

retrieve.py 在构建 paper dict 时，GitHub 搜索结果的 `url` 字段存的是 `https://api.github.com/repos/owner/repo`，不是人类可访问的 `https://github.com/owner/repo`。

这导致：
- `dataset_repo_extractor` 的 github fix 提取的 repo URL 是 API 地址
- `json_graph_builder` 的 `_owner_repo()` regex（匹配 `github.com/`）匹配不到 `api.github.com/`
- 前端展示的 repo URL 不可点击

#### 修改

**文件**：`apps/api/app/services/agents/graph/nodes/retrieve.py`

在构建 paper dict 的 `url` 字段时，如果 `tool == "github"` 且 URL 含 `api.github.com/repos/`，转换为 `github.com/owner/repo`：

```python
# 在 papers.append 之前，构建 url 时
url = h.get("url") or h.get("html_url") or h.get("abs_url") or ""
if tool == "github" and "api.github.com/repos/" in url:
    # https://api.github.com/repos/owner/repo → https://github.com/owner/repo
    path = url.split("api.github.com/repos/", 1)[-1].rstrip("/")
    url = f"https://github.com/{path}"
```

#### 3-case 验证

重跑 V-SLAM / V-CRACK / V-MED：

| 检查项 | 通过标准 |
|---|---|
| verified_papers 中 source=github 的 url 不含 `api.github.com` | V-SLAM 有 github 论文 → ≥2/3 的 github url 是 `github.com/` 格式 |
| graph 完成 | ≥2/3 has_final=True |
| 无 crash | ≥2/3 |

- [ ] 3 case 结果记录到 changelog。
- [ ] ≥2/3 通过 → 保留改动。
- [ ] 全失败 → 回滚 → 用旧代码继续 Fix 2。

### Fix 2: json_graph_builder.py — GitHub repo 标 type=repo (15min)

#### 问题

json_graph_builder 对所有 verified_papers 统一标 `type="paper"`，不检查 `source=github`。GitHub repo 被标为 `type="paper"` 而非 `type="repo"`。

#### 修改

**文件**：`apps/api/app/services/agents/graph/nodes/json_graph_builder.py`

在 verified_papers 循环中，检查 `source=github`，标 `type="repo"`：

```python
for p in verified:
    title = (p.get("title") or p.get("name") or "").strip()
    role = p.get("relation_to_topic") or "unknown"
    source = (p.get("source") or "").lower()
    ntype = "repo" if source == "github" else "paper"
    add_node(f"paper:<{_kebab(title)}>", ntype, title, role)
```

#### 3-case 验证

| 检查项 | 通过标准 |
|---|---|
| evidence_graph 中 source=github 的节点 type="repo" | V-SLAM 的 github 节点 ≥2/3 标为 type="repo" |
| 非 github 节点仍为 type="paper" | ≥2/3 正常 |
| graph 完成 | ≥2/3 |

### Fix 3: verify.py — 第一轮去重 + URL 去重 (20min)

#### 问题

verify 第一轮完全不去重。第二轮只按 title 去重，不按 URL。GitHub 结果 `xdspacelab/openvslam` 在 verified_papers 中出现 3 次。

#### 修改

**文件**：`apps/api/app/services/agents/graph/nodes/verify.py`

在构建 `keep` 列表时，按 title normalized + url 去重。在 `keep.append(item)` 之前加去重检查：

```python
# 在 for v in verdicts 循环中，keep.append(item) 之前
dedup_key = title.lower().strip()
url_key = (item.get("url") or "").lower().strip()
if dedup_key in _keep_titles or (url_key and url_key in _keep_urls):
    continue  # 跳过重复
_keep_titles.add(dedup_key)
if url_key:
    _keep_urls.add(url_key)
keep.append(item)
```

需要在循环前初始化 `_keep_titles = set()` 和 `_keep_urls = set()`。

对于第二轮（citation_done=True），合并已有 verified_papers 时也做去重：

```python
# 合并时去重
if citation_done:
    existing_verified = list(state.get("verified_papers") or [])
    existing_weak = list(state.get("weak_papers") or [])
    # 去重：新 verified 中与已有 title/url 重复的不追加
    existing_titles = {(p.get("title") or "").lower().strip() for p in existing_verified}
    existing_urls = {(p.get("url") or "").lower().strip() for p in existing_verified if p.get("url")}
    new_verified = [v for v in verified 
                     if (v.get("title") or "").lower().strip() not in existing_titles
                     and (v.get("url") or "").lower().strip() not in existing_urls]
    merged_verified = existing_verified + new_verified
```

#### 3-case 验证

| 检查项 | 通过标准 |
|---|---|
| verified_papers 无重复 title | ≥2/3 case 无重复（同 title 不出现 ≥2 次） |
| verified_papers 无重复 url | ≥2/3 case 无重复 url |
| graph 完成 | ≥2/3 |

### Fix 4: quality_filter.py — 补 Table/Figure 带冒号 pattern (10min)

#### 问题

`_NON_PAPER_PATTERNS` 有 `^table\s*\d+` 和 `^figure\s*\d+`，但没匹配 `Table 2:` 和 `Figure 3:`（冒号在数字后面，正则 `^table\s*\d+` 匹配 "Table 2" 但不匹配 "Table 2:" 因为 `:` 不在 `\d+` 中——实际上 `^table\s*\d+` 会匹配 "Table 2:" 的前缀 "Table 2"，所以应该能匹配）。

需要确认：`^table\s*\d+` 是否匹配 "Table 2: Accuracy comparison..."？

- `^table\s*\d+` 匹配 "Table 2" → 是的，`re.search(r"(?i)^table\s*\d+", "Table 2: Accuracy")` 会匹配。
- 但 quality_filter 的 pre_filter 只检查 title，如果 title 是 "Table 2: Accuracy comparison..."，`^table\s*\d+` 会匹配。

所以 **Fix 4 可能不需要**——已有 pattern 应该能匹配。需要在验证中确认。

如果确认已有 pattern 能匹配，Fix 4 跳过，记录"已有 pattern 可匹配，无需修改"。

如果确认不能匹配，改为：

```python
r"(?i)^table\s*\d+:?",   # 匹配 "Table 2:" 和 "Table 2"
r"(?i)^figure\s*\d+:?",  # 匹配 "Figure 3:" 和 "Figure 3"
```

#### 3-case 验证

| 检查项 | 通过标准 |
|---|---|
| verified_papers 中无 "Table \d" / "Figure \d" 开头的 title | ≥2/3 case 无此模式 |
| 如果已有 pattern 能匹配 → 跳过 Fix 4 | 记录"已有 pattern 足够" |

### Fix 5: dataset_repo_extractor.py — github URL 兜底 + heuristic dataset 提取 (30min)

#### 问题 A: github URL 兜底

Fix 1 在 retrieve 层修复了 URL，但 dataset_repo_extractor 的 github fix 代码也需要兜底（以防 Fix 1 未生效或旧数据）。

#### 修改 A

**文件**：`apps/api/app/services/agents/graph/nodes/dataset_repo_extractor.py`

在 github_repos 构建时，转换 URL：

```python
# 在 github_repos 构建时
if "api.github.com/repos/" in repo_url:
    path = repo_url.split("api.github.com/repos/", 1)[-1].rstrip("/")
    repo_url = f"https://github.com/{path}"
```

#### 问题 B: dataset heuristic 提取

LLM 从论文摘要提取 dataset 全部为空。但 innovation_points 的 stitching_plan 中经常提到已知数据集名（如 "TUM RGB-D"、"Bonn"、"EuRoC MAV"、"NEU-DET"）。应该从 stitching_plan 中提取已知数据集名作为 heuristic 补充。

#### 修改 B

**文件**：`apps/api/app/services/agents/graph/nodes/dataset_repo_extractor.py`

在 LLM 提取后，heuristic 补充：

```python
# 已知数据集注册表
_KNOWN_DATASETS = [
    "NEU-DET", "GC10-DET", "COCO", "Pascal VOC", "ImageNet",
    "KITTI", "TUM RGB-D", "EuRoC MAV", "Bonn", "ScanNet",
    "Cityscapes", "nuScenes", "DOTA", "DIOR", "AID",
    "CIFAR-10", "CIFAR-100", "MNIST", "Fashion-MNIST",
    "VisDrone", "Matterport3D", "ETH3D", "Tanks and Temples",
    "MedQA", "MedMCQA", "USMLE", "MMLU", "GLUE", "SQuAD",
    "PCB Defect", "CrackTree", "Crack500", "DeepCrack",
    "SDNET2018", "BDD100K", "TT100K",
]

# 在 LLM 提取后
innovation_points = state.get("innovation_points") or []
for inn in innovation_points:
    plan = inn.get("stitching_plan", "") or ""
    desc = inn.get("description", "") or ""
    text = f"{plan} {desc}"
    for ds_name in _KNOWN_DATASETS:
        if ds_name.lower() in text.lower():
            rec = {
                "from_paper": "innovation_plan",
                "linked_paper_id": "innovation_plan",
                "kind": "dataset",
                "name": ds_name,
                "url": None,
                "source": "innovation_plan_heuristic",
                "availability": "named",
                "status": "found",
                "reproducibility_hint": "mentioned in innovation plan",
                "risk": "",
            }
            k = ds_key(rec)
            if k and k not in ds_seen:
                ds_seen.add(k)
                datasets.append(rec)
```

注意：这个 heuristic 在 graph 执行顺序中，`dataset_repo_extractor` 在 `innovation_extractor` **之前**执行（graph 顺序是 dataset_repo → json_graph → baseline_classifier → feasibility → work_package → innovation_extractor）。所以 `state.get("innovation_points")` 在 dataset_repo_extractor 执行时为空。

**解决方案**：把 heuristic dataset 提取放到 `json_graph_builder` 之后、`final_recommendation` 之前的某个节点中。或者新增一个轻量 `dataset_enricher` 步骤。

**最简方案**：在 `dataset_repo_extractor` 中只做 github URL 修复（修改 A），不做 heuristic dataset 提取（修改 B）。heuristic dataset 提取留到 Re2.3。

#### 最终修改

只做修改 A（github URL 兜底），修改 B（heuristic dataset）跳过，记录"需要 graph 顺序调整，留到 Re2.3"。

#### 3-case 验证

| 检查项 | 通过标准 |
|---|---|
| repo_candidates 中 url 不含 `api.github.com` | ≥2/3 case 的 repo url 是 github.com 格式 |
| V-SLAM 的 repo_candidates ≥1 | V-SLAM 有 github 论文 → repo_candidates 非空 |
| graph 完成 | ≥2/3 |

## 4. 验证脚本设计

### re22_fix_verify.py

```python
"""Re2.2-fix 3-case 验证脚本。

用法:
    python apps/api/scripts/re22_fix_verify.py
"""

import json
import os
import time
from pathlib import Path

V_CASES = [
    ("V-SLAM", "基于深度学习的视觉SLAM语义地图的研究"),
    ("V-CRACK", "基于深度学习的混凝土桥梁裂缝检测研究"),
    ("V-MED", "基于大语言模型的医学问答可信度评估方法研究"),
]

OUT_DIR = Path("tmp_re22fix_eval/verify")
OUT_DIR.mkdir(parents=True, exist_ok=True)

def run_one_case(vid: str, topic: str) -> dict:
    """跑一个 case，返回结果摘要。"""
    from apps.api.app.services.agents.graph.research_graph import build_graph
    from apps.api.app.services.agents.graph.state import ResearchState

    t0 = time.time()
    g = build_graph()
    out = g.invoke(
        {"case_id": f"re22fix-{vid}", "topic": topic,
         "trace_events": [], "errors": [], "provider_profile": "fast_json"},
        config={"recursion_limit": 50},
    )
    elapsed = round(time.time() - t0, 1)

    verified = out.get("verified_papers") or []
    weak = out.get("weak_papers") or []
    repos = out.get("repo_candidates") or []
    datasets = out.get("dataset_candidates") or []
    eg = out.get("evidence_graph") or {}

    # 检查 1: github URL 不含 api.github.com
    github_papers = [p for p in verified if (p.get("source") or "").lower() == "github"]
    github_urls = [p.get("url") or "" for p in github_papers]
    has_api_url = any("api.github.com" in u for u in github_urls)

    # 检查 2: evidence_graph 中 github 节点 type
    eg_nodes = eg.get("nodes") or []
    github_eg_nodes = [n for n in eg_nodes if "github" in (n.get("title") or "").lower()
                       or "openvslam" in (n.get("title") or "").lower()
                       or "orb_slam" in (n.get("title") or "").lower()]
    github_as_repo = [n for n in github_eg_nodes if n.get("type") == "repo"]
    github_as_paper = [n for n in github_eg_nodes if n.get("type") == "paper"]

    # 检查 3: verified_papers 去重
    titles = [(p.get("title") or "").lower().strip() for p in verified]
    dup_titles = [t for t in set(titles) if titles.count(t) > 1]

    # 检查 4: Table/Figure 标题
    import re
    table_figure_titles = [p.get("title", "") for p in verified
                           if re.match(r"(?i)^(table|figure)\s*\d", p.get("title", ""))]

    # 检查 5: repo_candidates
    repo_urls = [r.get("url") or "" for r in repos]
    repo_has_api = any("api.github.com" in u for u in repo_urls)

    return {
        "vid": vid,
        "elapsed_s": elapsed,
        "has_final": bool(out.get("final_recommendation")),
        "n_verified": len(verified),
        "n_weak": len(weak),
        "n_repos": len(repos),
        "n_datasets": len(datasets),
        "github_papers_in_verified": len(github_papers),
        "github_url_has_api": has_api_url,
        "github_eg_as_repo": len(github_as_repo),
        "github_eg_as_paper": len(github_as_paper),
        "dup_titles": dup_titles,
        "table_figure_titles": table_figure_titles,
        "repo_urls": repo_urls[:5],
        "repo_has_api": repo_has_api,
        "crash": False,
    }


def main():
    results = []
    for vid, topic in V_CASES:
        print(f"\n{'='*60}")
        print(f"Running {vid}: {topic}")
        try:
            result = run_one_case(vid, topic)
            results.append(result)
            print(f"  has_final={result['has_final']}, verified={result['n_verified']}, "
                  f"repos={result['n_repos']}, datasets={result['n_datasets']}")
            print(f"  github_api_url={result['github_url_has_api']}, "
                  f"eg_repo={result['github_eg_as_repo']}, eg_paper={result['github_eg_as_paper']}")
            print(f"  dup_titles={result['dup_titles']}, table_figure={result['table_figure_titles']}")
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append({"vid": vid, "error": str(e), "crash": True})

    # 保存结果
    out_path = OUT_DIR / f"verify_{int(time.time())}.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nResults saved to {out_path}")

    # 汇总通过率
    checks = {
        "github_url_fixed": sum(1 for r in results if not r.get("github_url_has_api", True)),
        "eg_type_repo": sum(1 for r in results if r.get("github_eg_as_repo", 0) > 0),
        "no_dup_titles": sum(1 for r in results if not r.get("dup_titles")),
        "no_table_figure": sum(1 for r in results if not r.get("table_figure_titles")),
        "has_final": sum(1 for r in results if r.get("has_final")),
    }
    print(f"\nPass rates: {json.dumps(checks, indent=2)}")


if __name__ == "__main__":
    main()
```

## 5. 执行顺序

```
Fix 1 (retrieve URL) → 验证 3 case → 通过则 Fix 2
                                        ↓
Fix 2 (graph builder type) → 验证 3 case → 通过则 Fix 3
                                        ↓
Fix 3 (verify dedup) → 验证 3 case → 通过则 Fix 4
                                        ↓
Fix 4 (quality_filter pattern) → 验证 3 case → 确认已有 pattern 是否足够
                                        ↓
Fix 5 (dataset_repo github URL兜底) → 验证 3 case → 完成
```

每个 Fix 独立验证，失败回滚，不阻塞后续。

## 6. 禁止事项

- 禁止同时改多个文件。
- 禁止改完代码不跑 3-case 验证。
- 禁止验证失败不回滚。
- 禁止用 VOAPI / MiniMax。
- 禁止用 mock 数据做验证。
- 禁止只用 1 个 case 验证。

## 7. 交付物

代码：

- `apps/api/app/services/agents/graph/nodes/retrieve.py` 🔧 (Fix 1: github URL 转换)
- `apps/api/app/services/agents/graph/nodes/json_graph_builder.py` 🔧 (Fix 2: github type=repo)
- `apps/api/app/services/agents/graph/nodes/verify.py` 🔧 (Fix 3: 去重)
- `apps/api/app/services/agents/graph/nodes/quality_filter.py` 🔧 (Fix 4: 如果需要)
- `apps/api/app/services/agents/graph/nodes/dataset_repo_extractor.py` 🔧 (Fix 5: github URL 兜底)
- `apps/api/scripts/re22_fix_verify.py` 🆕 (3-case 验证脚本)

数据：

- `tmp_re22fix_eval/verify/` (3-case 验证结果, 多次)
- `tmp_re22fix_eval/changelog.md`

报告：

- `Plan/PaperAgent_Re2.2-fix_完工报告.md`

## 8. 最终验收条件

| # | 条件 | 验证方式 |
|---|---|---|
| 1 | github URL 不含 api.github.com | ≥2/3 验证 case |
| 2 | evidence_graph 中 github 节点 type=repo | ≥2/3 验证 case |
| 3 | verified_papers 无重复 title | ≥2/3 验证 case |
| 4 | verified_papers 无 Table/Figure 标题 | ≥2/3 验证 case |
| 5 | V-SLAM 的 repo_candidates ≥1 | 验证 case |
| 6 | graph 完成 | ≥2/3 验证 case |
| 7 | changelog 记录所有改动 | 文件检查 |
| 8 | 每次改动有 3-case 验证记录 | verify/ 目录 |
| 9 | 完工报告完整 | 报告检查 |
| 10 | VOAPI/MiniMax = 0 | 全程 |
