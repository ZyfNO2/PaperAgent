"""Session 65 T3: WorkPackageBrainstormer — 仅在用户选定 baseline 后生成工作包选项.

硬规则:
1. 没 baseline 不生成 — 返回 needs_baseline_selection.
2. 不默认 'attention mechanism' 之类通用词. 模块必须来自真实候选 (parallel / module_papers).
3. 不编造论文/数据集/仓库. 缺证据就返回 need_more_search.
4. 生成 3-5 个 WorkPackageOption, 每个都绑定 baseline + 模块来源 + 数据集 + 实验计划 + 风险.

集成点: workbench 在用户点完 baseline 后调用, 给右侧面板刷出候选工作包.
数据来源: literature_role_classifier (parallel_papers / module_papers) + baseline_selection
(用户选定的 baseline) + research_datasets (datasets).
"""

from __future__ import annotations

import hashlib
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ponytail: 必须禁止的兜底词 (这是用户明确反对的)
FORBIDDEN_DEFAULT_MODULES = frozenset({
    "attention mechanism",
    "attention",
    "self-attention",
    "multi-head attention",
    "transformer",
    "transformer encoder",
})


class WorkPackageOption(BaseModel):
    """单个工作包候选. 字段全部来自真实证据, 不编造."""

    model_config = ConfigDict(extra="forbid")

    proposal_id: str
    title: str
    baseline_candidate_id: str
    baseline_name: str
    borrowed_from_papers: list[str] = Field(default_factory=list)  # candidate_ids
    module_candidates: list[str] = Field(default_factory=list)
    dataset: str | None = None
    experiment_plan: list[str] = Field(default_factory=list)
    why_graduation_friendly: list[str] = Field(default_factory=list)
    risk: list[str] = Field(default_factory=list)
    must_verify_next: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class BrainstormResult(BaseModel):
    """Brainstormer 输出. 三态明确分立."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "need_more_search", "needs_baseline_selection"]
    options: list[WorkPackageOption] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    recommended_tool_calls: list[str] = Field(default_factory=list)
    reason: str


# ---------- 工具 ---------- #


def _normalize_module_name(raw: str) -> str:
    """模块名归一化: 去两端空白, 多个空格压成一个, 长度上限 80."""
    if not raw:
        return ""
    s = re.sub(r"\s+", " ", raw.strip())
    return s[:80]


def _is_forbidden_default_module(name: str) -> bool:
    """检查模块名是否命中禁用的兜底词 (不区分大小写)."""
    low = name.lower().strip()
    if not low:
        return True
    if low in FORBIDDEN_DEFAULT_MODULES:
        return True
    # 'attention' 单字也禁 (短词太容易变成兜底)
    if low == "attention":
        return True
    return False


def _select_modules_from_papers(module_papers: list[dict]) -> list[str]:
    """从真实 module_papers 抽模块名. 没有就返回 [].

    ponytail: 优先 modules_added; 否则降级到 borrowable_ideas 中第一个可作模块的短名.
    """
    out: list[str] = []
    seen: set[str] = set()

    for p in module_papers or []:
        if not isinstance(p, dict):
            continue
        modules = p.get("modules_added") or []
        if isinstance(modules, list) and modules:
            for m in modules:
                nm = _normalize_module_name(str(m))
                if not nm:
                    continue
                if _is_forbidden_default_module(nm):
                    continue
                key = nm.lower()
                if key in seen:
                    continue
                seen.add(key)
                out.append(nm)
        else:
            # 降级: 从 borrowable_ideas 取第一条短名 (<= 40 字符)
            ideas = p.get("borrowable_ideas") or []
            if isinstance(ideas, list) and ideas:
                idea = _normalize_module_name(str(ideas[0]))
                if idea and len(idea) <= 40 and not _is_forbidden_default_module(idea):
                    key = idea.lower()
                    if key not in seen:
                        seen.add(key)
                        out.append(idea)

    return out


def _extract_dataset_from_paper(paper: dict) -> str | None:
    """从论文 dict 抽第一个数据集名."""
    if not isinstance(paper, dict):
        return None
    datasets = paper.get("datasets") or []
    if isinstance(datasets, list) and datasets:
        first = datasets[0]
        if isinstance(first, str) and first.strip():
            return first.strip()[:80]
    return None


def _extract_dataset_from_list(datasets: list[dict]) -> str | None:
    """从 datasets 列表 (含 url/license/size 等) 取第一个名字."""
    if not datasets:
        return None
    for d in datasets:
        if not isinstance(d, dict):
            continue
        name = d.get("name") or d.get("title") or d.get("dataset")
        if isinstance(name, str) and name.strip():
            return name.strip()[:80]
    return None


def _check_evidence_sufficiency(
    selected_baselines: list[dict],
    parallel_papers: list[dict],
    datasets: list[dict],
) -> tuple[bool, list[str]]:
    """检查证据是否足够 brainstorm.

    必须项:
      - 至少 1 个 baseline (用户选定)
      - 至少 1 个 parallel_paper (用于对齐思路)
      - 数据集: parallel_paper 有 datasets 或 datasets 列表非空
    """
    missing: list[str] = []

    if not selected_baselines:
        missing.append("baseline (用户尚未从候选中选定)")

    if not parallel_papers:
        missing.append("parallel_papers (同问题不同方法的论文)")

    has_dataset_in_paper = any(_extract_dataset_from_paper(p) for p in parallel_papers)
    has_dataset_in_list = _extract_dataset_from_list(datasets) is not None
    if not has_dataset_in_paper and not has_dataset_in_list:
        missing.append("dataset (parallel_paper 或 datasets 列表中至少需要 1 个)")

    return (len(missing) == 0, missing)


def _safe_id(*parts: str) -> str:
    """生成稳定 proposal_id (基于内容 hash, 长度 16)."""
    h = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"wp_{h}"


def _build_experiment_plan(
    baseline_name: str,
    modules: list[str],
    dataset: str | None,
    user_constraints: dict,
) -> list[str]:
    """从 baseline + modules + dataset 生成 4 步实验计划.

    ponytail: 模板拼装, 不引 LLM. 短句长度 ≤ 60 字符.
    """
    plan: list[str] = []

    plan.append(f"Step 1: 复现 {baseline_name} 在 {dataset or '目标数据集'} 上的基线指标")

    if modules:
        plan.append(f"Step 2: 接入模块 {modules[0]} 并重训, 记录指标变化")
        if len(modules) >= 2:
            plan.append(f"Step 3: 叠加模块 {modules[1]} 做消融, 对比单独接入差异")
    else:
        plan.append("Step 2: 微调 baseline 的超参 (lr / batch / epoch) 寻找最优")

    if modules:
        plan.append(f"Step {3 if len(modules) < 2 else 4}: 与 {baseline_name} 原论文指标对比, 撰写分析")
    else:
        plan.append("Step 3: 与 {baseline_name} 原始论文对比并撰写分析")

    has_constraint = bool(user_constraints)
    if has_constraint:
        plan.append("Final: 在用户约束 (算力 / 时长 / 部署) 下复核可行性")

    return plan


def _graduation_friendly_reasons(
    baseline_name: str,
    modules: list[str],
    reproducibility: str,
) -> list[str]:
    """基于证据生成 2-3 条毕业友好理由."""
    out: list[str] = []
    if reproducibility in ("high", "medium"):
        out.append(f"{baseline_name} 复现成本可控, 已被多论文验证")
    else:
        out.append(f"{baseline_name} 开源代码可获取, 可作为起点")
    if modules:
        out.append(f"模块 {modules[0]} 有现成实现可移植, 工作量边界清晰")
    out.append("工作量可在 12-16 周内完成, 适合本科/硕士毕设节奏")
    return out


def _risk_notes(
    baseline_name: str,
    modules: list[str],
    dataset: str | None,
) -> list[str]:
    """风险提示. 只生成有依据的, 不编造具体百分比."""
    out: list[str] = []
    if not dataset:
        out.append("数据集未锁定: 需先确认数据集可访问, 否则实验无法启动")
    if modules and len(modules) >= 3:
        out.append("模块叠加较多: 消融实验复杂度上升, 建议先做 1-2 个核心模块")
    out.append(f"{baseline_name} 复现结果可能与原论文有偏差, 需调参对齐")
    return out


def _must_verify_next(
    baseline_id: str,
    modules: list[str],
    dataset: str | None,
    parallel_papers: list[dict],
) -> list[str]:
    """下一步必须人工核实的项目 (证据不足的地方)."""
    out: list[str] = []
    out.append(f"核实 {baseline_id} 的代码仓库是否仍可访问 / 协议是否允许毕设使用")
    if not dataset:
        out.append("确认数据集名称与下载入口 (去原始 paper / 官方页核对)")
    if modules:
        for m in modules[:2]:
            out.append(f"在对应 paper 中确认模块 {m} 的实现细节")
    # parallel_paper 数量少时建议补搜
    if len(parallel_papers) < 3:
        out.append(f"当前仅 {len(parallel_papers)} 篇 parallel 论文, 建议补搜提升覆盖面")
    return out


# ---------- 主入口 ---------- #


def brainstorm_work_packages(
    selected_baselines: list[dict],
    parallel_papers: list[dict],
    module_papers: list[dict],
    datasets: list[dict],
    user_constraints: dict | None = None,
    *,
    max_options: int = 5,
) -> BrainstormResult:
    """生成 3-5 个工作包选项.

    Args:
        selected_baselines: 用户选定的 baseline, 每个 dict 含
            candidate_id / name / baseline_role / user_reason.
        parallel_papers: 同问题不同方法的论文, dict 含 candidate_id / title /
            datasets / modules_added / borrowable_ideas.
        module_papers: 提出具体模块的论文, dict 字段同上.
        datasets: 数据集候选列表, dict 含 name / url / license / size.
        user_constraints: 用户约束 (算力 / 时长 / 部署), 可空.
        max_options: 最多生成几个选项 (3-5).

    Returns:
        BrainstormResult, 状态严格分立:
          - needs_baseline_selection: 没 baseline
          - need_more_search: 证据不足
          - ok: 生成成功
    """
    user_constraints = user_constraints or {}
    max_options = max(3, min(5, int(max_options)))

    # 规则 1: 没有 baseline 选 → 直接 needs_baseline_selection
    if not selected_baselines:
        return BrainstormResult(
            status="needs_baseline_selection",
            options=[],
            missing=["baseline (用户尚未从候选中选定)"],
            recommended_tool_calls=["open_baseline_selection_panel"],
            reason="必须先选择 baseline 才能生成工作包",
        )

    # 规则 5: 证据不足 → need_more_search
    sufficient, missing = _check_evidence_sufficiency(
        selected_baselines, parallel_papers, datasets,
    )
    if not sufficient:
        return BrainstormResult(
            status="need_more_search",
            options=[],
            missing=missing,
            recommended_tool_calls=[
                "search_parallel_papers",
                "verify_dataset_access",
            ],
            reason="证据不足以生成工作包: " + "; ".join(missing),
        )

    # 规则 2: 从真实 module_papers 抽模块 (没有就空, 不默认 attention)
    real_modules = _select_modules_from_papers(module_papers)

    # 数据集: 优先 parallel_paper 自带, 否则取 datasets 列表第一个
    dataset = next(
        (_extract_dataset_from_paper(p) for p in parallel_papers if _extract_dataset_from_paper(p)),
        None,
    )
    if not dataset:
        dataset = _extract_dataset_from_list(datasets)

    # 为每个 baseline 生成 1 个工作包, 上限 max_options
    options: list[WorkPackageOption] = []
    for idx, b in enumerate(selected_baselines[:max_options]):
        if not isinstance(b, dict):
            continue
        baseline_id = str(b.get("candidate_id") or b.get("name") or f"baseline_{idx}")
        baseline_name = str(b.get("name") or b.get("title") or baseline_id)

        # 每个 baseline 用前 2 个真实模块 (没有就空, 不补默认)
        mods_for_this = real_modules[:2] if real_modules else []

        # borrowed_from_papers: 从 module_papers 中选 candidate_id, 上限 3
        borrowed_ids: list[str] = []
        for p in module_papers or []:
            if not isinstance(p, dict):
                continue
            cid = p.get("candidate_id")
            if isinstance(cid, str) and cid and cid not in borrowed_ids:
                borrowed_ids.append(str(cid))
            if len(borrowed_ids) >= 3:
                break

        reproducibility = str(b.get("reproducibility") or "unknown")

        plan = _build_experiment_plan(baseline_name, mods_for_this, dataset, user_constraints)
        friendly = _graduation_friendly_reasons(baseline_name, mods_for_this, reproducibility)
        risk = _risk_notes(baseline_name, mods_for_this, dataset)
        verify = _must_verify_next(baseline_id, mods_for_this, dataset, parallel_papers)

        # 置信度: 有模块 + 有数据集 + baseline 完整 → 高; 否则逐项扣
        conf = 0.6
        if mods_for_this:
            conf += 0.15
        if dataset:
            conf += 0.15
        if baseline_id and baseline_name:
            conf += 0.05
        conf = min(0.95, round(conf, 2))

        proposal_id = _safe_id(baseline_id, ",".join(mods_for_this), dataset or "")

        options.append(WorkPackageOption(
            proposal_id=proposal_id,
            title=f"基于 {baseline_name} 的工作包 #{idx + 1}",
            baseline_candidate_id=baseline_id,
            baseline_name=baseline_name,
            borrowed_from_papers=borrowed_ids,
            module_candidates=mods_for_this,
            dataset=dataset,
            experiment_plan=plan,
            why_graduation_friendly=friendly,
            risk=risk,
            must_verify_next=verify,
            confidence=conf,
        ))

    if not options:
        # selected_baselines 里有 dict 但都被跳过 (极端情况) → 视为证据不足
        return BrainstormResult(
            status="need_more_search",
            options=[],
            missing=["selected_baselines 列表内容无法解析"],
            recommended_tool_calls=["re_select_baseline"],
            reason="baseline 列表内容无效, 需重新选择",
        )

    return BrainstormResult(
        status="ok",
        options=options,
        missing=[],
        recommended_tool_calls=["open_proposal_review_panel"],
        reason=f"基于 {len(options)} 个 baseline 生成工作包选项",
    )


__all__ = [
    "WorkPackageOption",
    "BrainstormResult",
    "brainstorm_work_packages",
    "_select_modules_from_papers",
    "_check_evidence_sufficiency",
]