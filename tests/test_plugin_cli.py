from __future__ import annotations

import json
from pathlib import Path

from paperagent.cli import main


def test_plugins_list_reports_builtins(capsys: object) -> None:
    assert main(["plugins", "list"]) == 0

    captured = capsys.readouterr()  # type: ignore[attr-defined]
    payload = json.loads(captured.out)
    assert [plugin["name"] for plugin in payload["plugins"]] == [
        "academic-method-tailoring",
        "echo-contract",
    ]
    assert payload["load_failures"] == []


def test_echo_plugin_cli_writes_byte_stable_output(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    input_path.write_text('{"message":"hello","nested":{"value":1}}', encoding="utf-8")
    argv = [
        "plugins",
        "run",
        "echo-contract",
        "--operation",
        "echo",
        "--input",
        str(input_path),
        "--output",
        str(output_path),
    ]

    assert main(argv) == 0
    first = output_path.read_bytes()
    assert main([*argv, "--overwrite"]) == 0
    second = output_path.read_bytes()

    assert first == second
    payload = json.loads(first)
    assert payload["output"]["echo"]["message"] == "hello"
    assert payload["request_id"].startswith("plugin-")


def test_plugin_cli_refuses_unrequested_overwrite(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    input_path.write_text("{}", encoding="utf-8")
    output_path.write_text("existing", encoding="utf-8")

    result = main(
        [
            "plugins",
            "run",
            "echo-contract",
            "--operation",
            "echo",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ]
    )

    assert result == 2
    assert output_path.read_text(encoding="utf-8") == "existing"


def test_academic_method_template_cli(tmp_path: Path) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "template.json"
    input_path.write_text("{}", encoding="utf-8")

    assert (
        main(
            [
                "plugins",
                "run",
                "academic-method-tailoring",
                "--operation",
                "template",
                "--input",
                str(input_path),
                "--output",
                str(output_path),
            ]
        )
        == 0
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["output"]["baseline"]["reproduced"] is False
    assert payload["evidence"]["network_used"] is False
