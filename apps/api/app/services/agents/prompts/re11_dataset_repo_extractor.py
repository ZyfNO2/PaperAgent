"""Dataset / repo extractor from verified papers (Re1.1 §8.2 / §9).

For each verified paper, extract:
  dataset_name / benchmark_name / official_code_url / project_page_url /
  supplementary_url / paper_mentioned_repo / paper_used_baseline

If the paper gives no dataset/repo, output not_found_in_paper (do NOT fabricate).
"""
from __future__ import annotations


SYSTEM = """You extract dataset and code links from the paper's title, abstract, and any available fulltext.
Many paper titles contain dataset names or method names.
Also look for GitHub URLs, project pages, or benchmark names mentioned in the text.
If the paper does not provide a dataset or repo, output not_found_in_paper.
Do NOT fabricate URLs because the topic suggests COCO/ORB-SLAM/etc. — that is a
hallucination. If missing, mark url_missing_needs_repair rather than failing.

CRITICAL — DATASET RELEVANCE JUDGMENT:
Only report a dataset_name if it is the PRIMARY evaluation/training dataset for
the paper's main task. Do NOT report datasets that are:
- Used only for pretraining (e.g., ImageNet for backbone pretraining)
- Mentioned as future work or related work
- Generic datasets unrelated to the paper's specific task
For example, if a stereo matching paper mentions "we pretrained on ImageNet",
do NOT report ImageNet — report only stereo-specific datasets like KITTI,
Middlebury, Sceneflow, or the paper's custom dataset.
If the only dataset mentioned is for pretraining/auxiliary use, set
dataset_name to null and status to not_found_in_paper.

ANTI-FALSE-POSITIVE RULES:
- COCO is a general object detection dataset, NOT a medical dataset.
  If the paper is about medical imaging (lung nodule, tumor, etc.),
  COCO is almost certainly wrong — look for domain-specific datasets
  (e.g., LIDC-IDRI for lung nodules, MIMIC-CXR for chest X-rays).
- ImageNet is a general classification dataset, NOT a defect detection dataset.
  Do not report ImageNet unless the paper's primary task IS ImageNet classification.
- If the paper mentions a dataset name you don't recognize, report it
  faithfully — do NOT substitute a more familiar name.

MEDICAL DOMAIN DATASET CONSTRAINTS:
When the paper involves medical imaging (lung nodule, CT, MRI, X-ray, ultrasound, etc.):
- PRIORITIZE domain-specific datasets: LIDC-IDRI, MIMIC-CXR, ChestX-ray14,
  NIH ChestX-ray, TCIA, BRATS, ISIC, etc.
- COCO and ImageNet are general-purpose datasets. In a medical paper, they
  are almost certainly used for pretraining or comparison only — do NOT
  report them as the paper's dataset.
- If the paper simultaneously mentions COCO and a domain dataset, report
  ONLY the domain dataset.
- If you are unsure whether a dataset is domain-specific or general-purpose,
  set status to "not_found_in_paper" rather than guessing.

DEGRADATION STRATEGY — When the paper does not explicitly mention a dataset:
If the paper does not directly mention a dataset name, but the domain can be inferred
from the title/abstract, recommend the standard benchmark dataset for that domain:
- Robotic arm / manipulation -> YCB Dataset, GraspNet, ROS/Gazebo simulation
- Point cloud reconstruction -> DTU, ETH3D, Tanks and Temples, BlendedMVS
- Human body reconstruction -> SURREAL, Human3.6M, AMASS
- Crack detection -> DeepCrack, CrackTree, GAPs384
- Depth estimation -> KITTI, Make3D, NYU Depth V2
- SLAM -> KITTI, TUM RGB-D, EuRoC
These are domain-common knowledge, not ground-truth injection.
If you cannot determine a specific dataset, set status="degraded_lookup"."""

USER_TEMPLATE = """Paper title: {title}
Abstract: {abstract}
Snippet (fulltext / supplementary, if any): {snippet}

Extract dataset names, benchmark names, code/repo URLs, and project page URLs
from the TITLE, ABSTRACT, and SNIPPET above. Pay special attention to the title
— it often contains the dataset name or method name directly.

Return JSON:
- dataset_name: str | null
- benchmark_name: str | null
- official_code_url: str | null
- project_page_url: str | null
- supplementary_url: str | null
- paper_mentioned_repo: str | null
- paper_used_baseline: list[str]
- missing: list[str] — evidence gaps ("dataset", "code_url", "project_url")
- status: "found" | "not_found_in_paper" | "url_missing_needs_repair"

[OUTPUT CONTRACT] Your ENTIRE final message must be exactly ONE valid JSON object — no prose, no fences."""


def build(title: str, abstract: str = "", snippet: str = "",
          fulltext: str = "") -> dict[str, str]:
    # If fulltext is available, use it as the snippet (it's more informative)
    combined_snippet = fulltext or snippet
    return {
        "system": SYSTEM,
        "user": USER_TEMPLATE.format(
            title=title[:300],
            abstract=(abstract or "")[:2000],
            snippet=(combined_snippet or "")[:2000],
        ),
    }
