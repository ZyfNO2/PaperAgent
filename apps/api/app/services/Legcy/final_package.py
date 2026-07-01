"""FinalPackage Markdown 报告生成 (Session 8 §4-§6).

输入: evidence store 里的 latest_snapshot (Session 7 §7 写入).
输出: 13 章节 Markdown 开题报告 + evidence 引用清单 + revision_checklist.

规则 (SOP §4.4-§4.5):
- coverage_score < 0.70 → 顶部加 warning
- rejected 证据不进入正向引用, 仅可选 appendix
- needs_check 证据只进入"风险预案"/"待补证据", 不进 supports
- core / accepted 优先进入"研究现状" / "可行性分析" / "工作包设计"
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..schemas import (
    EvidenceRef,
    FinalPackage,
    FinalPackageBuildOptions,
    FinalPackageSummary,
    ReportCitation,
    ReportSection,
)
from . import evidence as ev_store
from . import evidence_refs as refs_service
from . import report_templates as tmpl_service


# ---------- 章节模板 (SOP §4.2) ---------- #

SECTION_TITLES: list[tuple[str, str]] = [
    ("background", "一、研究背景与意义"),
    ("related_work", "二、国内外研究现状"),
    ("research_question", "三、研究问题与目标"),
    ("technical_route", "四、研究内容与技术路线"),
    ("data_baseline_metric", "五、数据集、Baseline 与评价指标"),
    ("work_packages", "六、工作包设计"),
    ("innovation", "七、预期创新点"),
    ("feasibility", "八、可行性分析"),
    ("risks", "九、风险预案"),
    ("schedule", "十、进度计划"),
    ("defense_qa", "十一、开题答辩可能追问"),
    ("citations", "十二、证据引用清单"),
    ("todo", "十三、待补证据与修改清单"),
    ("decision_log", "十四、关键决策记录"),  # Session 11 §8
]


# ---------- citation map (§6.3) ---------- #


def _build_citation_map(
    papers: list[Any], datasets: list[Any], repos: list[Any],
    feasibility_refs: list[dict], proposal_refs: list[dict],
    review_refs: list[dict], *,
    options: FinalPackageBuildOptions,
    extras: list[dict] | None = None,
) -> dict[str, ReportCitation]:
    """生成稳定的引用编号.

    - paper → E1, E2, ... (按 review_weight+score 排序, core 优先)
    - dataset → D1, D2, ...
    - repo → R1, R2, ...
    - 同一 evidence_id 在全文编号稳定
    - rejected 默认跳过 (除非 include_rejected_as_appendix)
    - needs_check 默认跳过正向引用 (除非 include_low_confidence_refs)
    - Session 10 §8: extras 提供 verification 字段, 写入 ReportCitation
    """

    cite: dict[str, ReportCitation] = {}
    used_in: dict[str, set[str]] = {}

    # 收集所有可能的 evidence_id 及 section 标签
    candidates: list[tuple[str, str, str, str, str, float | None, str | None]] = []
    for p in papers:
        pid = p.paper_id if hasattr(p, "paper_id") else p.get("paper_id", "")
        title = p.title if hasattr(p, "title") else p.get("title", "")
        url = p.url if hasattr(p, "url") else p.get("url")
        rs = getattr(p, "review_status", "accepted") or "accepted"
        score = getattr(p, "relevance_score", None) or p.get("relevance_score") if isinstance(p, dict) else None
        candidates.append(("paper", pid, title, url, rs, score, "papers"))
    for d in datasets:
        did = d.dataset_id if hasattr(d, "dataset_id") else d.get("dataset_id", "")
        title = d.name if hasattr(d, "name") else d.get("name", "")
        url = d.download if hasattr(d, "download") else d.get("download")
        rs = getattr(d, "fit", "中") or "中"
        candidates.append(("dataset", did, title, url, "accepted" if rs in ("高", "中") else "pending", None, "datasets"))
    for r in repos:
        bid = r.baseline_id if hasattr(r, "baseline_id") else r.get("baseline_id", "")
        title = r.name if hasattr(r, "name") else r.get("name", "")
        url = r.repository_url if hasattr(r, "repository_url") else r.get("repository_url")
        candidates.append(("repo", bid, title, url, "accepted", None, "repos"))

    # 过滤 rejected / needs_check
    def _include(c: tuple) -> bool:
        ev_type, eid, _t, _u, rs, _s, _g = c
        if rs == "rejected" and not options.include_rejected_as_appendix:
            return False
        if rs == "needs_check" and not options.include_low_confidence_refs:
            return False
        return True

    candidates = [c for c in candidates if _include(c)]

    # 排序: paper 优先 core/accepted, 再 score; dataset/repo 同
    def _rank(c: tuple) -> tuple:
        ev_type, _eid, _t, _u, rs, score, _g = c
        rw = refs_service.REVIEW_WEIGHT.get(rs or "pending", 0.2)
        return (0 if ev_type == "paper" else 1 if ev_type == "dataset" else 2, -rw, -(score or 0.5))

    candidates.sort(key=_rank)

    # 编号
    counters = {"paper": 0, "dataset": 0, "repo": 0, "note": 0}
    prefix = {"paper": "E", "dataset": "D", "repo": "R", "note": "N"}

    # Session 10 §8: 从 extras 拿 verification 字段 (手动/assistant_intake 的真实状态)
    extras_v = {}
    if extras:
        for e in extras:
            extras_v[e.get("evidence_id", "")] = {
                "verification_status": e.get("verification_status") or "unverified",
                "verification_confidence": e.get("verification_confidence"),
                "verification_warnings": list(e.get("verification_warnings") or []),
                # Session 13 §7.3: skill 来源合并
                "skill_sources": [
                    s for s in [
                        e.get("created_by_skill"),
                        e.get("scored_by_skill"),
                        e.get("validated_by_skill"),
                    ] if s
                ],
                # Session 15 §16: 来源模式 + 解析置信度 + 页码
                "source_mode": e.get("source_mode"),
                "parse_confidence": e.get("parse_confidence"),
                "page_refs": list(e.get("page_refs") or []),
            }

    for ev_type, eid, title, url, rs, score, group in candidates:
        counters[ev_type] += 1
        ref_no = f"{prefix[ev_type]}{counters[ev_type]}"
        v_meta = extras_v.get(eid, {})
        cite[eid] = ReportCitation(
            ref_no=ref_no,
            evidence_id=eid,
            evidence_type=ev_type,
            title=title or "(无标题)",
            url=url,
            review_status=rs,
            role="supports",
            score=score,
            used_in_sections=[],
            verification_status=v_meta.get("verification_status", "unverified"),
            verification_confidence=v_meta.get("verification_confidence"),
            verification_warnings=v_meta.get("verification_warnings", []),
            skill_sources=v_meta.get("skill_sources", []),
            source_mode=v_meta.get("source_mode"),
            parse_confidence=v_meta.get("parse_confidence"),
            page_refs=v_meta.get("page_refs", []),
        )
        used_in[eid] = set()

    # 标记 used_in_sections
    def _mark(refs_list: list[dict], section_key: str) -> None:
        for r in refs_list or []:
            eid = r.get("evidence_id", "")
            if eid in cite:
                cite[eid].used_in_sections.append(section_key)
                used_in[eid].add(section_key)

    _mark(feasibility_refs, "feasibility")
    _mark(proposal_refs, "work_packages")
    _mark(review_refs, "background")

    # 把 used_in_sections set 转 list (去重保持顺序)
    for eid, c in cite.items():
        seen = []
        for s in c.used_in_sections:
            if s not in seen:
                seen.append(s)
        c.used_in_sections = seen

    return cite


# ---------- 段落内容 (§6.2) ---------- #


def _format_refs(refs: list[dict], cite: dict[str, ReportCitation]) -> str:
    """把 EvidenceRef 列表渲染成 [E1][D1] 形式."""

    parts: list[str] = []
    for r in refs or []:
        eid = r.get("evidence_id", "")
        if eid in cite:
            parts.append(f"[{cite[eid].ref_no}]")
    return "".join(parts)


def _to_evidence_refs(refs: list[dict], cite: dict[str, ReportCitation], limit: int = 5) -> list[EvidenceRef]:
    """dict → EvidenceRef, 容错缺失 reason / review_status / score (snapshot 可能不全)."""

    out: list[EvidenceRef] = []
    for r in refs or []:
        if not isinstance(r, dict):
            continue
        eid = r.get("evidence_id", "")
        if eid not in cite:
            continue
        try:
            ref = EvidenceRef.model_validate({
                "evidence_id": eid,
                "evidence_type": r.get("evidence_type") or cite[eid].evidence_type,
                "title": r.get("title") or cite[eid].title,
                "role": r.get("role") or "supports",
                "reason": r.get("reason") or f"自动引用: {cite[eid].title[:40]}",
                "score": r.get("score") if r.get("score") is not None else cite[eid].score,
                "review_status": r.get("review_status") or cite[eid].review_status,
                "url": r.get("url") if r.get("url") is not None else cite[eid].url,
                "url_verified": r.get("url_verified"),
            })
        except Exception:
            continue
        out.append(ref)
        if len(out) >= limit:
            break
    return out


def _short(s: str | None, n: int = 80) -> str:
    if not s:
        return ""
    return s if len(s) <= n else s[:n] + "..."


def _build_sections(
    snapshot: dict[str, Any],
    cite: dict[str, ReportCitation],
    coverage_score: float,
    low_warning: bool,
    project_id: str = "",
) -> list[ReportSection]:
    """按 SOP §4.2 的 13 节, 每节用结构化数据 + evidence_refs 拼 Markdown."""

    feas = snapshot.get("feasibility") or {}
    proposal = snapshot.get("proposal_recommendation") or {}
    review = snapshot.get("light_review") or {}
    ev_sum = snapshot.get("evidence_summary") or {}

    feas_refs = feas.get("evidence_refs") or []
    blocking_refs = feas.get("blocking_refs") or []
    topic_refs = proposal.get("topic_evidence_refs") or []
    wp_list = proposal.get("work_packages") or []
    pivot_list = proposal.get("pivot_routes") or []
    review_checks = review.get("checks") or []
    reason_refs = proposal.get("reason_evidence_refs") or {}

    # 收集所有 risk / needs_check refs (不进 supports)
    risk_refs: list[dict] = []
    needs_check_refs: list[dict] = []
    for p in ev_sum.get("papers", []):
        if p.get("review_status") == "rejected":
            continue
        if (p.get("relevance_score") or 0) < 0.4:
            needs_check_refs.append({
                "evidence_id": p.get("paper_id", ""),
                "evidence_type": "paper",
                "title": p.get("title", ""),
            })

    sections: list[ReportSection] = []

    # 一、研究背景与意义 (从 feasibility.reason + topic_understanding 拼)
    feas_evidence_line = _format_refs(feas_refs, cite)
    sec_bg = ReportSection(
        key="background",
        title=SECTION_TITLES[0][1],
        content=(
            f"研究方向: {proposal.get('recommended_topic', '(待定)')}。\n\n"
            f"题目背景: {_short(feas.get('reason', ''), 200)}\n\n"
            f"主要研究意义与目标已通过低门槛审核, 后续章节将展开技术细节。\n\n"
            f"支撑证据: {feas_evidence_line or '[待补证据]'}"
        ),
        evidence_refs=_to_evidence_refs(feas_refs, cite, 5),
    )
    sections.append(sec_bg)

    # 二、国内外研究现状 (用 paper refs 拼)
    paper_refs_list: list[dict] = []
    for p in ev_sum.get("papers", [])[:5]:
        paper_refs_list.append({
            "evidence_id": p.get("paper_id", ""),
            "evidence_type": "paper",
            "title": p.get("title", ""),
            "role": "supports",
        })
    refs_str = _format_refs(paper_refs_list, cite)
    sec_related = ReportSection(
        key="related_work",
        title=SECTION_TITLES[1][1],
        content=(
            "本方向已有相关研究基础。以下文献为系统检索到的代表性工作, "
            "可作为本研究的研究现状参考。\n\n"
            f"主要相关文献: {refs_str or '[待补证据]'}\n\n"
            "具体文献标题见末尾\"证据引用清单\"。"
        ),
        evidence_refs=_to_evidence_refs(paper_refs_list, cite, 5),
    )
    sections.append(sec_related)

    # 三、研究问题与目标
    wp_titles = " / ".join([w.get("title", "") for w in wp_list[:3]]) if wp_list else "(待定)"
    sec_q = ReportSection(
        key="research_question",
        title=SECTION_TITLES[2][1],
        content=(
            f"研究目标: 在 {proposal.get('recommended_topic', '该方向')} 上完成可复现的研究与实验。\n\n"
            f"关键问题: 见工作包设计章节 ({wp_titles})。\n\n"
            "研究目标已在低门槛审核中通过, 具体细节见后续章节。"
        ),
        evidence_refs=_to_evidence_refs(topic_refs, cite, 3),
    )
    sections.append(sec_q)

    # 四、研究内容与技术路线
    tech_route = proposal.get("proposal_outline") or []
    route_text = "\n".join(f"- {line}" for line in tech_route[:6]) if tech_route else "(未生成技术路线)"
    sec_tech = ReportSection(
        key="technical_route",
        title=SECTION_TITLES[3][1],
        content=(
            "技术路线由系统根据证据池与可行性判断生成, 主要步骤如下:\n\n"
            f"{route_text}\n\n"
            "技术路线与退化路线保持一致, 用户可基于 pivot 选择重新生成。"
        ),
        evidence_refs=_to_evidence_refs(topic_refs, cite, 3),
    )
    sections.append(sec_tech)

    # 五、数据集、Baseline 与评价指标
    dataset_refs_list: list[dict] = []
    for d in ev_sum.get("datasets", [])[:3]:
        dataset_refs_list.append({
            "evidence_id": d.get("dataset_id", ""),
            "evidence_type": "dataset",
            "title": d.get("name", ""),
            "role": "supports",
        })
    repo_refs_list: list[dict] = []
    for b in ev_sum.get("baselines", [])[:3]:
        repo_refs_list.append({
            "evidence_id": b.get("baseline_id", ""),
            "evidence_type": "repo",
            "title": b.get("name", ""),
            "role": "supports",
        })
    metrics = ev_sum.get("metrics", []) or []
    sec_data = ReportSection(
        key="data_baseline_metric",
        title=SECTION_TITLES[4][1],
        content=(
            f"数据集: {_format_refs(dataset_refs_list, cite) or '[待补证据]'}\n\n"
            f"Baseline: {_format_refs(repo_refs_list, cite) or '[待补证据]'}\n\n"
            f"评价指标: {', '.join(metrics) if metrics else '[待补指标]'}\n\n"
            "具体名称见末尾\"证据引用清单\"。"
        ),
        evidence_refs=_to_evidence_refs(dataset_refs_list + repo_refs_list, cite, 5),
    )
    sections.append(sec_data)

    # 六、工作包设计
    if wp_list:
        wp_lines: list[str] = []
        wp_refs_total: list[dict] = []
        for w in wp_list:
            wp_id = w.get("wp_id", "")
            title = w.get("title", "")
            rq = _short(w.get("research_question", ""), 100)
            wp_refs = w.get("evidence_refs") or []
            wp_refs_total.extend(wp_refs)
            ref_str = _format_refs(wp_refs, cite)
            wp_lines.append(f"### {wp_id}: {title}\n\n- 研究问题: {rq}\n- 支撑证据: {ref_str or '[待补证据]'}")
        sec_wp = ReportSection(
            key="work_packages",
            title=SECTION_TITLES[5][1],
            content="\n\n".join(wp_lines),
            evidence_refs=_to_evidence_refs(wp_refs_total, cite, 8),
        )
    else:
        sec_wp = ReportSection(
            key="work_packages",
            title=SECTION_TITLES[5][1],
            content="[待补证据] 工作包设计需在证据补齐后生成。",
            unsupported_claims=["工作包未生成 (proposal_recommendation.work_packages 为空)"],
        )
    sections.append(sec_wp)

    # 七、预期创新点 (从 reason_evidence_refs 拼)
    reason_text_lines: list[str] = []
    innovation_refs: list[dict] = []
    for reason_key, refs in (reason_refs or {}).items():
        ref_str = _format_refs(refs, cite)
        reason_text_lines.append(f"- 理由 {reason_key}: 支撑证据 {ref_str or '[待补证据]'}")
        innovation_refs.extend(refs or [])
    if not reason_text_lines:
        reason_text_lines = ["[待补证据] 推荐理由需补全后由 LLM 生成。"]
    sec_inn = ReportSection(
        key="innovation",
        title=SECTION_TITLES[6][1],
        content=(
            "预期创新点 (基于推荐理由):\n\n" + "\n".join(reason_text_lines) + "\n\n"
            "具体创新点措辞需用户在交付前自行润色。"
        ),
        evidence_refs=_to_evidence_refs(innovation_refs, cite, 5),
    )
    sections.append(sec_inn)

    # 八、可行性分析
    feas_refs_str = _format_refs(feas_refs, cite)
    blocking_str = _format_refs(blocking_refs, cite)
    sec_feas = ReportSection(
        key="feasibility",
        title=SECTION_TITLES[7][1],
        content=(
            f"可行性判断: **{feas.get('verdict', '?')}**\n\n"
            f"判断依据: {_short(feas.get('reason', ''), 300)}\n\n"
            f"支撑证据: {feas_refs_str or '[待补证据]'}\n\n"
            f"阻断证据: {blocking_str or '(无)'}\n\n"
            f"缺失证据原因: {'; '.join(feas.get('missing_ref_reasons', [])) or '(无)'}\n\n"
            f"建议下一步: {feas.get('recommended_next_action', '')}"
        ),
        evidence_refs=_to_evidence_refs(feas_refs + blocking_refs, cite, 5),
    )
    sections.append(sec_feas)

    # 九、风险预案 (Session 10 §8: partial / failed 证据也列在这里)
    risk_lines: list[str] = []
    risk_refs_collected: list[dict] = []
    for missing in feas.get("missing_evidence", [])[:5]:
        risk_lines.append(f"- 风险: {missing}")
    if needs_check_refs:
        nc_str = _format_refs(needs_check_refs, cite)
        risk_lines.append(f"- 待复核证据: {nc_str}")
        risk_refs_collected.extend(needs_check_refs)
    # Session 10 §8: 关键 supports 中存在 partial → 在风险预案列出
    partial_supports: list[dict] = []
    failed_supports: list[dict] = []
    for c in cite.values():
        if not c.used_in_sections:
            continue
        if c.verification_status == "partial":
            partial_supports.append({"evidence_id": c.evidence_id, "title": c.title})
        elif c.verification_status == "failed":
            failed_supports.append({"evidence_id": c.evidence_id, "title": c.title})
    if partial_supports:
        ps_str = _format_refs(partial_supports, cite)
        risk_lines.append(f"- 部分验证证据 (引用过但未完全验证): {ps_str}")
        risk_refs_collected.extend(partial_supports)
    if failed_supports:
        fs_str = _format_refs(failed_supports, cite)
        risk_lines.append(f"- 验证失败的证据 (已降级为 warning, 不应正向引用): {fs_str}")
        risk_refs_collected.extend(failed_supports)
    if not risk_lines:
        risk_lines = ["- 暂无明确风险, 主要风险点已在缺失证据中体现。"]
    sec_risk = ReportSection(
        key="risks",
        title=SECTION_TITLES[8][1],
        content=(
            "主要风险与预案:\n\n" + "\n".join(risk_lines) + "\n\n"
            "每条预案在交付前需用户确认。"
        ),
        evidence_refs=_to_evidence_refs(risk_refs_collected, cite, 3),
    )
    sections.append(sec_risk)

    # 十、进度计划 (简单模板)
    sec_sched = ReportSection(
        key="schedule",
        title=SECTION_TITLES[9][1],
        content=(
            "进度计划 (按典型开题周期估算):\n\n"
            "- 第 1-2 周: 补充缺失证据, 确认数据集 license\n"
            "- 第 3-6 周: 实现 baseline, 跑通主实验\n"
            "- 第 7-10 周: 完成工作包 1-2 的核心实验\n"
            "- 第 11-14 周: 完成工作包 3 的对比实验与论文撰写\n"
            "- 第 15-16 周: 内部试讲与答辩准备"
        ),
        evidence_refs=[],
    )
    sections.append(sec_sched)

    # 十一、开题答辩可能追问
    qa_lines: list[str] = []
    for chk in review_checks:
        if chk.get("result") in ("需补充", "有条件通过", "不通过"):
            qa_lines.append(f"- 审核问: {chk.get('dimension', '?')} - {chk.get('comment', '')[:100]}")
    if not qa_lines:
        qa_lines = [
            "- 你的数据集 license 是否允许用于毕业设计? (来自数据集审核)",
            "- 复现 baseline 的硬件要求是什么? (来自 baseline 审核)",
            "- 题目风险词 (智能/高精度/实时) 如何界定? (来自题目边界审核)",
            "- 与已有方法相比, 创新点是否可量化? (来自创新性审核)",
        ]
    sec_qa = ReportSection(
        key="defense_qa",
        title=SECTION_TITLES[10][1],
        content=(
            "开题答辩中可能遇到的追问 (基于审核意见生成):\n\n" + "\n".join(qa_lines)
        ),
        evidence_refs=[],
    )
    sections.append(sec_qa)

    # 十二、证据引用清单 (在 render_markdown 里拼, 这里只占位)
    sections.append(ReportSection(key="citations", title=SECTION_TITLES[11][1], content=""))

    # 十三、待补证据与修改清单 (Session 10 §8: 验证未通过项也列出)
    todo_lines: list[str] = []
    for missing in feas.get("missing_ref_reasons", []) or []:
        todo_lines.append(f"- [待补证据] {missing}")
    for wp in wp_list:
        for q in wp.get("open_questions", []) or []:
            todo_lines.append(f"- [待补证据] {wp.get('wp_id', '')}: {q}")
    # Session 10 §8: failed / unverified key supports 出现在 待补清单
    for c in cite.values():
        if c.verification_status == "failed" and c.used_in_sections:
            todo_lines.append(
                f"- [待补证据/重验证] {c.ref_no} {c.title[:40]} 验证失败, 需重新检查 URL 或更换证据"
            )
        elif c.verification_status == "partial" and c.used_in_sections:
            warnings_short = "; ".join(c.verification_warnings[:2]) if c.verification_warnings else ""
            todo_lines.append(
                f"- [待补验证] {c.ref_no} {c.title[:40]} 部分验证 ({c.verification_confidence or 0:.2f}): {warnings_short}"
            )
    if not todo_lines:
        todo_lines = ["(无明显缺失, 可在交付前由用户再次复核)"]
    sec_todo = ReportSection(
        key="todo",
        title=SECTION_TITLES[12][1],
        content="待补证据与修改清单:\n\n" + "\n".join(todo_lines),
        unsupported_claims=[line for line in todo_lines if line.startswith("- [待补证据]")],
    )
    sections.append(sec_todo)

    # Session 11 §8: 十四、关键决策记录 (从 trace_store 拿)
    pid = project_id or (snapshot.get("project_id", "") if isinstance(snapshot, dict) else "")
    try:
        from . import trace_store as _ts
        summary = _ts.get_trace_summary(pid)
    except Exception:
        summary = None
    if summary and summary.key_decisions:
        decision_lines = [
            f"| {i+1} | {line} |" for i, line in enumerate(summary.key_decisions)
        ]
        sec_decision = ReportSection(
            key="decision_log",
            title=SECTION_TITLES[13][1],
            content=(
                "本节汇总本项目的关键操作与决策 (来自持久化 Trace):\n\n"
                f"- 用户操作: {summary.user_actions} 条\n"
                f"- 系统操作: {summary.system_actions} 条\n"
                f"- Agent 操作: {summary.agent_actions} 条\n"
                f"- 总事件数: {summary.total}\n"
                f"- 最近事件: {summary.last_event_ts or '(无)'}\n\n"
                "关键决策:\n\n"
                "| # | 决策 |\n"
                "|---|---|\n"
                + "\n".join(decision_lines)
            ),
        )
    else:
        sec_decision = ReportSection(
            key="decision_log",
            title=SECTION_TITLES[13][1],
            content="(暂无持久化决策记录)",
        )
    sections.append(sec_decision)

    return sections


def _render_markdown(
    sections: list[ReportSection],
    cite: dict[str, ReportCitation],
    final_topic: str,
    coverage_score: float,
    low_warning: bool,
    generated_at: str,
    ready: bool,
    template_key: str = "default",
) -> str:
    """按 SOP §4.2 渲染 13 章节 Markdown."""

    lines: list[str] = []
    lines.append(f"# 开题报告: {final_topic}")
    lines.append("")
    lines.append(tmpl_service.template_header_line(template_key))
    lines.append(f"> 生成时间: {generated_at}")
    lines.append(f"> 证据覆盖率: {coverage_score:.2f}")
    lines.append(f"> 状态: {'可提交草稿' if ready else '需补证据'}")
    # Session 13 §7.3: 列出本报告使用的内部 Skill
    try:
        from . import skill_registry as _sr
        enabled = _sr.list_skills(status="enabled")
        if enabled.skills:
            skill_names = ", ".join(s.name for s in enabled.skills)
            lines.append(f"> 本报告使用内部 Skill: {skill_names}")
    except Exception:
        pass
    lines.append("")

    if low_warning:
        lines.append("> ⚠️ **警告: 当前证据覆盖率不足 0.70。本文档可作为讨论草稿, 但不建议直接用于正式开题提交。**")
        lines.append("")

    lines.append("## 证据覆盖提示")
    lines.append("")
    lines.append(f"- 共挂载 **{len(cite)}** 条证据引用")
    lines.append(f"- 支持正向结论: {sum(1 for c in cite.values() if c.review_status in ('core', 'accepted', 'background'))} 条")
    lines.append(f"- 已被用户复核: {sum(1 for c in cite.values() if c.used_in_sections)} 条 (used_in_sections 非空)")

    # Session 10 §8: 证据验证率
    verified_n = sum(1 for c in cite.values() if c.verification_status == "verified")
    partial_n = sum(1 for c in cite.values() if c.verification_status == "partial")
    failed_n = sum(1 for c in cite.values() if c.verification_status == "failed")
    skipped_n = sum(1 for c in cite.values() if c.verification_status == "skipped")
    unverified_n = sum(1 for c in cite.values() if c.verification_status in (None, "unverified"))
    total_n = max(len(cite), 1)
    rate = (verified_n + partial_n) / total_n
    lines.append(f"- 证据验证率 (verified+partial / total): **{rate:.0%}** ({verified_n + partial_n}/{len(cite)})")
    if verified_n or partial_n or failed_n:
        lines.append(
            f"- 验证细分: verified={verified_n}, partial={partial_n}, "
            f"failed={failed_n}, skipped={skipped_n}, unverified={unverified_n}"
        )
    lines.append("")

    for sec in sections:
        if sec.key == "citations":
            # Session 10 §8: 证据清单增加 验证状态/置信度/警告 列
            # Session 13/14 §15: 增加 Skill 列
            # Session 15 §16: 增加 来源 / 页码 / 解析置信度 列
            lines.append(f"## {sec.title}")
            lines.append("")
            lines.append("| 编号 | 类型 | 标题 | 来源 | 页码 | 解析 | 审核状态 | 验证 | 置信度 | Skill | 警告 | 链接 |")
            lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
            for c in cite.values():
                title_short = _short(c.title, 50)
                url = c.url or "-"
                v_status = c.verification_status or "unverified"
                v_conf = f"{c.verification_confidence:.2f}" if c.verification_confidence is not None else "-"
                v_warn = _short("; ".join(c.verification_warnings[:2]), 40) if c.verification_warnings else "-"
                skill_str = ", ".join(c.skill_sources[:3]) if c.skill_sources else "-"
                source_str = c.source_mode or "-"
                page_str = ", ".join((c.page_refs or [])[:3]) if c.page_refs else "-"
                parse_str = f"{c.parse_confidence:.2f}" if c.parse_confidence is not None else "-"
                lines.append(
                    f"| {c.ref_no} | {c.evidence_type} | {title_short} | "
                    f"{source_str} | {page_str} | {parse_str} | {c.review_status} | "
                    f"{v_status} | {v_conf} | {skill_str} | {v_warn} | {url} |"
                )
            lines.append("")
            continue
        if sec.key == "todo":
            lines.append(f"## {sec.title}")
            lines.append("")
            lines.append(sec.content.replace("## 待补证据与修改清单:", "").strip())
            lines.append("")
            continue
        lines.append(f"## {sec.title}")
        lines.append("")
        lines.append(sec.content)
        lines.append("")

    return "\n".join(lines)


# ---------- 顶层 API (§6.1) ---------- #


def build_final_package(
    project_id: str,
    options: FinalPackageBuildOptions,
) -> FinalPackage:
    """从 snapshot + coverage_score 构建 FinalPackage."""

    snapshot = ev_store.get_snapshot(project_id)
    if not snapshot:
        raise ValueError(
            f"project_id {project_id} 还没有 snapshot, 请先 POST /analyze 或 /regenerate"
        )

    # 收集所有 evidence refs (从 feasibility / proposal / review)
    feas = snapshot.get("feasibility") or {}
    proposal = snapshot.get("proposal_recommendation") or {}
    review = snapshot.get("light_review") or {}
    ev_sum = snapshot.get("evidence_summary") or {}

    feas_refs = feas.get("evidence_refs") or []
    proposal_refs = proposal.get("topic_evidence_refs") or []
    review_refs: list[dict] = []
    for chk in review.get("checks", []) or []:
        review_refs.extend(chk.get("evidence_refs", []) or [])

    # coverage 评分
    try:
        from ..schemas import FeasibilitySummary, ProposalRecommendation, LightReview
        feas_obj = FeasibilitySummary.model_validate(feas)
        proposal_obj = ProposalRecommendation.model_validate(proposal)
        coverage = refs_service.coverage_score(feas_obj, proposal_obj)
    except Exception:
        coverage = 0.0

    low_warning = coverage < 0.70
    ready = coverage >= 0.70 and bool(feas_refs)

    # citation map (Session 10 §8: 传 extras 取 verification 状态)
    extras_pool = ev_store.get_pool_items(project_id)
    cite = _build_citation_map(
        papers=ev_sum.get("papers", []) or [],
        datasets=ev_sum.get("datasets", []) or [],
        repos=ev_sum.get("baselines", []) or [],
        feasibility_refs=feas_refs,
        proposal_refs=proposal_refs,
        review_refs=review_refs,
        options=options,
        extras=[it.model_dump() for it in extras_pool],
    )

    # template (Session 19)
    raw_template_key = options.template_key if options is not None else "default"
    template_key = tmpl_service.normalize_template_key(raw_template_key)
    template_hints = tmpl_service.check_template_readiness(
        template_key,
        paper_count=len(ev_sum.get("papers", []) or []),
        dataset_count=len(ev_sum.get("datasets", []) or []),
        baseline_count=len(ev_sum.get("baselines", []) or []),
    )

    # sections (模板重排)
    sections = _build_sections(snapshot, cite, coverage, low_warning, project_id=project_id)
    sections = tmpl_service.reorder_sections(template_key, sections)

    # revision checklist (合并模板提示)
    revision: list[str] = []
    for missing in feas.get("missing_ref_reasons", []) or []:
        revision.append(f"补 dataset/repo 证据: {missing}")
    for wp in (proposal.get("work_packages") or []):
        for q in wp.get("open_questions", []) or []:
            revision.append(f"工作包 {wp.get('wp_id', '?')}: {q}")
    if low_warning:
        revision.append("整体证据覆盖率不足, 建议至少补 1 个核心 dataset 或 repo 后重新生成报告。")
    revision.extend(template_hints)

    # unsupported claims
    unsupported: list[str] = []
    for sec in sections:
        unsupported.extend(sec.unsupported_claims)

    final_topic = proposal.get("recommended_topic") or feas.get("verdict") + "方向" or "(待定)"

    # markdown
    md = _render_markdown(
        sections=sections,
        cite=cite,
        final_topic=final_topic,
        coverage_score=coverage,
        low_warning=low_warning,
        generated_at=datetime.now(timezone.utc).isoformat(),
        ready=ready,
        template_key=template_key,
    )

    # 修正 last section (citations / todo) 在 sections 里的 content 不再被 markdown 拼
    pkg = FinalPackage(
        project_id=project_id,
        final_topic=final_topic,
        ready_for_proposal=ready,
        coverage_score=coverage,
        low_coverage_warning=low_warning,
        backend_verification="PASS" if ready else "WARN",
        ui_verification="NOT_RUN",
        playwright_verification="NOT_RUN",
        proposal_markdown=md,
        proposal_markdown_chars=len(md),
        sections=sections,
        citation_list=list(cite.values()),
        unsupported_claims=unsupported,
        revision_checklist=revision,
        section_count=len(sections),
        citation_count=len(cite),
        unsupported_claims_count=len(unsupported),
        revision_checklist_count=len(revision),
        generated_at=datetime.now(timezone.utc).isoformat(),
        cached=False,
        template_key=template_key,
        template_hints=template_hints,
    )

    # Session 11: 写 trace (final_package_build) 包含模板 key
    ev_store.append_trace(
        project_id=project_id,
        action="final_package_build",
        target_type="final_package",
        target_id=project_id,
        reason=f"FinalPackage build: chars={len(md)}, citations={len(cite)}, coverage={coverage:.2f}, template={template_key}",
        actor="system",
    )

    return pkg


def build_final_package_summary(project_id: str) -> FinalPackageSummary | None:
    """GET /final-package 摘要 (不含 markdown)."""

    pkg = ev_store.get_final_package(project_id)
    if not pkg:
        return None
    return FinalPackageSummary(
        project_id=pkg.project_id,
        final_topic=pkg.final_topic,
        ready_for_proposal=pkg.ready_for_proposal,
        coverage_score=pkg.coverage_score,
        low_coverage_warning=pkg.low_coverage_warning,
        backend_verification=pkg.backend_verification,
        ui_verification=pkg.ui_verification,
        playwright_verification=pkg.playwright_verification,
        proposal_markdown_chars=pkg.proposal_markdown_chars,
        section_count=pkg.section_count,
        citation_count=pkg.citation_count,
        unsupported_claims_count=pkg.unsupported_claims_count,
        revision_checklist_count=pkg.revision_checklist_count,
        generated_at=pkg.generated_at,
        cached=pkg.cached,
        template_key=pkg.template_key,
        template_hints=pkg.template_hints,
    )