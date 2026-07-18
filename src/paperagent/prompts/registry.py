from __future__ import annotations

from dataclasses import dataclass
from importlib import resources


class PromptNotFoundError(KeyError):
    pass


@dataclass(frozen=True)
class PromptSpec:
    task: str
    version: str
    system: str


_PROMPT_VERSIONS = {
    "planning": "planning.v0.1.2",
    "evidence_synthesis": "evidence_synthesis.v0.1.0",
    "method_design": "method_design.v0.1.0",
    "report": "report.v0.1.0",
}


def _load_prompt(task: str) -> str:
    try:
        package = resources.files("paperagent.prompts.v0_1")
        return package.joinpath(f"{task}.md").read_text(encoding="utf-8").strip()
    except (FileNotFoundError, ModuleNotFoundError) as exc:
        raise PromptNotFoundError(task) from exc


def get_prompt(task: str) -> PromptSpec:
    try:
        version = _PROMPT_VERSIONS[task]
    except KeyError as exc:
        raise PromptNotFoundError(task) from exc
    return PromptSpec(task=task, version=version, system=_load_prompt(task))


def all_prompts() -> tuple[PromptSpec, ...]:
    return tuple(get_prompt(task) for task in _PROMPT_VERSIONS)
