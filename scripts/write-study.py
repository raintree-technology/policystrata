#!/usr/bin/env python
"""Write-action (v2) fault-model study.

Deterministic; no LLM API key required.

Usage:
    uv run python scripts/write-study.py --out runs/writes.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from policystrata.writes import (
    WRITE_OPERATORS,
    evaluate_write_task,
    generate_clean_write_controls,
    generate_write_tasks,
    run_write_study,
    summarize_writes,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write-action fault-model study.")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--per-operator", type=int, default=6)
    parser.add_argument("--clean-count", type=int, default=40)
    args = parser.parse_args(argv)

    summary = run_write_study(per_operator=args.per_operator, clean_count=args.clean_count)
    per_operator = {}
    for operator_id in WRITE_OPERATORS:
        traces = [evaluate_write_task(t) for t in generate_write_tasks(per_operator=args.per_operator)
                  if t.operator == operator_id]
        s = summarize_writes(traces)
        per_operator[operator_id] = {
            "killed": s.killed,
            "localization_accuracy": s.localization_accuracy,
            "containment_rate": s.containment_rate,
            "uncontained_commits": s.uncontained_commits,
        }

    payload = {"summary": summary.model_dump(mode="json"), "per_operator": per_operator}
    if args.out is not None:
        args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"out": str(args.out)}, sort_keys=True))
    else:
        print(
            f"writes: total={summary.total} killed={summary.killed} "
            f"clean={summary.clean_controls} fp={summary.false_positives} "
            f"localization={summary.localization_accuracy:.2f} "
            f"containment={summary.containment_rate:.2f} "
            f"uncontained_commits={summary.uncontained_commits}"
        )
    _ = generate_clean_write_controls
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
