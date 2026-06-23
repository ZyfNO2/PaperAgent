# PaperAgent Session 32 SOP：学校模板合规与导出前检查

> 日期：2026-06-21  
> 前置：Session 29-31 已有报告草稿、复核和基线。  
> 本轮目标：不急着做精排 DOCX，先做导出前的学校模板合规检查与报告 readiness。

---

## 1. 目标

```text
判断当前开题报告草稿是否“可以导出给人看”。
```

---

## 2. Readiness 维度

```text
section_completeness
evidence_binding
reference_integrity
school_template_fit
risk_disclosure
workload_clarity
innovation_claim_safety
format_basic
```

每维输出：

```text
status: pass | warn | fail
message
required_fix
section_refs[]
```

---

## 3. 学校模板轻适配

先支持：

```text
default
engineering
cv_ai
```

检查：

```text
是否有研究背景；
是否有国内外研究现状；
是否有研究内容；
是否有技术路线；
是否有进度安排；
是否有参考文献；
是否有风险与备选方案；
是否有工作量和创新点。
```

---

## 4. 导出前硬拦截

```text
缺研究内容 -> fail；
缺技术路线 -> fail；
缺数据集但题目要求实验 -> fail；
参考资源全未验证 -> fail；
创新点含“首创/首次/完全解决”等夸大词 -> warn/fail；
EvidenceRef 为空 -> fail。
```

---

## 5. 测试

后端：

```text
1. 完整报告 readiness pass；
2. 缺技术路线 fail；
3. 缺 EvidenceRef fail；
4. 夸大创新词 warn/fail；
5. cv_ai 缺数据集 fail；
6. engineering 模板检查技术路线；
7. default 模板允许轻量但不允许空证据；
8. readiness 可序列化。
```

Playwright：

```text
S32-PW-1：导出前检查页可见；
S32-PW-2：8 维 readiness 显示；
S32-PW-3：fail 项显示 required_fix；
S32-PW-4：模板切换检查结果变化；
S32-PW-5：fail 时导出按钮 disabled；
S32-PW-6：pass/warn 时允许导出 Markdown；
S32-PW-7：S29 报告草稿不回退；
S32-PW-8：S31 baseline 不回退。
```

---

## 6. 验收标准

```text
1. Readiness 8 维完成；
2. 三个模板轻适配；
3. 导出前硬拦截生效；
4. Markdown 导出不回退；
5. 后端测试通过；
6. Playwright 通过；
7. 不承诺学校一定通过。
```

---

## 7. 完工报告

```text
Plan/reports/Session_32_ExportReadiness_TemplateCompliance_验收报告.md
```

