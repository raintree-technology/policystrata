#!/usr/bin/env bash
set -euo pipefail

run_root="${RUN_ROOT:-runs/repro}"

rm -rf "${run_root}"
mkdir -p "${run_root}"

uv run policystrata run --domain support_saas --suite seeded --out "${run_root}/seeded"
uv run policystrata run \
  --domain support_saas \
  --suite generated \
  --count 500 \
  --seed 1729 \
  --out "${run_root}/generated"
uv run policystrata run \
  --domain support_saas \
  --suite generated_alt_seed \
  --out "${run_root}/generated_alt_seed"
uv run policystrata run --domain finance_saas --suite seeded --out "${run_root}/finance"
uv run policystrata evidence \
  seeded="${run_root}/seeded" \
  generated="${run_root}/generated" \
  generated_alt_seed="${run_root}/generated_alt_seed" \
  finance_saas="${run_root}/finance" \
  --out "${run_root}/evidence.md"

printf '%s\n' "${run_root}/evidence.md"
