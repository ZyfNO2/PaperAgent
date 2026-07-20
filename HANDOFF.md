# Handoff

## Scope

Standalone benchmark-authoring branch for a clean Academic Method Holdout v2.

## Completed

- frozen protocol for public development, private holdout, and metamorphic sets;
- v2 JSON Schema;
- 12 public development cases across eight reasoning capabilities and at least ten domains;
- dependency-free validator with contamination checks;
- regression tests and GitHub Actions workflow;
- private holdout sealing procedure without committing private cases.

## Deliberate exclusions

- no changes to `src/paperagent`;
- no changes to PR #34;
- no private holdout prompts or gold;
- no production runner integration;
- no paid provider execution.

## Next implementation steps

1. Freeze the production and scorer commits.
2. Implement a runner that projects only `input` fields.
3. Implement structured scoring against `oracle` outside production execution.
4. Author and adjudicate the private 32-case set outside the evaluated repository.
5. Run the source-wide leakage scan and sealed formal evaluation.
