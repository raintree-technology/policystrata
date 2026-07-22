# Adapter TCB mutation analysis

PolicyStrata's paper states that its adapters are a trusted computing base
(TCB): if an adapter is buggy, it can hide real faults or invent false ones.
This document measures that claim.

## What the TCB is

The scanner trusts three adapter layers:

- **Trace importer** (`src/policystrata/trace_import.py`): parses JSONL trace
  exports, normalizes records, and validates them into `ImportedTrace` models.
- **Read-only SQL guard** (`assert_read_only_sql` in
  `src/policystrata/database.py`): the pure statement filter that decides which
  imported SQL is admitted. Only the pure functions are in scope here; live
  database execution is not tested.
- **Finding emission** (`src/policystrata/scanner.py`): the path that turns
  trace and state observations into `ScanFinding` records and the gate verdict.

Every finding the gate acts on flows through these layers. None of their
outputs are cross-checked by an independent mechanism.

## Method

`src/policystrata/tcb_catalog.py` defines 18 adapter mutations: small runtime
behavior overrides (attribute patches, always undone) over the three layers.
Each mutation replays a fixed detection scenario built from synthetic fixtures
in `tests/fixtures/tcb/` — traces with known true violations (an unauthorized
released metric, a missing tenant predicate, an unknown principal), known clean
traces, a malformed line, a smuggled write statement, and a cross-tenant state
leak served by an in-memory adapter. No live database and no network are used;
database result-shaping faults are emulated on an in-memory stand-in for
`PostgresAdapter.query`.

The scan output signature (gate outcome plus finding ids and severities) is
compared intact vs. mutated and classified:

- **HIDDEN** — a true finding disappears, or severity/gate is weakened
- **INVENTED** — a false finding appears, or severity/gate is escalated
- **NEUTRAL** — the observable output is unchanged
- **LOUD** — the mutation raises an explicit error (the good outcome)

`tests/test_tcb_mutation.py` pins the classification of every catalog entry, so
future adapter hardening shows up as a test diff. Regenerate the table with
`uv run scripts/tcb-mutation-report.py`.

## Headline

**16 of 18 adapter mutations change scan output silently today: 13 hide real
findings or weaken the verdict, 3 invent false findings. Only 1 mutation is
LOUD (an explicit crash), and 1 is neutral.** A single-line bug in the trace
importer (for example, defaulting `release_allowed` to false, or dropping the
semantic IR) is enough to turn a failing scan into a passing one with no error
reported.

## Results

| Mutation | Adapter | Scenario | Outcome | Consequence |
| --- | --- | --- | --- | --- |
| import_drops_tenant_ids | trace_import | main | INVENTED | A placeholder-bound clean trace loses its tenant binding and is falsely reported as missing tenant scope. |
| import_forces_release_denied | trace_import | main | HIDDEN | Both unsafe-release findings for a released, policy-denied query disappear. |
| import_drops_semantic_ir | trace_import | main | HIDDEN | The policy oracle is never consulted, so authorization findings vanish. |
| import_swaps_denied_metric | trace_import | main | HIDDEN | Two high release findings collapse into one medium metric-drift warning. |
| import_stamps_default_principal | trace_import | main | HIDDEN | The unknown-principal finding disappears and the trace scans clean. |
| import_drops_all_traces | trace_import | main | HIDDEN | Every trace finding disappears and the gate passes; no count invariant notices. |
| import_returns_none | trace_import | main | LOUD | The scan crashes with a TypeError; the fault cannot pass unnoticed. |
| import_drops_source_field | trace_import | main | NEUTRAL | Provenance is lost but no finding, severity, or gate outcome changes. |
| import_skips_malformed_lines | trace_import | malformed_line | HIDDEN | A critical input-rejection finding is replaced by a passing scan over partial input. |
| sql_guard_accepts_multi_statement | sql_guard | write_sql | HIDDEN | A smuggled 'select ...; drop table ...' trace loads and the critical rejection finding disappears. |
| sql_guard_rejects_cte | sql_guard | clean_cte | INVENTED | A valid CTE trace is rejected, inventing a critical input finding. |
| db_truncates_result_rows | db_results | state | HIDDEN | The cross-tenant row is dropped, so the leak assertion passes. |
| db_renames_result_columns | db_results | state | HIDDEN | Forbidden-value checks become vacuous and the leak assertion passes. |
| state_eval_ignores_forbidden_values | finding_emission | state | HIDDEN | The cross-tenant leak finding is silenced. |
| emit_drops_release_findings | finding_emission | main | HIDDEN | Both release findings disappear while the rest of the scan looks healthy. |
| emit_duplicates_static_findings | finding_emission | main | INVENTED | A duplicate copy of the tenant-scope finding is invented. |
| emit_downgrades_severity | finding_emission | main | HIDDEN | Every finding id survives but the gate flips from fail to pass. |
| gate_always_passes | finding_emission | main | HIDDEN | Findings remain listed but the failure verdict is hidden. |

Tally: 18 adapter mutations — HIDDEN=13, INVENTED=3, NEUTRAL=1, LOUD=1.
Silent (HIDDEN or INVENTED): 16 of 18.

Notes on individual rows:

- `import_swaps_denied_metric` also invents a medium warning while hiding two
  high findings; the classification records the worse effect (HIDDEN).
- `sql_guard_rejects_cte` is scored on an all-clean scenario. In a mixed batch
  the effect is worse: `load_imported_traces` rejects the whole file on the
  first bad trace, so an over-strict guard would also hide every true finding
  in that batch.
- `import_drops_source_field` is NEUTRAL for the gate, but it destroys
  provenance in witnesses and reports. Neutral here means "invisible to the
  gate", not harmless.
- The state-scenario rows use an in-memory adapter, so `db_truncates_result_rows`
  and `db_renames_result_columns` measure the scanner's sensitivity to a
  result-shaping fault in `PostgresAdapter.query`, not the adapter's own code.

## Mitigations that would convert HIDDEN/INVENTED into LOUD

These are documented only; no adapter code was changed.

- **Count invariants.** Record how many non-empty lines each trace file has and
  fail the scan if `parsed + skipped_non_sql != total`. This makes
  `import_skips_malformed_lines` and `import_drops_all_traces` LOUD. Emitting
  the trace count into `summary.json` and asserting it in CI catches the
  zero-trace case even without importer changes.
- **Input checksums.** Hash each trace record at export time and re-verify the
  hash over the normalized fields (`principal`, `tenant_ids`, `semantic_ir`,
  `release_allowed`, `sql`) after import. Any field-level rewrite
  (`import_forces_release_denied`, `import_drops_semantic_ir`,
  `import_swaps_denied_metric`, `import_stamps_default_principal`,
  `import_drops_tenant_ids`) then fails loudly instead of silently changing
  scan semantics.
- **Schema validation on required fields.** Today `semantic_ir`,
  `release_allowed`, and `tenant_ids` are optional, so dropping them yields a
  weaker but valid trace. A strict profile ("this exporter always sets these
  fields") would make their absence a validation error.
- **Self-test canaries.** Ship one known-bad and one known-good canary trace
  with every scan and assert that the known-bad trace produces its expected
  finding and the known-good one produces none. This converts
  `emit_drops_release_findings`, `emit_downgrades_severity`,
  `gate_always_passes`, `state_eval_ignores_forbidden_values`, and both SQL
  guard mutations into LOUD failures, because the canary expectation breaks.
- **Gate cross-check.** Recompute the gate from the written `findings.jsonl`
  in a separate step (or in CI) and compare with `scan.json`'s gate. Catches
  `gate_always_passes` and `emit_downgrades_severity`.
- **Result-shape assertions.** `require_columns` on state assertions already
  exists and would catch `db_renames_result_columns`; the fixture deliberately
  omits it to show the default. Pairing every `forbidden_values` check with
  `require_columns` and an `expected_rows` bound would also catch
  `db_truncates_result_rows`.
- **Duplicate-id rejection.** `assign_witness_paths` silently renames duplicate
  finding ids (`*_2`). Treating a duplicate id as an internal error would make
  `emit_duplicates_static_findings` LOUD.
- **SQL guard property tests.** The guard is a token filter; a small fixed
  corpus of must-accept and must-reject statements run at scan start would
  catch both a weakened and an over-strict guard before any trace is read.

The catalog is intentionally re-runnable: apply a mitigation, rerun
`uv run scripts/tcb-mutation-report.py`, and update the pinned expectations in
`tests/test_tcb_mutation.py`. The goal is to drive the silent count (16 of 18)
toward zero.
