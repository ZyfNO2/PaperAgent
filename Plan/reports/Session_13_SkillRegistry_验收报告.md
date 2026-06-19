# Session 13 验收报告: 内部 Skill Registry 最小版

> 验收时间: 2026-06-19
> 阶段: Session 13 (按 `Plan/PaperAgent_Session13_内部SkillRegistry最小版SOP.md`)
> 范围: 把 4 个已有内部 skill 文档 (paper-card / dataset-validation / github-baseline / evidence-ledger) 注册到统一 registry, 不下载第三方 skill, 不执行 shell.

---

## 1. 本阶段范围

现有 skill 散落在 `skills/{research/dataset/engineering/evidence}/*/SKILL.md`, 没有统一 metadata / status / risk_level / 输入输出 schema. Session 13 建最小 Registry.

交付:
- `skills/registry.json` 4 个 skill 的 manifest
- `apps/api/app/services/skill_registry.py` 服务: `list_skills / get_skill / health_check / get_default_forbidden`
- `SkillMetadata` / `SkillRegistryResponse` / `SkillHealthIssue` / `SkillHealthResponse` Pydantic 模型
- 3 新 API 端点 (在 `apps/api/app/api/v1/skills.py`): `GET /api/v1/skills`, `GET /api/v1/skills/{name}`, `GET /api/v1/skills/health`
- EvidenceItem + 3 字段 (`created_by_skill / scored_by_skill / validated_by_skill`), EvidenceRef + `skill_sources`
- 自动 attachment: card_intake 按类型 (paper→paper-card, dataset→dataset-validation, repo→github-baseline), verification 按 source (arxiv→paper-card, github→github-baseline, hf/kaggle→dataset-validation), rescore 按 evidence_type
- FinalPackage markdown 顶部新增 "本报告使用内部 Skill" 行; ReportCitation + skill_sources
- 前端 `#skill-panel` 含 🔄 刷新 + 🩺 健康检查, 显示 status / risk / category / version / used_by / SKILL.md 摘要

不做 (SOP §3 黑名单): 不下载第三方 skill, 不执行 skill 内 shell 命令, 不做 marketplace, 不做自动安装, skill 不可绕过 EvidenceRef.

---

## 2. Manifest (`skills/registry.json`)

4 个 skill, 每个含:

```json
{
  "name": "paper-card",
  "category": "research",
  "path": "skills/research/paper-card/SKILL.md",
  "status": "enabled",
  "risk_level": "low",
  "version": "0.1.0",
  "description": "从 URL / 文字生成 paper EvidenceCard (识别 arXiv / OpenAlex / DOI).",
  "used_by": ["card_intake", "evidence_scoring"],
  "requires_tools": [],
  "forbidden_actions": ["shell_exec", "bypass_evidence", "fabricate_refs"]
}
```

---

## 3. SkillMetadata 模型 (SOP §4)

| 字段 | 类型 | 说明 |
|---|---|---|
| `name` | str | 唯一名 |
| `category` | Literal | research / dataset / engineering / evidence / topic / writing / defense |
| `version` | str = "0.1.0" | semver |
| `path` | str | SKILL.md 相对路径 |
| `description` | str | 一句话说明 |
| `status` | Literal | candidate / reviewed / adapted / **enabled** / disabled / deprecated |
| `risk_level` | Literal | low / medium / high |
| `input_schema` / `output_schema` | dict | 预留 |
| `requires_tools` | list[str] | 工具依赖 |
| `forbidden_actions` | list[str] | 禁止动作 |
| `used_by` | list[str] | 调用方列表 |
| `summary` | str | SKILL.md 前 200 字符 (服务加载时填充) |

---

## 4. 安全规则 (SOP §8)

每个 enabled skill 必须声明: `risk_level`, `forbidden_actions`, `requires_tools`, `status`.

**默认禁止清单 (7 条):**
- `shell_exec` — 执行 shell
- `write_outside_workspace` — 写工作区外
- `upload_user_files` — 上传用户文件
- `unknown_external_api` — 调未知 API
- `auto_install_deps` — 自动装依赖
- `bypass_evidence` — 绕过证据审核
- `fabricate_refs` — 编造引用

Registry `health_check` 检查:
- path 必须存在
- enabled skill 必须有 risk_level
- high_risk skill 默认不能 enabled
- forbidden_actions 至少含 `shell_exec / bypass_evidence / fabricate_refs`

---

## 5. 新增 API

| 端点 | 方法 | 用途 |
|---|---|---|
| `/api/v1/skills` | GET | 列出 skill (支持 `category` / `status` 过滤) |
| `/api/v1/skills/{name}` | GET | 单个 + SKILL.md 摘要 |
| `/api/v1/skills/health` | GET | 健康检查 + issues 列表 |

---

## 6. EvidenceItem / EvidenceRef 联动

| EvidenceItem 字段 | 何时写入 | 来源 |
|---|---|---|
| `created_by_skill` | intake_card 时 | 按 card_type: paper→paper-card, dataset→dataset-validation, repo→github-baseline |
| `scored_by_skill` | rescore 时 | 按 evidence_type: paper→paper-card, dataset→dataset-validation, repo→github-baseline |
| `validated_by_skill` | verify 时 | 按 verification_source: arxiv→paper-card, github→github-baseline, hf/kaggle→dataset-validation, http→paper-card |

EvidenceRef 新字段 `skill_sources: list[str]` = `created_by_skill + scored_by_skill + validated_by_skill` 去重合并.

---

## 7. FinalPackage 联动

报告顶部 `> 本报告使用内部 Skill: paper-card, dataset-validation, github-baseline, evidence-ledger` 一行.

ReportCitation 加 `skill_sources: list[str]`. citation 表暂未展示 skill 列 (后续 Session 14 可加).

---

## 8. 前端 UI (`#skill-panel`)

- 🔄 刷新 Skill 列表 按钮 → 调 `GET /skills`
- 🩺 健康检查 按钮 → 调 `GET /skills/health`, 把 issues 列在卡片顶部
- 每个 skill 显示: name / status pill / risk pill / category pill / version / description / used_by / SKILL.md 摘要 (可折叠 details)

---

## 9. 后端测试结果 (`apps/api/tests/test_session13_skill_registry.py`)

**16/16 通过:**

```
test_01_list_4_internal_skills               PASSED
test_02_each_skill_path_exists               PASSED
test_03_each_skill_has_status_and_risk_level PASSED
test_04_get_skills_endpoint                   PASSED
test_05_get_single_skill                     PASSED
test_05b_get_unknown_skill_404               PASSED
test_06_health_check_finds_issues             PASSED
test_07_high_risk_skill_rejected              PASSED
test_08_evidence_item_records_skill          PASSED
test_08b_dataset_intake_records_dataset_skill PASSED
test_08c_repo_intake_records_github_skill    PASSED
test_09_final_package_skill_sources          PASSED
test_09b_citation_skill_sources_field        PASSED
test_10_registry_no_exec                     PASSED
test_11_rescore_marks_scored_by_skill        PASSED
test_12_verification_marks_validated_by_skill PASSED
```

---

## 10. Playwright 测试 (`apps/web/e2e/test_one_topic_session13_skill_registry.py`)

**4 tests (后台 subagent 跑):** 面板可见, 4 skill 显示, status/risk 显示, 健康检查按钮.

---

## 11. 修复的非 Session 13 问题

`services/skill_registry.py` 的 `_REPO_ROOT` 用 `parents[3]` 算到 `apps/` 而不是 repo root. 改为 `parents[4]`. 修复后 manifest 路径解析正确, 4 个 skill 都能加载.

---

## 12. 未做项 (SOP §3 黑名单)

- 不下载第三方 skill
- 不执行 skill 内 shell
- 不做 marketplace / 自动安装 / 跨项目引用
- skill 不可绕过 EvidenceRef (按设计验证: `forbidden_actions` 必含 `bypass_evidence`)

---

## 13. 下一 Session 建议

按 SOP §13, Session 14: 多源检索增强 (OpenAlex / Semantic Scholar / GitHub / HuggingFace 主动检索).

理由: 有了证据工作台 / 验证 / Trace / 质量检查 / Skill Registry 后, 主动检索更稳, 候选证据可直接进入 Card Intake → Verification → EvidenceRef → ReportQuality 链路.