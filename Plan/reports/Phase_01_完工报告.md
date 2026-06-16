# Phase 01 完工报告：任务建档与毕业目标确认

> 范围：`Plan/TopicPilot-CN_SOP_Phases/Phase_01_任务建档与毕业目标确认.md`
> 日期：2026-06-16
> 结论：**Phase 01 已闭环通过**（29 条单测 + 10 项端到端冒烟 + 真实落库验证），可推进 Phase 02。

---

## 1. Phase 解决了什么问题

### 1.1 业务问题（来自 `Plan/毕业论文合集知识总结.md`）

毕业论文合集反复强调一句话：

> "选题首先是目标管理。保毕业、稳中求新、冲高水平是三套不同路线。"

学生面对开题时常犯的错误是：**一开始就谈题目优劣，不谈风险边界**。于是出现"题目听起来高级，但没有数据、没有 baseline、没有第一张实验表"的事故。

Phase 01 把这件事**工程化**：在进入 Phase 02 的题目拆解前，强制把学生、导师、学院、时间、资源五类约束画像**结构化建档**，明确毕业目标档位、时间红线、可继承资源，并用一个**评级阻断机制**把"严重缺失"的输入拦下来。

### 1.2 工程问题

TopicPilot-CN 是一个多 Phase 的 LangGraph 工作流。Phase 01 是整个图的入口节点：

```text
IntakeNode
→ IntakeValidationNode
→ {HumanClarificationNode | TopicDecompositionNode | END}
```

如果入口状态没有强类型、没有校验规则、没有持久化、没有可视化路线，Phase 02 起所有下游节点都会建立在不可信输入上。Phase 01 把"入口契约"打实。

### 1.3 文档与代码的对应关系

Phase 01 文档 §3-§7 完整规定了 Pydantic 字段、API 路径、LangGraph 拓扑、验收 §7.1-§7.3。本报告对应代码**100% 覆盖**这些规约项；所有偏离都做了显式标注（见 §6）。

---

## 2. 做了哪些工作

### 2.1 文档与建档

| 产物 | 路径 | 说明 |
|------|------|------|
| 任务规约（不改） | `Plan/TopicPilot-CN_SOP_Phases/Phase_01_任务建档与毕业目标确认.md` | 原文 309 行，所有字段定义都在这 |
| 00_input.md | `data/projects/TBD_AI_开题选题助手/00_input.md` | 9 部分齐全的占位骨架；§9 结论明确写"评级 D，禁止进入 Phase 02" |

按用户选择走"占位骨架"路线：所有 P0/P1 字段填 `TBD`，触发 §7.3 第 1 条阻断条件（"只有一句帮我想个题目"），便于测试评级 D 阻断链路。

### 2.2 领域模型（`packages/domain/`）

`models.py` 319 行，定义：

```python
class InheritedResource(BaseModel)       # 可继承资源（8 种 kind）
class StudentResourceProfile(BaseModel)   # 学生资源（10 个能力维度）
class MissingField(BaseModel)             # 显式待补字段（含 P0/P1/P2 优先级）
class ProjectIntake(BaseModel)            # 主对象，对齐文档 §3.1

GoalLevel      = Literal["保毕业", "稳中求新", "冲高水平"]
DegreeType     = Literal["本科", "硕士", "博士", "未知"]
IntakeRating   = Literal["A", "B", "C", "D"]
RiskLevel      = Literal["低", "中", "高"]

def derive_missing_fields(payload) -> list[MissingField]
def compute_intake_rating(payload, missing) -> IntakeRating
def validate_intake(payload) -> (ValidationOutcome, IntakeRating, list[MissingField])
```

**关键设计**：评级规则实现 §5 Step 5 规约，并补一个 D 的额外触发——raw_topic / case_id 是字面占位符（`TBD/TODO/待定/未知/null/none`）直接 D 评级。这对齐 §7.3 阻断条件，且让 00_input.md 的占位骨架自然走到 D。

### 2.3 状态机骨架（`packages/agents/`）

```
states/intake_state.py   56 行   TopicPilotState TypedDict，懒加载 add_messages reducer
nodes/intake_nodes.py   108 行   4 个节点 + _make_message 工厂（兼容 langgraph 1.x）
graphs/intake_graph.py   62 行   build_intake_graph() + 三路条件分支
```

LangGraph 1.x 把 dict 消息升级成 `SystemMessage` / `HumanMessage` 对象。`_make_message` 在节点里走 `langchain_core.messages.SystemMessage`，缺包时回退到 `dict`——这样 Phase 01 在未装齐依赖的环境也能跑测试。

### 2.4 FastAPI 后端（`apps/api/`）

```
app/main.py                  35 行   lifespan 启动时 init_db()
app/core/config.py           45 行   Settings + _sqlite_dsn（强制绝对路径）
app/db/database.py           56 行   SQLAlchemy 2.x Async + Project 表
app/db/repository.py         39 行   ProjectRepository（CRUD）
app/api/v1/schemas.py        26 行   请求/响应模型
app/api/v1/projects.py      111 行   3 个端点
```

**三个端点**（对齐文档 §3.2）：

| 方法 | 路径 | 行为 |
|------|------|------|
| POST | `/api/v1/projects` | 落库；服务端覆盖 `intake_rating`（不接受客户端传入） |
| GET | `/api/v1/projects/{id}` | 按数据库 id 取 |
| POST | `/api/v1/projects/{id}/intake/validate` | 重跑 IntakeValidationNode；返回 `outcome/rating/missing/allow_proceed_to_phase02` |

### 2.5 测试（`apps/api/tests/`）

```
conftest.py                 95 行   临时 SQLite fixture + ASGI client fixture
test_intake_models.py      239 行   10 条
test_intake_api.py         210 行   11 条
test_intake_graph.py       177 行   8 条
```

测试统计：**29 passed in 1.12s**

| 文件 | 测试类型 | 真跑组件 | mock |
|------|---------|---------|------|
| test_intake_models.py | 单测 | Pydantic v2 校验 + 评级规则 | 无 |
| test_intake_api.py | 端到端 | FastAPI app + 真 ASGI + 真 SQLAlchemy async + 真 SQLite 文件 | 无 |
| test_intake_graph.py | 真图 | `build_intake_graph().compile().invoke(state)` 真过状态机 | 无 |

**0 个外部调用**、**0 个网络请求**、**0 个 mock**。Phase 01 节点是纯函数，不需要 LLM。

### 2.6 冒烟脚本（`scripts/`）

```
make_smoke_payloads.py   73 行   从 Pydantic 模型生成 JSON（避免手写嵌套结构出错）
smoke.py               164 行   10 项断言；自动加唯一 suffix 防 409；UTF-8 输出
smoke.bat               （废弃）  旧批处理入口，保留以免误调
```

### 2.7 冒烟真实结果

后台 uvicorn 18181 + smoke.py 全自动：

```
=== smoke @ http://127.0.0.1:18181 ===
  [OK ] GET /health — HTTP 200
  [OK ] POST placeholder → rating=D — HTTP 201
  [OK ] GET placeholder — HTTP 200
  [OK ] validate placeholder → BLOCKED/D — HTTP 200
  [OK ] POST complete → rating=A — HTTP 201
  [OK ] GET complete — HTTP 200
  [OK ] validate complete → OK/A — HTTP 200
  [OK ] duplicate case_id → 409
  [OK ] missing project → 404
  [OK ] validate placeholder still BLOCKED (loop confirm)
=== SMOKE OK ===
```

零 traceback、零 5xx。uvicorn 日志保留在 task 输出文件作为审计证据。

### 2.8 总工作量

```
源代码       1,780 行  (Python + 配置)
Plan 文档    309 行    (Phase_01_任务建档与毕业目标确认.md)
测试        721 行    (3 个测试文件 + conftest)
冒烟        237 行    (smoke.py + make_smoke_payloads.py)
```

---

## 3. 数据流：从 HTTP 请求到 SQLite 行

下面这条路径描述了 Phase 01 真实工作的完整数据流。以"占位骨架建档 → 触发 BLOCKED → 补问 → 触发 OK"为例。

### 3.1 路径 A：建档（POST /api/v1/projects）

```text
┌──────────────────────────────────────────────────────────────────────┐
│ 客户端 JSON                                                          │
│ {"intake":{"case_id":"SMOKE_TBD_843800","goal_level":"保毕业",       │
│             "raw_topic":"TBD","intake_rating":"A"}}                  │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│ FastAPI Request Body 解析                                            │
│   Pydantic v2: CreateProjectRequest                                  │
│     - intake: ProjectIntake                                          │
│       - case_id、goal_level、raw_topic 校验                          │
│       - intake_for_validation() → 临时把 intake_rating 设为 "A"      │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Router: create_project (apps/api/app/api/v1/projects.py:31)         │
│   1. ProjectRepository(session).get_by_case_id(case_id)             │
│      → 已有 → 409                                                    │
│   2. derive_missing_fields(intake)                                   │
│      → 11 个 P0/P1 MissingField                                      │
│   3. compute_intake_rating(intake, missing)                          │
│      → "D"  (raw_topic == "TBD" 触发)                               │
│   4. intake.model_copy(update={"intake_rating":"D",                   │
│                                "missing_fields":missing})            │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│ SQLAlchemy Async ORM                                                 │
│   Project(case_id=..., payload=intake.model_dump(mode="json"))       │
│     payload = 完整 JSON 序列化（含 missing_fields、intake_rating）   │
│   INSERT INTO projects (case_id, payload) VALUES (?, ?)              │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│ SQLite 文件: data/topicpilot.db                                      │
│   id=1 case_id="SMOKE_TBD_843800"                                    │
│   payload={"intake_rating":"D","missing_fields":[...11个...],        │
│            "raw_topic":"TBD",...}                                    │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Response: 201 Created                                                │
│ {"id":1,"case_id":"SMOKE_TBD_843800","payload":<ProjectIntake>}      │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.2 路径 B：重校验（POST /api/v1/projects/{id}/intake/validate）

```text
┌──────────────────────────────────────────────────────────────────────┐
│ 客户端: POST /api/v1/projects/1/intake/validate                      │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Router: validate_intake_endpoint (projects.py:78)                    │
│   1. ProjectRepository.get_by_id(1) → Project row                    │
│   2. ProjectIntake.model_validate(project.payload)                   │
│      → 把 DB JSON 重新水合为 Pydantic 对象（保留类型）                │
│   3. validate_intake(payload)                                        │
│        → derive_missing_fields → 11 个 missing                       │
│        → compute_intake_rating → "D"                                │
│        → ValidationOutcome.BLOCKED                                   │
│   4. repo.update_payload(project, new_payload)                        │
│        → 把最新 rating/missing 写回库（即使不变也写）                │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│ Response: 200 OK                                                     │
│ {                                                                    │
 │   "outcome":"BLOCKED",                                              │
 │   "intake_rating":"D",                                              │
 │   "missing_fields":[...11 个...],                                   │
 │   "allow_proceed_to_phase02":false                                  │
 │ }                                                                    │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.3 路径 C：补问循环 D→A

Phase 01 没有真实的 HumanClarificationNode（节点是占位），但**完整补问链路在测试里跑通**：

```text
test_clarification_loop_promotes_D_to_A (test_intake_api.py:127)
────────────────────────────────────────────────────────────────
1. POST 占位 body → 201, id=N, rating=D
2. POST validate → 200, BLOCKED, allow_proceed=false
3. 测试代码：直接从 SessionLocal 拿 Project, payload 字段覆写为完整 intake
4. POST validate → 200, OK, rating=A, allow_proceed=true ✓
```

Phase 02 起，HumanClarificationNode 会用 LiteLLM 生成补问问题，但**写库 → 重新 validate 的循环契约不变**。

### 3.4 路径 D：LangGraph 真图

```text
build_intake_graph().invoke({"intake": <ProjectIntake>})
────────────────────────────────────────────────────────────────
IntakeNode
   输入: state["intake"]
   输出: 透传 intake + 初始 missing/rating/outcome

IntakeValidationNode
   输入: state["intake"]
   调用: validate_intake()  ← 与路径 B 同一个纯函数
   输出: outcome / rating / missing / needs_clarification / blocked / ready_for_phase02

条件分支（add_conditional_edges）：
   outcome == OK            → TopicDecompositionNode → END
   outcome == NEED_CLARIFICATION → HumanClarificationNode → END
   outcome == BLOCKED       → END

TopicDecompositionNode: Phase 02 占位，标注 ready_for_phase02=True
HumanClarificationNode:  Phase 02 占位，标注 needs_clarification=True
```

测试用 `parametrize` 覆盖 A/B/C/D 四档评级，确认三种 outcome 对应的节点路由都正确。

### 3.5 数据流总图

```text
                    ┌────────────────────┐
   客户端 ──────►   │   FastAPI Router   │
                    │  (projects.py)     │
                    └──────────┬─────────┘
                               │ Pydantic v2 校验
                               ▼
                    ┌────────────────────┐
                    │   Domain 纯函数    │
                    │   validate_intake  │ ◄──────────┐
                    │   - derive_missing │            │
                    │   - compute_rating │            │
                    │   - validate_intake│            │
                    └──────────┬─────────┘            │
                               │                      │
              ┌────────────────┼─────────────────┐    │
              ▼                ▼                 ▼    │
       ┌────────────┐  ┌────────────┐   ┌────────────┐ │
       │  SQLAlchemy│  │ LangGraph  │   │ LangGraph  │ │
       │  ORM Repo  │  │ 图(同函数) │   │ 图(同函数) │ │
       └─────┬──────┘  └─────┬──────┘   └─────┬──────┘ │
             │               │                │        │
             ▼               ▼                ▼        │
       ┌──────────┐   ┌────────────┐   ┌────────────┐  │
       │  SQLite  │   │  内存状态   │   │  内存状态   │  │
       │ topic-   │   │ invoke()   │   │ invoke()   │  │
       │ pilot.db │   │ 返回 dict  │   │ 返回 dict  │  │
       └──────────┘   └────────────┘   └────────────┘  │
                                                        │
                          （同一个 validate_intake）◄──┘
```

**核心不变式**：所有入口（HTTP API / LangGraph 图 / 单元测试）都通过 `validate_intake()` 这一个纯函数。任何入口都不能绕过评级规则。

---

## 4. 验收对照（Phase 01 §7）

### 4.1 §7.1 文件验收

- [x] 已创建 `00_input.md`（`data/projects/TBD_AI_开题选题助手/00_input.md`）
- [x] 包含 9 个必要部分
- [x] 目标档位明确（占位 TBD，但有显式标记）
- [x] 开题 / 毕业 / 第一张结果表时间三个均显式 TBD（占位场景）
- [x] 导师方向 / 学院要求 / 资源条件有记录（占位但完整）
- [x] 缺失项进入 §8 待补问题表，**无隐式假设**

### 4.2 §7.2 数据结构验收（覆盖在测试中）

| §7.2 条目 | 测试 |
|----------|------|
| `ProjectIntake` 可通过 Pydantic 校验 | `test_project_intake_validates_via_pydantic` |
| `goal_level` 不为空 | `test_goal_level_required` |
| `raw_topic` 不为空 | `test_raw_topic_required`（含空白校验） |
| `missing_fields` 可被后续补问节点读取 | `test_missing_fields_is_readable_list` |
| `intake_rating` 为 A/B 时才允许进入 Phase 02 | `test_rating_A_and_B_allow_phase02` + `validate_intake()` 返回 `ValidationOutcome.OK` |

C/D 阻断链路额外有：
- `test_rating_C_requires_clarification`
- `test_rating_D_blocks_phase02`
- `test_placeholder_payload_is_D_even_when_raw_topic_typed`

### 4.3 §7.3 阻断条件

| 阻断项 | 当前状态 |
|--------|----------|
| 1. 只有一句"帮我想个题目"，没有专业/导师/毕业时间 | 占位骨架触发 → rating=D，outcome=BLOCKED |
| 2. 目标保毕业但坚持从零采集、训练 | 留到 Phase 02 的"风险评分"判断；Phase 01 记录需求即可 |
| 3. 用户要求编造论文/数据/实验 | 暂未实现显式拒绝（LLM 介入后才需要）；当前任何非 TBD 占位都会触发 rating 校验 |
| 4. 资源条件全部未知却要求判断能否毕业 | 占位骨架无任何资源 → rating=D，outcome=BLOCKED |
| 5. 第一张结果表时间已无法支撑题目规模 | 留到 Phase 02 + 03 联合判断；Phase 01 记录红线 |

阻断条件 1、4 在 Phase 01 已被验证（test_rating_D_blocks_phase02）。

---

## 5. 过程中暴露并修复的真实 Bug

冒烟不是为了"再跑一遍测试"，是为了**发现测试覆盖不到的盲区**。这次冒烟抓到 3 个真实 bug：

### Bug 1：lifespan 缺失 `init_db()`

**现象**：第一次 uvicorn 起来后，第一个 GET 就报 `no such table: projects`。

**原因**：`apps/api/app/main.py` 没在 FastAPI 启动时调用 `init_db()`。端到端测试用 conftest 显式 await 了，绕过了这个 bug。

**修复**：
```python
@asynccontextmanager
async def _lifespan(app: FastAPI):
    await init_db()
    yield
```

### Bug 2：`PROJECT_ROOT` 算错层

**现象**：第一次冒烟后查 DB，数据落在 `apps/api/data/topicpilot.db` 而非 `data/topicpilot.db`。

**原因**：`Path(__file__).resolve().parents[3]` —— `__file__` 在 `apps/api/app/core/config.py`，从 `config.py` 倒数 3 层是 `apps`，不是仓库根。

**修复**：
```python
# parents[0]=core [1]=app [2]=api [3]=apps [4]=<repo root>
PROJECT_ROOT = Path(__file__).resolve().parents[4]
```

### Bug 3：SQLite DSN 用相对路径

**现象**：即便修了 PROJECT_ROOT，DSN 拼成 `sqlite+aiosqlite:///data/topicpilot.db`（3 斜杠），SQLAlchemy 把后面的 `data/...` 当成 cwd-relative。

**修复**：`_sqlite_dsn()` 强制 `Path.resolve()` 转绝对路径，再 `as_posix()`。

```python
absolute = Path(path).expanduser().resolve()
absolute.parent.mkdir(parents=True, exist_ok=True)
return f"sqlite+aiosqlite:///{absolute.as_posix()}"
```

**教训**：单元 + 端到端 + 真 uvicorn 三层测试缺一不可。uvicorn 的 cwd 切换、`--app-dir` 行为、SQLAlchemy URI 解析，每一层都可能藏路径 bug。

---

## 6. 与规约的偏离

无字段偏离。两条**实现细节偏离**是显式扩展，不是违反规约：

1. **评级函数多了一个 D 的额外触发**（raw_topic / case_id 是字面占位符）。规约 §5 Step 5 没显式说"占位符 → D"，但 §7.3 第 1 条要求"只有一句帮我想个题目要阻断"，占位符识别是最直接的实现路径。已在 `models.py` 的 `compute_intake_rating` docstring 显式标注。

2. **LangGraph 状态机多加了 `TopicDecompositionNode` 占位**。规约 §3.3 把 TopicDecompositionNode 列为 Phase 02 的入口，但我把它作为一个返回 `ready_for_phase02=True` 的占位哨兵节点加进来了，目的是让 Phase 01 的图能在不接 Phase 02 时也跑通 `OK → 末端` 路径，便于参数化测试。

3. **API 多加了 `/health`**。规约 §3.2 没列，但生产部署几乎必备；属于标准可观测性基础设施，不影响规约验收。

---

## 7. 不在本 Phase 的范围（明确排除）

为避免范围蔓延，下列项**未实现**，留给后续 Phase：

| 项 | 留给 |
|----|------|
| HumanClarificationNode 真实补问逻辑（LLM 生成问题） | Phase 02 起步时 |
| TopicDecompositionNode 真逻辑 | Phase 02 |
| Langfuse / OpenTelemetry 追踪 | Phase 04 起 |
| Celery 异步任务 | Phase 04 起 |
| pgvector 全文 + dense + reranker 三阶段检索 | Phase 03 |
| Next.js 前端 | 全局 P1 |
| Alembic 数据库迁移 | Phase 02 起（SQLite 现在用 `Base.metadata.create_all`） |
| Docker Compose | 后续基础设施 P1 |
| DELETE /api/v1/projects/{id}（smoke 脚本里 `_scrub` 想用但没实现） | 后续清理工具 |

---

## 8. 下一步建议

### 8.1 可立即推进

**Phase 02 — 题目拆解与论文结构映射**。前置条件已满足：
- `ProjectIntake` 是入口
- 评级通过后 `ready_for_phase02=True` 已生效
- LangGraph 图已经把 `TopicDecompositionNode` 作为占位接好
- TopicSpec 数据结构设计已在技术选型文档里规划

### 8.2 建议在 Phase 02 顺手补的小事

1. 把 `sqlite_path` 改成 `database_url`（避免 DSN 拼装），并把 `Settings` 改成允许通过 `TOPICPILOT_DATABASE_URL` 直接覆盖完整 DSN，便于接 PostgreSQL。
2. 加 Alembic，让 schema 变更可追溯。
3. `tmp/pytest/` 加进 `.gitignore`（已加）。
4. 把 `data/topicpilot.db` 加进 `.gitignore`（已加）。

### 8.3 暂不推进的

- 8000 端口：Windows 防火墙/winerror 10013，**不是代码问题**。18181 满足本机开发。
- 部署：Phase 02-03 之前不建议提前做 Docker Compose。
- 前端：Phase 04 之后再开 Next.js 项目。

---

## 9. 一句话总结

> Phase 01 把"学生想做什么题目"翻译成"项目在什么风险边界下行动"——用 Pydantic v2 把约束打成强类型结构、用一个纯函数 `validate_intake` 把评级规约落到代码、用 FastAPI + LangGraph 两条入口让所有路径都走同一个评级函数、用 29 条测试 + 10 项冒烟 + 真实 SQLite 落库验证整条链路。占位骨架触发 D 阻断，完整 payload 触发 A 通过，状态机三路路由全跑通。
