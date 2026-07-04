# 阶段执行三条铁律（写于 S66v / Re10 迭代，从用户多次反馈固化）

> 这三条规则跟 `session66-66v-rewrite.md` 同样自动加载。任何 Re0X、Re10+ 、
> 任何 batch / validator / smoke 的阶段工作都必须遵守。

## 0. 多并发：长 batch 必须开并行 subagent

**触发条件**：单 batch 任务预计 ≥ 15 分钟（如 Balanced40、100-case 全量、
Continuous validator 跑过夜、机器学习训练）。

**必须**：

- 把 batch 切成 ≤4 个 subagent，每个负责独立子集（不重叠 ID）写独立 out-dir
  （`<out_dir>_subX`）。例如：
  ```bash
  # 4 subagents × 10 cases each
  for i in 0 1 2 3; do
    start=$((i * 10 + 1))
    end=$((start + 9))
    sed -n "${start},${end}p" ids.txt > ids_sub${i}.txt &
  done
  wait
  python merge_summaries.py re10_fix2_balanced40_sub* > re10_fix2_balanced40/
  ```
- 主 session 只 poll 进度，**永远不阻塞** 等长任务结束。

**绝对禁止**：在 main session 里跑 `python ... && sleep 1800 && python ...`
（80 分钟空跑，浪费 context window）。

## 1. 小迭代：修完跑全量前先小量测验

**触发条件**：改了 reflection loop、validator、agent prompt、熔断、
verify 等核心代码。

**必须**：

- 先用 `python scripts/run_balanced40_reflection_re10.py
  --raw-topics "<fail1>||<fail2>"` 单跑 fail cases（小量测试）。
- 小量过 → 再跑全量。
- 小量不过 → 继续修，**绝不**跳到全量。

**目的**：避免一个 P0 修复把原本 pass 的 39 case 搞回 fail。
每一轮迭代必须隔离副作用。

## 2. 自查：全量 95% 后必须 audit fail 列表

**触发条件**：Re0X Balanced40 / 大 batch 拿到 `pass+weak ≥ 95%`。

**必须**：

- 派一个 audit subagent 读所有 `fail / blocked_tooling / weak` cases 的
  trace JSON。
- 输出 ranked root-cause list（不是症状清单）。
- 对每个 root cause：定点修复 → **只测失败 case** → 再全量 reval。
- 重复迭代直到 fail list 清零或 3 轮内收敛。
- **最终报告里写明 iteration count** + 每轮修了什么。

**绝对禁止**：95% pass 就交报告。剩余 5% 必须处理。

## 这三条的关系

```
并发 ──► 小迭代 ──► 自查 ──► 全量 ──► 全量复算
   │           │         │
   │           │         └─► 出 95% → audit → iter → 收敛
   │           └─► 只测 fail, 不全量
   └─► ≥15 min batch 必须 split
```

**memory 链接**：`feedback_parallelize_with_subagents_by_default`、
`feedback_parallelize_large_batches`、`feedback_iterate_from_audit`。
