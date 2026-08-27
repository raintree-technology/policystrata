# arXiv Submission Fields

## Title

PolicyStrata: Responsibility-Scoped Testing for Cross-Layer Policy Drift in LLM Data Agents

## Authors

Zachary Roth

## Abstract

LLM data agents translate natural-language requests into semantic plans, SQL queries, and analytical answers. Existing evaluations emphasize text-to-SQL correctness, malformed-output reduction, or model refusal behavior. Deployed agents also replicate authorization, semantic, lineage, version, and release obligations across model-visible manifests, grammars, validators, compilers, database controls, and output filters. These non-equivalent surfaces can drift after policy, schema, or semantic model updates, producing failures that component tests miss.

We present PolicyStrata, a regression-testing framework for cross-layer policy drift in governed data-agent stacks. PolicyStrata generates principals, requests, plans, mixed-version surface configurations, database states, and lowered queries, then checks whether each surface preserves its assigned authorization, semantic, lineage, containment, and release obligations. Its minimized witnesses identify the first violated transition. The artifact includes DataPolicyDriftBench, a deterministic benchmark with three analytics domains; seeded, generated, detector-frozen held-out, and clean-control suites; baseline comparators; ablations; JSONL traces; optional database smoke fixtures; and a brownfield integration check. On deterministic, non-equivalent mutant suites generated from the implemented operators and fixtures, PolicyStrata reports witnesses for all 1720 covered injected faults, with 0 false positives on 80 clean controls. This is v1 fault-model coverage, not recall on unknown production faults.

## Comments

8 pages. Public artifact and reproducibility kit available at https://github.com/raintree-technology/policystrata.

## Suggested Category

Primary: cs.SE

Optional cross-list: cs.CR

## Public Artifact Links

- Repository: https://github.com/raintree-technology/policystrata
- Paper PDF: https://raintree.technology/papers/PolicyStrata.pdf
- Release note: https://raintree.technology/blog/policystrata-release
- Artifact zip: https://github.com/raintree-technology/policystrata/releases/download/policystrata-paper-2026-06-26/policystrata-submission-kit-2026-06-26.zip

## Local Upload File

- arXiv source zip: `/Users/mb1/Code/raintree/papers/conference-kit/submissions/arxiv-public-preprint/policystrata-arxiv-source.zip`
- SHA256: `c83fe33345306699d373bce1e4adec3805a772721e65f9f2f31e3158558b2d7c`
