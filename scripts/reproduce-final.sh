#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
run_root_input="${POLICYSTRATA_RUN_ROOT:-$ROOT/runs/final}"
if [[ "$run_root_input" = /* ]]; then
  RUN_ROOT="$run_root_input"
else
  RUN_ROOT="$ROOT/$run_root_input"
fi
FREEZE_ROOT="$RUN_ROOT/freeze"
EXPORT_ROOT="$RUN_ROOT/exports"

mkdir -p "$FREEZE_ROOT" "$EXPORT_ROOT"
cd "$ROOT"

uv run policystrata doctor

uv run policystrata freeze-benchmark \
  --domain support_saas \
  --suite generated \
  --count 500 \
  --seed 1729 \
  --out "$FREEZE_ROOT/support-generated.json"

uv run policystrata freeze-benchmark \
  --domain support_saas \
  --suite heldout_v1 \
  --count 500 \
  --seed 260626 \
  --out "$FREEZE_ROOT/support-heldout-v1.json"

uv run policystrata freeze-benchmark \
  --domain finance_saas \
  --suite heldout_v1 \
  --count 250 \
  --seed 260626 \
  --out "$FREEZE_ROOT/finance-heldout-v1.json"

uv run policystrata freeze-benchmark \
  --domain analytics_clickhouse \
  --suite generated \
  --count 300 \
  --seed 260626 \
  --out "$FREEZE_ROOT/analytics-clickhouse-generated.json"

uv run policystrata freeze-benchmark \
  --domain support_saas \
  --suite clean_controls \
  --count 80 \
  --seed 260627 \
  --out "$FREEZE_ROOT/support-clean-controls.json"

uv run policystrata run \
  --domain support_saas \
  --suite seeded \
  --out "$RUN_ROOT/support-seeded"

uv run policystrata run \
  --domain support_saas \
  --suite generated \
  --count 500 \
  --seed 1729 \
  --freeze-manifest "$FREEZE_ROOT/support-generated.json" \
  --out "$RUN_ROOT/support-generated"

uv run policystrata run \
  --domain support_saas \
  --suite heldout_v1 \
  --count 500 \
  --seed 260626 \
  --freeze-manifest "$FREEZE_ROOT/support-heldout-v1.json" \
  --out "$RUN_ROOT/support-heldout-v1"

uv run policystrata run \
  --domain finance_saas \
  --suite seeded \
  --out "$RUN_ROOT/finance-seeded"

uv run policystrata run \
  --domain finance_saas \
  --suite heldout_v1 \
  --count 250 \
  --seed 260626 \
  --freeze-manifest "$FREEZE_ROOT/finance-heldout-v1.json" \
  --out "$RUN_ROOT/finance-heldout-v1"

uv run policystrata run \
  --domain analytics_clickhouse \
  --suite seeded \
  --out "$RUN_ROOT/analytics-clickhouse-seeded"

uv run policystrata run \
  --domain analytics_clickhouse \
  --suite generated \
  --count 300 \
  --seed 260626 \
  --freeze-manifest "$FREEZE_ROOT/analytics-clickhouse-generated.json" \
  --out "$RUN_ROOT/analytics-clickhouse-generated"

uv run policystrata run \
  --domain support_saas \
  --suite clean_controls \
  --count 80 \
  --seed 260627 \
  --freeze-manifest "$FREEZE_ROOT/support-clean-controls.json" \
  --out "$RUN_ROOT/clean-controls"

uv run policystrata baselines \
  "$RUN_ROOT/support-seeded" \
  "$RUN_ROOT/support-generated" \
  "$RUN_ROOT/support-heldout-v1" \
  "$RUN_ROOT/finance-seeded" \
  "$RUN_ROOT/finance-heldout-v1" \
  "$RUN_ROOT/analytics-clickhouse-seeded" \
  "$RUN_ROOT/analytics-clickhouse-generated" \
  --out "$RUN_ROOT/baselines.json"
uv run policystrata ablations \
  "$RUN_ROOT/support-seeded" \
  "$RUN_ROOT/support-generated" \
  "$RUN_ROOT/support-heldout-v1" \
  "$RUN_ROOT/finance-seeded" \
  "$RUN_ROOT/finance-heldout-v1" \
  "$RUN_ROOT/analytics-clickhouse-seeded" \
  "$RUN_ROOT/analytics-clickhouse-generated" \
  --out "$RUN_ROOT/ablations.json"
uv run policystrata export "$RUN_ROOT/support-heldout-v1" --format inspect --out "$EXPORT_ROOT/inspect.jsonl"
uv run policystrata export "$RUN_ROOT/support-heldout-v1" --format benchflow --out "$EXPORT_ROOT/benchflow.json"

uv run policystrata evidence \
  support_seeded="$RUN_ROOT/support-seeded" \
  support_generated="$RUN_ROOT/support-generated" \
  support_heldout_v1="$RUN_ROOT/support-heldout-v1" \
  finance_seeded="$RUN_ROOT/finance-seeded" \
  finance_heldout_v1="$RUN_ROOT/finance-heldout-v1" \
  analytics_clickhouse_seeded="$RUN_ROOT/analytics-clickhouse-seeded" \
  analytics_clickhouse_generated="$RUN_ROOT/analytics-clickhouse-generated" \
  clean_controls="$RUN_ROOT/clean-controls" \
  --out "$RUN_ROOT/evidence.md"

uv run policystrata artifact-report "$RUN_ROOT/support-heldout-v1" --out "$RUN_ROOT/artifact-report.md"

printf 'Final PolicyStrata reproduction artifacts written to %s\n' "$RUN_ROOT"
