#!/usr/bin/env python3
"""SessionStart hook: 提示参考项目 + 科研 Skill 重合度, 避免重复造轮子.

行为:
1. 读 .claude/hooks/_session_intel_cache.json (上次算的)
2. 失效 / 不存在 → 重新扫描:
   a. Plan/Faraway/PaperAgent_*.md  (改造计划 + Skill 清单)
   b. apps/api, apps/web 现有代码
   c. 列出重合部分 (model / endpoint / page), 提示 "可直接复用"
   d. 列出缺口 (改造计划要做的, 当前还没做的)
3. 把结果写到 cache, 打印到 stderr
4. 不阻断 (exit 0)

不联网 — 只扫本地 Plan + 源码. (升级: 可加 gh api 拉参考仓库的 SKILL.md 摘要)
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PLAN_DIR = REPO / "Plan" / "Faraway"
CACHE_PATH = Path(__file__).parent / "_session_intel_cache.json"

# 改造计划里点名的关键能力
PLAN_CAPABILITIES = {
    "evidence_ledger": "手动添加论文 / 数据集 / 工程 (SOP §5)",
    "human_gate": "关键词/检索/证据/可行性/工作包 的人工 Gate (SOP §6)",
    "retrieval_scoring": "PaperRelevance / DatasetScore / RepoScore (SOP §7)",
    "pivot_route": "3 条退化路线 (保守/平衡/激进) (SOP §10)",
    "work_package_matrix": "WP 关联 1 baseline + 1 dataset + 2-3 paper + 1 指标 (SOP §11)",
    "feasibility_5tier": "GO/NARROW/PIVOT/PARK/STOP 5 档 (SOP §9.4)",
    "markdown_export": "导出开题报告 Markdown (SOP §6.2)",
}

# Session 范围: 1-4 验收完, 5 在做, 6 待做
SESSION_PROGRESS = {
    "session_1": ("Evidence 数据模型 + 手动入池", "done", "Session_01_Evidence_验收报告"),
    "session_2": ("证据工作台 UI + 审核状态机", "done", "Session_02_Evidence_Workbench_验收报告"),
    "session_3": ("Human Gate 1-2 (关键词 + 检索计划)", "done", "Session_03_Human_Gates_验收报告"),
    "session_4": ("5 档可行性 + 3 条退化路线", "done", "Session_04_Pivot_Routes_验收报告"),
    "session_5": ("去重 + 评分 (PaperRel/DatasetScore/RepoScore) + 接入 feasibility", "done", "Plan/reports/Session_05_Evidence_Scoring_验收报告.md"),
    "session_6": ("LLM 路径全激活 (搜索助手 + rerank + recommend + review) + 症状 3 根治", "done", "Plan/reports/Session_06_LLM_Path_Activation_验收报告.md"),
}

# PINN 诊断待办 (来自 PINN_数字孪生_诊断报告.md)
PINN_PENDING = [
    "扩展 _METHOD_HINTS 覆盖 PINN/数字孪生/GNN/Diffusion/GAN/Mamba/RL/DETR",
    "添加 _OBJECT_HINTS (机构/传动链/工业装备/传感器/振动)",
    "arXiv 检索结果按 PaperRelevance 过滤 irrelevant",
    "Pivot 路线模板化 (根除硬编码钢材)",
]

# 哪些 Skill 是参考价值最高的 (P0 级别, 来自 Skill 下载链接汇总)
REFERENCE_SKILLS = {
    "deep-research": "Weizhena/Deep-Research-skills: 分阶段研究 + HITL outline 模板",
    "academic-pipeline": "imbad0202/academic-research-skills: 10 阶段 orchestrator + Integrity Gate",
    "literature-review": "PRISMA / PICO 系统综述 skill",
    "claude-scholar": "question → evidence → experiment → analysis → claim → writing",
}


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return ""


def _hash_paths(paths: list[Path]) -> str:
    """把要扫描的文件的 mtime + size 拼成指纹, 用于 cache 失效判断."""

    h = hashlib.sha256()
    for p in paths:
        try:
            st = p.stat()
            h.update(p.name.encode())
            h.update(str(st.st_mtime).encode())
            h.update(str(st.st_size).encode())
        except Exception:
            h.update(b"<missing>")
    return h.hexdigest()[:16]


def _scan() -> dict:
    """扫本地代码 + 改造计划, 算出重合度."""

    plan_files = [
        PLAN_DIR / "PaperAgent_交互式证据工作台改造计划书与SOP.md",
        PLAN_DIR / "PaperAgent_科研Skill下载链接汇总.md",
    ]
    code_files = []
    for sub in [REPO / "apps" / "api" / "app", REPO / "apps" / "web"]:
        if sub.exists():
            code_files.extend(sub.rglob("*.py"))
            code_files.extend(sub.rglob("*.js"))
            code_files.extend(sub.rglob("*.html"))
    plan_text = "".join(_read(p) for p in plan_files)
    code_text = "".join(_read(p) for p in code_files)

    # 改造计划要求 vs 当前代码
    coverage: dict[str, str] = {}
    for key, desc in PLAN_CAPABILITIES.items():
        # 简单关键字命中: 改造计划提了 + 代码也提了
        plan_hit = bool(_keyword_in(key, plan_text))
        code_hit = bool(_keyword_in(key, code_text))
        if plan_hit and code_hit:
            coverage[key] = "ok"
        elif plan_hit and not code_hit:
            coverage[key] = "missing"
        else:
            coverage[key] = "n/a"

    # 当前代码里出现但改造计划没强调的 (OneTopic MVP 已有的)
    existing = [k for k in ["raw_topic", "keyword_breakdown", "feasibility",
                            "evidence_summary", "proposal_recommendation",
                            "light_review"] if _keyword_in(k, code_text)]

    return {
        "plan_files": [p.name for p in plan_files if p.exists()],
        "plan_capabilities": coverage,
        "existing_capabilities": existing,
        "reference_skills": REFERENCE_SKILLS,
        "missing_count": sum(1 for v in coverage.values() if v == "missing"),
    }


def _keyword_in(keyword: str, text: str) -> bool:
    """宽松匹配: 拆成小词, 全部出现 (允许大小写不敏感)."""

    parts = re.split(r"[_]+", keyword.lower())
    text_l = text.lower()
    return all(p in text_l for p in parts if len(p) > 2)


def _load_cache() -> dict | None:
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return None


def _save_cache(data: dict) -> None:
    try:
        CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _emit_stderr(msg: str) -> None:
    print(msg, file=sys.stderr)


def main() -> int:
    paths = [
        PLAN_DIR / "PaperAgent_交互式证据工作台改造计划书与SOP.md",
        PLAN_DIR / "PaperAgent_科研Skill下载链接汇总.md",
        REPO / "apps" / "api" / "app" / "schemas.py",
        REPO / "apps" / "api" / "app" / "services" / "one_topic.py",
        REPO / "apps" / "web" / "app.js",
        REPO / "apps" / "web" / "index.html",
    ]
    paths = [p for p in paths if p.exists()]
    fp = _hash_paths(paths)

    cache = _load_cache()
    if cache and cache.get("fingerprint") == fp and cache.get("report"):
        report = cache["report"]
    else:
        report = _scan()
        _save_cache({"fingerprint": fp, "report": report})

    missing = [k for k, v in report["plan_capabilities"].items() if v == "missing"]
    ok = [k for k, v in report["plan_capabilities"].items() if v == "ok"]

    _emit_stderr("")
    _emit_stderr("=" * 70)
    _emit_stderr("  SessionStart intel: PaperAgent 参考项目重合度")
    _emit_stderr("=" * 70)
    _emit_stderr(f"  Plan 文档: {', '.join(report['plan_files'])}")
    _emit_stderr("")
    _emit_stderr("  Session 进度 (按 SOP §4-§12):")
    for sid, (title, status, report) in SESSION_PROGRESS.items():
        marker = "DONE" if status == "done" else ("DOING" if status == "in_progress" else "TODO ")
        line = f"    [{marker}] {sid}: {title}"
        if report:
            line += f"  ({report})"
        _emit_stderr(line)
    _emit_stderr("")
    _emit_stderr("  当前已有 (OneTopic MVP):")
    for cap in report["existing_capabilities"]:
        _emit_stderr(f"    - {cap}")
    _emit_stderr("")
    _emit_stderr(f"  改造计划要求 / 当前实现: {len(ok)} ok / {len(missing)} missing")
    if missing:
        _emit_stderr("  待补能力 (改造计划要求, 还没做):")
        for m in missing:
            desc = PLAN_CAPABILITIES.get(m, "")
            _emit_stderr(f"    - {m}: {desc}")
    _emit_stderr("")
    _emit_stderr("  PINN 诊断待办 (从 PINN_数字孪生_诊断报告.md):")
    for item in PINN_PENDING:
        _emit_stderr(f"    - {item}")
    _emit_stderr("")
    _emit_stderr("  参考 Skill (P0 级别, 改写前先看):")
    for name, desc in report["reference_skills"].items():
        _emit_stderr(f"    - {name}: {desc}")
    _emit_stderr("")
    _emit_stderr("  复用原则:")
    _emit_stderr("    - SKILL.md 模板: 参考 Weizhena/Deep-Research-skills (YAML frontmatter + HITL AskUserQuestion)")
    _emit_stderr("    - 阶段编排 + Integrity Gate: 参考 imbad0202/academic-pipeline (10 阶段 orchestrator)")
    _emit_stderr("    - 不要原封照搬, 改写成 PaperAgent 自己的 Skill + 绑定 Evidence ID")
    _emit_stderr("=" * 70)
    _emit_stderr("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
