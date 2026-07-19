from __future__ import annotations

import argparse
import json
import tempfile
import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from paperagent.api import create_app
from paperagent.demo import DemoTaskExecutor
from paperagent.plugins import MethodPlan, audit_method_plan

ROOT = Path(__file__).resolve().parents[1]
TERMINAL = {"succeeded", "failed", "cancelled"}


def _request_payload() -> dict[str, Any]:
    path = ROOT / "examples" / "interview" / "task-request.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _wait_for_terminal(client: TestClient, task_id: str) -> dict[str, Any]:
    for _ in range(200):
        response = client.get(f"/v1/tasks/{task_id}")
        response.raise_for_status()
        payload = response.json()
        if payload["status"] in TERMINAL:
            return payload
        time.sleep(0.01)
    raise RuntimeError("demo task did not reach a terminal state")


def run_demo(database: Path) -> dict[str, Any]:
    app = create_app(
        executor=DemoTaskExecutor(delay_seconds=0),
        database_path=database,
        sse_poll_seconds=0.01,
        sse_heartbeat_seconds=0.1,
    )
    request_payload = _request_payload()
    idempotency_key = "interview-demo-001"

    with TestClient(app) as client:
        first = client.post(
            "/v1/tasks",
            headers={"Idempotency-Key": idempotency_key},
            json=request_payload,
        )
        first.raise_for_status()
        task_id = first.json()["task_id"]

        duplicate = client.post(
            "/v1/tasks",
            headers={"Idempotency-Key": idempotency_key},
            json=request_payload,
        )
        duplicate.raise_for_status()

        conflicting_payload = json.loads(json.dumps(request_payload))
        conflicting_payload["request"]["question"] = "A different request must conflict."
        conflict = client.post(
            "/v1/tasks",
            headers={"Idempotency-Key": idempotency_key},
            json=conflicting_payload,
        )

        terminal = _wait_for_terminal(client, task_id)
        event_page = client.get(f"/v1/tasks/{task_id}/events", params={"limit": 100})
        event_page.raise_for_status()
        events = event_page.json()["events"]

        papers_response = client.get(f"/v1/tasks/{task_id}/papers")
        papers_response.raise_for_status()
        papers = papers_response.json()["items"]
        accepted_paper = next(item for item in papers if item["verification_status"] == "accepted")
        review = client.put(
            f"/v1/tasks/{task_id}/papers/{accepted_paper['paper_id']}/review",
            json={
                "decision": "accepted",
                "favorite": True,
                "expected_version": accepted_paper["review_version"],
            },
        )
        review.raise_for_status()

        exported = client.get(
            f"/v1/tasks/{task_id}/exports/json",
            params={"selection": "accepted"},
        )
        exported.raise_for_status()
        diagnostics = client.get("/v1/diagnostics/runtime")
        diagnostics.raise_for_status()
        metrics = client.get("/metrics")
        metrics.raise_for_status()

    plan_path = ROOT / "examples" / "v0_8" / "go-plan.json"
    plan = MethodPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
    audit = audit_method_plan(plan)
    return {
        "task_id": task_id,
        "idempotency_reused": duplicate.json()["reused"] is True,
        "idempotency_conflict_rejected": conflict.status_code == 409,
        "task_terminal": terminal["status"],
        "event_count": len(events),
        "event_types": [event["event_type"] for event in events],
        "review_created": review.json()["decision"] == "accepted",
        "export_created": bool(exported.headers.get("X-PaperAgent-SHA256")),
        "export_item_count": int(exported.headers["X-PaperAgent-Item-Count"]),
        "plugin_verdict": audit.verdict.value,
        "schema_version": diagnostics.json()["database"]["schema"]["current_version"],
        "metrics_exposed": "paperagent_tasks_total" in metrics.text,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the deterministic PaperAgent interview demo")
    parser.add_argument("--database", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    if args.database is None:
        with tempfile.TemporaryDirectory(prefix="paperagent-interview-") as directory:
            summary = run_demo(Path(directory) / "paperagent.db")
    else:
        summary = run_demo(args.database)

    rendered = json.dumps(summary, indent=2, sort_keys=True)
    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
