#!/usr/bin/env python
"""Run the higher-order (compound) mutation study across built-in domains.

Writes one JSON report per domain plus a combined summary. Deterministic; no
LLM API key required.

Usage:
    uv run python scripts/compound-study.py --out runs/compound
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from policystrata.compound import run_compound_study
from policystrata.domain import BUILTIN_DOMAINS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Higher-order compound mutation study.")
    parser.add_argument("--out", type=Path, default=Path("runs/compound"))
    parser.add_argument("--orders", default="2,3")
    parser.add_argument("--per-order", type=int, default=60)
    args = parser.parse_args(argv)

    orders = tuple(int(part.strip()) for part in args.orders.split(",") if part.strip())
    args.out.mkdir(parents=True, exist_ok=True)

    combined: dict[str, dict[str, float | int]] = {}
    for domain in BUILTIN_DOMAINS:
        report = run_compound_study(domain, orders=orders, per_order=args.per_order)
        (args.out / f"{domain}.json").write_text(
            json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        combined[domain] = {
            "total": report.total,
            "detection_rate": report.detection_rate,
            "attribution_accuracy": report.attribution_accuracy,
            "class_accuracy": report.class_accuracy,
        }
        print(
            f"{domain}: total={report.total} detection={report.detection_rate:.3f} "
            f"attribution={report.attribution_accuracy:.3f} class={report.class_accuracy:.3f}"
        )

    (args.out / "combined.json").write_text(
        json.dumps(combined, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
