# Expected Results

These are the expected outputs for `./reproduce-final.sh`. The older `./reproduce.sh` remains a
short compatibility check for the 620-case public deterministic suite.

## Deterministic Suite Results

| Suite | Mutants | Killed | Survived | Clean controls | False positives | Frozen |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `support_saas` seeded | 50 | 50 | 0 | 0 | 0 | no |
| `support_saas` generated | 500 | 500 | 0 | 0 | 0 | yes |
| `support_saas` heldout_v1 | 500 | 500 | 0 | 0 | 0 | yes |
| `finance_saas` seeded | 20 | 20 | 0 | 0 | 0 | no |
| `finance_saas` heldout_v1 | 250 | 250 | 0 | 0 | 0 | yes |
| `analytics_clickhouse` seeded | 100 | 100 | 0 | 0 | 0 | no |
| `analytics_clickhouse` generated | 300 | 300 | 0 | 0 | 0 | yes |
| `clean_controls` | 80 | 0 | 0 | 80 | 0 | yes |
| Combined non-clean suites | 1720 | 1720 | 0 | - | - | mixed |

Interpretation: the final result is deterministic artifact-suite coverage over implemented
operators, fixtures, frozen generated suites, and generated held-out suites. It is not production
recall and not an authorization boundary.

## Baseline Comparators

| Comparator | Failures caught | Catch rate |
| --- | ---: | ---: |
| Grammar only | 121/1720 | 0.07 |
| Semantic validator only | 573/1720 | 0.33 |
| SQL AST policy checker | 1043/1720 | 0.61 |
| DB policy only | 326/1720 | 0.19 |
| Release filter only | 364/1720 | 0.21 |
| Lineage only | 239/1720 | 0.14 |
| Policy-as-code precheck | 363/1720 | 0.21 |
| Defense-in-depth stack v2 | 1550/1720 | 0.90 |
| Defense-in-depth stack | 1561/1720 | 0.91 |

The defense-in-depth stack unions validator-only, SQL-snapshot, DB/RLS-only, and final-answer
checks. Its remaining 159 misses are the clearest examples for why responsibility-scoped contracts
and witness localization matter beyond stacked point controls.

## Ablation Results

| Ablation | Failures still caught | Missed after removal |
| --- | ---: | ---: |
| Without database containment | 1394/1720 | 326 |
| Without independent oracle | 1357/1720 | 363 |
| Without lineage | 1657/1720 | 63 |
| Without release policy | 1682/1720 | 38 |
| Without transition obligations | 363/1720 | 1357 |

The minimization and policy-version ablations are usability/provenance ablations in the current
artifact; they do not change the deterministic kill count and should be discussed separately from
detection-rate ablations.

## Required Files

Each deterministic run should include:

```text
runs/final/<suite>/traces.jsonl
runs/final/<suite>/summary.json
runs/final/<suite>/metadata.json
runs/final/<suite>/benchmark_manifest.json
runs/final/<suite>/witnesses/*.json
```

The reproduction script also writes:

```text
runs/final/evidence.md
runs/final/baselines.json
runs/final/ablations.json
runs/final/artifact-report.md
runs/final/exports/inspect.jsonl
runs/final/exports/benchflow.json
```

## Negative Claims

The current public artifact does not include:

- externally authored mutation suites;
- verified production incident reconstructions;
- model-in-the-loop reachability experiments;
- cumulative-release privacy guarantees;
- full source-code root-cause localization.
