"""Keep the paper's precision population distinct from adapter demo cases."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_brownfield_population_accounting() -> None:
    primary: list[dict[str, object]] = []
    inventory: list[dict[str, object]] = []
    for target in ("metricflow", "midday", "WrenAI", "cube"):
        traces = [
            json.loads(line)
            for line in (ROOT / "examples/brownfield" / target / "traces.jsonl")
            .read_text()
            .splitlines()
            if line.strip()
        ]
        inventory.extend(traces)
        primary.extend(
            trace
            for trace in traces
            if trace.get("regression_case") in (None, "pass_to_pass", "allow_to_allow")
        )
    clean_variant = [
        json.loads(line)
        for line in (ROOT / "examples/brownfield/cube/traces_clean.jsonl")
        .read_text()
        .splitlines()
        if line.strip()
    ]
    assert len({trace["id"] for trace in primary}) == len(primary) == 75
    assert len(inventory) + len(clean_variant) == 79
    assert len(inventory) - len(primary) == 3
    assert len(clean_variant) == 1
    assert round(100 / len(primary), 1) == 1.3
    assert "75 real-SQL traces" in (ROOT / "paper/main.tex").read_text()
    results = (ROOT / "paper/sections/07-results.tex").read_text()
    assert "Brownfield SQL & 75" in results
    assert "(1.3\\%)" in results
