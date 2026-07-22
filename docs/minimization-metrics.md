# Witness Minimization Metrics

The evidence table reports one aggregate - median witness bytes - which says
nothing about how much the minimizer removed or whether the result is
irreducible. `policystrata minimization-report` quantifies the reducer on any
completed run.

```bash
uv run policystrata run --domain support_saas --suite generated --count 200 --out runs/min-gen
uv run policystrata minimization-report runs/min-gen --out runs/min-gen/minimization.json
```

Per witness it records: pre/post witness bytes and full-witness reduction ratio;
pre/post **semantic-IR** bytes and IR reduction ratio (the reducer only touches
the semantic IR, so this isolates its real effect from the fixed contract
scaffolding); dimensions and filters removed; whether the limit was reset;
reducer attempts/accepted; **1-minimality** (no single further reduction
preserves the witness); and wall-clock reduction time.

## What the numbers say

On the deterministic support_saas suites:

| Metric | Seeded (50) | Generated (200) |
| --- | --- | --- |
| Median full-witness reduction | ~0.02 | ~0.03 |
| Median semantic-IR reduction | ~0.02 | ~0.06 |
| 1-minimal | 100% | 100% |
| Total reduction time | a few ms | tens of ms |

Two honest observations:

1. **The reduction ratios are small because the inputs are already small.** The
   generated queries carry one dimension and a default limit, so there is little
   to remove. The full-witness ratio is smaller still because most witness bytes
   are fixed surface-contract and responsibility scaffolding, not the semantic IR
   the reducer targets - which is why the report separates the IR ratio.
2. **Every witness is 1-minimal.** No single further dimension/filter/limit
   reduction preserves the witness, so the reducer reaches a local minimum under
   its move set on every case. That is the property the "median bytes" column
   could not show.

## Limitations

- The reducer is a bounded semantic-IR replay reducer, not search-based delta
  debugging; 1-minimality here means minimal under its move set (drop a
  dimension, drop a filter, reset the limit), not globally minimal over arbitrary
  edits.
- Reduction ratios will be larger on suites with wider queries (more dimensions
  and filters); the current generators emit narrow queries, so these numbers are
  a floor, not a ceiling.
