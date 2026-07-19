# Gate L v3 Formal Runbook

## Current status

```text
Formal contract tooling:        IMPLEMENTED
Formal holdout authored:        PENDING INDEPENDENT OWNER
Formal manifest frozen:         PENDING
Real-provider execution:        PENDING
Deterministic evidence audit:   PENDING
Two independent blind reviews: PENDING
Adjudication and agreement:     PENDING
Gate L decision:                INCOMPLETE
```

The earlier v1 and v2 corpora remain diagnostic evidence only. They must not be renamed, copied, or scored as the formal v3 holdout.

## Why a second formal contract is required

The original v3 acceptance manifest fixed the case file and planning-prompt version, but it did not bind every input that can change scientific behaviour. In particular, a run could use a different repository commit, another prompt, a modified quality policy, an altered strategy profile, or a changed price table while retaining the old manifest identity.

The formal contract closes that gap by binding:

- the exact repository source SHA used for execution;
- the complete 16-case holdout and independent-owner attestation;
- all packaged prompt versions and prompt-file digests;
- methodology contract and audit-policy versions;
- explicitly listed behaviour-bearing source files;
- strategy profiles and their referenced price tables;
- the fixed Gate L acceptance thresholds;
- the names, but never values, of required environment variables.

Any digest, prompt version, policy version, strategy, price table, or runtime-SHA mismatch fails before provider execution.

## Required independent inputs

A formal run cannot begin until an independent holdout owner supplies:

1. exactly 16 new cases using one `v3-*` version;
2. exactly four cases in each category: `in_domain`, `ood`, `insufficient_evidence`, and `adversarial`;
3. predeclared allowed workflow terminals, budgets, deterministic checks, evidence requirements, forbidden properties, and a 100-point review rubric;
4. an attestation that the cases were not used for remediation or tuning and that the author did not inspect previous holdout outputs;
5. the exact SHA-256 digest of the final case file.

The repository contains templates only:

- `evals/v0_6/gate_l_v3/formal_freeze_spec.example.json`;
- `evals/v0_6/gate_l_v3/holdout_attestation.example.json`.

The attestation example deliberately contains `false` values and cannot pass freeze accidentally.

## Prepare the final source commit

Before freezing:

1. create the new holdout and completed attestation;
2. create the actual strategy profile, for example `config/gate-l-strategies/formal-balanced.json`;
3. ensure the profile contains no credential values;
4. make sure its `price_table` points to a committed file listed in the freeze spec;
5. commit all cases, profiles, policy files, code, tests, and documentation;
6. run the full engineering CI;
7. stop changing scientific prompts, retrieval behaviour, decision policies, graders, and formal-run scripts.

Do not put the final commit SHA inside the committed freeze spec. Doing so creates a self-referential commit that can never stabilize. Supply the SHA to the freeze command after the final commit exists.

## Freeze the formal manifest

Run from a clean repository checkout at the exact intended execution commit:

```bash
SOURCE_SHA="$(git rev-parse HEAD)"

python scripts/gate_l_formal_contract.py freeze \
  --spec evals/v0_6/gate_l_v3/formal_freeze_spec.json \
  --manifest-out build/gate-l-v3-formal/manifest.json \
  --source-sha "$SOURCE_SHA"
```

The manifest is an evidence artifact under ignored `build/`; it is not required to be committed. Preserve it with the final evidence bundle.

Verify it before spending provider budget:

```bash
python scripts/gate_l_formal_contract.py verify \
  --manifest build/gate-l-v3-formal/manifest.json \
  --runtime-sha "$(git rev-parse HEAD)" \
  --strategy config/gate-l-strategies/formal-balanced.json \
  --price-table config/price-table-mistral.json
```

Expected result:

```text
Formal Gate L manifest verified
```

Any mismatch exits with status `2` and must stop the run.

## Execute all cases

A formal run must execute the complete frozen set exactly once. Case filters are prohibited.

```bash
python scripts/run_gate_l_formal.py \
  --manifest build/gate-l-v3-formal/manifest.json \
  --strategy config/gate-l-strategies/formal-balanced.json \
  --output-dir build/gate-l-v3-formal/execution
```

Required real environment values depend on the selected provider. For Mistral this normally includes `MISTRAL_API_KEY`; literature contact identity should be supplied through `PAPERAGENT_CONTACT_EMAIL`. Never commit these values.

The wrapper checks before execution:

- full 40-character runtime SHA equals the frozen SHA;
- working tree is clean;
- all frozen artifact digests still match;
- all packaged prompt versions match;
- methodology policy versions match;
- strategy and price table are members of the frozen contract;
- no case filter is present.

The output contains:

- `run-record.json`;
- `formal-preflight.json`;
- one immutable evidence JSON per case;
- output and trace digests;
- provider/model, price-table, strategy, manifest, source-SHA, and budget identities.

## Deterministic audit and blind review

After execution:

1. perform the deterministic provenance, citation, unsupported-claim, secret-disclosure, budget, and false-GO audit;
2. assemble the deterministic summary with `scripts/assemble_gate_l_v3_summary.py`;
3. build the randomized blinded package with `scripts/gate_l_acceptance_v3.py blind`;
4. collect two reviews from distinct human experts;
5. require complete independence attestations;
6. adjudicate every decision or critical-defect disagreement;
7. score with `scripts/gate_l_acceptance_v3.py score`.

Synthetic, stub, duplicated, model-authored, or same-identity reviewers are invalid. Missing review, adjudication, telemetry, or real-source evidence leaves Gate L `INCOMPLETE`.

## Invalidating changes

After manifest freeze, any of the following requires a new holdout version and new manifest:

- case, rubric, budget, expected-terminal, or threshold edits;
- any packaged prompt or prompt-version edit;
- retrieval, verification, method-design, quality-gate, or report behaviour change;
- audit or scoring logic change;
- strategy or price-table change;
- running another repository SHA;
- tuning after inspecting formal outputs.

## Boundary

Passing engineering CI or contract preflight does not pass Gate L. The formal scientific decision remains `INCOMPLETE` until real execution, deterministic evidence audit, blinded expert review, agreement measurement, and required adjudication all finish on the exact frozen identity.
