# Adversarial Clean Controls

The shipped clean-control suite has 80 cases - too small a denominator for a
precision claim. This suite scales to 1000+ clean controls per domain built from
adversarial archetypes: legitimate configurations a naive detector is tempted to
flag but that carry no policy violation.

```bash
uv run policystrata run --domain support_saas --suite adversarial_clean_controls --count 1000 --out runs/adv
uv run python scripts/adversarial-controls-study.py --out runs/adv-controls
```

Archetypes (all `mutation = none`, all expected CLEAN):

| Archetype | What it stresses |
| --- | --- |
| `authorized` | ordinary allowed query |
| `staged_rollout` | grammar/validator versions legitimately ahead of manifest |
| `feature_flag` | allowed query carrying a flag filter |
| `boundary_budget` | allowed query at exactly the role's row budget |
| `service_account_ambient` | broadest-tenant principal reading across owned tenants |
| `correctly_denied_metric` | a metric the policy legitimately denies; stack agrees |
| `correctly_denied_dimension` | a dimension the policy legitimately denies; stack agrees |

The existing 80-case suite is untouched and byte-identical (a test pins this), so
frozen manifests and the evidence table do not change.

## Result

On 1000 support_saas adversarial clean controls:

| Detector / baseline | False positives |
| --- | --- |
| PolicyStrata responsibility contracts | **0 / 1000** |
| `naive_surface_equality` (deployable) | 0 / 1000 |
| `property_differential` (deployable) | 0 / 1000 |
| `conventional_test_suite` (deployable) | 0 / 1000 |
| `validator_only` (naive denial-flagging) | 285 / 1000 |

Two honest readings:

1. **The denominator is now 1000+, and the contract detector's false-positive
   rate stays 0.** That is the direct answer to "0/80 is too small a
   denominator."
2. **Only the correctly-denied archetype separates detectors.** A naive checker
   that treats any policy denial as a finding false-positives on 285/1000
   legitimate denials; the responsibility contracts return CLEAN because the
   layers agreed to deny. The well-designed baselines (surface equality,
   pairwise differential, conventional tests) also see 0 false positives here.

## The honest limitation this surfaces

In the deterministic simulator a clean control cannot trip a *decision-based*
detector, because clean-by-construction means every surface agrees. So a 0
false-positive rate on this suite - for the contract detector and for deployable
baselines alike - is partly structural. The simulator cannot manufacture a
benign case that fools a well-designed detector, so this suite cannot, on its
own, prove precision against benign-but-drift-like configurations.

The genuine precision evidence for those cases lives in the scanner on real
inputs (see the brownfield results), where false positives are measured on
artifacts the simulator did not generate. Baseline false positives are measured
with `policystrata.baselines.evaluate_false_positives`; note that baselines whose
predicate references the detector's own `localized_surface` field (an ablation of
PolicyStrata, not a deployable competitor) report artifactual false positives on
clean traces and are excluded from the deployable comparison above.
