"""Run a synthetic SQL regression through the existing PolicyStrata scanner."""

import argparse
import json
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[2])
parser.add_argument("--out", type=Path, required=True)
args = parser.parse_args()
out = args.out.resolve()
if out.exists():
    parser.error("--out must be a new directory; existing evidence is preserved")
out.mkdir(parents=True)
log = []


def run(*parts):
    command = ["uv", "run", "--locked", "--no-dev", "policystrata", *map(str, parts)]
    result = subprocess.run(command, cwd=args.source.resolve(), text=True, capture_output=True)
    log.extend(["$ " + " ".join(command), result.stdout, result.stderr, f"Exit: {result.returncode}\n"])
    return result.returncode


assert run("init-scan", "--out", out / "fixture") == 0
trace_path = out / "fixture/traces.example.jsonl"
original = trace_path.read_text()
trace = json.loads(original)
assert "accounts.tenant_id in ('acme')" in trace["sql"]
trace["sql"] = trace["sql"].replace("accounts.tenant_id in ('acme')", "accounts.legacy_tenant_id in ('acme')")
trace.pop("expected_policy", None)
trace.pop("regression_case", None)
trace_path.write_text(json.dumps(trace) + "\n")
before = run("scan", "--config", out / "fixture/policystrata.yaml", "--out", out / "before")
(out / "broken-trace.jsonl").write_text(trace_path.read_text())
trace["sql"] = trace["sql"].replace("accounts.legacy_tenant_id", "accounts.tenant_id")
trace_path.write_text(json.dumps(trace) + "\n")
after = run("scan", "--config", out / "fixture/policystrata.yaml", "--out", out / "after")
(out / "fixed-trace.jsonl").write_text(trace_path.read_text())
(out / "transcript.txt").write_text("\n".join(log))
assert before == 1, f"Expected scanner rejection, got {before}"
assert after == 0, f"Expected passing scan, got {after}"
findings = [json.loads(line) for line in (out / "before/findings.jsonl").read_text().splitlines()]
assert len(findings) == 1, f"Expected one tenant finding, got {len(findings)}"
assert findings[0]["id"] == "tenant_scope_missing_example_ticket_count"
assert findings[0]["surface"] == "compiler"
assert findings[0]["witness_class"] == "lowering_violation"
assert not (out / "after/findings.jsonl").read_text().strip(), "Repair left findings"
print(f"PASS: stale tenant predicate rejected ({before}); corrected predicate passed ({after}).")
print(f"Evidence: {out}")
