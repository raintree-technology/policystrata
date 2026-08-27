#!/usr/bin/env bash
set -euo pipefail

kit_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
papers_root="$(cd "${kit_dir}/.." && pwd)"
artifact_root="${POLICYSTRATA_ARTIFACT_ROOT:-${papers_root}/../policystrata}"
run_root="${RUN_ROOT:-runs/conference-kit}"

if ! command -v uv >/dev/null 2>&1; then
  echo "error: uv is required to reproduce the artifact" >&2
  exit 1
fi

if [[ ! -f "${artifact_root}/pyproject.toml" ]]; then
  echo "error: artifact checkout not found at ${artifact_root}" >&2
  echo "set POLICYSTRATA_ARTIFACT_ROOT=/path/to/policystrata" >&2
  exit 1
fi

cd "${artifact_root}"

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

uv run policystrata scan \
  --config examples/postgres_dbt/policystrata_clean.yaml \
  --out "${run_root}/scan-clean"

uv run policystrata export \
  "${run_root}/seeded" \
  --format inspect \
  --out "${run_root}/seeded/inspect.jsonl"
uv run policystrata export \
  "${run_root}/seeded" \
  --format benchflow \
  --out "${run_root}/seeded/benchflow.json"

grep -q "| seeded | 50 | 50 | 0 |" "${run_root}/evidence.md"
grep -q "| generated | 500 | 500 | 0 |" "${run_root}/evidence.md"
grep -q "| generated_alt_seed | 50 | 50 | 0 |" "${run_root}/evidence.md"
grep -q "| finance_saas | 20 | 20 | 0 |" "${run_root}/evidence.md"

cat <<EOF
PolicyStrata reproduction complete.

Evidence:
  ${artifact_root}/${run_root}/evidence.md

Scanner smoke test:
  ${artifact_root}/${run_root}/scan-clean/report.md

Exports:
  ${artifact_root}/${run_root}/seeded/inspect.jsonl
  ${artifact_root}/${run_root}/seeded/benchflow.json
EOF
