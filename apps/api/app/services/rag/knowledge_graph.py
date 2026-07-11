"""Re4.5: Simple knowledge graph from RAG index.

Extracts (paper, dataset, method) triples from chunk text using regex patterns.
Returns nodes + edges in the same format as evidence_graph_builder.
"""
from __future__ import annotations

import re
from typing import Any


def build_knowledge_graph(
    index: dict[str, Any], case_id: str
) -> dict[str, Any]:
    """Build a simple knowledge graph from RAG-indexed chunks."""
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_node_ids: set[str] = set()

    def add_node(node_id: str, node_type: str, label: str) -> None:
        if node_id not in seen_node_ids:
            nodes.append({"id": node_id, "type": node_type, "label": label})
            seen_node_ids.add(node_id)

    def add_edge(from_id: str, to_id: str, label: str = "uses") -> None:
        if not any(e["from"] == from_id and e["to"] == to_id for e in edges):
            edges.append({"from": from_id, "to": to_id, "label": label})

    dataset_names = [
        "NEU-DET", "GC10-DET", "MVTec AD", "COCO", "ImageNet", "CIFAR", "MNIST",
        "Cityscapes", "nuScenes", "DOTA", "VisDrone", "UAVDT", "Waymo",
        "LIDC-IDRI", "MIMIC-CXR", "ChestX-ray14", "BRATS", "ISIC",
    ]
    method_patterns = [
        r"\b(YOLOv\d+|YOLO|SSD|Faster\s+R-CNN|Mask\s+R-CNN|ResNet|VGG|Transformer|BERT|GPT|ViT|DETR)\b",
    ]

    for doc in index.get("documents", []):
        chunk_id = doc["chunk_id"]
        text = doc.get("text", "")
        source = doc.get("source", "")

        if source:
            paper_id = f"paper:{source}"
            add_node(paper_id, "paper", source)
        else:
            paper_id = f"chunk:{chunk_id}"
            add_node(paper_id, "chunk", chunk_id)

        for ds_name in dataset_names:
            if ds_name.lower() in text.lower():
                ds_id = f"dataset:{ds_name.lower()}"
                add_node(ds_id, "dataset", ds_name)
                add_edge(paper_id, ds_id, "uses_dataset")

        for pattern in method_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                method_name = match.group(1).strip()
                method_id = f"method:{method_name.lower()}"
                add_node(method_id, "method", method_name)
                add_edge(paper_id, method_id, "uses_method")

    return {
        "case_id": case_id,
        "nodes": nodes,
        "edges": edges,
        "n_nodes": len(nodes),
        "n_edges": len(edges),
    }
