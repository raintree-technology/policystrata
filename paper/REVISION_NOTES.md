# Review Revision Map

This file tracks the July 2026 rewrite against reviews 38A, 38B, and 38C. It is an editing aid, not
part of the paper.

| Review concern | Manuscript response | Evidence source |
| --- | --- | --- |
| Synthetic-only evaluation | Abstract, Introduction, Results, and Threats separate synthetic scores from external-source, historical-revision, and deployment-linked evidence | `docs/evidence.md`, `docs/production-pilot.md`, `benchmarks/external_source/`, `benchmarks/historical_replay/` |
| Unclear 1720-case construction | Benchmark Construction splits 170 hand-authored from 1550 generated cases and describes selection, seeding, operator cycling, shuffling, freezing, and equivalent/invalid accounting | `docs/methodology.md`, `src/policystrata/generator.py`, `src/policystrata/domain.py` |
| Thin related work | Related Work directly compares the question and guarantee boundary for policy verification, SQL equivalence, runtime enforcement, and PolicyStrata | `paper/references.bib` |
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

- No independently operated production deployment or external adoption study exists.
- The externally authored MetricFlow source cases use a Raintree-authored adapter and are not a
  PolicyStrata-blind suite.
- Historical BetterOff replay checks exact pre/post-fix source contracts; it does not execute the
  vulnerable services.
- Three authenticated production probes need an isolated BetterOff smoke principal.
- The model-reachability harness has not been run with an LLM.
