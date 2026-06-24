"""Session 51: 从测试集 markdown 生成 thesis_eval 数据文件。

读 docs/PaperAgent_工科学位论文爬取测试集_100篇.md 的 100 篇表格，
生成 data/thesis_eval/ 下的 thesis_seed_100.jsonl / smoke_20.txt /
labels/experiment_need_labels.json / labels/difficulty_labels.json。

gold 真值由 experiment_need 文本启发式映射得到（对齐
Plan/design/Session51_测试集方案设计与验收标准.md §7）。

幂等：重复运行覆盖输出。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_MD = ROOT / "docs" / "PaperAgent_工科学位论文爬取测试集_100篇.md"
OUT_DIR = ROOT / "data" / "thesis_eval"
LABELS_DIR = OUT_DIR / "labels"

DOMAINS = [
    "三维视觉/SLAM/点云", "土木/交通基础设施损伤检测", "工业缺陷检测/机器视觉",
    "自动驾驶/交通感知", "电力/轨交巡检视觉", "工科AI/计算机视觉",
    "机器人/机械臂实验系统", "遥感/无人机目标检测", "能源装备/故障诊断",
    "医学/人体三维视觉",
]

SMOKE_20 = [
    "015", "016", "018", "024", "027", "028", "032", "033", "043", "046",
    "050", "063", "066", "074", "075", "080", "091", "092", "093", "096",
]


def _domain_set(title: str) -> str | None:
    for d in DOMAINS:
        if d in title:
            return d
    return None


def map_gold(need_text: str, difficulty: str, cycle: str, repeatability: str,
             domain: str, title: str) -> dict:
    """从 experiment_need 文本 + 元信息映射 gold 多标签。

    规则对齐验收标准 §7。保守宁可漏标不要错标高风险。
    """
    t = (need_text or "") + " " + (title or "")
    tl = t.lower()

    compute_need: list[str] = []
    data_need: list[str] = []
    hardware_need: list[str] = []

    # ---- compute_need ----
    if "scada" in tl or "传感器" in t or "实验台" in t or "材料" in t or "防冰" in t \
            or "传统" in t or "可靠性" in t or "电动云台" in t:
        compute_need.append("cpu_or_light_gpu_ok")
    elif "单卡" in t or ("yolo" in tl) or ("u-net" in tl or "unet" in tl) \
            or "faster r-cnn" in tl or "mask r-cnn" in tl or "gan" in tl \
            or "retinanet" in tl or "分割" in t:
        if "大模型" in t or "完整三维链路" in t or "较强gpu" in t or "大规模" in t:
            compute_need.append("large_gpu_optional")
        else:
            compute_need.append("single_gpu_ok")
    elif "三维" in t or "点云" in t or "多模态" in t or "slam" in tl:
        compute_need.append("large_gpu_optional")
    elif "大模型" in t or "完整三维链路" in t or "较强gpu" in t or "大规模" in t:
        compute_need.append("large_gpu_optional")
    else:
        compute_need.append("single_gpu_ok")

    # ---- data_need ----
    if "公开" in t and ("数据集" in t or "数据" in t):
        data_need.append("public_dataset_available")
    if "自采" in t or "自建" in t or "真实数据多需" in t or "现场" in t or "企业" in t \
            or "缺陷样本采集" in t:
        data_need.append("self_collected_dataset")
    if "医疗" in t or "医学" in t or "人体" in t or "合规" in t or "数据权限" in t \
            or domain == "医学/人体三维视觉" or "scada" in tl:
        data_need.append("domain_data_permission_risk")
    if "类别不均衡" in t or "大量标注" in t or "标注" in t:
        data_need.append("annotation_heavy")
    if not data_need:
        # 默认保守：能从公开数据起步
        data_need.append("public_dataset_available")

    # ---- hardware_need ----
    hw_words = ["机械臂", "机器人", "相机", "jetson", "结构光", "lidar", "雷达",
                "zed", "ros", "云台", "双目", "深度相机", "rgb-d", "rgb"]
    if any(w in tl or w in t for w in hw_words) and "算法训练单卡" in t:
        # 巡检/双目等若只做识别不强制硬件，但测试集强调硬件是主风险
        if any(w in t for w in ["机械臂", "机器人", "云台", "结构光", "深度相机", "zed"]):
            hardware_need.append("hardware_platform_required")
        elif domain == "机器人/机械臂实验系统":
            hardware_need.append("hardware_platform_required")
    if domain == "机器人/机械臂实验系统":
        if "hardware_platform_required" not in hardware_need:
            hardware_need.append("hardware_platform_required")

    return {
        "compute_need": compute_need,
        "data_need": data_need,
        "hardware_need": hardware_need,
        "difficulty": difficulty,
        "cycle": cycle,
        "repeatability": repeatability,
    }


def parse_rows() -> list[dict]:
    """解析 markdown 表格 100 行（逐行按 | 切分，稳健处理含 / 的单元格）。"""
    text = SRC_MD.read_text(encoding="utf-8")
    rows: list[dict] = []
    url_re = re.compile(r"\((https?://[^)]+)\)")
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("| ENG-THESIS-"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 10:
            continue
        tid, title, year, domain, link_cell, need, diff, cycle, repeat = cells[:9]
        testpt = "|".join(cells[9:])  # 测试点可能含 |
        m = url_re.search(link_cell)
        if not m:
            continue
        url = m.group(1)
        domain = domain.strip()
        if domain not in DOMAINS:
            domain = _domain_set(title) or domain
        try:
            year_i = int(year)
        except ValueError:
            continue
        rows.append({
            "id": tid,
            "title": title,
            "year": year_i,
            "source_url": url,
            "domain": domain,
            "experiment_need": need,
            "difficulty": diff.strip(),
            "cycle": cycle.strip(),
            "repeatability": repeat.strip(),
            "paperagent_test": testpt.strip(),
        })
    return rows


def main() -> None:
    rows = parse_rows()
    assert len(rows) == 100, f"expected 100 rows, got {len(rows)}"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LABELS_DIR.mkdir(parents=True, exist_ok=True)

    jsonl_path = OUT_DIR / "thesis_seed_100.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as f:
        for r in rows:
            gold = map_gold(r["experiment_need"], r["difficulty"], r["cycle"],
                            r["repeatability"], r["domain"], r["title"])
            rec = {
                "id": r["id"],
                "title": r["title"],
                "year": r["year"],
                "source_url": r["source_url"],
                "domain": r["domain"],
                "experiment_need": r["experiment_need"],
                "difficulty": r["difficulty"],
                "cycle": r["cycle"],
                "repeatability": r["repeatability"],
                "paperagent_test": r["paperagent_test"],
                "gold": gold,
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # smoke_20
    (OUT_DIR / "smoke_20.txt").write_text(
        "\n".join(f"ENG-THESIS-{n}" for n in SMOKE_20) + "\n", encoding="utf-8"
    )

    # labels
    need_labels: dict[str, list[str]] = {}
    diff_labels: dict[str, dict] = {}
    for r in rows:
        gold = map_gold(r["experiment_need"], r["difficulty"], r["cycle"],
                        r["repeatability"], r["domain"], r["title"])
        need_labels[r["id"]] = sorted(set(gold["compute_need"] + gold["data_need"] + gold["hardware_need"]))
        diff_labels[r["id"]] = {
            "difficulty": gold["difficulty"],
            "cycle": gold["cycle"],
            "repeatability": gold["repeatability"],
        }
    (LABELS_DIR / "experiment_need_labels.json").write_text(
        json.dumps(need_labels, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (LABELS_DIR / "difficulty_labels.json").write_text(
        json.dumps(diff_labels, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 分布统计
    dom_count: dict[str, int] = {}
    diff_count: dict[str, int] = {}
    for r in rows:
        dom_count[r["domain"]] = dom_count.get(r["domain"], 0) + 1
        diff_count[r["difficulty"]] = diff_count.get(r["difficulty"], 0) + 1
    print(f"rows: {len(rows)}")
    print(f"domain distribution: {json.dumps(dom_count, ensure_ascii=False)}")
    print(f"difficulty distribution: {json.dumps(diff_count, ensure_ascii=False)}")
    print(f"smoke_20: {len(SMOKE_20)} ids")
    print(f"written: {jsonl_path}")


if __name__ == "__main__":
    main()
