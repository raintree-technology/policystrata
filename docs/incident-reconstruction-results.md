# Incident Reconstruction Results

This is a separate evidence snapshot from [`docs/evidence.md`](evidence.md). It reports recall over
a suite of deterministic fixtures reconstructed from 19 real, citation-backed, cross-layer policy
faults (public CVEs, security advisories, and vendor-acknowledged bug reports), not recall over the
synthetic operator-generated suites `docs/evidence.md` reports. **The two numbers must not be
combined or compared as if they measured the same thing.**

Domain and suite: `benchmarks/incident_reconstruction/` (self-contained; not a built-in domain --
run with `--domain-path`). Full fault -> operator mapping, per-fault justification, and the 6
faults that were not reconstructed (with reasons) are in
[`benchmarks/incident_reconstruction/MAPPING.md`](../benchmarks/incident_reconstruction/MAPPING.md).

## Reproduce

```bash
uv run policystrata run \
  --domain incident_reconstruction \
  --domain-path benchmarks/incident_reconstruction \
  --suite reconstructed \
  --out runs/incident-reconstruction
```

## Result

| Metric | Value |
| --- | --- |
| Faults in source ledger (`real-faults.json`) | 25 |
| Faults reconstructed as tasks | 19 |
| Faults dropped as non-reconstructable | 6 |
| Tasks killed | **19 / 19** |
| Mutant kill rate | 1.0 |
| Localization accuracy | 1.0 |
| Expected-class accuracy | 1.0 |
| Distinct operators exercised | 12 of 22 |
| Evidence level | `deterministic_fixture` |
| Suite provenance | `incident_reconstruction` |

(Reproduced from `runs/incident-reconstruction/summary.json` and `metadata.json` after running the
command above.)

## Per-source summary

See the full table in
[`benchmarks/incident_reconstruction/MAPPING.md`](../benchmarks/incident_reconstruction/MAPPING.md#included-faults-19)
for every fault ID, source URL, chosen operator, resulting surface/witness class, and a one-line
justification for the mapping, plus the 6 dropped faults and why each was excluded.

By source system, of the 19 reconstructed:

| System | Faults reconstructed |
| --- | --- |
| PostgreSQL (core) | 8 |
| Supabase | 2 |
| ClickHouse | 2 |
| Cube | 1 |
| Looker | 1 |
| dbt / MetricFlow | 1 |
| Metabase | 1 |
| Apache Superset | 1 |
| Hasura | 1 |
| LangChain | 1 |

## What "recall" means here, and what it does not

- **What it means:** each of the 19 tasks encodes an existing PolicyStrata mutation operator chosen
  to honestly reflect a real, cited fault's documented cross-layer drift (its `layer_mapping` and
  `drift_shape`, per `real-faults.json`). "19/19 killed, localization 1.0" means PolicyStrata's
  detector correctly classified and localized every one of those 19 fixtures -- i.e., **the
  detector kills fixtures grounded in real incidents**, not synthetic ones invented without an
  external citation.
- **What it does not mean:** it is not evidence of recall over unknown production faults, and it is
  not a claim that PolicyStrata would have caught any of these 19 incidents in the original
  product. No new detection logic or operator was written for this suite -- every task reuses one
  of the 22 operators that also produce the 100% kill rates in `docs/evidence.md`. Several of the
  underlying real triggers (planner statistics internals, plan-cache role reuse, a caching layer,
  prompt injection into an LLM chain) are not modeled by PolicyStrata's deterministic simulator at
  all; what's reconstructed is the operator's own generic drift shape that best matches each
  fault's documented *resulting* visibility drift, not a replay of the vulnerable code path. See
  the "What this suite does not claim" section of `MAPPING.md` for the full caveat, including that
  3 of the 12 operators used are each responsible for 3 of the 19 tasks (reuse, not independent
  detection capability), and that 6 of the 25 source faults were dropped rather than mapped onto an
  operator that would misrepresent their direction or mechanism (also detailed in `MAPPING.md`).

## Tests

`tests/test_incident_reconstruction.py` loads this suite via `base_path`, runs it, and asserts:

- every task is killed (`accounting_status == "killed"` for all 19 traces);
- `localization_accuracy == 1.0` and `expected_class_accuracy == 1.0` in the summary;
- suite metadata provenance is `incident_reconstruction` with evidence level
  `deterministic_fixture`.
