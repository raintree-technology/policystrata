# Review Revision Map

This file tracks the July 2026 rewrite against reviews 38A, 38B, and 38C. It is an editing aid, not
part of the paper.

| Review concern | Manuscript response | Evidence source |
| --- | --- | --- |
| Synthetic-only evaluation | Abstract, Introduction, Results, and Threats separate synthetic scores from external-source, historical-revision, executed-policy, and deployment-linked evidence | `docs/evidence.md`, `docs/production-pilot.md`, `benchmarks/external_source/`, `benchmarks/historical_replay/` |
| Real system, not synthetic data | All 20 policies across the 6 policy-bearing tables in Midday's frozen migrations execute verbatim in PostgreSQL 18.4; 13/13 live checks pass intact and weakening one real predicate fails exactly the 4 checks covering it | `scripts/midday-live-db-evidence.py`, `examples/brownfield/midday/live_db/`, `studies/midday-live-db-evidence.json` |
| Unclear 1720-case construction | Benchmark Construction splits 170 hand-authored from 1550 generated cases and describes selection, seeding, operator cycling, shuffling, freezing, and equivalent/invalid accounting | `docs/methodology.md`, `src/policystrata/generator.py`, `src/policystrata/domain.py` |
| Benchmark representativeness | Two external cross-checks measure the registry against an 8-class data-agent vulnerability taxonomy and LASM's 7-layer/4-timescale vocabulary derived from 116 papers; the latter shows coverage in 3 layers and one temporal class | `scripts/external-taxonomy-study.py`, `scripts/second-taxonomy-study.py`, `docs/external-taxonomy-coverage.md`, `docs/second-taxonomy-coverage.md` |
| Thin related work (six references) | Related Work now spans five lines including the translation-validation and secure-compilation lineage the compiler contract descends from, and the 2026 agent-conformance neighbours; 32 references, all cited | `paper/references.bib`, `paper/sections/02-related-work.tex` |
| No real competitor | Results promotes the specification-derived conventional suite and pairwise differential; point checks are labeled ablations rather than competitors | `src/policystrata/baselines.py`, `docs/evidence.md` |
| No worked example | Introduction follows one tenant-scope failure from semantic plan through stale lowering, RLS containment, and release | seeded support-domain contract |
| Undefined version vectors and lowerings | Introduction defines both in practitioner terms before the formal model | `paper/sections/01-introduction.tex` |
| Cross-layer method unclear | Checking Procedure gives the input contract, oracle split, six-step algorithm, attribution rule, and reduction acceptance predicate | detector, runner, and minimizer source |
| Soundness unclear | Model and Appendix state the checked implication and its proof boundary; Results reports the property and exhaustive checks | `src/policystrata/soundness.py`, `tests/test_soundness.py` |
| Retargeting cost unclear | Implementation and Retargeting lists the required policy, surface, trace, adapter, and optional database inputs and explains when human specification is unavoidable | scanner models and four brownfield adapters |
| Localization circular | Results reports counterfactual sufficiency/necessity and the forced-wrong teeth test | `docs/counterfactual-repair.md` |
| Minimization vague | Model and Checking Procedure state the exact three reductions, preservation predicate, 32-attempt bound, and limited measured reductions | `src/policystrata/minimize.py`, `docs/minimization-metrics.md` |
| Adapter trust implicit | Implementation and Threats report the 18-mutation TCB study, including 16 silent corruptions | `docs/tcb-analysis.md` |
| Dense, list-heavy presentation | The rewrite defines one pipeline, moves the example before notation, removes package/gateway inventory, and organizes results by research question | manuscript |
| Demo is short and silent | A reproducible 3:24 narrated 1080p MP4 now includes an English caption track and explicit evidence boundaries | `scripts/build-demo-video.py`, `paper/DEMO_SCRIPT.md`, `paper/build/PolicyStrata-demo.mp4` |

## Still open

These need a person or a credential we do not have; none is blocked on writing.

- No independently operated production deployment or external adoption study exists. Needs an
  external team.
- No PolicyStrata-blind suite authored by an external party after detector freeze. Needs an
  external author. The MetricFlow source cases are upstream-authored but use a Raintree adapter,
  so they are external-source, not external-operation.
- Three authenticated production probes need an isolated BetterOff smoke principal. Needs a
  provisioned production credential; the pilot deliberately holds no such token today.
- Historical BetterOff replay checks exact pre/post-fix source contracts; it does not execute the
  vulnerable services. Needs period-accurate dependency and data fixtures.
- The model-reachability harness has not been run with an LLM. Needs an API key and a decision to
  put stochastic results next to a deterministic score.
- The executed-policy pass covers the frozen migration corpus's full 20-policy, 6-table set under
  a Raintree-authored Supabase bridge, not Midday's deployed runtime.
