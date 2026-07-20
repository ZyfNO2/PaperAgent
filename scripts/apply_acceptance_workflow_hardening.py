from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / ".github/workflows/claw-clean-v2-acceptance-pr.yml"


def replace_once(old: str, new: str) -> None:
    text = PATH.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one acceptance workflow replacement, found {count}: {old[:120]!r}")
    PATH.write_text(text.replace(old, new), encoding="utf-8")


replace_once(
    """jobs:
  accept-clean-v2:
    if: github.event.pull_request.head.repo.full_name == github.repository
    runs-on: ubuntu-24.04
""",
    """jobs:
  gate:
    if: github.event.pull_request.head.repo.full_name == github.repository
    runs-on: ubuntu-24.04
    outputs:
      enabled: ${{ steps.subject.outputs.enabled }}
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
          fetch-depth: 1
      - name: Check dedicated acceptance trigger
        id: subject
        shell: bash
        run: |
          subject=$(git log -1 --pretty=%s)
          if [ "$subject" = "test(eval): trigger clean v2 acceptance" ]; then
            echo "enabled=true" >> "$GITHUB_OUTPUT"
          else
            echo "enabled=false" >> "$GITHUB_OUTPUT"
            echo "Skipping paid acceptance for commit: $subject"
          fi

  accept-clean-v2:
    needs: gate
    if: needs.gate.outputs.enabled == 'true'
    runs-on: ubuntu-24.04
""",
)
replace_once(
    """        run: pytest --no-cov -q tests/real_provider/test_mistral_smoke.py
""",
    """        shell: bash
        run: |
          set -o pipefail
          mkdir -p build/clean-v2-acceptance
          pytest --no-cov -q tests/real_provider/test_mistral_smoke.py \
            2>&1 | tee build/clean-v2-acceptance/mistral-smoke.log
""",
)
replace_once(
    """        run: pytest --no-cov -q tests/real_provider/test_literature_smoke.py
""",
    """        shell: bash
        run: |
          set -o pipefail
          mkdir -p build/clean-v2-acceptance
          log=build/clean-v2-acceptance/literature-smoke.log
          : > "$log"
          for attempt in 1 2; do
            echo "literature smoke attempt $attempt" | tee -a "$log"
            if pytest --no-cov -q tests/real_provider/test_literature_smoke.py \
              2>&1 | tee -a "$log"; then
              exit 0
            fi
            if [ "$attempt" -lt 2 ]; then
              sleep 10
            fi
          done
          exit 1
""",
)

print("acceptance workflow hardening applied")
