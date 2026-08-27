# Archival Abstract

## Recommended first archival lane

Target the next software-testing/software-engineering research cycle rather than forcing the current 2026 main-track deadlines, which have already passed for ISSTA, ASE, and FSE. The strongest framing remains:

**Cross-layer policy drift testing for LLM data agents.**

## Title

PolicyStrata: Responsibility-Scoped Conformance Testing for Governed LLM Data Agents

## Abstract

LLM data agents translate natural-language requests into semantic plans, SQL queries, and user-facing analytical answers. Existing evaluations emphasize text-to-SQL correctness, malformed-output reduction, or model refusal behavior, but deployed agents also replicate authorization, semantic, and release policies across model-visible manifests, grammars, validators, compilers, database controls, and output filters. These surfaces can drift after policy, schema, or semantic-model updates, producing failures that component-level tests miss.

PolicyStrata is a regression-testing framework for cross-layer policy drift in governed data-agent stacks. Given canonical authorization, semantic, and release specifications plus implementation surfaces, PolicyStrata generates principals, requests, semantic plans, mixed-version surface configurations, database states, and lowerings; checks responsibility-scoped conformance contracts; and emits minimized witnesses for the first violated transition. The artifact includes DataPolicyDriftBench, a deterministic benchmark with three analytics domains; seeded, generated, detector-frozen held-out, and clean-control suites; baseline comparators; ablations; JSONL traces; optional database smoke fixtures; and a brownfield integration check. On controlled deterministic non-equivalent mutant suites, PolicyStrata reports witnesses for 1720/1720 injected faults covered by the implemented operators and fixtures, with 0 false positives on 80 clean controls. These results establish deterministic artifact-suite coverage and feasibility, not recall on unknown production faults.

## Submission posture

Use the anonymous PDF for double-blind venues. Keep the public PDF, live website, GitHub repository, and Raintree branding out of the submitted manuscript unless the venue is single-blind or explicitly allows public artifacts during review.
