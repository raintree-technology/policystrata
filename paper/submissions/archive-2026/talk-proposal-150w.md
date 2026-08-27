# Talk Proposal: Testing Policy Drift in LLM Data Agents

LLM data agents often fail between layers, not inside one model call. A metric may be visible in a
model manifest, accepted by a semantic validator, lowered by a SQL compiler, contained or missed by
database policy, and finally released through an output filter. Each layer can look reasonable on
its own while the composition violates authorization, semantic, or release obligations.

This talk presents PolicyStrata, a deterministic research artifact for testing cross-layer policy
drift in governed LLM data-agent stacks. We will walk through a concrete tenant-isolation failure,
show how responsibility-scoped contracts differ from naive surface equality, and demo how minimized
database-backed witnesses identify the first violated transition. The artifact includes
DataPolicyDriftBench, seeded, generated, held-out, and clean-control suites, baseline comparators,
JSONL traces, and optional database smoke fixtures.

The takeaway: valid SQL is not enough; teams need regression tests for policy obligations as data
agent requests move across representations.
