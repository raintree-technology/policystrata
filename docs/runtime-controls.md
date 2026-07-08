# Runtime Controls

PolicyStrata runtime events are redacted metadata envelopes for local app-side evaluation. They
should contain hashes, schema refs, policy refs, data classes, resource names, and decision
metadata, not raw prompts, rows, documents, or tool payloads.

## Kill Switch

Use the runtime kill switch to fail closed without changing application code:

```json
{
  "schemaVersion": "policystrata.runtime_manifest.v1",
  "version": "runtime.prod",
  "defaultDecision": "deny",
  "resources": [
    {"name": "support_tickets", "actions": [{"name": "read", "allowedRoles": ["support_manager"]}]}
  ],
  "controls": {
    "runtime": {"killSwitch": true}
  }
}
```

When enabled, every runtime event is denied with control ID `runtime_kill_switch`.

## PII And Regulated Fields

Represent data exposure with classes, not values:

```json
{
  "schemaVersion": "0.2.0",
  "eventId": "evt_pii_redaction",
  "project": "support-bi",
  "observedAt": "2026-07-06T15:58:52Z",
  "agent": {"key": "support-bi-copilot"},
  "layer": "output_filter",
  "operation": "release_answer",
  "summary": "Answer references customer contact fields",
  "dataClasses": ["pii", "customer_contact"],
  "policyRefs": ["policy://support_saas/pii_minimization"],
  "payloadHash": "sha256:..."
}
```

Configure `controls.data.redactClasses`, `secretClasses`, and `deniedClasses` in the manifest.

## SQL Parameterization

Set `controls.sql.requireParameterized` when runtime SQL events should fail closed on inline string
or numeric literals:

```json
{
  "controls": {
    "sql": {
      "tenantColumn": "tenant_id",
      "requireParameterized": true,
      "allowedQueryRisks": ["read"],
      "maxRows": 1000
    }
  }
}
```

This check is intentionally conservative and metadata-based. Keep database drivers and query
builders responsible for actual parameter binding.

## MCP Tool Schema Evidence

Reference schemas by stable local artifact path or URI:

```json
{
  "schemaVersion": "0.2.0",
  "eventId": "evt_mcp_schema",
  "project": "support-bi",
  "observedAt": "2026-07-06T15:58:52Z",
  "agent": {"key": "support-bi-copilot"},
  "layer": "tool_call",
  "operation": "call_tool",
  "summary": "MCP tool call validated against schema refs",
  "resource": {"kind": "mcp_tool", "name": "workspace.search_tickets"},
  "toolInputSchemaRef": "schemas/workspace.search_tickets.input.json",
  "toolOutputSchemaRef": "schemas/workspace.search_tickets.output.json",
  "mcpInputSchemaRef": "mcp/workspace.search_tickets.input.schema.json",
  "mcpOutputSchemaRef": "mcp/workspace.search_tickets.output.schema.json",
  "payloadHash": "sha256:..."
}
```

## Browser Action Event

```json
{
  "schemaVersion": "0.2.0",
  "eventId": "evt_browser_export",
  "project": "support-bi",
  "observedAt": "2026-07-06T15:58:52Z",
  "agent": {"key": "support-bi-copilot"},
  "layer": "browser_action",
  "operation": "download_file",
  "summary": "Browser automation attempted a CSV download",
  "resource": {"kind": "browser", "name": "download", "uri": "https://app.example/export"},
  "dataClasses": ["export"],
  "policyRefs": ["policy://support_saas/export_approval"],
  "payloadHash": "sha256:..."
}
```

## Code Execution Event

```json
{
  "schemaVersion": "0.2.0",
  "eventId": "evt_code_exec",
  "project": "support-bi",
  "observedAt": "2026-07-06T15:58:52Z",
  "agent": {"key": "support-bi-copilot"},
  "layer": "code_execution",
  "operation": "run_python",
  "summary": "Sandboxed code requested network egress",
  "resource": {"kind": "sandbox", "name": "python-runner"},
  "dataClasses": ["derived_aggregate"],
  "policyRefs": ["policy://support_saas/code_execution"],
  "payloadHash": "sha256:..."
}
```

## Human Approval Event

```json
{
  "schemaVersion": "0.2.0",
  "eventId": "evt_approval",
  "project": "support-bi",
  "observedAt": "2026-07-06T15:58:52Z",
  "agent": {"key": "support-bi-copilot"},
  "layer": "egress",
  "operation": "export",
  "summary": "Approved customer support export",
  "resource": {"kind": "webhook", "name": "approved_vendor", "destinationClass": "approved_vendor"},
  "approvalRequiredSatisfied": true,
  "decision": {
    "action": "allow",
    "reason": "approved by reviewer",
    "approvalRef": "approval://support-bi/exp_123"
  }
}
```
