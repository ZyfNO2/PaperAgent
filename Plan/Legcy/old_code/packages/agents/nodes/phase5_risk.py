"""Phase 05: 六维风险评分 + Pivot 候选生成。

MVP 设计：
- 六维评分：纯规则，从 EvidenceLedger 字段数 / 字段质量 / TopicSpec 字段推
- 总体评级：A/B/C/D 取决于 overall_score + goal_level 阈值
- Pivot 候选：优先 LLM（需要创造力），失败 fallback 启发式
"""

from __future__ import annotations

from packages.domain import (
    DimensionKey,
    DimensionScore,
    EvidenceLedger,
    PivotCandidate,
    ProjectIntake,
    RiskEvaluation,
    RiskScore,
    SearchQueryPlan,
    TopicSpec,
)
from packages.llm import chat_json, LLMUnavailable


_PIVOT_PROMPT = """你是中国研究生开题选题助手。基于 EvidenceLedger + TopicSpec，
生成 1-3 个 Pivot 候选方案：

每条候选需满足：
- pivot_id: "P01" / "P02" / "P03"
- pivot_type: "收缩"（题目过大但证据可用）或 "换向"（关键证据缺失）
- new_topic: 收缩 / 转向后的新题目（中文，30 字以内）
- rationale: 一句话说明为什么这样 pivot
- preserved_evidence: 可保留的论文 / baseline / 数据名称
- new_evidence_needed: 还需补哪些证据
- residual_risk: 低/中/高/未知

如果 evidence_rating='A' 且决策为"继续"，可以只生成 1 个收缩候选（防御性）。

输入：
goal_level: {goal_level}
overall_rating: {overall_rating}
overall_score: {overall_score}
max_risk_dimension: {max_risk}
raw_topic: {raw_topic}
normalized_topic: {normalized_topic}
risk_terms: {risk_terms}
papers_count: {papers_count}
datasets_count: {datasets_count}
baselines_count: {baselines_count}
metrics_count: {metrics_count}
thesis_templates_count: {thesis_templates_count}

严格 JSON 输出: {{"pivots": [ ... ]}}
"""


# ---------------- 六维评分 ---------------- #


def _score_maturity(ledger: EvidenceLedger) -> DimensionScore:
    """方向成熟度: 论文 + 综述 + 学位论文模板 (带 ++/-- 信号)."""

    pluses: list[str] = []
    minuses: list[str] = []
    s = 0.0
    n_papers = len(ledger.papers)
    paper_score = min(n_papers * 4, 40)
    s += paper_score
    if n_papers >= 5:
        pluses.append(f"方向论文多 ({n_papers} 篇) +{paper_score}")
    elif n_papers >= 3:
        pluses.append(f"方向论文中等 ({n_papers} 篇) +{paper_score}")
    else:
        minuses.append(f"方向论文少 ({n_papers} 篇) +{paper_score}")
    n_surveys = len(ledger.surveys)
    survey_score = min(n_surveys * 10, 20)
    s += survey_score
    if n_surveys >= 1:
        pluses.append(f"有综述 ({n_surveys} 篇) +{survey_score}")
    else:
        minuses.append("缺综述 +0")
    n_tpl = len(ledger.thesis_templates)
    tpl_score = min(n_tpl * 15, 25)
    s += tpl_score
    if n_tpl >= 1:
        pluses.append(f"有学位论文模板 ({n_tpl} 份) +{tpl_score}")
    if n_papers >= 5 and n_surveys >= 1:
        s += 15
        pluses.append("论文+综述齐 +15")
    s = min(s, 100.0)
    return DimensionScore(
        key="方向成熟度",
        score=s,
        evidence_summary=f"{n_papers} 篇论文 + {n_surveys} 篇综述 + {n_tpl} 份学位论文模板",
        risk_note=("论文数 < 5" if n_papers < 5 else None),
        pluses=pluses,
        minuses=minuses,
    )


def _score_data(ledger: EvidenceLedger, intake: ProjectIntake) -> DimensionScore:
    """数据可得性: datasets + inherited_resources (带 ++/-- 信号)."""

    pluses: list[str] = []
    minuses: list[str] = []
    s = 0.0
    n_ds = len(ledger.datasets)
    ds_score = min(n_ds * 25, 60)
    s += ds_score
    if n_ds >= 2:
        pluses.append(f"数据集候选足 ({n_ds} 个) +{ds_score}")
    elif n_ds == 1:
        pluses.append(f"数据集候选勉强 ({n_ds} 个) +{ds_score}")
        minuses.append("数据集候选 < 2 偏少")
    else:
        minuses.append("无数据集候选 +0")
    inherited_avail = sum(1 for r in intake.inherited_resources if r.available)
    ir_score = min(inherited_avail * 20, 40)
    s += ir_score
    if inherited_avail >= 1:
        pluses.append(f"继承资源可用 ({inherited_avail} 项) +{ir_score}")
    elif intake.inherited_resources:
        minuses.append(f"继承资源未标可用 ({len(intake.inherited_resources)} 项) +0")
    else:
        minuses.append("无继承资源 (需自采数据) +0")
    s = min(s, 100.0)
    return DimensionScore(
        key="数据可得性",
        score=s,
        evidence_summary=f"{n_ds} 个数据集候选, {inherited_avail} 项继承资源可用",
        risk_note=("无数据集候选" if n_ds == 0 else None),
        pluses=pluses,
        minuses=minuses,
    )


def _score_baseline(ledger: EvidenceLedger) -> DimensionScore:
    """baseline 清晰度: 复现难度 + 数量 (带 ++/-- 信号)."""

    pluses: list[str] = []
    minuses: list[str] = []
    n_b = len(ledger.baselines)
    if n_b == 0:
        return DimensionScore(
            key="baseline清晰度",
            score=0.0,
            evidence_summary="0 个 baseline 候选",
            risk_note="无 baseline 候选",
            pluses=[],
            minuses=["无 baseline 候选, 必须自实现 baseline"],
        )
    diff_score = {"低": 30, "中": 18, "高": 5, "未知": 12}
    raw = sum(diff_score.get(b.reproduce_difficulty, 12) for b in ledger.baselines)
    s = min(raw + 10, 100.0)
    n_low = sum(1 for b in ledger.baselines if b.reproduce_difficulty == "低")
    n_mid = sum(1 for b in ledger.baselines if b.reproduce_difficulty == "中")
    n_high = sum(1 for b in ledger.baselines if b.reproduce_difficulty == "高")
    n_unk = sum(1 for b in ledger.baselines if b.reproduce_difficulty == "未知")
    if n_low >= 1:
        pluses.append(f"有低复现难度 baseline ({n_low} 个) +{n_low * 30}")
    if n_mid >= 1:
        pluses.append(f"有中复现难度 baseline ({n_mid} 个) +{n_mid * 18}")
    if n_b >= 2:
        pluses.append(f"baseline 候选数足 ({n_b} 个) +10")
    if n_high >= 1:
        minuses.append(f"{n_high} 个高复现难度 baseline +{n_high * 5}")
    if n_unk >= 1:
        minuses.append(f"{n_unk} 个未知复现难度 +0")
    if n_b < 2:
        minuses.append(f"baseline 候选 < 2 ({n_b} 个)")
    return DimensionScore(
        key="baseline清晰度",
        score=s,
        evidence_summary=f"{n_b} 个 baseline 候选, 复现难度: 低 {n_low} / 中 {n_mid} / 高 {n_high} / 未知 {n_unk}",
        risk_note=None,
        pluses=pluses,
        minuses=minuses,
    )


def _score_experiment(ledger: EvidenceLedger) -> DimensionScore:
    """实验可行性: metrics + experiment_templates (带 ++/-- 信号)."""

    pluses: list[str] = []
    minuses: list[str] = []
    s = 0.0
    n_metrics = len(ledger.metrics)
    metric_score = min(n_metrics * 8, 50)
    s += metric_score
    if n_metrics >= 1:
        pluses.append(f"有评价指标 ({n_metrics} 套) +{metric_score}")
    else:
        minuses.append("无评价指标 (无法量化结果) +0")
    n_exp = len(ledger.experiment_templates)
    exp_score = min(n_exp * 15, 40)
    s += exp_score
    if n_exp >= 2:
        pluses.append(f"实验模板足 ({n_exp} 个, 对比+消融齐) +{exp_score}")
    elif n_exp == 1:
        pluses.append(f"实验模板勉强 ({n_exp} 个) +{exp_score}")
        minuses.append("实验模板 < 2 偏少")
    else:
        minuses.append("无实验模板 +0")
    if ledger.metrics:
        s += 10
        pluses.append("指标可复现 +10")
    s = min(s, 100.0)
    return DimensionScore(
        key="实验可行性",
        score=s,
        evidence_summary=f"{n_metrics} 套指标 + {n_exp} 个实验模板",
        risk_note=("无指标" if not ledger.metrics else None),
        pluses=pluses,
        minuses=minuses,
    )


def _score_workload(spec: TopicSpec, ledger: EvidenceLedger) -> DimensionScore:
    """工作量可拆性: WP 数量 + wp_binding 覆盖 (带 ++/-- 信号)."""

    pluses: list[str] = []
    minuses: list[str] = []
    s = 0.0
    n_wp = len(spec.work_package_drafts)
    wp_score = min(n_wp * 35, 70)
    s += wp_score
    if n_wp >= 2:
        pluses.append(f"工作包可拆 ({n_wp} 个) +{wp_score}")
    else:
        minuses.append(f"工作包数 < 2 ({n_wp} 个) +{wp_score}")
    bound_wp = set()
    for ev in (*ledger.papers, *ledger.datasets, *ledger.baselines):
        bound_wp.update(ev.wp_binding or [])
    bind_score = min(len(bound_wp) * 15, 30)
    s += bind_score
    if len(bound_wp) >= 2:
        pluses.append(f"证据已绑定 ({len(bound_wp)} 个 WP 被绑) +{bind_score}")
    else:
        minuses.append(f"证据未充分绑定 ({len(bound_wp)} 个被绑) +{bind_score}")
    s = min(s, 100.0)
    return DimensionScore(
        key="工作量可拆性",
        score=s,
        evidence_summary=f"{n_wp} 个工作包, {len(bound_wp)} 个被 evidence 绑定",
        risk_note=("WP < 2" if n_wp < 2 else None),
        pluses=pluses,
        minuses=minuses,
    )


def _score_time(ledger: EvidenceLedger, intake: ProjectIntake) -> DimensionScore:
    """毕业时间风险: 首张结果表 + baseline 复现周期 (带 ++/-- 信号)."""

    pluses: list[str] = []
    minuses: list[str] = []
    s = 0.0
    if not intake.first_result_deadline:
        return DimensionScore(
            key="毕业时间风险",
            score=20.0,
            evidence_summary="无 first_result_deadline, 无法估算时间红线",
            risk_note="无时间红线",
            pluses=[],
            minuses=["未填首张结果表时间, 无法估算毕业时间风险"],
        )
    high_diff = sum(1 for b in ledger.baselines if b.reproduce_difficulty == "高")
    s = 80.0 - high_diff * 15
    s = max(min(s, 100.0), 0.0)
    if high_diff == 0:
        pluses.append("无高复现难度 baseline, 8 个月内能出第一张表 +80")
    elif high_diff == 1:
        minuses.append("1 个高复现难度 baseline 可能拖进度 -15")
    else:
        minuses.append(f"{high_diff} 个高复现难度 baseline, 时间红线危险 -{high_diff * 15}")
    weekly = (intake.student_resources.weekly_hours if intake.student_resources else 0) or 0
    if weekly >= 25:
        pluses.append(f"每周投入足 ({weekly}h ≥ 25)")
    return DimensionScore(
        key="毕业时间风险",
        score=s,
        evidence_summary=f"首张结果表 {intake.first_result_deadline}, {high_diff} 个高复现难度 baseline",
        risk_note=("baseline 复现周期可能超时间红线" if high_diff > 0 else None),
        pluses=pluses,
        minuses=minuses,
    )


# ---------------- 总体评级 ---------------- #


def _overall(goal: str, dim_scores: list[DimensionScore]) -> tuple[float, str]:
    """根据 goal_level 调阈值。保毕业要求更高。"""

    avg = sum(d.score for d in dim_scores) / len(dim_scores)
    # 阈值: 保毕业 70/55/40, 稳中求新 65/50/35, 冲高水平 60/45/30
    if goal == "保毕业":
        a, b, c = 70, 55, 40
    elif goal == "稳中求新":
        a, b, c = 65, 50, 35
    else:  # 冲高水平
        a, b, c = 60, 45, 30

    if avg >= a:
        rating = "A"
    elif avg >= b:
        rating = "B"
    elif avg >= c:
        rating = "C"
    else:
        rating = "D"
    return avg, rating


def _min_viable_path(intake: ProjectIntake, ledger: EvidenceLedger, rating: str) -> str:
    if rating == "A":
        return (
            f"按当前方向继续：先复现 1 个低难度 baseline，"
            f"再以 {intake.goal_level} 目标在 {intake.first_result_deadline or '约定时间'} 前出第一张主结果表"
        )
    if rating == "B":
        return (
            "继续当前方向，但必须并行准备 1 个 Pivot 候选；"
            "若 1 个月内 baseline 复现失败或数据无法到位，立刻切换"
        )
    if rating == "C":
        return (
            "建议先做 1-2 周额外证据补强（公开数据集 + 1 个低复现难度 baseline）；"
            "若仍不到位，立即采用 Pivot 候选"
        )
    return (
        "不建议继续当前题目；请从 Pivot 候选中选 1 个新方向并回到 Phase 01 重跑建档"
    )


# ---------------- pivot 候选 ---------------- #


def _heuristic_pivots(
    intake: ProjectIntake, spec: TopicSpec, rating: str
) -> list[PivotCandidate]:
    """P0: 给 1 个通用"收缩到具体场景" + 1 个"换向到 fallback 任务"。"""

    raw = intake.raw_topic
    narrowed = raw
    for kw in ("大模型的", "通用", "全自动", "智能", "实时"):
        if kw in narrowed:
            # 把"大模型"换成"基于证据链的辅助"，保留核心名词
            narrowed = narrowed.replace(kw, "基于证据链的辅助")
    pivots: list[PivotCandidate] = [
        PivotCandidate(
            pivot_id="P01",
            pivot_type="收缩",
            new_topic=f"面向 {intake.major or '本专业'} 的 {narrowed} 方法研究",
            rationale=(
                "原题范围过大；通过限定专业 + 替换高风险词缩小到具体场景，"
                "保留与现有 evidence 的兼容性"
            ),
            preserved_evidence=[
                "现有 papers / surveys / baselines",
                "原 work_package_drafts 的章节结构",
            ],
            new_evidence_needed=[
                "限定场景的公开数据集",
                "场景内的 1 个 baseline 实现",
            ],
            residual_risk="中",
        ),
        PivotCandidate(
            pivot_id="P02",
            pivot_type="换向",
            new_topic=(
                f"基于 {spec.task_type[0] if spec.task_type else '推荐/分类'} "
                f"任务的 {spec.method_family[0] if spec.method_family else '深度学习'} "
                f"基线对比与消融研究"
            ),
            rationale=(
                "若原题关键证据无法补齐；换到证据更充足的成熟任务，"
                "工作量小、毕业风险低"
            ),
            preserved_evidence=[
                "evaluation_metrics 体系",
                "experiment_templates（对比 / 消融）",
            ],
            new_evidence_needed=[
                "新任务的公开数据集",
                "新任务上的 2 个 baseline",
            ],
            residual_risk="低" if rating in ("C", "D") else "中",
        ),
    ]
    return pivots


def _llm_pivots(
    intake: ProjectIntake,
    spec: TopicSpec,
    ledger: EvidenceLedger,
    risk: RiskScore,
) -> list[PivotCandidate]:
    prompt = _PIVOT_PROMPT.format(
        goal_level=intake.goal_level,
        overall_rating=risk.overall_rating,
        overall_score=f"{risk.overall_score:.1f}",
        max_risk=risk.max_risk_dimension,
        raw_topic=intake.raw_topic,
        normalized_topic=spec.normalized_topic,
        risk_terms="; ".join(t.term for t in spec.risk_terms) or "无",
        papers_count=len(ledger.papers),
        datasets_count=len(ledger.datasets),
        baselines_count=len(ledger.baselines),
        metrics_count=len(ledger.metrics),
        thesis_templates_count=len(ledger.thesis_templates),
    )
    raw = chat_json(
        [
            {"role": "system", "content": "严格按 schema 输出 JSON。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
        max_tokens=2000,
    )
    out: list[PivotCandidate] = []
    for i, p in enumerate(raw.get("pivots") or []):
        try:
            out.append(
                PivotCandidate(
                    pivot_id=p.get("pivot_id") or f"P{i+1:02d}",
                    pivot_type=p.get("pivot_type", "收缩")
                    if p.get("pivot_type") in {"收缩", "换向"} else "收缩",
                    new_topic=str(p.get("new_topic", "")).strip() or f"Pivot {i+1}",
                    rationale=str(p.get("rationale", "")).strip() or "需手动评估",
                    preserved_evidence=list(p.get("preserved_evidence") or []),
                    new_evidence_needed=list(p.get("new_evidence_needed") or []),
                    residual_risk=p.get("residual_risk", "中")
                    if p.get("residual_risk") in {"低", "中", "高", "未知"} else "中",
                )
            )
        except Exception:
            continue
    return out


# ---------------- 公开入口 ---------------- #


def build_risk_score(intake: ProjectIntake, spec: TopicSpec, ledger: EvidenceLedger) -> RiskScore:
    dims = [
        _score_maturity(ledger),
        _score_data(ledger, intake),
        _score_baseline(ledger),
        _score_experiment(ledger),
        _score_workload(spec, ledger),
        _score_time(ledger, intake),
    ]
    overall, rating = _overall(intake.goal_level, dims)
    min_dim = min(dims, key=lambda d: d.score)
    return RiskScore(
        project_id="",
        evidence_ledger_id="",
        goal_level=intake.goal_level,
        dimensions=dims,
        overall_score=overall,
        overall_rating=rating,  # type: ignore[arg-type]
        max_risk_dimension=min_dim.key,
        min_viable_path=_min_viable_path(intake, ledger, rating),
    )


def build_pivots(
    intake: ProjectIntake,
    spec: TopicSpec,
    ledger: EvidenceLedger,
    risk: RiskScore,
    *,
    prefer: str = "auto",
) -> list[PivotCandidate]:
    if prefer == "heuristic":
        return _heuristic_pivots(intake, spec, risk.overall_rating)
    if prefer == "llm":
        return _llm_pivots(intake, spec, ledger, risk)
    # auto
    try:
        out = _llm_pivots(intake, spec, ledger, risk)
        if out:
            return out
    except (LLMUnavailable, ValueError):
        pass
    return _heuristic_pivots(intake, spec, risk.overall_rating)


def build_risk_evaluation(
    intake: ProjectIntake,
    spec: TopicSpec,
    plan: SearchQueryPlan,
    ledger: EvidenceLedger,
    *,
    prefer: str = "auto",
) -> RiskEvaluation:
    risk = build_risk_score(intake, spec, ledger)
    pivots = build_pivots(intake, spec, ledger, risk, prefer=prefer)

    if risk.overall_rating == "A":
        decision = "继续"
        rationale = f"六维平均 {risk.overall_score:.1f}，保底 1 个 pivot 已就绪"
    elif risk.overall_rating == "B":
        decision = "继续"
        rationale = "中低风险，建议继续但并行准备 pivot"
    elif risk.overall_rating == "C":
        decision = "收缩"
        rationale = "中高风险，必须先收缩题目或补证据"
    else:
        decision = "转向"
        rationale = "高风险，不建议继续当前题目"

    must_supplement: list[str] = []
    if len(ledger.datasets) < 2:
        must_supplement.append("至少 2 个数据集候选")
    if len(ledger.baselines) < 2:
        must_supplement.append("至少 2 个 baseline 候选")
    if not ledger.metrics:
        must_supplement.append("至少 1 套评价指标")
    high = [b for b in ledger.baselines if b.reproduce_difficulty == "高"]
    if high:
        must_supplement.append("至少 1 个低/中复现难度的 baseline 替代高难度候选")

    return RiskEvaluation(
        project_id="",
        evidence_ledger_id="",
        goal_level=intake.goal_level,
        risk_score=risk,
        decision=decision,  # type: ignore[arg-type]
        decision_rationale=rationale,
        pivot_candidates=pivots,
        must_supplement=must_supplement,
    )


def allow_proceed_to_phase06(ev: RiskEvaluation) -> tuple[bool, str]:
    if ev.risk_score.overall_rating == "D" and ev.decision != "转向":
        return False, "评级为 D 但决策不是 '转向'"
    if not ev.pivot_candidates and ev.risk_score.overall_rating in ("C", "D"):
        return False, "C/D 评级必须至少 1 个 PivotCandidate"
    return True, "ok"
