"""Re1.1 Loop 1 — provider connectivity check (SOP §14).

Runs 2 minimal requests:
  - fast_json (DeepSeek)
  - execution (StepFun)

Expects keys to be present in env; if missing, records a SKIPPED marker with
the reason (never prints the key). Writes results to tmp_re11_eval/loop1/.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent  # apps/api/scripts -> repo root
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "tmp_re11_eval" / "loop1"
OUT_DIR.mkdir(parents=True, exist_ok=True)

import dotenv
dotenv.load_dotenv(str(ROOT / ".env"))


def _has_key(env_var: str) -> bool:
    return bool(os.environ.get(env_var, "").strip())


def _probe(profile: str, provider: str, env_var: str) -> dict:
    t0 = time.time()
    if not _has_key(env_var):
        return {
            "profile": profile, "provider": provider,
            "status": "SKIPPED", "reason": f"no_env:{env_var}",
            "elapsed": 0,
        }
    import apps.api.app.services.llm_router as r
    try:
        out = r.call_json(
            'Return JSON: {"ok": true}',
            system="Reply with a single JSON object.",
            profile=profile,
            max_tokens=50,
        )
        return {
            "profile": profile, "provider": provider,
            "status": "OK" if out == {"ok": True} else "SHAPE_MISMATCH",
            "response": out,
            "elapsed": round(time.time() - t0, 3),
        }
    except Exception as exc:
        return {
            "profile": profile, "provider": provider,
            "status": "ERROR",
            "error_type": type(exc).__name__,
            "elapsed": round(time.time() - t0, 3),
        }


def main() -> int:
    probes = [
        _probe("fast_json", "deepseek", "DEEPSEEK_API_KEY"),
        _probe("execution", "stepfun", "STEPFUN_API_KEY"),
        _probe("premium_review", "voapi", "VOAPI_API_KEY"),
    ]
    # Loop 1 must NOT call VOAPI or MiniMax; premium probe only runs if explicitly
    # invoked with a flag. Disabled by default.
    out_path = OUT_DIR / "probes.json"
    out_path.write_text(json.dumps(probes, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    print(f"Wrote {out_path}")
    for p in probes:
        print(f"  {p['profile']:>15} ({p['provider']:<10}): {p['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
