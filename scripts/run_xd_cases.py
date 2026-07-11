"""Re7.2 Cross-domain test runner — submits 10 topics, waits, collects results."""
import asyncio
import json
import os
import time
from pathlib import Path

import httpx

BASE_URL = os.environ.get("PAPERAGENT_URL", "http://127.0.0.1:18182")
OUT_DIR = Path("G:/PaperAgent/artifacts/re7_5/round0")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# 10 cross-domain cases from Re7.2 SOP
CASES = [
    ("XD-01", "基于视觉 Transformer 的钢材表面缺陷检测"),
    ("XD-02", "面向无人机遥感的小目标飞机检测轻量化方法"),
    ("XD-03", "基于水声信号的船舶类型识别与跨域泛化"),
    ("XD-04", "医学影像分割模型在跨医院数据上的可信评估"),
    ("XD-05", "面向法律文本的中文长文档事实核验"),
    ("XD-06", "基于时序传感器的锂电池 SOH 预测"),
    ("XD-07", "桥梁裂缝图像检测与三维定位联合研究"),
    ("XD-08", "面向移动机器人的室内语义建图与避障"),
    ("XD-09", "利用公开转录组数据预测罕见病药物反应"),
    ("XD-10", "基于大语言模型的高校心理咨询辅助问答"),
]


async def submit_and_wait(case_id: str, topic: str):
    case_dir = OUT_DIR / case_id
    case_dir.mkdir(exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  CASE: {case_id} | TOPIC: {topic}")
    print(f"{'='*60}", flush=True)

    async with httpx.AsyncClient(timeout=15) as c:
        try:
            resp = await c.post(
                f"{BASE_URL}/api/v1/research/",
                json={"case_id": case_id, "topic": topic},
            )
            print(f"  Submit: {resp.status_code}")
            if resp.status_code >= 400:
                print(f"  Submit error: {resp.text[:200]}")
                return
        except Exception as e:
            print(f"  Submit failed: {e}")
            return

    t0 = time.time()
    final_state = None

    for i in range(200):
        await asyncio.sleep(3)
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                resp = await c.get(f"{BASE_URL}/api/v1/research/{case_id}/status")
                data = resp.json()
                st = data.get("status", "?")
                if i % 10 == 0:
                    print(f"  t={i*3}s: {st} node={data.get('current_node','?')} "
                          f"papers={data.get('n_papers','?')}")
                if st in ("done", "error"):
                    elapsed = round(time.time() - t0, 1)
                    print(f"  Done: {st} elapsed={elapsed}s papers={data.get('n_papers','?')} "
                          f"error={data.get('error','')}")

                    # Get full state
                    try:
                        async with httpx.AsyncClient(timeout=15) as c2:
                            state_resp = await c2.get(f"{BASE_URL}/api/v1/research/{case_id}/state")
                            if state_resp.status_code == 200:
                                final_state = state_resp.json()
                    except Exception as e2:
                        print(f"  State fetch failed: {e2}")

                    break
        except Exception as e:
            print(f"  Status poll failed: {e}")
            await asyncio.sleep(5)

    # Save results
    result = {
        "case_id": case_id,
        "topic": topic,
        "status": final_state.get("status") if final_state else "unknown",
        "elapsed_s": round(time.time() - t0, 1),
        "n_papers": final_state.get("verified_papers", []) if final_state else [],
        "n_paper_count": len(final_state.get("verified_papers", [])) if final_state else 0,
        "n_baselines": len(final_state.get("baseline_candidates", [])) if final_state else 0,
        "feasibility_verdict": final_state.get("feasibility_report", {}).get("verdict", "") if final_state else "",
        "final_recommendation": final_state.get("final_recommendation", "") if final_state else "",
        "innovation_points_count": len(final_state.get("innovation_points", [])) if final_state else 0,
        "novelty_review_verdict": final_state.get("novelty_review_verdict", "") if final_state else "",
        "errors": final_state.get("errors", []) if final_state else [],
    }

    with open(case_dir / "result.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    print(f"  Result saved to {case_dir / 'result.json'}")


async def main():
    print(f"Base URL: {BASE_URL}")
    print(f"Output: {OUT_DIR}")

    for case_id, topic in CASES:
        await submit_and_wait(case_id, topic)
        await asyncio.sleep(2)

    print("\nAll 10 cases complete.")


if __name__ == "__main__":
    asyncio.run(main())
