# Trace Interoperability

PolicyStrata keeps core execution independent from external eval frameworks. Interoperability is
provided through adapters and stable JSON artifacts.

## Stable Core Artifacts

- `traces.jsonl`: deterministic trace records.
- `summary.json`: aggregate suite metrics.
- `metadata.json`: domain, suite, version, operator, and surface-contract metadata.
- `witnesses/*.json`: minimized witness records.
- scanner `scan.json`, `findings.jsonl`, `report.md`, and optional SARIF.

Fields should be added compatibly. Existing fields should not be renamed or repurposed.

## Export Adapters

Use:

```bash
policystrata export runs/example --format inspect --out runs/example/inspect.jsonl
policystrata export runs/example --format benchflow --out runs/example/benchflow.json
```

The exports are adapter files, not runtime dependencies. PolicyStrata does not require Inspect,
BenchFlow, OpenTelemetry, or OpenInference to run deterministic suites.

## Conceptual Trace Mapping

| PolicyStrata field | External eval concept |
| --- | --- |
| `task_id` | case/task ID |
| `request` | input/user request |
| `semantic_ir` | structured action or plan |
| `surface_versions` | harness/environment version vector |
| `compiled_sql` | tool action |
| `db_result` | world-state observation |
| `release_decision` | final output/release guard |
| `witness_class` | deterministic score class |
| `localized_surface` | failing span/surface |
| `containment_layer` | state-diff containment evidence |

For model-mediated experiments, log model ID, prompt/tool schema versions, retry policy, sampling
settings, and attempt index outside the deterministic core trace or in compatible optional fields.
