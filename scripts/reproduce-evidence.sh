#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
run_root_input="${RUN_ROOT:-$root/runs/final}"
if [[ "$run_root_input" = /* ]]; then
  run_root="$run_root_input"
else
  run_root="$root/$run_root_input"
fi

POLICYSTRATA_RUN_ROOT="${run_root}" "${root}/scripts/reproduce-final.sh" >/dev/null
printf '%s\n' "${run_root}/evidence.md"
