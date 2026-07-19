# Gate L v3 Formal Runbook

## Current status

```text
Formal contract tooling:         IMPLEMENTED IN PR #26
Artifact-chain verification:     IMPLEMENTED IN PR #26
Formal execution workflow:       IMPLEMENTED IN PR #26
Deterministic audit workflow:    IMPLEMENTED IN PR #26
Blinded-package separation:      IMPLEMENTED IN PR #26
Final scoring workflow:          IMPLEMENTED IN PR #26
Formal holdout authored:         PENDING INDEPENDENT OWNER
Formal manifest frozen:          PENDING
Real-provider execution:         PENDING
Human content audit:             PENDING
Two independent blind reviews:  PENDING
Adjudication and agreement:      PENDING
Gate L decision:                 INCOMPLETE
```

Engineering automation does not establish scientific acceptance. The earlier v1 and v2 corpora remain diagnostic evidence only and must not be renamed, copied, or scored as the formal v3 holdout.

## Formal evidence chain

The authoritative cloud sequence is:

```text
exact source SHA + independent holdout + attestation + strategy + price table
        ↓
Gate L Formal Freeze
        ↓ immutable freeze artifact
Gate L Formal Execute
        ↓ immutable 16-case execution artifact
Gate L Formal Audit (prepare)
        ↓ fail-closed human audit template
human evidence auditor completes and seals the audit on a separate ref
        ↓
Gate L Formal Audit (finalize)
        ↓ deterministic-summary artifact
Gate L Build Blinded Review Package
        ↓ reviewer artifact + separate private custodian artifact
Reviewer A and Reviewer B submit independently on a sealed review ref
        ↓ optional recorded adjudication
Gate L Formal Score
        ↓ PASS / FAIL / INCOMPLETE evidence artifact
```

Each downstream workflow downloads artifacts by exact workflow run ID and exact artifact name. Every artifact contains a relocatable `SHA256SUMS` inventory. The chain verifier rejects checksum drift, source-SHA drift, manifest drift, missing cases, missing per-case evidence, identity mismatches, and incomplete artifact sets.

## Why the formal contract is required

A case-file digest alone does not bind every input that can change scientific behavior. A formal run must bind:

- the exact repository source SHA;
- the complete 16-case holdout and independent-owner attestation;
- all packaged prompt versions and prompt-file digests;
- methodology contract and audit-policy versions;
- behavior-bearing source files, including artifact-chain, audit, review-package, and scoring utilities;
- strategy profiles and referenced price tables;
- fixed Gate L acceptance thresholds;
- required environment-variable names, never secret values.

Any digest, prompt version, policy version, strategy, price table, threshold, or runtime-SHA mismatch fails before provider execution.

## Required independent inputs

A formal run cannot begin until a holdout owner who did not implement or tune the remediation supplies:

1. exactly 16 new cases using one `v3-*` version;
2. exactly four cases in each category: `in_domain`, `ood`, `insufficient_evidence`, and `adversarial`;
3. predeclared allowed workflow terminals, budgets, deterministic checks, evidence requirements, forbidden properties, and a 100-point rubric;
4. an attestation that the cases were not used for remediation or tuning and that the owner did not inspect earlier holdout outputs;
5. the exact SHA-256 digest of the final case file.

Templates:

- `evals/v0_6/gate_l_v3/formal_freeze_spec.example.json`;
- `evals/v0_6/gate_l_v3/holdout_attestation.example.json`.

The attestation template deliberately contains false values and cannot pass accidentally.

## Prepare the final source commit

Before freezing:

1. create the new holdout and completed attestation;
2. create the real strategy profile, for example `config/gate-l-strategies/formal-balanced.json`;
3. keep all credentials out of the strategy file;
4. make the strategy reference a committed price table listed in the freeze spec;
5. commit cases, profiles, policy files, code, tests, workflows, and documentation;
6. run the full engineering CI;
7. stop changing scientific prompts, retrieval behavior, decision policies, graders, and formal-run scripts.

Do not place the final commit SHA inside the committed freeze spec. Supply it as the workflow input after the final commit exists.

## Protected environment and secrets

Create a protected GitHub Environment named:

```text
gate-l-formal
```

Require manual approval for the environment. Store only the credentials needed by the frozen strategy. A Mistral-based run normally uses:

```text
MISTRAL_API_KEY
PAPERAGENT_CONTACT_EMAIL
```

Optional provider or literature secrets may include:

```text
PAPERAGENT_OPENAI_API_KEY
OPENAI_API_KEY
SEMANTIC_SCHOLAR_API_KEY
```

Secrets must never enter strategy JSON, manifests, logs, review artifacts, or committed files.

## 1. Freeze the formal manifest

Run the manual workflow:

```text
Gate L Formal Freeze
```

Input:

```text
source_sha = exact 40-character final source SHA
```

The workflow checks out the exact SHA, verifies a clean tree, runs focused regression tests, creates and re-verifies the formal manifest, records workflow identity, generates relocatable checksums, and uploads:

```text
gate-l-formal-freeze-<source_sha>
```

Preserve the freeze workflow run ID, artifact name, artifact digest, manifest digest, source SHA, and artifact-bundle digest.

## 2. Execute all frozen cases

Run:

```text
Gate L Formal Execute
```

Required inputs:

- exact source SHA;
- freeze workflow run ID;
- exact freeze artifact name;
- frozen strategy path;
- confirmation text `RUN_FORMAL_GATE_L`.

The job uses the protected `gate-l-formal` environment. It verifies the downloaded freeze artifact before provider calls and prohibits case filters. The run must execute all 16 cases exactly once.

The execution artifact contains:

- `run-record.json`;
- `formal-preflight.json`;
- one evidence JSON per case;
- output and trace digests;
- provider/model, strategy, price-table, manifest, source-SHA, usage, latency, retry, repair, and budget identities;
- `execution-workflow-record.json`;
- `verified-execution.json` when the chain is valid;
- `SHA256SUMS`.

Execution errors, incomplete usage accounting, token/call/time/cost violations, or other per-case budget failures make `formal_execution_eligible` false. Failed runs still upload their evidence and remain auditable; they are never silently discarded.

## 3. Prepare and finalize deterministic content audit

First run:

```text
Gate L Formal Audit
mode = prepare
```

This produces a fail-closed audit template. A real human evidence auditor must review every case for:

- claim-evidence alignment;
- citation and identifier validity;
- unsupported claims;
- critical unsupported claims;
- secret or hidden-information disclosure;
- repair behavior;
- zero-tolerance failures.

The template starts incomplete, uses placeholder identity, and has every attestation and review flag set to false.

The completed audit must be sealed on a separate Git ref. Then run:

```text
Gate L Formal Audit
mode = finalize
audit_ref = sealed audit commit/branch/tag
content_audit_path = path inside audit_ref
```

Finalization rejects missing attestations, synthetic/stub auditors, incomplete per-case reviews, duplicate/missing cases, impossible counts, and aggregate rates supplied without underlying case-level counts. It creates the normalized audit and deterministic summary from the exact immutable execution evidence.

## 4. Build the blinded review package

Run:

```text
Gate L Build Blinded Review Package
```

The workflow verifies execution eligibility, randomizes arm IDs, and uploads two separate artifacts:

1. reviewer artifact: tasks, allowed constraints, outputs, accepted evidence, and rubric;
2. private custodian artifact: arm-to-case mapping, upstream verification records, and package digest.

The reviewer package guard rejects raw case IDs, expected terminals or decisions, provider/model identity, strategy/price-table identity, execution identity, and any package/mapping mismatch.

Never give the custodian artifact to reviewers.

## 5. Collect independent human reviews

Recruit two distinct human experts who did not generate the outputs or alter the prompts after freeze. Each reviewer must:

- receive only the blinded reviewer artifact;
- submit independently before seeing the other review;
- use a distinct reviewer identity;
- complete every arm exactly once;
- attest that the review is human, independent, blinded, and not synthetic or stubbed.

Seal both reviews on a separate Git ref. If reviewers disagree on a decision or critical-defect flag, record adjudication with rationale. Agreement is measured before adjudication.

## 6. Score the formal gate

Run:

```text
Gate L Formal Score
```

Inputs bind the exact freeze, execution, finalized audit, private mapping, sealed review ref, two review files, and optional adjudication file. Confirmation text must be:

```text
SCORE_FORMAL_GATE_L
```

The scorer verifies the upstream checksum chain, requires execution-eligible evidence and a complete deterministic audit, rejects identical reviewers or incomplete attestations, computes case/category acceptance, mean scores, Cohen's kappa, score-distance agreement, repair and budget handling, and emits:

```text
PASS
FAIL
INCOMPLETE
```

The workflow uploads the decision artifact even when scoring fails. Only a true `PASS` exits successfully.

## Invalidating changes

After freeze, any of the following requires a new holdout version and new freeze:

- case, rubric, budget, expected-terminal, or threshold edits;
- any packaged prompt or prompt-version edit;
- retrieval, verification, method-design, quality-gate, or report behavior change;
- execution, artifact-chain, audit, review-package, or scoring logic change;
- strategy or price-table change;
- running another repository SHA;
- tuning after inspecting formal outputs.

## Boundary

Passing engineering CI, generating a freeze artifact, or completing a real-provider run does not by itself pass Gate L. Formal scientific acceptance remains `INCOMPLETE` until the exact frozen identity has a complete deterministic human content audit, two independent blinded human reviews, agreement measurement, required adjudication, and a final scorer artifact.
