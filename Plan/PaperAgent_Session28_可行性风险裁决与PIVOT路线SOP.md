# PaperAgent Session 28 SOP：可行性风险裁决与 PIVOT 路线

> 日期：2026-06-21  
> 前置：Session 26 至少能生成 EvidenceRef，Session 27 最好已有可回放事件。  
> 本轮目标：基于已选资料和已晋升 EvidenceRef，给出开题可行性裁决和可操作 PIVOT 路线。

---

## 1. 目标

```text
把“这个题目能不能做”变成结构化判断：
GO / CONDITIONAL / PIVOT / PARK / STOP。
```

---

## 2. 风险维度

建议 7 维：

```text
EvidenceSupport
DataAvailability
BaselineReadiness
ExperimentalClarity
ScopeControl
ResourceFit
NoveltyDifferentiation
```

每维输出：

```text
score: 0-100
level: low | medium | high | fatal
evidence_refs[]
reason
suggestion
```

---

## 3. 硬性否决

```text
无数据集 -> 不得 GO；
无评价指标 -> 不得 GO；
无 baseline / repo / 可比较方法 -> 不得 GO；
只有文字方案无实验 -> 不得 GO；
URL 全部未验证 -> 不得 GO；
EvidenceRef 少于最低阈值 -> 不得 GO。
```

---

## 4. 裁决

```text
GO：证据、数据、baseline、指标基本齐；
CONDITIONAL：可做，但需补 1-2 个关键资源；
PIVOT：方向需要收缩或换对象/数据集；
PARK：当前条件不足，未来可重启；
STOP：核心条件不可验证，不建议继续。
```

---

## 5. PIVOT 路线

至少给三条：

```text
保守路线：缩小对象/任务，保证毕业；
平衡路线：保留方法，换更可验证数据；
进取路线：保留创新点，但补充风险条件。
```

每条路线包含：

```text
new_topic
changed_keywords
required_evidence
expected_workload
risk_delta
recommended_for
```

---

## 6. 测试

后端：

```text
1. 无数据集 -> STOP/PIVOT；
2. 有数据集无 baseline -> CONDITIONAL/PIVOT；
3. 证据齐全 -> GO；
4. URL 未验证 -> 不得 GO；
5. fatal 维度覆盖总分；
6. PIVOT 至少三条；
7. 每条建议绑定 evidence_refs 或 missing_evidence；
8. S26 EvidenceRef 不回退。
```

Playwright：

```text
S28-PW-1：可行性卡显示 7 维；
S28-PW-2：硬性否决显示；
S28-PW-3：GO/CONDITIONAL/PIVOT/PARK/STOP 可见；
S28-PW-4：PIVOT 路线可展开；
S28-PW-5：点击路线不会直接改题，需确认；
S28-PW-6：每条结论有证据或缺口；
S28-PW-7：S25-S27 不回退。
```

---

## 7. 验收标准

```text
1. 可行性裁决结构化；
2. 硬性否决生效；
3. PIVOT 路线可操作；
4. 结论绑定 EvidenceRef 或缺口；
5. 不把候选当证据；
6. 后端测试通过；
7. Playwright 通过。
```

---

## 8. 完工报告

```text
Plan/reports/Session_28_Feasibility_Pivot_验收报告.md
```

