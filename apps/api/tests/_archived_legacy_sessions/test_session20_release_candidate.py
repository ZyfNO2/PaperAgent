"""Session 20: 维护版收束 / v0.1 Release Candidate — 后端测试.

覆盖:
1. VERSION 存在且格式正确
2. CHANGELOG 存在且含 0.1.0-rc1
3. Known_Limitations 存在
4. Release_Checklist 存在
5. Roadmap 存在
6. Architecture_Overview 存在
7. Scope_And_Compliance 仍存在
8. S17 baseline 文件仍存在
9. README 含项目边界
10. 不存在明显 secret 占位泄露
11. docs/project/ 必需文件全部存在
12. .gitignore 排除 .runtime / .env
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]


# ---------- 1: VERSION ---------- #


def test_01_version_file_exists():
    p = ROOT / "VERSION"
    assert p.exists(), f"VERSION 不存在: {p}"
    content = p.read_text(encoding="utf-8").strip()
    assert content, "VERSION 不能为空"


def test_02_version_format_semver():
    p = ROOT / "VERSION"
    content = p.read_text(encoding="utf-8").strip()
    # 允许 0.1.0-rc1 / 0.1.0 / 0.2.0-beta 形式
    assert re.match(r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$", content), (
        f"VERSION 格式不符 (semver): {content!r}"
    )


# ---------- 2: CHANGELOG ---------- #


def test_03_changelog_exists():
    p = ROOT / "CHANGELOG.md"
    assert p.exists(), f"CHANGELOG.md 不存在: {p}"
    content = p.read_text(encoding="utf-8")
    assert "0.1.0-rc1" in content, "CHANGELOG.md 应包含 0.1.0-rc1"


def test_04_changelog_keep_a_changelog_sections():
    p = ROOT / "CHANGELOG.md"
    content = p.read_text(encoding="utf-8")
    assert "### Added" in content, "CHANGELOG.md 缺 Added 段"
    assert "### Changed" in content, "CHANGELOG.md 缺 Changed 段"


# ---------- 3-6: docs/project/ ---------- #


@pytest.mark.parametrize(
    "filename",
    [
        "Known_Limitations.md",
        "Release_Checklist.md",
        "Roadmap.md",
        "Architecture_Overview.md",
        "Scope_And_Compliance.md",
    ],
)
def test_05_project_doc_exists(filename):
    p = ROOT / "docs" / "project" / filename
    assert p.exists(), f"docs/project/{filename} 不存在"
    content = p.read_text(encoding="utf-8")
    assert len(content) > 100, f"docs/project/{filename} 太小"


def test_06_known_limitations_has_required_sections():
    p = ROOT / "docs" / "project" / "Known_Limitations.md"
    content = p.read_text(encoding="utf-8")
    # 必须有 12 条限制中的关键几条
    assert "不生成完整毕业论文" in content
    assert "DOCX" in content
    assert "OCR" in content
    assert "Demo baseline" in content or "demo" in content.lower()
    assert "LLM" in content and "heuristic" in content


def test_07_roadmap_has_versions():
    p = ROOT / "docs" / "project" / "Roadmap.md"
    content = p.read_text(encoding="utf-8")
    for v in ["v0.1", "v0.2", "v0.3", "v0.4", "v1.0"]:
        assert v in content, f"Roadmap 缺少 {v}"


def test_08_release_checklist_marked():
    p = ROOT / "docs" / "project" / "Release_Checklist.md"
    content = p.read_text(encoding="utf-8")
    # 至少 8 个 [x] 标记
    assert content.count("[x]") >= 8, "Release_Checklist.md 勾选项不足"


def test_09_architecture_overview_has_dataflow():
    p = ROOT / "docs" / "project" / "Architecture_Overview.md"
    content = p.read_text(encoding="utf-8")
    for kw in ["Evidence Ledger", "FinalPackage", "Verification", "Trace"]:
        assert kw in content, f"Architecture_Overview 缺少 {kw}"


# ---------- 7-8: S17 baseline 仍存在 ---------- #


def test_10_s17_baseline_test_exists():
    p = ROOT / "apps" / "api" / "tests" / "test_session17_demo_baseline.py"
    assert p.exists(), "S17 baseline 测试文件丢失"


def test_11_s17_demo_baseline_fixtures_exist():
    """S17 baseline 数据合同文件: docs/demo/baselines/."""

    baselines = ROOT / "docs" / "demo" / "baselines"
    assert baselines.exists(), f"S17 baselines 目录丢失: {baselines}"
    expected = [
        "yolo_steel_defect_input.json",
        "yolo_steel_defect_mock_sources.json",
        "yolo_steel_defect_expected.json",
        "risky_mllm_industrial_input.json",
        "risky_mllm_industrial_mock_sources.json",
        "risky_mllm_industrial_expected.json",
    ]
    for f in expected:
        assert (baselines / f).exists(), f"S17 baseline 缺文件: {f}"


# ---------- 9: README 边界声明 ---------- #


def test_12_readme_mentions_scope():
    p = ROOT / "README.md"
    assert p.exists(), "README.md 不存在"
    content = p.read_text(encoding="utf-8")
    # 项目边界关键词
    assert any(
        kw in content
        for kw in ["不自动代写", "不伪造", "boundary", "Scope", "边界"]
    ), "README 缺项目边界声明"


# ---------- 10: 隐私 / 凭据 ---------- #


def test_13_no_hardcoded_secret_in_python():
    """扫描 .py 文件, 不应出现硬编码的 API key."""

    secret_patterns = [
        r"MINIMAX_API_KEY\s*=\s*['\"][a-zA-Z0-9_-]{10,}",
        r"sk-[a-zA-Z0-9]{20,}",
        r"ghp_[a-zA-Z0-9]{20,}",
    ]
    api_dir = ROOT / "apps" / "api"
    bad = []
    for py in api_dir.rglob("*.py"):
        # 跳过测试 / 虚拟环境
        if "tests" in str(py) or ".venv" in str(py):
            continue
        text = py.read_text(encoding="utf-8", errors="ignore")
        for pat in secret_patterns:
            if re.search(pat, text):
                bad.append((str(py), pat))
    assert not bad, f"发现疑似硬编码 secret: {bad}"


def test_14_env_example_present():
    p = ROOT / ".env.example"
    assert p.exists(), ".env.example 不存在 (应入 git, .env 不入)"


def test_15_gitignore_excludes_runtime_and_env():
    p = ROOT / ".gitignore"
    assert p.exists(), ".gitignore 不存在"
    content = p.read_text(encoding="utf-8")
    assert ".runtime" in content, ".gitignore 应排除 .runtime"
    # .env 排除 (但允许 .env.example)
    assert re.search(r"^\.env$|^\.env\b.*$", content, re.MULTILINE) or ".env" in content


# ---------- 11: 报告目录约定 ---------- #


def test_16_reports_dir_exists():
    p = ROOT / "Plan" / "reports"
    assert p.exists(), "Plan/reports/ 目录丢失"
    # 应有 Session 1-18 的报告
    reports = list(p.glob("Session_*.md"))
    assert len(reports) >= 18, f"Plan/reports/Session_*.md 不足, 当前 {len(reports)} 份"


# ---------- 12: 一致性 ---------- #


def test_17_changelog_mentions_19_20():
    p = ROOT / "CHANGELOG.md"
    content = p.read_text(encoding="utf-8")
    # S19 模板
    assert "Session 19" in content or "报告模板" in content or "templates" in content.lower()
    # S20 RC
    assert "Session 20" in content or "Release Candidate" in content or "RC" in content


def test_18_test_count_growth_sanity():
    """S20 测试数量应 >= 10 条."""

    p = ROOT / "apps" / "api" / "tests" / "test_session20_release_candidate.py"
    content = p.read_text(encoding="utf-8")
    n_tests = content.count("def test_")
    assert n_tests >= 10, f"S20 测试数 {n_tests} < 10, 应增长"
