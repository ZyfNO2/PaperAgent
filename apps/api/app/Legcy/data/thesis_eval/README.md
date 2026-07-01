# thesis_eval 测试集

> 100 篇工科学位论文题录样本，用于 PaperAgent 选题可行性评估闭环回归测试。
> 来源：`docs/PaperAgent_工科学位论文爬取测试集_100篇.md`
> 方案：`Plan/design/Session51_测试集方案设计与验收标准.md`
> SOP：`Plan/PaperAgent_Session51_工科学位论文爬取测试集与可行性评估闭环_SOP.md`

## 文件结构

```text
data/thesis_eval/
├── thesis_seed_100.jsonl           # 100 条题录 + gold 真值
├── smoke_20.txt                    # 20 个 smoke_test id
├── labels/
│   ├── experiment_need_labels.json # 多标签真值（id -> 标签列表）
│   └── difficulty_labels.json      # 难度周期真值（id -> {difficulty,cycle,repeatability}）
└── outputs/                        # 评估跑批输出
```

## JSONL schema

```json
{
  "id": "ENG-THESIS-001",
  "title": "...",
  "year": 2021,
  "source_url": "https://cdmd.cnki.com.cn/...",
  "domain": "机器人/机械臂实验系统",
  "experiment_need": "...",
  "difficulty": "高",
  "cycle": "1–3周/轮",
  "repeatability": "1–3轮",
  "paperagent_test": "...",
  "gold": {
    "compute_need": ["single_gpu_ok"],
    "data_need": ["public_dataset_available"],
    "hardware_need": ["hardware_platform_required"],
    "difficulty": "高",
    "cycle": "1–3周/轮",
    "repeatability": "1–3轮"
  }
}
```

## 样本分布

领域（10 类）：三维视觉/SLAM/点云 19、土木 16、工业缺陷 15、自动驾驶 13、电力 10、工科AI 9、机器人 7、遥感 5、能源 4、医学 2。

难度：中 46、中-高 26、低-中 16、高 12。

## 子集

- `smoke_20`：20 条快速验证（含高风险 + 低风险混合，不只 YOLO）。
- `regression_60`：常规回归（剩余 60 条）。
- `hard_20`：高风险专项（高 + 中-高 子集）。

## 重建

```bash
.venv/Scripts/python.exe scripts/build_thesis_eval_dataset.py
```

幂等，重复运行覆盖输出。gold 真值由 `experiment_need` 文本启发式映射（规则见方案文档 §7）。

## 注意

- 链接是题录入口，不代表全文开放；受限内容保留链接 + 题录级证据，提醒用户手动上传 PDF（走 Session 46 论文库）。
- H100 不是默认需求；硕士工程多用单卡，真正风险是数据和硬件。
