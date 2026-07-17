# PaperAgent v0.6 Live Mistral Smoke Runbook

## Required repository secret

Create the GitHub Actions secret `MISTRAL_API_KEY`. Never commit the key or place it in workflow inputs.

## Run

Dispatch the `PaperAgent v0.6 Live LLM Smoke` workflow and provide an explicit supported Mistral model
identifier. The workflow has a five-minute timeout and executes only the separately marked live smoke.

## Success

- the provider returns an object matching the requested Pydantic schema;
- the test exits successfully;
- no API key, authorization header, raw provider payload, or chain-of-thought appears in logs or artifacts.

## Failure evidence to retain

Return the workflow run URL, failed step, redacted traceback, HTTP status class, provider error code, and
model identifier. Do not return the API key.

## Current verification state

`PENDING`: the repository secret has not been configured or exercised by this development session.
