# 项目边界与合规声明 (Scope and Compliance)

> PaperAgent (TopicPilot-CN) 是一个**开题辅助工具**，不是论文生成器。
> 本文档明确系统能做、不能做、必须遵守的合规底线。

---

## 1. 系统定位

```text
PaperAgent 是一个面向中国研究生开题/选题场景的交互式证据工作台，
帮助用户把题目、论文、数据集、GitHub 工程、PDF/截图/网页材料整理成
可审核的证据链，并产出可追溯的开题报告 Markdown。

系统输出是开题辅助建议，所有证据、题目、创新点和实验方案必须由用户复核。
```

---

## 2. 系统不会做的事（8 条边界）

| # | 不会做 | 原因 |
|---|---|---|
| 1 | **不生成完整毕业论文正文** | 学术诚信由学生和导师负责，系统只给开题阶段辅助材料 |
| 2 | **不替代导师与学生的学术判断** | 可行性判断、题目选择、创新点定义由人决策 |
| 3 | **不绕过付费数据库权限** | 不抓 IEEE / ACM / Springer 等付费墙后正文，仅用公开 metadata |
| 4 | **不伪造引用** | 所有 `url` / `doi` / `arxiv_id` 必须来自用户上传或公开检索结果，不编造 |
| 5 | **不把未验证资料当事实** | `verification_status != verified` 的证据不进 supports |
| 6 | **不上传用户文件到第三方服务** | PDF / 截图存 `.runtime/materials/`，不外发 |
| 7 | **不运行用户上传代码** | GitHub repo 仅做静态字段核查（README / license / 训练脚本等），不执行 |
| 8 | **不自动保证毕业** | 工具是辅助，最终能否开题/答辩由学术判断与实证结果决定 |

---

## 3. 证据规则（强约束）

```text
rejected 不引用；
pending 不直接 supports；
failed verification 不 supports；
所有 AI/解析结果需用户确认；
所有开题报告中的引用必须挂接 EvidenceRef (无 ref 即 unsupported_claim)。
```

详见 [apps/api/app/services/evidence.py](../apps/api/app/services/evidence.py)
与 [apps/api/app/services/final_package.py](../apps/api/app/services/final_package.py)。

---

## 4. 数据存储与隐私

- **本地优先**：所有 trace / 资料 / 中间结果存 `.runtime/`，不上云。
- **外部 API**：调用 OpenAlex / arXiv / GitHub / HuggingFace 时只发公开检索词，不发用户原文。
- **LLM**：走 MiniMax-M3 (Anthropic-compatible)，凭据从 `.env` 读，`.env` 不进 git。
- **失败兜底**：所有 LLM 路径都有 heuristic fallback；外部 API 失败时返回降级结果而非崩溃。

---

## 5. 内容来源声明

| 类型 | 来源 | 用途 |
|---|---|---|
| 论文元数据 | OpenAlex / arXiv 公开 API | `papers` 候选 |
| 数据集元数据 | HuggingFace / Papers With Code | `datasets` 候选 |
| GitHub 仓库元数据 | GitHub REST API | `repos` 候选 |
| 用户上传 PDF / 图片 | 用户本地文件 | 解析后变 DraftEvidenceCard，需用户确认 |
| 用户粘贴网页文字 / 备注 | 用户输入 | 解析后变 DraftEvidenceCard，需用户确认 |

所有外部来源在 UI 与 FinalPackage 报告里都明确标注 `source_mode` 与 `verification_status`。

---

## 6. 输出使用规范

PaperAgent 产出的 Markdown 报告：

- **可以**：作为开题阶段思路梳理、文献整理、答辩前自查的辅助材料；
- **建议**：与导师、同行评议交叉核对后再写入正式开题文档；
- **不应**：直接复制粘贴到毕业论文正文。

---

## 7. 安全与边界

- 文件大小硬限制 **20MB**（PDF / 图片 / 文本）；
- MIME 白名单：`application/pdf / image/png / image/jpeg / image/webp / text/plain / text/markdown`；
- 文件名 sanitize：移除控制字符 / 路径分隔符 / 连续点，限长 120，中文保留；
- 不读工作区外路径；不写工作区外路径；不上传到第三方。

---

## 8. 责任声明

本项目按 “as-is” 提供，不对以下情况负责：

- 用户自行填入的题目 / 证据 / 备注导致的错误结论；
- 外部 API（OpenAlex / arXiv / GitHub / HuggingFace）返回的过时或不准确元数据；
- LLM 凭据泄露 / `.env` 不当管理造成的安全问题；
- 用户将系统输出直接用于学术不端场景（如伪造引用、抄袭）。

学术诚信责任始终在用户与导师。