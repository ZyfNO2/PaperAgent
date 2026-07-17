# PaperAgent v0.5.1 Release Candidate Runbook

## Local deterministic demo

```bash
python -m pip install -e '.[dev,release]'
paperagent serve
```

Open `http://127.0.0.1:8000/app`.

The built-in executor is deterministic and synthetic. It exists to exercise task submission, SSE and polling progress, cancellation boundaries, paper review, favorites, validation guards, and deterministic exports. It is not a scientific answer and does not call an LLM or literature provider.

The CLI refuses a non-loopback bind unless `--allow-public-bind` is supplied. This flag is only an explicit acknowledgement; it does not add authentication or tenant isolation.

## Live provider smoke

```bash
PAPERAGENT_CONTACT_EMAIL=you@example.com paperagent provider-smoke --timeout 20
```

The command checks OpenAlex and arXiv discovery plus Crossref and DataCite DOI verification. It returns a non-zero exit code unless all four checks pass. Upstream rate limits and regional network failures must be recorded separately from application defects.

## Browser smoke

```bash
python -m pip install -e '.[dev,browser]'
python -m playwright install chromium
pytest -q -m browser tests/browser/test_pwa_smoke.py
```

The smoke starts the installed CLI, submits a demo task through Chromium, waits for terminal progress, accepts one paper, and downloads the accepted JSON export.

## Container

```bash
docker build -t paperagent:0.5.1 .
docker run --rm -p 8000:8000 -v paperagent-data:/data paperagent:0.5.1
```

The container runs as an unprivileged user and stores SQLite data under `/data`. `/readyz` checks SQLite integrity and packaged web assets.

## Release boundary

This candidate is suitable for local single-user use and trusted-network evaluation. It is not approved for an unauthenticated public multi-user deployment.