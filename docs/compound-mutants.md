# Higher-Order (Compound) Mutants

The deterministic benchmark injects exactly one operator per case. Real policy
drift is often compound: a stale model-visible manifest and a stale compiler
tenant key can be live at the same time. This study composes two or more
single-surface skews into one case and measures whether detection and
first-transition attribution survive composition.

Run it:

```bash
uv run policystrata compound --domain support_saas --orders 2,3 --per-order 60
uv run python scripts/compound-study.py --out runs/compound
```

## What a compound case is

A compound case carries an ordered set of two or more mutation operators that
each affect a **distinct** surface. It is evaluated as the **union of
independent single-surface skews**: each constituent operator is run on its own
through the standard `evaluate_task` path, and the per-surface contract
violations are merged (a surface violates its contract in the compound case iff
it violates it in any constituent).

Expected labels under composition (`compound_expectations`):

- **First transition** is the earliest affected surface in
  `manifest → grammar → validator → compiler → database → release`.
- **Witness class** is that earliest operator's class.
- **Containment** holds only when the declared containment layer is not itself
  one of the skewed surfaces. If a compiler tenant-drop is contained by the
  database but the database row policy is *also* skewed in the same case,
  containment no longer holds and the case is expected to surface at the
  compiler.

## Result and how to read it

Across the three built-in domains, all generated compound cases (orders 2 and 3)
are detected and attributed to the correct first transition:

| Domain | Cases | Detection | First-transition attribution | Class |
| --- | --- | --- | --- | --- |
| support_saas | 80 | 1.00 | 1.00 | 1.00 |
| finance_saas | 80 | 1.00 | 1.00 | 1.00 |
| analytics_clickhouse | 80 | 1.00 | 1.00 | 1.00 |

Read this as a **stability property, not a discovery result**. It says the
detector's first-transition rule is stable under distinct-surface composition:
merging contract violations and taking the earliest violated surface provably
returns the earliest skew, so attribution does not degrade when independent
skews are stacked. The containment adjustment is the one place composition
changes the expected label, and the study confirms the detector tracks it.

## Limitations

- **Distinct surfaces only.** Same-surface interaction (e.g. two compiler
  rewrites on one query that partially cancel, or a fan-out and a distinct-drop
  on the same aggregate) is not modeled. That is where attribution could
  genuinely degrade, and it requires threading multiple operators through the
  compiler and DB simulator rather than composing independent single-operator
  traces. It is future work.
- Because constituents are evaluated independently, this study does not exercise
  emergent behavior where one skew masks another's observable effect at the
  database layer. The contract-level merge captures responsibility violations,
  not every downstream numeric interaction.
- Like the single-operator benchmark, expected labels are derived from the same
  operator taxonomy the detector checks, so the perfect scores are a
  consistency property of the composition rule, not evidence about unknown
  real-world compound faults.
