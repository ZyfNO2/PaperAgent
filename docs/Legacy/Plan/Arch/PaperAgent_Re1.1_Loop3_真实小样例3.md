### steel（baseline 缺口，low_bar blocked）

仅 1 包留下：baseline = 「Faster Metallic Surface Defect Detection Using Deep Learning with Channel Shuffling」；risk = 「深度可分离卷积可能降低特征提取能力」。evidence_audit 缺口：建议加入 1 篇 **YOLOv5-on-NEU-DET baseline** 论文并做 `dataset_name_targeted_search: NEU-DET`。

### medical（score pass，baseline 弱）

5 packages 都直接挂 `baseline=<已 accept paper>`，但全部 6 篇 accept 论文都归 parallel；evidence_audit 显式要求「具体的大语言模型 baseline 实现细节（如 GPT-4, Med-PaLM 等）」— 最诚实的待修项。

## 附录 B — Paper-Repo-Dataset 关系网（最小，SOP §5.5）

| case | paper | role | linked_repo | linked_dataset | relation_confidence | missing_links |
| --- | --- | --- | --- | --- | --- | --- |
| steel | Faster Metallic Surface Defect Detection Using Deep Learning with Channel Shuffling | parallel | — | NEU-DET, GC10-DET (url_missing_needs_repair) | 中 | repo 缺 |
| steel | STS-YOLO … | parallel | — | GC10-DET | 中 | repo 缺 |
| steel | An Improved YOLOv5 … | parallel | — | NEU-DET | 中 | repo 缺 |
| steel | Real-Time Detection … | parallel | — | GC10-DET | 中 | dataset url_missing / repo 缺 |
| slam | Kimera … | baseline | MIT-SPARK/Kimera | — | 高（官方库反查命中）| dataset 需从 README 补 |
| slam | SoCubeSLAM … | baseline | SoCubeSLAM/SoCubeSLAM | TUM RGB-D, KITTI, EuRoC MAV, SOCO | 高（官方库反查命中）| project_url |
| slam | Semantic Visual SLAM … Survey | survey | — | — | 中 | repo+dataset 皆缺 |
| slam | Evaluating the Impact … | parallel | — | — | 中（url_missing）| repo 缺 |
| slam | Real-Time Monocular Object-Model Aware Sparse … | parallel | — | — | 中 | repo 缺 |
| medical | Uncertainty Estimation … | parallel | — | — | 中 | repo 缺 |
| medical | MedHallu … | parallel | — | — | 中 | repo 缺 |
| medical | Self-MedRAG … | parallel | github.com/HealthCatalyst/self-medrag | MedQuAD, PubMedQA, MedMCQA | 中 | repo URL 待人工验证 |
| medical | RGAR … | parallel | — | — | 中-低 | repo 缺 |

> 所有 repo/dataset `url` 均由 `re11_dataset_repo_extractor` 从论文项目页反查产生，`found` 状态 URL 为 extractor 自主推断；本报告未对其做任何人工补强，提醒后续 human_gate 与人工审验时应明确标注置信度。