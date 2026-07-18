from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shlex
import subprocess
import sys
import time
import venv
from pathlib import Path
from typing import Any, NamedTuple


class Step(NamedTuple):
    name: str
    command: tuple[str, ...]


def build_plan(profile: str, *, python: str = sys.executable) -> tuple[Step, ...]:
    if profile not in {"quick", "full"}:
        raise ValueError("profile must be quick or full")
    pytest_command = (
        python,
        "-m",
        "pytest",
        "-q",
        "tests/local",
        "tests/review/test_consolidated_regressions.py",
        "tests/api/test_diagnostics.py",
        "tests/release/test_release_candidate.py",
    )
    if profile == "full":
        pytest_command = (
            python,
            "-m",
            "pytest",
            "--cov=paperagent",
            "--cov-branch",
            "--cov-report=term-missing",
            "-q",
        )
    benchmark_tasks = "100" if profile == "quick" else "500"
    steps = [
        Step("compile", (python, "-m", "compileall", "-q", "src/paperagent")),
        Step("ruff-lint", ("ruff", "check", ".")),
        Step("ruff-format", ("ruff", "format", "--check", "--diff", ".")),
        Step("mypy", ("mypy", "--config-file", "pyproject.toml")),
        Step("pytest", pytest_command),
        Step(
            "state-roundtrip",
            (
                python,
                "scripts/local_state_roundtrip.py",
                "--workdir",
                "build/local-acceptance/state",
                "--output",
                "build/local-acceptance/state-roundtrip.json",
            ),
        ),
        Step(
            "interview-demo",
            (
                python,
                "scripts/interview_demo.py",
                "--output",
                "build/local-acceptance/interview-demo.json",
            ),
        ),
        Step(
            "openapi",
            (
                python,
                "scripts/export_openapi.py",
                "--output",
                "build/local-acceptance/openapi.json",
            ),
        ),
        Step(
            "benchmark",
            (
                python,
                "scripts/repository_benchmark.py",
                "--tasks",
                benchmark_tasks,
                "--output",
                "build/local-acceptance/repository-benchmark.json",
            ),
        ),
        Step(
            "academic-evaluation",
            (
                python,
                "scripts/run_academic_tailoring_eval.py",
                "--output-dir",
                "build/local-acceptance/academic-tailoring",
            ),
        ),
    ]
    if profile == "full":
        steps.append(
            Step(
                "build-wheel",
                (
                    python,
                    "-m",
                    "build",
                    "--wheel",
                    "--outdir",
                    "build/local-acceptance/dist",
                ),
            )
        )
    return tuple(steps)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_step(root: Path, logs: Path, step: Step) -> dict[str, Any]:
    started = time.monotonic()
    process = subprocess.run(
        step.command,
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    duration = round(time.monotonic() - started, 3)
    log_path = logs / f"{step.name}.log"
    log_path.write_text(process.stdout, encoding="utf-8")
    return {
        "name": step.name,
        "command": shlex.join(step.command),
        "returncode": process.returncode,
        "duration_seconds": duration,
        "log": str(log_path.relative_to(root)),
        "passed": process.returncode == 0,
    }


def _installed_wheel_smoke(root: Path, logs: Path) -> dict[str, Any]:
    wheels = sorted((root / "build/local-acceptance/dist").glob("*.whl"))
    if len(wheels) != 1:
        return {
            "name": "installed-wheel-smoke",
            "returncode": 1,
            "passed": False,
            "error": f"expected one wheel, found {len(wheels)}",
        }
    environment = root / "build/local-acceptance/venv"
    if environment.exists():
        import shutil

        shutil.rmtree(environment)
    venv.EnvBuilder(with_pip=True, clear=True).create(environment)
    scripts = environment / ("Scripts" if os.name == "nt" else "bin")
    python = scripts / ("python.exe" if os.name == "nt" else "python")
    paperagent = scripts / ("paperagent.exe" if os.name == "nt" else "paperagent")
    commands = (
        (str(python), "-m", "pip", "install", "--upgrade", "pip"),
        (str(python), "-m", "pip", "install", str(wheels[0])),
        (str(paperagent), "--help"),
        (str(paperagent), "plugins", "list"),
    )
    started = time.monotonic()
    output: list[str] = []
    returncode = 0
    for command in commands:
        process = subprocess.run(
            command,
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        output.append(f"$ {shlex.join(command)}\n{process.stdout}")
        if process.returncode != 0:
            returncode = process.returncode
            break
    duration = round(time.monotonic() - started, 3)
    log_path = logs / "installed-wheel-smoke.log"
    log_path.write_text("\n".join(output), encoding="utf-8")
    return {
        "name": "installed-wheel-smoke",
        "returncode": returncode,
        "duration_seconds": duration,
        "log": str(log_path.relative_to(root)),
        "wheel": str(wheels[0].relative_to(root)),
        "wheel_sha256": _sha256(wheels[0]),
        "passed": returncode == 0,
    }


def run(profile: str, output: Path, *, continue_on_error: bool = False) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[1]
    build_dir = root / "build/local-acceptance"
    logs = build_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for step in build_plan(profile):
        result = _run_step(root, logs, step)
        results.append(result)
        if not result["passed"] and not continue_on_error:
            break
    if profile == "full" and all(item["passed"] for item in results):
        results.append(_installed_wheel_smoke(root, logs))

    artifacts: list[dict[str, str]] = []
    for path in sorted(build_dir.rglob("*")):
        if path.is_file() and path != output:
            artifacts.append(
                {
                    "path": str(path.relative_to(root)),
                    "sha256": _sha256(path),
                }
            )
    summary = {
        "profile": profile,
        "passed": bool(results) and all(item["passed"] for item in results),
        "python": sys.version,
        "platform": platform.platform(),
        "repository_root": str(root),
        "steps": results,
        "artifacts": artifacts,
        "network_required": False,
        "live_llm_required": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run deterministic local acceptance without network or provider credentials."
    )
    parser.add_argument("--profile", choices=("quick", "full"), default="quick")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("build/local-acceptance/summary.json"),
    )
    parser.add_argument("--continue-on-error", action="store_true")
    parser.add_argument("--print-plan", action="store_true")
    args = parser.parse_args()
    if args.print_plan:
        print(
            json.dumps(
                [
                    {"name": item.name, "command": shlex.join(item.command)}
                    for item in build_plan(args.profile)
                ],
                indent=2,
            )
        )
        return 0
    summary = run(args.profile, args.output, continue_on_error=args.continue_on_error)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
