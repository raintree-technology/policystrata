# Point-by-Point Author Response

This draft responds to every substantive criticism in reviews 38A, 38B, and 38C. “Addressed” means
the paper or artifact now contains a direct answer. “Partial” means the revision adds evidence but
cannot supply the requested external event. “Open” means the requested evidence does not exist and
the paper now says so.

## Review 38A

### A1 - Evaluation is synthetic and BetterOff uses synthetic data

**Status: partial; deployment-linked pilot complete, authenticated and external operation open.**

The abstract, Introduction, Evaluation Results, What Remains Unestablished, and Threats to Validity
now separate a deployment-linked BetterOff pilot from production-effectiveness claims. The pilot
is bound to the exact Git revision and Vercel deployment running in production. It used no customer
rows and made no production mutations. Evidence levels now include:

- 1,720 declared-operator cases for internal regression coverage;
- 42 spec-blind cases for contract clarity;
- 25 public faults screened and 19 mapped to existing drift shapes;
- 74 real-SQL traces from four independent repositories for static adapter behavior;
- 33 passing live public and denial-boundary probes on the BetterOff production deployment;
- three exact historical BetterOff pre/post-fix source-contract replays.

None is described as field-recall evidence. Three authenticated probes remain blocked on an
isolated production smoke principal, and no external team operated the pilot.

### A2 - Construction and representativeness of 1,720 cases are unclear

**Status: addressed.**

Benchmark Construction now states:

- 170 cases are expanded from hand-authored YAML matrices;
- 1,550 are generated algorithmically;
- the exact seeds are 1729, 260626, and 260627;
- operator selection cycles over the domain-applicable registry;
- query fields come from the declared policy and are chosen to activate the operator;
- the affected surface version is changed and tasks are deterministically shuffled;
- arbitrary application code and SQL are not mutated;
- equivalent and invalid mutants are defined and remain zero because this generator emits only
  well-formed, behavior-changing cases;
- per-operator frequencies range from 13 to 121 and are listed in Appendix B.

Representativeness is no longer inferred from 1,720/1,720. It is discussed through the public-fault,
spec-blind, and brownfield studies, with their limits.

### A3 - Related work is thin and has too few references

**Status: addressed.**

The related-work section now compares Margrave, XACML mutation testing, Cedar’s
verification-guided differential testing, distilled SQL test suites, VeriEQL/SpotIt+, Beacon,
runtime monitors, constrained generation, and data-agent benchmarks. The comparison states both
directions:

- what those methods can prove or test more strongly than PolicyStrata;
- what cross-representation transition PolicyStrata observes that they do not;
- why the paper does not claim an empirical win against tools with different input languages.

### A4 - No external use or adoption

**Status: open and explicitly disclosed.**

The paper states that external teams have not authored a PolicyStrata-blind suite or reported
adoption. A fresh MetricFlow freeze provides 68 upstream-authored requests and expected-SQL cases,
but Raintree authored the policy bridge and operated the study. This is external-source evidence,
not external operation or a blind detector evaluation.

### A5 - Were cases manual, trace-derived, or algorithmic?

**Status: addressed.**

The suite table separates hand-authored, generated, detector-frozen generated, clean-control,
spec-blind, reconstructed-public-fault, and imported-real-trace inputs. These categories are never
merged into one recall number.

### A6 - Explain differences from policy verification and SQL testing

**Status: addressed.**

Related Work contains a capability-boundary table and explains a possible composition: use a policy
verifier as the authorization oracle, a bounded SQL verifier as the compiler-semantic checker, and
database/runtime monitors as observed surfaces inside PolicyStrata’s transition harness.

### A7 - Test a real deployed system

**Status: partial; deployment-linked read-only pilot complete.**

The study binds the BetterOff adapter to production Git object
`3663f1e475eb2ba452dc887a10b052689455a4f4` and Vercel deployment
`dpl_5MQsJfscJaALxGU8nBh2srXBWQNr`. Thirty-three live probes passed, none failed, and three
authenticated reads were skipped because no isolated smoke session or API token exists. The
deployed-revision adapter passed six SQL traces and four disposable-database checks. This establishes
deployment identity and denial boundaries, not authenticated cross-tenant behavior or customer-data
safety.

### A8 - Explain version vectors and lowerings; add a worked example

**Status: addressed.**

The Introduction defines lowering as translation from typed semantic plan to SQL and a version
vector as the ordered version of the six policy surfaces. One tenant-isolation example follows the
request, accepted plan, stale tenant-key lowering, distinguishing database state, RLS containment,
release decision, and emitted witness.

## Review 38B

### B1 - Presentation is dense and relies on enumeration

**Status: addressed through structure; final editorial judgment remains subjective.**

The revision defines one six-surface “policy pipeline” and reuses that term. The example appears
before formal notation. Package and gateway inventories were removed. Results are organized by
research question and evidence boundary. Tables replace repeated lists where exact comparison or
accounting matters.

### B2 - Test generation is not explained

**Status: addressed.**

Checking Procedure defines the input schema and replay algorithm. Benchmark Construction gives the
operator-cycling and policy-guided query-generation rule, exact seeds, version mutation, shuffle,
and freeze behavior. Appendix B lists the resulting operator counts.

### B3 - Witness minimization is not explained

**Status: addressed and narrowed.**

The paper now states the only three edits: remove one dimension, remove one filter, or reset a
non-default limit. Replay must preserve class, first surface, containment, release, localized failed
contract, and relevant semantic/database evidence. The bound is 32 attempts. “One-minimal” is
defined only over this edit neighborhood; global minimality is not claimed.

### B4 - The benchmark is self-injected

**Status: addressed as a claim boundary.**

The abstract now calls 1,720/1,720 a construction-consistency check. The main comparative result is
the 141 cases missed by a specification-derived conventional test suite and the 159 missed by a
layered point-control stack. Spec-blind misses and adapter mutations are reported rather than hidden.

### B5 - Lists stand in for definitions; unclear whether exhaustive

**Status: addressed.**

The paper defines the pipeline, semantic-query tuple, policy schema, surface contract, witness
classes, localization order, mutant accounting states, evidence kinds, and completeness boundary.
Appendix B is explicitly the exhaustive v1 operator registry. Other example lists are labeled
representative or target-specific.

### B6 - Applying the tool elsewhere and specification work are unclear

**Status: addressed with measured artifacts, not person-hour claims.**

Retargeting PolicyStrata lists the four required input groups and what happens when a surface is
missing. It reports the checked-in transformation scripts and trace counts for four targets:
MetricFlow 378 lines/68 traces, Midday 57/5, WrenAI 222/2, and Cube 389/4. It also identifies the
main synthesized boundary for each. Script length is explicitly not presented as person-hours.

### B7 - Is this mutation testing?

**Status: addressed.**

The paper now names the method as deterministic mutation testing over a 22-operator cross-layer
fault registry, defines killed/survived/equivalent/invalid accounting, and explains how it differs
from mutating arbitrary application source or a single XACML policy.

### B8 - Novelty and technical rigor need stronger emphasis

**Status: addressed.**

The novelty statement is intentionally narrow: PolicyStrata composes evidence across heterogeneous,
versioned representations and assigns failure to the first responsibility-bearing transition. The
paper adds exact algorithms, a contract-relative invariant and proof sketch, counterfactual repair,
spec-blind misses, comparator information access, and TCB mutation testing.

### B9 - Doctor mode appears useful but its role is unclear

**Status: addressed.**

Implementation distinguishes three roles: the benchmark measures deterministic fault-model
coverage; the scanner gates imported evidence; doctor inventories missing or partial wiring.
Doctor output is explicitly not proof that the application invokes every configured control.

## Review 38C

### C1 - The problem and solution are hard to identify

**Status: addressed.**

The first page now defines the failure in plain language and walks one example end to end before
stating contributions. The checker’s six ordered steps appear in Checking Procedure.

### C2 - Soundness and violation detection are unclear

**Status: addressed relative to the implemented contracts.**

The paper states `Witness(T) => Violation(T)`, defines both sides, gives a detector-control-flow
proof sketch, reports 400 property-generated cases and the applicable operator/domain sweep over
25 seeds, and states what is not proved: canonical-policy correctness, adapter correctness, faults
outside the registry, or a global converse.

### C3 - Cross-layer conformance analysis is unclear

**Status: addressed.**

The paper defines each surface’s accepted and emitted obligations, the ordered contract map, the
first-failure selection rule, and the special final release comparison. It explains why later RLS
containment does not move attribution away from an earlier compiler failure.

### C4 - Demo is short and has no voice

**Status: addressed in the artifact; external hosting remains optional.**

The built-in CLI demo now prints a step-by-step stale-tenant-key case: request, principal, version
vector, canonical decision, first violated transition, contract reason, distinguishing result,
containment, release, and witness path. `paper/DEMO_SCRIPT.md` provides a timed 3:30 narration,
commands, captions requirement, and on-screen synthetic-evidence disclaimer. The existing hosted
`bun run paper:demo-video` now builds a 3:24 narrated 1920x1080 MP4 with an English caption track.
The storyboard covers the worked example, the source-frozen MetricFlow result, the BetterOff pilot,
historical replay, and the remaining claim boundary. The generated MP4 and checksum metadata are
published with the paper artifact and linked from the website.

### C5 - Simulated faults may not represent real cases

**Status: partially addressed; field representativeness remains open.**

The revision reports exact taxonomy dependence, 25 screened public faults with six exclusions, 42
spec-blind cases with three misses, 68 source-frozen upstream cases, three historical revision
replays, and a deployment-linked pilot. It does not convert these into a field-recall claim.

### C6 - Comparisons are ablations, not real competitors

**Status: addressed without creating a false apples-to-apples benchmark.**

Point checks remain labeled ablations. Two implementation-level comparators are now primary:

- a six-check conventional suite derived from the published specification without operator access;
- a pairwise surface differential inspired by model/engine authorization testing.

The related-work table separately states why Margrave, VeriEQL, Beacon, and runtime monitors were
not run as interchangeable binaries, and what a future composed evaluation would require.

## Remaining actions requiring external work

1. Configure an isolated BetterOff production smoke principal and run the three authenticated probes.
2. Obtain a PolicyStrata-blind suite authored by an external party after detector freeze.
3. Run an independently operated deployment/adoption study.
4. Advance historical replay from exact source-contract probes to executable vulnerable services.
