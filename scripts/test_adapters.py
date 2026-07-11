"""Direct adapter test."""
import asyncio, sys
sys.path.insert(0, "G:/PaperAgent")

async def main():
    from apps.api.app.services.retrieval.adapters.semantic_scholar_search import semantic_scholar_search
    r = await semantic_scholar_search(["object detection steel defect"], top_k=3)
    print(f"S2: {len(r)} results")
    for h in r[:3]:
        print(f"  {h.get('title', '')[:100]}")

    from apps.api.app.services.retrieval.adapters.openalex_search import openalex_search
    r2 = await openalex_search(["object detection steel defect"], top_k=3)
    print(f"OpenAlex: {len(r2)} results")
    for h in r2[:3]:
        print(f"  {h.get('title', '')[:100]}")

asyncio.run(main())
