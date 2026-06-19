# TopicPilot-CN / PaperAgent

> 中国研究生开题/选题场景下的交互式证据工作台。
> 不是全自动论文生成器，而是帮你把题目、论文、数据集、GitHub 工程、
> PDF / 截图 / 网页材料整理成可审核的证据链，并产出可追溯的开题报告 Markdown。

---

## 项目定位

PaperAgent（TopicPilot-CN）是面向**保毕业 / 稳中求新 / 冲高水平**三档定位的中国研究生开题选题助手：

- 用户只输入**一个题目** + 目标档位，即可获得关键词拆解、三线检索、可行性五档判断。
- 在交互式证据工作台里手动 / 自动补充 **论文 / 数据集 / GitHub baseline / 笔记**四类证据。
- 所有 AI 抓取 / 解析结果默认 **pending**，需要用户在双栏工作台里**审核 / 移动**到 `accepted / core / background / rejected`。
- **rejected 不引用；pending 不直接 supports；failed verification 不 supports**。
- 系统产出开题报告 Markdown + ReportQuality 8 维审核 + Trace 操作回放，但**不替代导师与学术判断**。

主闭环：

```text
输入题目 → 关键词拆解 → 多源检索 → 工作台审核
        → URLVerified → 资料卡片化 → Trace 持久化
        → FinalPackage Markdown → ReportQuality 8 维
```

---

## 核心能力（Session 09 → Session 15 主闭环）

| Session | 能力 | 关键产物 |
|---|---|---|
| 09 | 双栏证据工作台 + Agent Card Intake | `workspace_lane` 字段，证据工作台 UI |
| 10 | 多源轻验证 + URL Verified | `verify_evidence_item` + `verification_status` |
| 11 | Trace 持久化与操作回放 | `.runtime/traces/{project_id}.jsonl` |
| 12 | 报告质量检查（8 维）+ 委员会复核 | `report_quality.py` + `defense_questions` |
| 13 | 内部 Skill Registry | `skills/registry.json`（4 个内部 skill） |
| 14 | 多源检索增强 | `retrieval/` orchestrator + 6 个适配器 |
| 15 | 资料卡片化（PDF / 图片 / 网页 / 备注） | `materials/` orchestrator + DraftEvidenceCard |

---

## 快速启动

### 1. 准备环境

```bash
# Windows / PowerShell 或 Git Bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev]"
.venv/Scripts/python.exe -m playwright install chromium
```

可选：复制 `.env.example` → `.env` 并填入 `MINIMAX_API_KEY`（不填也能跑，heuristic fallback 兜底）。

### 2. 启动后端 + 前端

```bash
# 一键启动（Windows）
start_all.bat

# 或手动：
.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 18181
.venv/Scripts/python.exe apps/web/dev_server.py
```

打开 <http://127.0.0.1:18181> 即可访问前端；后端 API 在 <http://127.0.0.1:18181/docs>。

### 3. 跑测试

```bash
# 全量回归（含 Playwright + 后端）
run_tests.bat

# 仅后端
.venv/Scripts/python.exe -m pytest apps/api/tests -v

# 仅前端
.venv/Scripts/python.exe -m pytest apps/web/e2e -v
```

详细部署说明：[docs/deployment/Local_Runbook.md](docs/deployment/Local_Runbook.md)。

---

## Demo 样例

主 Demo：

> **基于 YOLO 的钢材表面缺陷检测**

理由：方法词（YOLO）+ 任务词（缺陷检测）+ 对象词（钢材表面）齐全；
数据集（NEU-DET / GC10-DET）和 baseline（YOLOv5/v8 官方仓库）易找；
典型“过宽 → 收缩 → 工作包 → 开题报告”演示路径。

高风险 Demo：

> **基于多模态大模型的通用工业缺陷智能诊断**

用来演示**可行性 5 档 → 暂缓 / 不建议** + **3 条退化路线**。

完整脚本：[docs/demo/OneTopic_Demo_Script.md](docs/demo/OneTopic_Demo_Script.md)，
案例对比：[docs/demo/Demo_Cases.md](docs/demo/Demo_Cases.md)。

---

## 关键模块

```
apps/
  api/
    app/
      api/v1/                  # 路由: one_topic, skills
      services/
        evidence.py            # 证据池 + workspace_lane
        verification.py        # 多源轻验证 + URL Verified
        trace_store.py         # JSONL Trace 持久化
        report_quality.py      # 8 维报告审核
        skill_registry.py      # 内部 Skill 注册表
        retrieval/             # 多源检索 orchestrator
        materials/             # 资料卡片化 orchestrator
        final_package.py       # 开题报告 Markdown 生成
      schemas*.py              # Pydantic v2 模型
    tests/                     # Session 01-15 后端测试
  web/
    app.js                     # 前端逻辑（含 trace / quality / skills / retrieval / materials 面板）
    index.html
    styles.css
    e2e/                       # Session 01-15 Playwright 测试
docs/
  demo/                        # Demo 脚本与案例
  deployment/                  # 部署说明
  project/                     # 边界声明 / 简历描述
  testing/                     # 测试矩阵
skills/
  registry.json                # 4 个内部 skill
Plan/reports/                  # Session 01-16 验收报告
```

---

## 测试结果（截至 Session 15）

- 后端：`184 passed, 1 skipped`（覆盖 Session 01-15）
- Playwright：Session 14 主路径 `59 passed`；Session 15 `10 passed`
- 详细矩阵：[docs/testing/Test_Matrix.md](docs/testing/Test_Matrix.md)

---

## 项目边界（合规摘要）

PaperAgent **不会**：

- 生成完整毕业论文正文；
- 替代导师和学生的学术判断；
- 绕过付费数据库权限；
- 伪造引用；
- 把未验证资料当事实；
- 上传用户文件到第三方服务；
- 运行用户上传代码；
- 自动保证毕业。

详细声明：[docs/project/Scope_And_Compliance.md](docs/project/Scope_And_Compliance.md)。

---

## 后续路线（不在 Session 16 范围）

- **Session 17 候选**：Demo 数据固化与回归基线 —— 把 1-2 条 Demo 项目的输入、候选证据、报告输出与质量审核结果固化为回归基线。
- 不扩功能、不做新的智能体能力，专注**稳定、可复现、可比较**。

---

## 项目描述（简历用）

详见 [docs/project/Resume_Project_Description.md](docs/project/Resume_Project_Description.md)。