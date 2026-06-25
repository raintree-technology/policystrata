# Incident Reconstruction Template

Use this template for reconstructed real policy-drift incidents. Do not include confidential data.

## Metadata

- Incident ID:
- Source type: issue, commit, customer report, postmortem, synthetic adaptation of real issue
- Date observed:
- Reconstructed by:
- Reviewed by:
- Publicly shareable: yes/no

## Policy Context

- Canonical policy obligation:
- Principal or role:
- Tenant/account/firm scope:
- Restricted metric, dimension, row, or release boundary:
- Expected behavior:

## Drift

- Affected surface: manifest, grammar, validator, compiler, database, release
- Drift description:
- Version or deployment condition:
- Why local component tests missed it:
- Whether a later layer contained it:

## Reproduction

- Domain or sanitized fixture:
- Imported trace or semantic IR:
- SQL or lowered object:
- Database state distinction:
- Expected witness class:
- Regression case label:

## Evidence Boundary

- Was this externally authored before detector changes?
- Is the reconstruction faithful to the original incident?
- What was sanitized or simplified?
- What should not be claimed from this case?

## PolicyStrata Suite Metadata

Use this block when adding the reconstruction to a static suite:

```yaml
suite_metadata:
  provenance: incident_reconstruction
  evidence_level: imported_trace
  detector_frozen: false
  detector_freeze_id:
  authored_after_detector_freeze: false
  notes:
    - sanitized reconstruction; not evidence of unknown-incident recall
```
