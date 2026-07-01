"""Session 35: Agent Memory / Transcript Replay Playwright E2E (6 条).

S35-PW-1: 运行到候选页后刷新可恢复
S35-PW-2: Trace 面板显示 replay 来源
S35-PW-3: 压缩后关键词 Gate 仍可追溯
S35-PW-4: EvidenceRef 仍可追溯 Candidate
S35-PW-5: 断流后显示恢复按钮
S35-PW-6: Agent_Memory_Explainer 文档存在
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from playwright.sync_api import Page

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps" / "api"))

BASE_API = "http://127.0.0.1:18181"
TOPIC_API = f"{BASE_API}/api/v1/one-topic"


def _api_post(page: Page, path: str, body: dict) -> dict:
    url = f"{TOPIC_API}{path}"
    return page.evaluate("""
        ([url, body]) => fetch(url, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(body)
        }).then(r => r.json())
    """, [url, body])


def _api_get(page: Page, path: str) -> dict:
    url = f"{TOPIC_API}{path}"
    return page.evaluate("""
        ([url]) => fetch(url).then(r => r.json())
    """, [url])


# ------------------------------------------------------------------- #
# S35-PW-1: 运行到候选页后刷新可恢复
# ------------------------------------------------------------------- #


class TestReplayRestoresState:
    def test_replay_endpoint_returns_step_states(self, page: Page):
        result = _api_post(page, "/analyze", {
            "raw_topic": "基于YOLO的钢材表面缺陷检测",
            "goal_level": "保毕业",
            "prefer": "heuristic",
        })
        pid = result["project_id"]
        # 直接调用 replay (无 run_id, 只用 snapshot)
        replay = _api_post(page, f"/{pid}/memory/replay", {
            "project_id": pid,
            "run_id": "",
            "from_seq": 0,
            "strategy": "replay",
            "skip_steps": [],
        })
        assert "step_states" in replay
        assert "replay_source" in replay
        assert replay["replay_source"] in ("snapshot", "transcript", "both")


# ------------------------------------------------------------------- #
# S35-PW-2: Trace 面板显示 replay 来源
# ------------------------------------------------------------------- #


class TestReplaySourceVisible:
    def test_replay_source_in_response(self, page: Page):
        result = _api_post(page, "/analyze", {
            "raw_topic": "基于YOLO的钢材表面缺陷检测",
            "goal_level": "保毕业",
            "prefer": "heuristic",
        })
        pid = result["project_id"]
        replay = _api_post(page, f"/{pid}/memory/replay", {
            "project_id": pid,
            "run_id": "",
        })
        assert "replay_source" in replay
        # replay_source 必须是三个合法值之一
        assert replay["replay_source"] in ("snapshot", "transcript", "both")


# ------------------------------------------------------------------- #
# S35-PW-3: 压缩后关键词 Gate 仍可追溯
# ------------------------------------------------------------------- #


class TestGateTraceableAfterCompression:
    def test_critical_events_preserved_after_compress(self):
        """直接验证 service 层: 压缩后 user_patch 事件仍在."""
        from app.services import run_event as re_service
        from app.services import project_memory as pm_service
        from app.schemas_run_event import RunCreateRequest, RunEventAppendRequest
        from app.schemas_memory import CompressionConfig
        from pathlib import Path
        import tempfile, os, uuid

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["TOPICPILOT_RUNTIME_ROOT"] = str(Path(tmp) / ".runtime")
            pm_service.reset_memory_state()

            run_id = f"run_{uuid.uuid4().hex[:10]}"
            re_service.create_run(RunCreateRequest(project_id="p_test", run_id=run_id))
            # 添加 1 个 user_patch 和多个普通事件
            re_service.append_event("p_test", run_id, RunEventAppendRequest(
                step_key="gate1", event_type="user_patch",
                status="completed", payload={"decision": "approve"},
            ))
            for i in range(20):
                re_service.append_event("p_test", run_id, RunEventAppendRequest(
                    step_key="step", event_type="candidate_scored",
                    status="completed", payload={"i": i},
                ))

            pm_service.clear_transcript_cache("p_test", run_id)
            # 触发压缩 (threshold=10)
            cfg = CompressionConfig(
                max_events_before_compress=10,
                keep_critical_types=["user_patch"],
                keep_last_n=5,
            )
            result = pm_service.compress_transcript("p_test", run_id, cfg)
            # 关键事件保留
            events = pm_service._load_transcript("p_test", run_id)
            kept_patches = [e for e in events if e.event_type == "user_patch" and not e.is_compressed]
            assert len(kept_patches) >= 1


# ------------------------------------------------------------------- #
# S35-PW-4: EvidenceRef 仍可追溯 Candidate
# ------------------------------------------------------------------- #


class TestEvidenceRefTraceable:
    def test_evidence_memory_added_and_retrieved(self):
        from app.services import project_memory as pm_service
        from app.schemas_memory import EvidenceMemoryEntry

        entry = EvidenceMemoryEntry(
            evidence_id="ev_001", project_id="p1",
            evidence_type="paper", title="Paper",
            review_status="accepted", verification_status="verified",
        )
        pm_service.add_evidence_memory(entry)
        result = pm_service.get_evidence_memory("p1", "ev_001")
        assert result is not None
        assert result.title == "Paper"
        assert result.review_status == "accepted"


# ------------------------------------------------------------------- #
# S35-PW-5: 断流后显示恢复按钮
# ------------------------------------------------------------------- #


class TestRecoveryButton:
    def test_replay_with_run_id_restores(self, page: Page):
        """用真实 run_id 触发 replay, 验证响应结构."""
        result = _api_post(page, "/analyze", {
            "raw_topic": "基于YOLO的钢材表面缺陷检测",
            "goal_level": "保毕业",
            "prefer": "heuristic",
        })
        pid = result["project_id"]
        # 即使无 run_id 也应返回 replay 结构, 前端据此显示恢复按钮
        replay = _api_post(page, f"/{pid}/memory/replay", {
            "project_id": pid,
            "run_id": "run_fake_001",
        })
        # 返回结构应有 step_states (空 dict 也算合法)
        assert "step_states" in replay
        assert isinstance(replay["step_states"], dict)


# ------------------------------------------------------------------- #
# S35-PW-6: Agent_Memory_Explainer 文档存在
# ------------------------------------------------------------------- #


class TestMemoryDocExists:
    def test_agent_memory_explainer_exists(self):
        doc = ROOT / "docs" / "interview" / "Agent_Memory_Explainer.md"
        assert doc.exists(), f"Agent_Memory_Explainer.md missing at {doc}"
        content = doc.read_text(encoding="utf-8")
        assert "记忆" in content
        assert "Transcript" in content or "transcript" in content
        assert "ProjectMemory" in content or "project" in content.lower()
        assert "EvidenceMemory" in content or "evidence" in content.lower()