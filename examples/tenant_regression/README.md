# Reproduce a tenant-rule regression

This exercise lets a maintainer check one PolicyStrata failure and its correction. It uses synthetic data and the existing offline scanner. No database, model key, or customer data is required.

## Verified result

Using source revision `420dc2b` (package version 1.1.3), the scanner rejected a query with `accounts.legacy_tenant_id` where the configured policy required `accounts.tenant_id`. Restoring the correct predicate produced a passing scan.

| Query predicate | Findings | Gate | Exit code |
| --- | ---: | --- | ---: |
| Stale tenant field | 1 | Fail | 1 |
| Correct tenant field | 0 | Pass | 0 |

The trace’s fixture expectations were removed before both scans. The check uses the configured policy and scanner behavior. It does not execute SQL or verify live row-level security. The built-in demo separately models database containment and blocked release. Neither result establishes detection of unknown production failures.

## Run the exercise

Prerequisites: Python 3.10 or later, uv, and a checkout of this repository. The first run needs network access to install the project’s locked dependencies. Use a new output directory to preserve previous evidence.

1. Open a terminal in the repository root.
2. Run the saved script, using a new output directory:

   ```sh
   python3 examples/tenant_regression/reproduce.py --out runs/tenant-regression
   ```

3. Read `transcript.txt`, `before/report.md`, and the broken and fixed traces in the output directory. Confirm one failed scan and one passing scan.

The script asserts both exit codes. A failed assertion means the expected result was not reproduced.

## External setup attempt

No external maintainer has completed this exercise yet. Give a participant the source revision, script, and these instructions without explaining the implementation. Ask them to:

1. Reproduce both scans without assistance.
2. Identify the changed predicate and explain why the scanner rejects it.
3. Explain what the passing result does and does not establish.
4. Describe what they would need to export from their own system to try the scanner.

Record setup time, failed commands, questions, assistance given, and any inaccurate conclusions. Remove identifying or sensitive information before sharing the notes. An attempt using this fixture tests setup and comprehension; adoption requires use in the participant’s own system on later revisions.

