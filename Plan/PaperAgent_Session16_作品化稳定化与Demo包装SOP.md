# PaperAgent Session 16 SOP：作品化、稳定化与 Demo 包装

> 日期：2026-06-19  
> 阶段定位：Session 09-15 已完成交互式证据工作台主闭环，本轮停止继续扩功能，转向可展示、可验收、可复盘的项目作品化。  
> 本轮目标：整理 README、Demo 样例、测试矩阵、错误提示、部署说明、项目边界声明和简历描述，让 PaperAgent 能作为完整项目被理解、运行、演示和评估。

---

## 1. Session 15 验收判断

已审阅：

```text
Plan/reports/Session_15_Material_Card_Intake_验收报告.md
```

判断：

```text
Session 15 可过验收；
可以进入 Session 16。
```

依据：

```text
1. PDF / 图片 / 网页文字 / URL+描述 / 导师备注入口已完成；
2. DraftEvidenceCard 可生成、编辑、导入 Evidence Ledger；
3. 导入后默认 pending，不直接 supports；
4. Trace 已记录 material_uploaded / parsed / draft_card_imported 等事件；
5. FinalPackage 已显示来源、页码、解析置信度；
6. ReportQuality 不因 pending + unverified material 证据虚假升分；
7. 后端新增 20 tests passed，全量后端回归 184 passed, 1 skipped；
8. Playwright 新增 10 passed；
9. 未做项边界明确：不做 OCR、不做复杂 PDF 版面、不做批处理、不做全文 chunk 检索。
```

进入 Session 16 的理由：

```text
Session 09-15 已形成完整主闭环：
工作台 → 证据导入 → 多源检索 → URL 验证 → Trace → 报告导出 → 报告质量审核 → 资料卡片化。
```

此时继续扩展全文 RAG、视频解析或复杂多 Agent 审核，会提高复杂度但不明显提升当前项目可展示性。Session 16 应优先收束。

---

## 2. Session 16 名称

```text
作品化、稳定化与 Demo 包装
```

一句话目标：

```text
把 PaperAgent 从“连续开发中的功能集合”整理成“能运行、能演示、能说明边界、能证明测试覆盖”的项目作品。
```

---

## 3. 本阶段不做什么

| 不做 | 原因 |
|---|---|
| 不新增核心 Agent 能力 | 当前主闭环已经完成，优先稳定 |
| 不做全文向量库 / 大规模 RAG | 会引入新的架构风险 |
| 不做视频解析 / 批量图片处理 | 非当前开题证据工作台 P0 |
| 不做 DOCX / PPT 高级导出 | 展示阶段先保证 Markdown 与项目说明 |
| 不接入第三方 Skill Marketplace | 内部 Skill Registry 已够当前演示 |
| 不改动核心证据规则 | 避免作品化阶段引入 supports 污染 |

---

## 4. 本阶段核心交付

Session 16 交付 6 类文档和 2 类稳定化改造：

```text
1. README 重写 / 增补；
2. Demo 样例与演示脚本；
3. 测试矩阵；
4. 部署与运行说明；
5. 项目边界与合规声明；
6. 简历 / 项目介绍描述；
7. 前端错误提示与空状态优化；
8. 最小 smoke checklist。
```

建议新增文档：

```text
README.md
docs/demo/OneTopic_Demo_Script.md
docs/demo/Demo_Cases.md
docs/testing/Test_Matrix.md
docs/deployment/Local_Runbook.md
docs/project/Scope_And_Compliance.md
docs/project/Resume_Project_Description.md
Plan/reports/Session_16_Productization_Demo_验收报告.md
```

如果不想在本轮大改根 README，可先新增：

```text
docs/project/PaperAgent_Project_Overview.md
```

但最终 README 仍需要能引导外部读者。

---

## 5. README 改造要求

README 至少包含：

```text
1. 项目定位；
2. 核心问题；
3. 核心能力；
4. 主流程图；
5. 快速启动；
6. Demo 样例；
7. 关键模块；
8. 测试结果；
9. 项目边界；
10. 后续路线。
```

项目定位建议：

```text
PaperAgent 是一个面向中国研究生开题/选题场景的交互式证据工作台。
它不是全自动论文生成器，而是帮助用户把题目、论文、数据集、工程项目、
PDF/截图/网页材料整理成可审核证据链，并生成可追溯的开题报告 Markdown。
```

README 必须明确：

```text
rejected 不引用；
pending 不直接 supports；
failed verification 不 supports；
所有 AI/解析结果需用户确认；
系统只辅助选题与开题，不替代学术判断。
```

---

## 6. Demo 样例设计

### 6.1 推荐 Demo 题目

主 Demo：

```text
基于 YOLO 的钢材表面缺陷检测
```

原因：

```text
1. 方法词明确：YOLO；
2. 任务词明确：缺陷检测；
3. 对象词明确：钢材表面；
4. 容易找到论文、数据集、GitHub baseline；
5. 适合展示“过宽题目 → 可行路线 → 工作包 → 开题报告”。
```

备选 Demo：

```text
基于深度学习的脑肿瘤 MRI 图像分割
基于 Transformer 的中文文本情感分析
基于图神经网络的交通流预测
```

### 6.2 Demo 脚本

`docs/demo/OneTopic_Demo_Script.md` 应按真实演示顺序写：

```text
1. 输入题目；
2. 查看关键词拆解；
3. 运行多源检索；
4. 导入候选论文 / 数据集 / GitHub；
5. 运行 URLVerified；
6. 上传或粘贴一条用户资料；
7. 在工作台移动 / 审核证据；
8. 查看 Trace；
9. 生成 FinalPackage Markdown；
10. 运行 ReportQuality；
11. 展示最终开题报告与修改清单。
```

每一步都写：

```text
目标；
操作；
预期页面变化；
如果失败的降级处理。
```

---

## 7. 测试矩阵

新增：

```text
docs/testing/Test_Matrix.md
```

测试矩阵应覆盖：

| 范围 | 文件 | 目标 |
|---|---|---|
| Verification | `apps/api/tests/test_session10_verification.py` | URL 轻验证与 supports 约束 |
| Trace | `apps/api/tests/test_session11_trace_persistence.py` | jsonl 持久化与 timeline |
| ReportQuality | `apps/api/tests/test_session12_report_quality.py` | 8 维报告审核 |
| SkillRegistry | `apps/api/tests/test_session13_skill_registry.py` | 内部 Skill 注册与健康检查 |
| Retrieval | `apps/api/tests/test_session14_multi_source_retrieval.py` | 多源检索、导入、去重 |
| Materials | `apps/api/tests/test_session15_material_card_intake.py` | PDF/图片/网页资料卡片化 |
| Frontend S10-S15 | `apps/web/e2e/test_one_topic_session*.py` | 主路径 UI 验收 |

必须记录最新结果：

```text
Session 15 报告：后端 184 passed, 1 skipped；
Session 15 Playwright：10 passed；
Session 14 Playwright S14 + S7-S13：59 passed；
```

后续若重跑，以最新测试输出覆盖。

---

## 8. 部署与运行说明

新增：

```text
docs/deployment/Local_Runbook.md
```

内容：

```text
1. 环境要求；
2. 安装依赖；
3. 启动后端；
4. 启动前端；
5. 运行测试；
6. 常见问题；
7. 清理 .runtime；
8. 外部 API 降级说明；
```

必须说明：

```text
OpenAlex / arXiv / GitHub / HuggingFace 可能受网络影响；
Semantic Scholar / Kaggle 当前是占位或可选；
测试默认 mock 外部 API；
.runtime 保存 trace / materials / retrieval 等本地数据。
```

---

## 9. 项目边界与合规声明

新增：

```text
docs/project/Scope_And_Compliance.md
```

必须覆盖：

```text
1. 不生成完整毕业论文正文；
2. 不替代导师和学生的学术判断；
3. 不绕过付费数据库权限；
4. 不伪造引用；
5. 不把未验证资料当事实；
6. 不上传用户文件到第三方服务；
7. 不运行用户上传代码；
8. 只输出可追溯的开题辅助材料。
```

合规表达：

```text
系统输出是开题辅助建议，所有证据、题目、创新点和实验方案必须由用户复核。
```

---

## 10. 前端稳定化

本轮允许做小范围 UX 修补，不做新功能。

优先项：

```text
1. 空状态提示；
2. 加载中状态；
3. 外部检索失败提示；
4. 上传失败提示；
5. verification failed 的解释；
6. ReportQuality 低分的下一步建议；
7. Trace 无记录时的说明；
```

不做：

```text
大改布局；
新增复杂页面路由；
引入新的 UI 框架；
做营销式 landing page。
```

---

## 11. Demo 数据与样例输出

建议新增：

```text
docs/demo/Demo_Cases.md
```

至少包含 2 个样例：

```text
1. 成熟可行题目：基于 YOLO 的钢材表面缺陷检测；
2. 风险较高题目：基于多模态大模型的通用工业缺陷智能诊断。
```

每个样例记录：

```text
输入题目；
关键词拆解；
检索结果概览；
核心证据；
可行性判断；
建议收缩方向；
工作包；
报告质量审核结果；
```

不要保存大文件或真实用户隐私资料。

---

## 12. 简历项目描述

新增：

```text
docs/project/Resume_Project_Description.md
```

建议包含三种长度：

```text
1. 一句话版本；
2. 简历项目版本；
3. 面试展开版本；
```

强调点：

```text
FastAPI / 前端 MVP；
证据工作台；
多源检索；
URLVerified；
Trace 持久化；
ReportQuality；
Skill Registry；
资料卡片化；
pytest + Playwright 测试闭环；
```

避免表达：

```text
全自动写论文；
自动保证毕业；
自动替代导师判断；
```

---

## 13. 验收标准

通过条件：

```text
1. README 或项目总览能说明项目定位、能力、运行方式和边界；
2. Demo 脚本能按步骤演示主流程；
3. 至少 2 个 Demo Case 完成记录；
4. Test Matrix 覆盖 Session 10-15 后端和 Playwright；
5. Local Runbook 能指导本地启动和测试；
6. Scope / Compliance 明确系统边界；
7. Resume 描述完成；
8. 前端关键空状态 / 错误提示有基本覆盖；
9. 不新增破坏 EvidenceRef / Verification / Trace 的行为；
10. 后端核心回归通过；
11. Playwright 主路径通过；
12. 新增 Session 16 验收报告。
```

最低可接受 MVP：

```text
README；
Demo Script；
Test Matrix；
Local Runbook；
Scope And Compliance；
Resume Project Description；
Session 16 验收报告。
```

---

## 14. 测试要求

### 14.1 后端回归

至少运行：

```text
apps/api/tests/test_session10_verification.py
apps/api/tests/test_session11_trace_persistence.py
apps/api/tests/test_session12_report_quality.py
apps/api/tests/test_session13_skill_registry.py
apps/api/tests/test_session14_multi_source_retrieval.py
apps/api/tests/test_session15_material_card_intake.py
```

### 14.2 Playwright 回归

至少运行：

```text
apps/web/e2e/test_one_topic_session10_verification.py
apps/web/e2e/test_one_topic_session11_trace_persistence.py
apps/web/e2e/test_one_topic_session12_report_quality.py
apps/web/e2e/test_one_topic_session13_skill_registry.py
apps/web/e2e/test_one_topic_session14_retrieval.py
apps/web/e2e/test_one_topic_session15_material_cards.py
```

### 14.3 文档检查

检查：

```text
1. 所有新增文档路径存在；
2. README 中的命令可执行；
3. Demo 脚本无明显过期路径；
4. 测试矩阵中的测试文件存在；
5. 边界声明与实际功能一致。
```

---

## 15. 完工报告要求

完成后新增：

```text
Plan/reports/Session_16_Productization_Demo_验收报告.md
```

报告必须包含：

```text
1. 本阶段范围；
2. 新增 / 修改文档清单；
3. README 改造内容；
4. Demo Case；
5. Test Matrix；
6. Local Runbook；
7. Scope / Compliance；
8. Resume 描述；
9. 前端稳定化修改；
10. 后端测试结果；
11. Playwright 测试结果；
12. 未做项；
13. 下一 Session 建议。
```

报告中必须明确写：

```text
是否新增功能；
是否改动证据规则；
是否跑过完整回归；
Demo 是否能从空项目跑通；
```

---

## 16. 下一 Session 预告

Session 17 建议：

```text
Demo 数据固化与回归基线
```

目标：

```text
把 1-2 条 Demo 项目的输入、候选证据、报告输出和质量审核结果固化成回归基线，便于后续每次修改都能判断是否破坏主流程。
```

边界：

```text
不扩功能；
不做新的智能体能力；
只做稳定、可复现、可比较。
```

