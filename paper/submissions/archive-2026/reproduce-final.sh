#!/usr/bin/env bash
set -euo pipefail

kit_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
papers_root="$(cd "${kit_dir}/.." && pwd)"
artifact_root="${POLICYSTRATA_ARTIFACT_ROOT:-${papers_root}/../policystrata}"

if [[ ! -x "${artifact_root}/scripts/reproduce-final.sh" ]]; then
  echo "error: final reproduction script not found at ${artifact_root}/scripts/reproduce-final.sh" >&2
  echo "set POLICYSTRATA_ARTIFACT_ROOT=/path/to/policystrata" >&2
  exit 1
fi

POLICYSTRATA_RUN_ROOT="${POLICYSTRATA_RUN_ROOT:-${artifact_root}/runs/final}" \
  "${artifact_root}/scripts/reproduce-final.sh"
