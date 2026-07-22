#!/usr/bin/env python3
"""Run the adapter-TCB mutation catalog and print the markdown report.

Usage: uv run scripts/tcb-mutation-report.py
The table output is pasted into docs/tcb-analysis.md.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from policystrata.tcb_catalog import (  # noqa: E402
    CATALOG,
    outcome_tally,
    render_markdown_report,
    run_catalog,
)


def main() -> int:
    fixture_dir = ROOT / "tests" / "fixtures" / "tcb"
    with tempfile.TemporaryDirectory() as tmp:
        results = run_catalog(fixture_dir, Path(tmp))
    tally = outcome_tally(results)
    silent = tally.get("HIDDEN", 0) + tally.get("INVENTED", 0)
    print(render_markdown_report(results))
    print()
    print(
        f"Tally: {len(CATALOG)} adapter mutations — "
        + ", ".join(f"{name}={tally.get(name, 0)}" for name in ("HIDDEN", "INVENTED", "NEUTRAL", "LOUD"))
    )
    print(f"Silent (HIDDEN or INVENTED): {silent} of {len(CATALOG)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
