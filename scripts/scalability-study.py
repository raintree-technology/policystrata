#!/usr/bin/env python
"""Scalability study: detector throughput curves and covering-array savings.

Deterministic; no LLM API key required.

Usage:
    uv run python scripts/scalability-study.py --out runs/scalability
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from policystrata.domain import BUILTIN_DOMAINS
from policystrata.scalability import (
    covering_array,
    factor_scaling,
    throughput_curve,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scalability and covering-array study.")
    parser.add_argument("--out", type=Path, default=Path("runs/scalability"))
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    throughput = {
        domain: throughput_curve(domain).model_dump(mode="json") for domain in BUILTIN_DOMAINS
    }
    (args.out / "throughput.json").write_text(
        json.dumps(throughput, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    for domain, curve in throughput.items():
        last = curve["points"][-1]
        print(f"{domain}: {last['cases']} cases in {last['total_ms']:.1f}ms "
              f"({last['mean_ms_per_case']:.3f}ms/case)")

    example = covering_array(
        {
            "principal": [f"p{i}" for i in range(8)],
            "role": [f"r{i}" for i in range(4)],
            "schema_object": [f"s{i}" for i in range(8)],
            "operator": [f"op{i}" for i in range(21)],
        },
        strength=2,
    )
    (args.out / "covering_array_example.json").write_text(
        json.dumps(example.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"pairwise covering array: {example.covering_array_size} cases vs "
        f"{example.full_cross_product} full cross ({example.reduction_ratio:.1%} fewer)"
    )

    scaling = [point.model_dump(mode="json") for point in factor_scaling()]
    (args.out / "factor_scaling.json").write_text(
        json.dumps(scaling, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    for point in scaling:
        print(
            f"principals={point['principals']}: covering={point['covering_array_size']} "
            f"vs full={point['full_cross_product']} ({point['reduction_ratio']:.1%} fewer)"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
