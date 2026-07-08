"""Debug: call retrieve node directly to see exact errors."""
import asyncio
from dotenv import load_dotenv
load_dotenv("G:/PaperAgent/.env", override=True)

from apps.api.app.services.agents.graph.nodes.retrieve import _run_direct_adapter_retrieval

atoms = {
    "method": ["deep learning", "convolutional neural network", "U-Net"],
    "object": ["medical image segmentation"],
    "dataset_terms": [],
}

result = asyncio.run(_run_direct_adapter_retrieval("基于深度学习的医学图像分割研究", atoms))
raw = result.get("raw", {})
failed = result.get("failed_adapters", [])
print(f"raw: { {k: len(v) for k, v in raw.items()} }")
print(f"failed_adapters: {failed}")
for tool, hits in raw.items():
    if hits:
        print(f"\n{tool} ({len(hits)} hits):")
        for h in hits[:2]:
            title = h.get("title") or h.get("full_name") or h.get("name") or ""
            print(f"  - {title[:80]}")
