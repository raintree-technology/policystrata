#!/usr/bin/env python
"""Replay source-contract probes against historical Git revisions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from policystrata.revision_replay import (
    load_replay_cases,
    render_report,
    replay_cases,
    write_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    cases = load_replay_cases(args.manifest)
    results = replay_cases(args.repository, cases)
    report = render_report(args.repository, args.manifest, results)
    if args.out:
        write_report(args.out, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if all(result.reproduced for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
