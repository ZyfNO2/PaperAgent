"""开题报告模板加载与渲染 (Session 19 SOP).

提供 3 种 Markdown 模板 (default / engineering / cv_ai):
- 模板只重排章节标题与顺序;
- 不绕过 citation;
- 不引用 rejected / pending+unverified / failed 证据;
- 保留 evidence_id / verification / skill / source.

模板文件位于 docs/templates/opening_report_*.md, 头部 YAML frontmatter 声明元数据.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..schemas import FinalPackageBuildOptions


# ---------- 模板注册 ---------- #

TEMPLATES_DIR = Path(__file__).resolve().parents[4] / "docs" / "templates"

# template_key → 文件名
_TEMPLATE_FILES = {
    "default": "opening_report_default.md",
    "engineering": "opening_report_engineering.md",
    "cv_ai": "opening_report_cv_ai.md",
    # Session 49: 已有小论文扩展 (Track B)
    "paper_extension": "opening_report_paper_extension.md",
}

DEFAULT_TEMPLATE_KEY = "default"

# cv_ai 模板的必备证据类别 (用于缺失提示)
_CV_AI_REQUIRED_KINDS = ("dataset", "baseline")
_ENGINEERING_REQUIRED_KINDS = ("dataset",)


def list_template_keys() -> list[str]:
    """返回所有支持的 template_key (稳定顺序)."""

    return list(_TEMPLATE_FILES.keys())


def normalize_template_key(template_key: str | None) -> str:
    """未知 / 缺省 → default (不报错, 向后兼容)."""

    if not template_key or template_key not in _TEMPLATE_FILES:
        return DEFAULT_TEMPLATE_KEY
    return template_key


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """解析 Markdown 文件头部的 YAML frontmatter (轻量解析, 不引入 PyYAML 依赖).

    支持: 标量 (key: value)、列表 (- item). 不支持嵌套 dict.
    """

    meta: dict[str, Any] = {}
    body = text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.DOTALL)
    if not m:
        return meta, body
    raw = m.group(1)
    body = m.group(2)
    cur_key: str | None = None
    cur_list: list[str] | None = None
    for line in raw.splitlines():
        if not line.strip():
            continue
        # 列表项
        if line.lstrip().startswith("- "):
            val = line.lstrip()[2:].strip()
            if cur_key is not None and cur_list is not None:
                cur_list.append(val)
            continue
        # key: value
        if ":" in line:
            if cur_key is not None and cur_list is not None:
                meta[cur_key] = cur_list
                cur_list = None
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            if val:
                meta[key] = val
            else:
                # 可能是列表起始
                cur_key = key
                cur_list = []
    if cur_key is not None and cur_list is not None:
        meta[cur_key] = cur_list
    return meta, body


def load_template(template_key: str | None) -> dict[str, Any]:
    """加载一个模板: 返回 {key, name, version, required_sections, evidence_required, placeholders, body}.

    文件缺失时回退到 default 的最小元数据 (不抛异常, 保证 FinalPackage 不挂).
    """

    key = normalize_template_key(template_key)
    path = TEMPLATES_DIR / _TEMPLATE_FILES[key]
    if not path.exists():
        return {
            "template_key": key,
            "name": key,
            "version": "0.1.0",
            "required_sections": [],
            "evidence_required": True,
            "placeholders": [],
            "applies_to": "",
            "body": "",
        }
    text = path.read_text(encoding="utf-8")
    meta, body = _split_frontmatter(text)
    return {
        "template_key": key,
        "name": meta.get("name", key),
        "version": meta.get("version", "0.1.0"),
        "applies_to": meta.get("applies_to", ""),
        "required_sections": meta.get("required_sections", []) or [],
        "evidence_required": bool(meta.get("evidence_required", True)),
        "placeholders": meta.get("placeholders", []) or [],
        "body": body.strip(),
    }


def list_templates() -> list[dict[str, Any]]:
    """列出全部模板的元数据 (不含 body)."""

    out: list[dict[str, Any]] = []
    for key in _TEMPLATE_FILES:
        t = load_template(key)
        out.append({
            "template_key": t["template_key"],
            "name": t["name"],
            "version": t["version"],
            "applies_to": t["applies_to"],
            "required_sections": t["required_sections"],
            "evidence_required": t["evidence_required"],
            "placeholders": t["placeholders"],
        })
    return out


# ---------- 缺失证据提示 ---------- #


def check_template_readiness(
    template_key: str | None,
    *,
    paper_count: int,
    dataset_count: int,
    baseline_count: int,
) -> list[str]:
    """根据模板类型返回缺失证据提示 (不阻断 build, 只给提示).

    - cv_ai: 缺 dataset 或 baseline → 提示
    - engineering: 缺 dataset → 提示
    - default: 不强提示
    """

    key = normalize_template_key(template_key)
    hints: list[str] = []
    if key == "cv_ai":
        if dataset_count == 0:
            hints.append("CV/AI 模板建议至少补 1 个公开数据集后再生成报告。")
        if baseline_count == 0:
            hints.append("CV/AI 模板建议至少补 1 个可复现 baseline 后再生成报告。")
    elif key == "engineering":
        if dataset_count == 0:
            hints.append("工程实现型模板建议补 1 个数据来源后再生成报告。")
    return hints


# ---------- 章节顺序 (模板影响 build 时章节排序) ---------- #

# 各模板对 FinalPackage 14 章节的优先顺序 (key 顺序).
# 不在列表里的章节 (如 citations / todo / decision_log) 固定在末尾.
_SECTION_ORDER: dict[str, list[str]] = {
    "default": [
        "background", "related_work", "research_question", "technical_route",
        "data_baseline_metric", "work_packages", "innovation", "feasibility",
        "risks", "schedule", "defense_qa",
    ],
    "engineering": [
        "background", "research_question", "data_baseline_metric", "technical_route",
        "work_packages", "feasibility", "risks", "schedule", "innovation", "defense_qa",
        "related_work",
    ],
    "cv_ai": [
        "background", "related_work", "data_baseline_metric", "feasibility",
        "technical_route", "work_packages", "innovation", "risks", "schedule",
        "research_question", "defense_qa",
    ],
}


def reorder_sections(template_key: str | None, sections: list[Any]) -> list[Any]:
    """按模板重排 sections 顺序 (不改变章节内容).

    citations / todo / decision_log 固定在末尾, 保持原相对顺序.
    """

    key = normalize_template_key(template_key)
    order = _SECTION_ORDER.get(key, _SECTION_ORDER[DEFAULT_TEMPLATE_KEY])
    rank = {sec_key: i for i, sec_key in enumerate(order)}

    def _sort_key(sec: Any) -> tuple[int, int]:
        sk = getattr(sec, "key", "") if not isinstance(sec, dict) else sec.get("key", "")
        if sk in rank:
            return (0, rank[sk])
        # 末尾固定组: citations / todo / decision_log
        tail_order = {"citations": 0, "todo": 1, "decision_log": 2}
        if sk in tail_order:
            return (1, tail_order[sk])
        return (1, 99)

    # 稳定排序: 保持同 rank 内原顺序
    indexed = list(enumerate(sections))
    indexed.sort(key=lambda pair: (_sort_key(pair[1]), pair[0]))
    return [s for _, s in indexed]


def template_header_line(template_key: str | None) -> str:
    """生成 Markdown 头部的模板标注行 (写入 proposal_markdown)."""

    t = load_template(template_key)
    return f"> 报告模板: {t['name']} (`{t['template_key']}` v{t['version']})"


# ---------- Session 49: paper_extension 模板渲染 ---------- #


def render_paper_extension_sections(
    *,
    card: Any,
    mappings: list[Any],
    plan: Any,
    risks: list[Any],
    paper_excerpt: str = "",
) -> dict[str, str]:
    """渲染 paper_extension 模板的 6 个 placeholder 字段.

    输入是 small_paper 服务的 Pydantic 模型 (避免循环 import, 用 Any).
    返回: {placeholder_name: rendered_markdown, ...}
    """

    # 1) paper_info: 标题 + venue + publication_status
    pub_status = getattr(card, "publication_status", "unknown") or "unknown"
    venue = getattr(card, "venue", None) or "-"
    paper_info = (
        f"**标题**: {getattr(card, 'title', '(无标题)')}\n\n"
        f"**发表状态**: {pub_status}\n\n"
        f"**发表场所**: {venue}\n\n"
        f"**paper_id**: `{getattr(card, 'paper_id', '')}`"
    )

    # 2) contributions: 贡献点 + 方法 + 数据集 + 指标
    contrib_lines: list[str] = []
    pts = getattr(card, "contribution_points", []) or []
    for i, c in enumerate(pts, 1):
        contrib_lines.append(f"{i}. {c}")
    if not contrib_lines:
        contrib_lines = ["(未抽取出贡献点, 抽取置信度 %.2f)" % getattr(card, "extraction_confidence", 0.0)]
    methods = getattr(card, "method_modules", []) or []
    datasets = getattr(card, "datasets", []) or []
    metrics = getattr(card, "metrics", []) or []
    contrib_md = "\n".join(contrib_lines) + "\n\n"
    contrib_md += f"**方法模块**: {', '.join(methods) if methods else '-'}\n\n"
    contrib_md += f"**数据集**: {', '.join(datasets) if datasets else '-'}\n\n"
    contrib_md += f"**评价指标**: {', '.join(metrics) if metrics else '-'}"

    # 3) chapter_mappings: 表格
    map_lines = [
        "| 小论文章节 | 大论文章节 | 复用方式 | 备注 |",
        "|---|---|---|---|",
    ]
    for m in (mappings or []):
        map_lines.append(
            f"| {getattr(m, 'small_paper_section', '-')} "
            f"| {getattr(m, 'thesis_chapter', '-')} "
            f"| {getattr(m, 'reuse_type', '-')} "
            f"| {getattr(m, 'note', '') or '-'} |"
        )
    if len(map_lines) == 2:
        map_lines.append("| (无映射) | - | - | - |")
    chapter_md = "\n".join(map_lines)

    # 4) gap_analysis
    gap_md = "\n".join(f"- {g}" for g in (getattr(plan, "gap_analysis", []) or [])) or "- (无)"

    # 5) extension_experiments
    exp_lines: list[str] = []
    for e in (getattr(plan, "extension_experiments", []) or []):
        exp_lines.append(
            f"### {getattr(e, 'experiment_id', '?')}: {getattr(e, 'title', '')}\n\n"
            f"- 描述: {getattr(e, 'description', '')}\n"
            f"- 数据集: {', '.join(getattr(e, 'datasets', []) or []) or '-'}\n"
            f"- Baselines: {', '.join(getattr(e, 'baselines', []) or []) or '-'}\n"
            f"- 工作量: {getattr(e, 'estimated_effort', 'medium')}\n"
            f"- 优先级: {getattr(e, 'priority', 3)}\n"
            f"- 补章节: {getattr(e, 'fills_chapter', '?')}"
        )
    exp_md = "\n\n".join(exp_lines) or "(无扩展实验建议)"

    # 6) repeat_risks
    risk_lines: list[str] = []
    for r in (risks or []):
        risk_lines.append(
            f"- **[{getattr(r, 'severity', '?')}]** {getattr(r, 'category', '?')}: "
            f"{getattr(r, 'note', '')}"
            + (f" (related: {getattr(r, 'related_section', '')})" if getattr(r, 'related_section', None) else "")
        )
    risk_md = "\n".join(risk_lines) or "- (无明显重复风险)"

    # 7) work_packages
    wp_lines: list[str] = []
    swp = getattr(plan, "second_work_package", None)
    twp = getattr(plan, "third_work_package", None)
    if swp:
        wp_lines.append(
            f"### WP2: {getattr(swp, 'title', '')}\n\n"
            f"- 目标: {getattr(swp, 'goal', '')}\n"
            f"- 交付物: {getattr(swp, 'deliverable', '')}\n"
            f"- 依赖: {', '.join(getattr(swp, 'dependencies', []) or []) or '-'}\n"
            f"- 工作量: {getattr(swp, 'estimated_effort', 'medium')}"
        )
    if twp:
        wp_lines.append(
            f"### WP3: {getattr(twp, 'title', '')}\n\n"
            f"- 目标: {getattr(twp, 'goal', '')}\n"
            f"- 交付物: {getattr(twp, 'deliverable', '')}\n"
            f"- 依赖: {', '.join(getattr(twp, 'dependencies', []) or []) or '-'}\n"
            f"- 工作量: {getattr(twp, 'estimated_effort', 'medium')}"
        )
    wp_md = "\n\n".join(wp_lines) or "(无第二/第三工作包)"

    # 8) chunk_refs
    refs = getattr(card, "evidence_refs", []) or []
    chunk_md = (
        f"已挂载 chunk evidence: {len(refs)} 条\n\n"
        + (f"- IDs: {', '.join(refs)}" if refs else "- (本卡未挂载 chunk evidence)")
        + (f"\n\n**论文摘要片段**:\n\n> {paper_excerpt[:300]}..." if paper_excerpt else "")
    )

    # 9) thesis_outline
    outline_md = "\n".join(f"- {line}" for line in (getattr(plan, "thesis_outline", []) or [])) or "- (无)"

    return {
        "paper_info": paper_info,
        "contributions": contrib_md,
        "chapter_mappings": chapter_md,
        "gap_analysis": gap_md,
        "extension_experiments": exp_md,
        "repeat_risks": risk_md,
        "work_packages": wp_md,
        "chunk_refs": chunk_md,
        "thesis_outline": outline_md,
    }
