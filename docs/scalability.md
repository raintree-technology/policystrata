# Scalability and Covering Arrays

Two things the review asked for that the paper only mentioned: covering-array
case generation, and detector cost as the workload grows.

```bash
uv run python scripts/scalability-study.py --out runs/scalability
```

## Covering arrays

Exhaustively crossing every principal x role x schema-object x operator is
combinatorial. A pairwise (2-way) covering array covers all pairs of factor
values with far fewer cases. `policystrata.scalability.covering_array` implements
a deterministic greedy generator and verifies coverage.

For 8 principals x 4 roles x 8 schema objects x 21 operators:

| Cases | Count |
| --- | --- |
| Full cross product | 5376 |
| Pairwise covering array | 439 |
| Reduction | 91.8% |

Every pair is covered (the test independently reconstructs the pair set and
checks containment). As the factor space grows, the covering array grows far
slower than the cross product:

| Principals | Full cross | Covering array | Reduction |
| --- | --- | --- | --- |
| 2 | 1344 | 265 | 80.3% |
| 8 | 5376 | 439 | 91.8% |
| 32 | 21504 | 1173 | 94.5% |

The generator is greedy, not optimal: it guarantees full t-way coverage but the
array is larger than the theoretical lower bound (roughly the product of the two
largest factor sizes). It is deterministic and dependency-free.

## Throughput

Detector cost per case is flat as suite size grows - detection is O(1) per case
over the trace:

| Domain | 800 cases | Per case |
| --- | --- | --- |
| support_saas | ~19 ms | ~0.024 ms |
| finance_saas | ~18 ms | ~0.023 ms |
| analytics_clickhouse | ~23 ms | ~0.029 ms |

## Limitations

- The version vector has a fixed dimensionality of six surfaces in this model,
  so version-vector scaling is not a free variable here; the covering-array
  study varies principals, roles, schema objects, and operators instead.
- Throughput is measured on the deterministic simulator. Real database
  containment checks (Postgres/ClickHouse) add per-case I/O that this curve does
  not include; those paths are outside the deterministic benchmark and measured
  separately.
- Covering-array minimality is greedy, not optimal; a constraint-aware or
  IPOG-style generator would produce smaller arrays.
