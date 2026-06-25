# External Suite Protocol

Use this protocol when adding blinded or externally authored PolicyStrata evidence.

## Roles

- **Detector owner**: maintains PolicyStrata code, mutation operators, scanner, and docs.
- **Suite author**: creates cases after a detector freeze or without tuning against detector output.
- **Reviewer**: checks that labels, fixtures, and claims match the evidence boundary.

One person may play multiple roles for internal engineering work, but paper claims should identify
when no independent suite author was involved.

## Freeze

Before collecting blinded evidence, record:

- PolicyStrata git SHA;
- mutation operator IDs;
- scanner config schema version;
- domain policy version;
- allowed adapters;
- scorer rules;
- whether the suite author can see detector output.

After freeze, detector changes that improve results should trigger a new evidence snapshot rather
than silently replacing the original result.

Static PolicyStrata suite files should record the freeze boundary in top-level `suite_metadata`:

```yaml
suite: external_blinded
suite_metadata:
  provenance: externally_authored
  evidence_level: blinded_suite
  detector_frozen: true
  detector_freeze_id: ps-freeze-YYYY-MM-DD
  authored_after_detector_freeze: true
  notes:
    - externally authored after the detector freeze
```

The runner copies this block into `metadata.json`; `policystrata evidence` reports the evidence
level, provenance, and detector-freeze status beside the suite score.

## Suite Contents

Each case should include:

- domain or adapter source;
- principal and policy context;
- semantic IR or trace input;
- expected policy outcome;
- expected witness class when applicable;
- expected localized surface when known;
- regression case label: `fail_to_pass`, `pass_to_pass`, `contain_to_contain`, `deny_to_deny`, or
  `allow_to_allow`;
- whether labels were externally authored, detector-frozen, reconstructed, or synthetic.

Do not put private customer data in public fixtures. Sanitize rows and preserve only the policy
distinctions required to reproduce the witness.

## Reporting

Report blinded suites separately from public/generated suites:

- total cases;
- killed/caught cases;
- survived cases;
- equivalent or stillborn cases;
- false positives on `pass_to_pass` and `allow_to_allow`;
- containment rate for `contain_to_contain`;
- evidence levels and adapter coverage.

Do not merge blinded results into the 620/620 public deterministic result.
