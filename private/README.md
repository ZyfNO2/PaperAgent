# Private holdout handling

Do not commit private prompts, gold labels, paper lists, domain inventories, or per-case traces to this branch.

## Authoring procedure

1. Freeze the production commit, scorer commit, schema version, and acceptance thresholds.
2. Author 40–48 candidates outside the evaluated repository.
3. Use at least 10 domains absent from the contaminated v1 cases and production topic tables.
4. Independently adjudicate each candidate twice.
5. Remove ambiguous cases or encode multiple accepted decisions when both are defensible.
6. Select 32 primary cases balanced across the eight capabilities.
7. Create 8 metamorphic groups with 2–3 variants each.
8. Hash prompts, gold, scorer config, and manifest.
9. Run the frozen system once without exposing gold to production execution.
10. Record aggregate results before unsealing per-case details.

## Required manifest fields

```json
{
  "dataset_schema": "paperagent.academic-holdout.manifest.v2",
  "production_commit": "<40-hex>",
  "scorer_commit": "<40-hex>",
  "created_at": "<RFC3339>",
  "case_count": 32,
  "metamorphic_variant_count": 16,
  "prompt_digest": "<sha256>",
  "gold_digest": "<sha256>",
  "thresholds_digest": "<sha256>",
  "sealed": true
}
```

Any case inspected during debugging becomes development data and must be replaced before the next formal holdout claim.
