# Counterfactual-Repair Validation

Localization accuracy (`localized_surface == expected_localized_surface`)
compares two labels that both come from the operator taxonomy. A perfect score
is circular: it only shows the detector reproduces the injection label, not that
the attributed surface is actually the cause.

Counterfactual repair replaces that comparison with an intervention. For a case
whose witness is attributed to surface **A**, it checks two causal claims:

- **Sufficiency** - repair the skew on A (remove that operator) and re-run. The
  A-witness must disappear: attribution moves off A, or the case goes clean. If
  A is repaired and attribution stays on A, A was not the cause.
- **Necessity** - repair a skew on some *other* surface B while leaving A. The
  attribution must remain A. If removing B moves attribution off A, then B - not
  A - was driving it.

Both directions require more than one skewed surface, so the study runs over
compound cases (see [compound-mutants.md](compound-mutants.md)).

Run it:

```bash
uv run policystrata counterfactual --domain support_saas --orders 2,3 --per-order 60
uv run python scripts/counterfactual-study.py --out runs/counterfactual
```

## Result

| Domain | Cases | Sufficiency | Necessity | Counterfactual-valid |
| --- | --- | --- | --- | --- |
| support_saas | 120 | 1.00 | 1.00 | 1.00 |
| finance_saas | 120 | 1.00 | 1.00 | 1.00 |
| analytics_clickhouse | 120 | 1.00 | 1.00 | 1.00 |

Worked example from `support_saas`: a case skews `manifest` (stale metric alias)
and `grammar` (forbidden dimension), attributed to `manifest`. Repairing the
manifest skew moves the first transition to `grammar` (sufficiency holds);
repairing the grammar skew leaves the first transition at `manifest` (necessity
holds). Attribution to `manifest` is therefore causally supported, not just
label-matched.

## Why the perfect score is not the circular kind

Unlike localization accuracy, this metric can fail. The test suite includes a
teeth check: forcing the detector to always attribute to `database` regardless
of which surfaces are skewed makes counterfactual validity drop to false,
because repairing the (non-causal) `database` claim does not move a constant
attribution. The 1.00 here means every attribution survived an intervention that
a wrong attribution would not.

## Limitations

- Runs over the same distinct-surface compound cases as the compound study, so
  it inherits that model's scope (no same-surface interaction).
- It validates attribution *within* the operator taxonomy - it shows the
  detector's attribution is causally consistent with its own simulator, which is
  a stronger claim than label matching but still not evidence about unknown
  real-world faults.
