# TopicPilot-CN

中国研究生开题选题助手。当前阶段：**Phase 02 — 题目拆解与论文结构映射**（进行中）。

## LLM 配置

复制 `.env.example` → `.env`，填入 MiniMax M3 凭据：

```bash
cp .env.example .env
# 编辑 .env，把 MINIMAX_API_KEY=... 替换为你的真实 key
```

调用入口：`packages.llm.chat()` / `packages.llm.chat_json()`，已通过 LiteLLM 接到 MiniMax-M3。

## 仓库结构

```text
topicpilot-cn/
├── apps/
│   └── api/                    # FastAPI 后端
│       ├── app/
│       │   ├── api/v1/         # 路由（projects）
│       │   ├── core/           # 配置
│       │   ├── db/             # SQLAlchemy 异步引擎、仓储
│       │   └── main.py
│       └── tests/              # pytest
├── packages/
│   ├── domain/                 # Pydantic v2 领域模型（ProjectIntake 等）
│   └── agents/                 # LangGraph 状态机
│       ├── states/
│       ├── nodes/
│       └── graphs/             # build_intake_graph()
├── data/
│   ├── projects/               # 每个案例一个目录，含 00_input.md
│   └── topicpilot.db           # SQLite 库（运行时生成）
├── Plan/                       # 项目设计文档与原始资料
└── pyproject.toml
```

## Phase 01 范围

按 `Plan/TopicPilot-CN_SOP_Phases/Phase_01_任务建档与毕业目标确认.md` 实现：

- `ProjectIntake` 等 Pydantic 模型（`packages/domain/models.py`）
- FastAPI 端点：
  - `POST /api/v1/projects`
  - `GET  /api/v1/projects/{id}`
  - `POST /api/v1/projects/{id}/intake/validate`
- LangGraph `TopicPilotGraph` 骨架（`packages/agents/graphs/intake_graph.py`）：
  `IntakeNode → IntakeValidationNode → {HumanClarificationNode | TopicDecompositionNode | END}`
- 单元测试覆盖验收标准 §7.2

## 快速运行

```bash
# 1. 装依赖（uv 推荐，亦可 pip）
uv sync

# 2. 启服务
uv run uvicorn app.main:app --app-dir apps/api --reload

# 3. 跑测试
uv run pytest
```

## Phase 01 阻断规则（自动）

`intake_rating` 由后端在创建/重校验时计算：

| 评级 | 触发条件 | outcome | 允许进 Phase 02 |
|------|---------|---------|-----------------|
| A | 无任何缺失 | OK | 是 |
| B | 仅缺 P2，或 P1 ≤ 2 | OK | 是（带显式假设） |
| C | 任一 P0 缺失 | NEED_CLARIFICATION | 否（须先 HumanClarification） |
| D | P1 ≥ 3 或 P0 大量缺失 | BLOCKED | 否 |

P0 字段：`major`, `goal_level`（必填）, `proposal_deadline`, `thesis_deadline`, `first_result_deadline`, `advisor_direction`, `raw_topic`（必填）。

## 后续 Phase

- Phase 02 — 题目拆解与论文结构映射
- Phase 03 — 方向成熟度与检索计划
- Phase 04 — 证据采集与 Baseline 账本
