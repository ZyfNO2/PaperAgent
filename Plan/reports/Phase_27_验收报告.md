# Session 27 验收报告 — RunEvent JSONL 持久化 + StreamClient

## 产物清单

### 新增文件
| 文件 | 说明 |
|------|------|
| `apps/api/app/schemas_run_event.py` | RunEvent / RunState / RunCreateRequest 等 Pydantic schemas |
| `apps/api/app/services/run_event.py` | JSONL 持久化服务：create_run, append_event, get_events, resume, complete |
| `apps/web/stream_client.js` | 前端 StreamClient：createRun, consumeNDJSON, consumeSSE, replayRun, resumeRun, isReady |
| `apps/api/tests/test_session27_run_event.py` | 17 个后端测试 |
| `apps/web/e2e/test_one_topic_session27_stream_client.py` | 8 个 Playwright e2e 测试 |
| `pytest.ini` | 新增 `addopts = --basetemp` 修复 Windows tmp_path 权限问题 |

### 修改文件
| 文件 | 说明 |
|------|------|
| `apps/web/index.html` | 添加 `<script src="stream_client.js">` |

## 测试结果

| 类型 | 通过 | 总数 | 状态 |
|------|------|------|------|
| 后端 pytest | 17 | 17 | ✅ 全绿 |
| Playwright e2e | 8 | 8 | ✅ 全绿 |
| 全量回归 | 344 | 345 (1 skip) | ✅ 无回退 |

## 关键设计决策

1. **JSONL 事件流**：每个 run 一个目录，events.jsonl 追加写入，state.json 存聚合状态
2. **seq 自增**：event_id = `evt_{run_id}_{seq:04d}`，seq 从 events.jsonl 行数推导
3. **RunStatus 状态机**：pending → running → completed/failed/aborted
4. **用户补丁**：user_patches.jsonl 记录用户覆盖，user_patch_count 在 RunState 中聚合
5. **恢复策略**：replay（从头重放）、continue（继续）、branch（分支）
6. **Windows tmp_path 修复**：pytest.ini 添加 `--basetemp=G:/PaperAgent/tmp/pytest`

## Bug 修复

- **tmp_path PermissionError**：Windows 上 `C:\Users\...\AppData\Local\Temp\pytest-of-ZYF` 权限拒绝 → 通过 pytest.ini `--basetemp` 重定向到项目目录
