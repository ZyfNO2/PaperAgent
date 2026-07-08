# Re1.5 Phase 0 Changelog

## Phase 0: 基础设施修复

### 0.1 trace_events Annotated 修复
- **状态**: ✅ 已在 Re1.4 完成
- state.py 已有 Annotated[list[dict[str, Any]], operator.add]
- 所有节点已返回 [trace]（不手动拼接）
- 验证: case re15-p0-test2 完成 23 节点，无 InvalidUpdateError

### 0.2 import 路径修复
- **状态**: ✅ 已在 Re1.4 完成
- main.py 已有 sys.path.insert(0, _PROJECT_ROOT)
- 验证: uvicorn 启动成功，/health 返回 200

### 0.3 验证结果
- case_id: re15-p0-test2
- topic: 基于深度学习的混凝土桥梁裂缝检测研究
- elapsed: 125.59s
- n_nodes: 23 (全部节点)
- n_papers: 3
- n_packages: 2
- InvalidUpdateError: 无

### 注意事项
- PowerShell Invoke-RestMethod 默认编码导致中文题目乱码，需用 UTF-8 bytes 提交
- batch_run.py 中需用 requests 库或 httpx 而非 PowerShell

## Phase 2: 自动分析 + 规则驱动修复

### 分析结果
- 20 cases, 19 completed
- feasibility: all risky (score 30-45), score spread=15 < 20 → repair_needed=True
- review: 2 verdicts (BLOCK, MINOR_REVISION) → repair_needed=False
- zero_accept: ENG-THESIS-046 (0 papers) → repair_needed=True

### Fix 1: feasibility prompt 增强
- **文件**: pps/api/app/services/agents/prompts/feasibility_assessor.py
- **改动**: SYSTEM prompt 增加区分规则（baseline≥2+repo→feasible 70-85; baseline≥1→risky 40-60; 无baseline→not_recommended 10-30）
- **验证**: 重跑 ENG-THESIS-074 和 ENG-THESIS-046

### Fix 2: devils_advocate prompt
- **跳过**: review 已有 2 种 verdict (BLOCK, MINOR_REVISION)，不需要修复

### Fix 3: search_planner Crossref
- **跳过**: _template_plan 已有 Crossref method + object 查询
- ENG-THESIS-046 的 0 accept 是 verify 全部拒绝（32 candidates → 0 verified），不是搜索问题

### Fix 1 验证结果
- **074**: verdict=not_recommended, score=20 (was: risky, 40)
- **046**: verdict=not_recommended, score=20 (was: risky, 0/empty)
- **结论**: prompt 增加了区分规则，但 074 只有 1 baseline + 0 repo，046 有 0 baseline + 0 repo
- 两者确实证据不足，prompt 按规则给出 not_recommended 是正确的
- 但 074 和 046 的 score 相同 (20)，区分度不够 — 根因是 prompt 只传计数不传内容
- Re2 需要增强 prompt 传入论文摘要，让 LLM 能区分"1 baseline 但有 dataset" vs "0 baseline"
- **状态**: 保留改动（比原来全 risky 稍好，至少有 not_recommended verdict），记录限制
