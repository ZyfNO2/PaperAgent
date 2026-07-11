"""Re4.5: Knowledge graph builder tests."""
from __future__ import annotations

from apps.api.app.services.rag.knowledge_graph import build_knowledge_graph


class TestKnowledgeGraph:
    def test_empty_index(self):
        index = {"documents": []}
        kg = build_knowledge_graph(index, "test")
        assert kg["nodes"] == []
        assert kg["edges"] == []

    def test_dataset_extraction(self):
        index = {
            "documents": [
                {
                    "chunk_id": "c0",
                    "text": "We use NEU-DET dataset for training YOLO model.",
                    "source": "arxiv:2401.00001",
                },
            ],
        }
        kg = build_knowledge_graph(index, "test")
        node_types = [n["type"] for n in kg["nodes"]]
        assert "paper" in node_types
        assert "dataset" in node_types
        assert "method" in node_types

    def test_edge_creation(self):
        index = {
            "documents": [
                {
                    "chunk_id": "c0",
                    "text": "YOLO model trained on COCO dataset.",
                    "source": "paper-1",
                },
            ],
        }
        kg = build_knowledge_graph(index, "test")
        assert len(kg["edges"]) >= 2

    def test_node_ids_unique(self):
        index = {
            "documents": [
                {"chunk_id": "c0", "text": "YOLO on NEU-DET", "source": "p1"},
                {"chunk_id": "c1", "text": "YOLO on NEU-DET again", "source": "p2"},
            ],
        }
        kg = build_knowledge_graph(index, "test")
        node_ids = [n["id"] for n in kg["nodes"]]
        assert len(node_ids) == len(set(node_ids))
