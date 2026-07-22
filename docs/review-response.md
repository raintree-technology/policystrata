# Review Response

This maps each external-review item to what changed in the repo. Every study is
deterministic with its own reproduction script and doc; none require an LLM API
key unless noted. All numbers here were run, not estimated.

## Framing and CI

- **Lead with the defense-in-depth gap, not 1720/1720.** The README and evidence
  snapshot now lead with the 159-miss gap (a layered stack of conventional
  controls misses 159/1720 that responsibility contracts catch) and state that
  1720/1720 is a consistency check over the operator taxonomy, 100% by
  construction. ([README.md](../README.md), [evidence.md](evidence.md))
- **CI runs on pull requests.** `ci.yml` triggered only on `workflow_dispatch`;
  it now runs on push and pull_request, and the PostgreSQL job runs by default
  (was dispatch-only). A ClickHouse integration job was added.

## Tier 1 — External validity

- **Item 1, reconstructed real-fault suite.** 25 real public faults mined and
  citation-verified (PostgreSQL RLS CVEs, Supabase/Lovable RLS incidents,
  ClickHouse/Cube/MetricFlow/Superset issues). 19 reconstructed as deterministic
  fixtures mapped to existing operators (19/19 killed, 100% localization); 6
  dropped honestly (over-restrictive direction the taxonomy can't express, RCE
  faults outside the model, one unconfirmed outcome). Recall is reported
  separately from synthetic kills.
  ([incident-reconstruction-results.md](incident-reconstruction-results.md),
  `benchmarks/incident_reconstruction/MAPPING.md`)
- **Item 2, brownfield on real OSS stacks.** Scanned four real open-source
  data-agent stacks (metricflow, cube, WrenAI, midday). Honest outcome: **zero
  new real bugs discovered** (0 class-(a) findings). The value is a real
  false-positive measurement — ~1.4% (1 of 74 real-SQL traces) genuine
  content-level false positive — and a clean true-positive demo: the cube scan
  caught cube's *own* intentionally-broken ACL fixtures (which cube's test suite
  already asserts are rejected) while passing its correctly-configured fixture.
  The pass also surfaced 5 concrete scanner gaps. The two most consequential are
  now **fixed**: the hardcoded `accounts.tenant_id` tenant-column fallback for
  custom domains (which inflated metricflow to 163 findings — now 95, with 0
  spurious tenant-scope findings) and the lack of per-table tenancy config (now a
  `table_tenant_columns` map). Built-in behavior and true-positive detection are
  unchanged; gaps 3–5 remain documented. ([brownfield-results.md](brownfield-results.md),
  `tests/test_scanner_tenancy_fallback.py`)
- **Item 3, spec-blind mutant suite.** 42 mutants authored from the contract
  spec without detector access. The detector agrees on 39/42 (100% localization,
  92.9% class accuracy); the 3 misses expose a genuine contract ambiguity (the
  cost-combination rule is in no contract doc). A procedural deviation is
  disclosed in the doc. ([spec-blind-results.md](spec-blind-results.md))
- **Item 4, higher-order mutants.** Compound cases stack 2–3 distinct-surface
  skews; first-transition attribution is stable under composition (a correctness
  property of the merge, not a discovery result), with containment correctly
  dropped when the containing layer is itself skewed.
  ([compound-mutants.md](compound-mutants.md))

## Tier 2 — Put the LLM back in the loop

- **Items 5–7, reachability harness (build-only).** A harness that asks a model
  to emit semantic queries from paraphrase sets under a manifest-derived prompt,
  with a repair budget, and checks which latent drifts are reachable; plus a
  manifest-skew behavioral probe showing a version-skewed manifest changes the
  emitted plan. No paid runs were made (guarded behind an explicit env flag);
  stub results are harness verification only. ([reachability.md](reachability.md))

## Tier 3 — Baselines and attribution

- **Item 8, real comparators.** Added `conventional_test_suite` (a competent
  engineer's spec-derived test suite: 1579/1720, 141 misses) and
  `property_differential` (Cedar-style pairwise differential: 899/1720). Both
  flag 0/80 clean controls. These replace the strawman framing.
  ([evidence.md](evidence.md) baselines table)
- **Item 9, attribution accuracy — done as counterfactual repair.** Plain
  localization accuracy is circular. Counterfactual repair validates attribution
  interventionally: repair the attributed layer and the witness must disappear
  (sufficiency); repair another layer and attribution must persist (necessity).
  100% valid across domains, and a teeth-test confirms a broken attribution is
  rejected. ([counterfactual-repair.md](counterfactual-repair.md))
- **Item 10, quantify minimization.** Per-witness pre/post bytes, full-witness
  and semantic-IR reduction ratios, 1-minimality, and wall time. Honest finding:
  reduction is small because inputs are already narrow, and the bounded reducer
  reaches 1-minimality on the standard suites but does not guarantee it.
  ([minimization-metrics.md](minimization-metrics.md))

## Tier 4 — Scale, false positives, engines

- **Item 11, scalability + covering arrays.** A deterministic greedy pairwise
  covering-array generator (verified: all pairs covered) that cuts cases ~90%
  vs the full cross product, plus flat per-case throughput curves.
  ([scalability.md](scalability.md))
- **Item 12, adversarial clean controls at scale.** 1000+ clean controls per
  domain (staged rollout, feature flag, boundary budget, service-account ambient
  authority, legitimately-denied requests). Detector false positives 0/1000; a
  naive denial-flagging baseline is 285/1000. Honest limit: in the simulator
  clean controls can't trip decision-based detectors, so strong benign-skew
  precision evidence still comes from the scanner on real inputs. The shipped
  80-case suite is byte-identical (pinned by a test).
  ([adversarial-clean-controls.md](adversarial-clean-controls.md))
- **Item 13, database containment.** PostgreSQL RLS was already real; its CI job
  now runs by default. Added a real ClickHouse row-policy adapter, DDL fixture,
  env-gated integration tests, evidence script, and CI job — verified against a
  real ClickHouse 25.6 server. ([clickhouse.md](clickhouse.md))
- **Item 14, trusted-computing-base test.** In-process adapter mutation testing:
  16 of 18 adapter mutations silently corrupt scan output today (hide or invent
  findings); only 1 is loud. Documented with mitigations.
  ([tcb-analysis.md](tcb-analysis.md))

## Tier 5 — Formal depth and v2 scope

- **Item 15, soundness + completeness.** Soundness (witness ⇒ contract
  violation) is checked with Hypothesis (400 examples) plus an exhaustive sweep,
  zero counterexamples; completeness is characterized per fault class rather than
  claimed globally. ([soundness-completeness.md](soundness-completeness.md))
- **Item 16, fault-model extension — write actions, done properly.** A
  self-contained write-action model (INSERT/UPDATE/DELETE) with its own witness
  classes, surfaces, operators, simulator, and first-transition detector; write
  containment via database `WITH CHECK`. 48/48 killed, 0 false positives, 100%
  localization. The other v2 dimensions were left for later rather than added
  shallowly. ([write-actions.md](write-actions.md))
- **Item 17, benchmark productization.** Difficulty tiers derived from the
  baseline kill matrix, tied to the existing freeze/verify versioning and the
  Inspect/BenchFlow export adapters. Leaderboard and third-party reproduction
  remain external. ([benchmark-release.md](benchmark-release.md))

## Paper-grade classification

Not every study belongs in the paper. Graded by whether it changes what the
paper can claim or directly answers the reviewer.

### Paper-grade — put these in the paper

- **The 159-miss reframing.** This is the paper's actual argument (a layered
  conventional stack misses 159/1720 that responsibility contracts localize).
  Lead with it; demote 1720/1720 to a construction-consistency check.
- **Real-fault reconstruction (item 1).** 19 cited public faults grounded in the
  operator taxonomy — the strongest answer to "your fault model is self-invented."
- **Brownfield scans (item 2).** Frame honestly: a *null* result on discovery (0
  new bugs) but a positive result on precision (real-input FP rate) and a
  true-positive demo on cube's own broken fixtures, plus 5 real scanner gaps (2
  fixed). It is field evidence, not a bug-count headline.
- **Real baselines (item 8).** `conventional_test_suite` (1579/1720) and
  `property_differential` (899/1720) replace the strawmen; the 141-miss analysis
  is the comparison the paper needs.
- **Counterfactual-repair attribution (item 9).** Replaces circular localization
  accuracy with an interventional validation — a methodological contribution that
  answers the "attribution is circular" criticism directly.
- **Soundness + completeness (item 15).** Witness ⇒ contract violation
  (property-tested + exhaustive) and per-class completeness — a "Properties"
  section, with the honest caveat that it is exhaustively checked, not mechanized.
- **Spec-blind suite (item 3).** 39/42 agreement with an independent reading of
  the contract; the 3 misses expose a genuine contract ambiguity worth reporting.
- **TCB adapter mutation testing (item 14).** 16/18 adapter mutations silently
  corrupt output — the honest threats-to-validity result that measures the
  authors' own trust assumptions.

### Supporting — artifact / appendix, not headline

- **Compound mutants (item 4)** — a stability property, not a discovery; the
  perfect score is a correctness property of the merge.
- **Minimization metrics (item 10)** — corrects an over-claim (small reduction,
  1-minimality not guaranteed); appendix rigor.
- **Scalability + covering arrays (item 11)** — engineering evidence.
- **Adversarial clean controls (item 12)** — 0/1000 FP, but the honest limitation
  (the simulator can't trip a decision-based detector on a clean control) makes
  this appendix material; the real FP evidence is brownfield.

### Artifact / future work — do not present as this paper's evidence

- **ClickHouse adapter (item 13)** — shows containment generalizes to a second
  real engine; an artifact strength, mentioned not headlined.
- **Write-action model (item 16)** — explicitly a v2 dimension; future work.
- **Reachability harness (items 5–7)** — build-only, unrun. Cannot appear as
  evidence; present only as available methodology. The manifest-skew behavioral
  result is a stub, not a model run.
- **Difficulty tiers / benchmark release (item 17)** and **CI-on-PR** — tooling
  and hygiene, not paper claims.

## What was not done, and why

- No public leaderboard, no filed upstream issues, and no paid model runs: these
  require external humans or billed API calls and are outside a code change.
  Brownfield findings include DRAFT upstream issue text, unfiled.
- The spec-blind suite is spec-blind, not independently authored by a third
  party; the reachability harness is built but unrun; the real-fault suite maps
  incidents onto existing operators rather than modeling novel fault mechanics.
  Each doc states its own caveat.
