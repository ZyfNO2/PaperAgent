from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from paperagent.cli import main
from paperagent.demo import DemoTaskExecutor


def test_real_executor_requires_model_and_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PAPERAGENT_LLM_MODEL", raising=False)
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)

    with pytest.raises(SystemExit) as exc_info:
        main(["serve", "--executor", "real"])

    assert exc_info.value.code == 2


def test_real_executor_cli_builds_validated_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    captured: dict[str, Any] = {}

    def fake_build(config: Any, *, literature_settings: Any) -> DemoTaskExecutor:
        captured["config"] = config
        captured["literature_settings"] = literature_settings
        return DemoTaskExecutor(delay_seconds=0)

    def fake_run(app: Any, *, host: str, port: int, log_level: str) -> None:
        captured.update(app=app, host=host, port=port, log_level=log_level)

    monkeypatch.setenv("MISTRAL_API_KEY", "top-secret")
    monkeypatch.setenv("PAPERAGENT_CONTACT_EMAIL", "operator@example.com")
    monkeypatch.setattr("paperagent.cli.build_real_task_executor", fake_build)
    monkeypatch.setattr("paperagent.cli.uvicorn.run", fake_run)

    assert (
        main(
            [
                "serve",
                "--executor",
                "real",
                "--llm-model",
                "test-model",
                "--database",
                str(tmp_path / "real-cli.db"),
            ]
        )
        == 0
    )
    assert captured["config"].model == "test-model"
    assert captured["config"].api_key.get_secret_value() == "top-secret"
    assert captured["literature_settings"].contact_email == "operator@example.com"
    assert "top-secret" not in repr(captured["config"])
