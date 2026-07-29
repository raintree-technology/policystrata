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
spec-blind, and brownfield studies, with their limits, and a new section measures the registry
against a fault vocabulary nobody here wrote — see A5a below.

### A5a - How representative is the operator registry?

**Status: addressed with a new external cross-check.**

Benchmark Construction now contains an External Taxonomy Cross-Check against the eight data-agent
vulnerabilities of Wang et al. (arXiv:2606.08661), derived independently and evaluated on six data
agents including two production cloud analytics services. The mapping is a human judgement and is
checked into `scripts/external-taxonomy-study.py` so it can be disputed; the case counts are
derived from the materialized traces.

Two of eight classes are covered and one partially, accounting for 1,319 of 1,720 cases. The five
that fall outside each do so because of a v1 boundary the paper already declared — V1 and V2
precede the typed plan, V5 needs multi-step requests, V6 is a property of the model context, V8
needs cumulative release accounting.

The reverse direction is the more useful result and we report it rather than burying it: 401 cases
have no counterpart in that taxonomy at all, because the two threat models differ. Their adversary
controls the prompt and uploaded data; our fault needs no adversary. A retired alias still
advertised to the model is what an update breaks, not what an attacker induces. Neither taxonomy
subsumes the other.

### A3 - Related work is thin and has too few references

**Status: addressed.**

The reference list is now 32 entries, every one of them cited in the text. Related Work covers
five lines rather than four, and the comparison states both directions throughout: what those
methods prove or test more strongly than PolicyStrata, what cross-representation transition
PolicyStrata observes that they do not, and why the paper claims no empirical win over tools that
accept different input languages.

Two additions matter more than the count:

- **The lineage the compiler contract descends from.** PolicyStrata's compiler check is an
  instance of translation validation (Pnueli et al.), and "authorization-preserving lowering" is
  the property-class form of what secure-compilation work calls robust property preservation
  (Abate et al.). Naming that lineage makes the novelty boundary sharper, not weaker: the
  contribution is not a preservation technique but the observation that a data agent runs several
  such lowerings between separately versioned representations.
- **The 2026 agent-conformance neighbours.** Constraint drift argues the same thesis at
  multi-agent granularity, and PolicyStrata is a narrow executable instance of it. AgentRFC shares
  the extract-check-replay shape but targets protocol conformance between agents. TDAD applies
  mutation testing to agent specifications. AgentRaft, Cordon, and C-Trace bound what PolicyStrata
  does not do: tool-flow taint, transactional containment of irreversible effects, and runtime
  regulatory enforcement.

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

**Status: partial; real policy code now executes, and a deployment-linked read-only pilot is
complete.**

The clearest answer to "the BetterOff fixture uses synthetic data" is a target whose real
authorization code we can run. Midday commits real PostgreSQL row-level security, so all 20
`CREATE POLICY` statements across the six policy-bearing tables in its frozen migrations are now
loaded verbatim into PostgreSQL 18.4 and executed. Thirteen checks connect as a non-owner,
non-superuser role, because a table owner or superuser bypasses RLS silently and the fixture would
report safety it never tested.

| Fixture | Expected gate | Observed gate | Findings |
| --- | --- | --- | --- |
| midday policies intact | pass | pass | 0 |
| one real predicate weakened to `USING (true)` | fail | fail | 4, all on `insights` |

The second row is the load-bearing one. A checker that passes the first and also passes the second
is checking nothing. Weakening one real predicate — the `db_rls_old_ownership_field` drift shape
applied to real policy text — fails three RLS checks and one state assertion, including a read
that becomes available unauthenticated, while the five tables whose policies were untouched stay
clean.

Boundaries, stated in the paper and in `examples/brownfield/midday/live_db/README.md`: this is not
a Midday defect (its committed predicate is correct), not Midday's deployed Supabase runtime (the
roles and `auth.uid()` are a Raintree-authored bridge, because Midday does not commit them), not
real data, or Midday's full deployed schema. It does cover every policy committed in the frozen
migration corpus; Supabase-managed base-schema policies remain unavailable.

The BetterOff study additionally binds the adapter to production Git object
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

Verified properties of the current build: 204.4 s (3:24), 1920x1080 H.264, AAC narration, an
embedded `mov_text` subtitle stream, and a sidecar `PolicyStrata-demo.en.vtt` with eight caption
cues. The build is reproducible from source and records its own duration and SHA-256.

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
replays, an executed real-RLS pass with a negative control, and a deployment-linked pilot. It also
now measures the registry against an independently authored eight-class data-agent vulnerability
taxonomy (A5a). It does not convert any of these into a field-recall claim.

### C6 - Comparisons are ablations, not real competitors

**Status: addressed without creating a false apples-to-apples benchmark.**

Point checks remain labeled ablations. Two implementation-level comparators are now primary:

- a six-check conventional suite derived from the published specification without operator access;
- a pairwise surface differential inspired by model/engine authorization testing.

The related-work table separately states why Margrave, VeriEQL, Beacon, and runtime monitors were
not run as interchangeable binaries, and what a future composed evaluation would require.

## Remaining actions requiring external work

Each of these needs a person or a credential the authors do not have. None is blocked on writing,
and the paper says so rather than implying the evidence exists.

1. Configure an isolated BetterOff production smoke principal and run the three authenticated
   probes. Needs a provisioned production credential; the pilot holds no such token today.
2. Obtain a PolicyStrata-blind suite authored by an external party after detector freeze. Needs an
   external author.
3. Run an independently operated deployment/adoption study. Needs an external team.
4. Advance historical replay from exact source-contract probes to executable vulnerable services.
   Needs period-accurate dependency and data fixtures.
5. Re-run the full 20-policy executed-policy pass against a runtime its maintainers operate rather
   than the reconstructed Supabase bridge. Needs an external team or an exported runtime fixture.
