# Failure Taxonomy

PolicyStrata reports a small, stable `WitnessClass` enum in traces and witnesses. The enum is
intentionally coarse so JSON artifacts remain stable while docs, reports, and scanners can explain
more specific failure modes.

The most important question is not whether every layer made the same allow/deny decision. Different
layers have different jobs. PolicyStrata asks whether each layer preserved the canonical policy
obligations it accepted from the previous layer.

| `WitnessClass` | Concrete failures covered | Typical surfaces | What the witness establishes |
| --- | --- | --- | --- |
| `clean` | No observed policy drift | Any | The declared surface responsibilities and transition obligations were preserved for this case. |
| `over_permissive` | Manifest overclaim, grammar exposure of forbidden intent, validator bypass, database policy gap, cost-budget bypass | `manifest`, `grammar`, `validator`, `database`, `compiler` | A layer accepted, exposed, or failed to contain behavior that the canonical policy or its declared responsibilities reject. |
| `over_restrictive` | Manifest underclaim, validator false denial, stale policy denying an authorized metric or dimension | `manifest`, `validator` | A layer rejected behavior that the canonical policy allows. |
| `lowering_violation` | Compiler refinement violation, dropped tenant predicate, stale tenant key, tenant/account scope confusion | `compiler` | An authorized semantic query was lowered into SQL that failed to preserve bound obligations such as tenant scope. |
| `semantic_drift` | Gross/net metric confusion, join-grain fanout, removed `DISTINCT`, inner-join row loss, fiscal/calendar time drift | `compiler` | The lowered query stayed executable but no longer computed the canonical business semantics. |
| `unsafe_release` | Output release leak, contained result released, unauthorized downstream value surfaced as text | `release` | The output layer released data that should have been withheld after an upstream denial or containment decision. |

## Reading a Witness

A minimized witness records:

- `witness_class`: the stable coarse failure class.
- `localized_surface`: the first layer that violated its declared responsibility.
- `containment_layer`: the downstream layer that contained the failure, when one did.
- `contract_decisions`: the per-surface responsibility checks.
- `transition_obligations`: the obligations that should have survived the stack.
- `compiled_sql`, `db_result`, and `release_allowed`: the observable behavior that made the drift
  reproducible.

For example, a `lowering_violation` localized to `compiler` with `containment_layer: database`
means the compiler dropped or corrupted an obligation such as tenant scope, and the database layer
blocked the observable row release. The failure still matters because the compiler violated the
policy-preserving transition even though a downstream control contained it.

## Why The Enum Is Coarse

The enum is part of the stable trace and witness surface. More specific names such as
`manifest_overclaims`, `validator_bypass`, `compiler_refinement_violation`, or
`output_release_leak` are useful in reports, but encoding every subtype as a trace enum would make
artifact compatibility harder. PolicyStrata keeps the stable class small and uses `mutation`,
`localized_surface`, `reasons`, and scanner finding titles for finer detail.
