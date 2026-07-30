# Audit Fixtures

PolicyStrata keeps a metadata-only audit fixture catalog at
`tests/fixtures/audit/audit-fixtures.json`.

The catalog covers:

- metadata-only enforcement
- redaction
- tenant isolation
- runner-token abuse
- evidence integrity
- release decisions
- waiver evidence as schema data, not hosted workflow state
- runtime events
- SQL/RLS
- retrieval
- PII
- egress
- MCP/tool schema evidence
- CI gates
- adapter-based exports

It also defines a small human-review data format and quality-tracking fields for validated
false negatives and noisy false positives. These are local evidence formats; they do not depend on
Clearance hosted workflows.
