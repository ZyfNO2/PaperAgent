"""Re6.5 Robustness Lab — L0 emulator config tests."""
from __future__ import annotations

import pytest


class TestEmulatorConfig:
    def test_valid_baseline_emulator(self):
        from apps.api.app.services.router.emulators import EmulatorConfig
        cfg = EmulatorConfig(
            emulator_id="t1", label="test",
            response_shape="openai-json", status_code=200,
            response_template={"ok": True},
        )
        assert cfg.emulator_id == "t1"
        assert cfg.response_shape == "openai-json"

    def test_core_emulators_valid(self):
        from apps.api.app.services.router.emulators import CORE_EMULATORS
        assert len(CORE_EMULATORS) == 4
        for em in CORE_EMULATORS:
            assert em.emulator_id
            assert em.label

    def test_all_emulators_valid(self):
        from apps.api.app.services.router.emulators import ALL_EMULATORS
        assert len(ALL_EMULATORS) == 12
        shapes = {em.response_shape for em in ALL_EMULATORS}
        assert "openai-json" in shapes
        assert "all-fallback-fail" in shapes


class TestRunManifest:
    def test_valid_manifest(self):
        from apps.api.app.services.router.emulators import RunManifest
        m = RunManifest(
            run_id="run-001", test_level="L2",
            total_cases=10, passed=8, failed=1, degraded=1,
            conclusion="8/10 pass, 1 degraded on malformed",
        )
        assert m.run_id == "run-001"
        assert m.test_level == "L2"
