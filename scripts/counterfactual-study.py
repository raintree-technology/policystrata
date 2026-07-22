#!/usr/bin/env python
"""Run counterfactual-repair validation of attribution across built-in domains.

Deterministic; no LLM API key required.

Usage:
    uv run python scripts/counterfactual-study.py --out runs/counterfactual
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from policystrata.counterfactual import run_counterfactual_study
from policystrata.domain import BUILTIN_DOMAINS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Counterfactual-repair attribution validation.")
    parser.add_argument("--out", type=Path, default=Path("runs/counterfactual"))
    parser.add_argument("--orders", default="2,3")
    parser.add_argument("--per-order", type=int, default=60)
    args = parser.parse_args(argv)

    orders = tuple(int(part.strip()) for part in args.orders.split(",") if part.strip())
    args.out.mkdir(parents=True, exist_ok=True)

    combined: dict[str, dict[str, float | int]] = {}
    for domain in BUILTIN_DOMAINS:
        report = run_counterfactual_study(domain, orders=orders, per_order=args.per_order)
        (args.out / f"{domain}.json").write_text(
            json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        combined[domain] = {
            "total": report.total,
            "validity_rate": report.validity_rate,
            "sufficiency_rate": report.sufficiency_rate,
            "necessity_rate": report.necessity_rate,
        }
        print(
            f"{domain}: total={report.total} valid={report.validity_rate:.3f} "
            f"sufficiency={report.sufficiency_rate:.3f} necessity={report.necessity_rate:.3f}"
        )

    (args.out / "combined.json").write_text(
        json.dumps(combined, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
