# Generic Evidence Exports

PolicyStrata OSS does not require Clearance for notifications or ticketing. Export a redacted
local JSON evidence file first, then let the caller decide where to send a summary:

```bash
policystrata export runs/policystrata \
  --format policystrata-json \
  --out runs/policystrata/evidence.json
```

The examples below assume the receiving system is already configured by the caller. Do not send raw
prompts, documents, rows, tool payloads, private schemas, credentials, or full traces.

## Slack Webhook

Send a compact CI summary to a generic incoming webhook:

```bash
SUMMARY="$(jq -r '"PolicyStrata \(.metadata.run.domain // "run"): \(.summary.total) findings, kill rate \(.summary.mutant_kill_rate)"' runs/policystrata/evidence.json)"
curl -fsS "$SLACK_WEBHOOK_URL" \
  -H 'content-type: application/json' \
  --data "$(jq -n --arg text "$SUMMARY" '{text: $text}')"
```

Keep the full `evidence.json` as a CI artifact rather than posting it into chat.

## Jira Issue Payload

Create a ticket from a redacted summary. The exact endpoint, project key, and auth method belong to
the caller's Jira deployment:

```bash
jq -n --slurpfile evidence runs/policystrata/evidence.json '{
  fields: {
    project: {key: env.JIRA_PROJECT_KEY},
    summary: "PolicyStrata evidence needs review",
    issuetype: {name: "Task"},
    description: {
      type: "doc",
      version: 1,
      content: [{
        type: "paragraph",
        content: [{
          type: "text",
          text: ("Findings: " + ($evidence[0].summary.total | tostring) + ", gate artifact: runs/policystrata/evidence.json")
        }]
      }]
    }
  }
}' > runs/policystrata/jira-issue.json
```

Review the payload locally before sending it to Jira.

## Datadog Log Event

Ship a small metadata log event to a Datadog-compatible log intake:

```bash
jq -c '{
  service: "policystrata",
  source: "policystrata",
  message: "PolicyStrata evidence summary",
  policystrata: {
    version: .version,
    domain: .metadata.run.domain,
    suite: .metadata.run.suite,
    total: .summary.total,
    mutant_kill_rate: .summary.mutant_kill_rate
  }
}' runs/policystrata/evidence.json > runs/policystrata/datadog-log.json
```

Use the platform's normal log shipper or HTTPS intake after reviewing the generated file.

## Snowflake Text-to-SQL Evidence

For Snowflake-backed agents, start with the deterministic imported-trace fixture under
`examples/integrations/snowflake_text_to_sql`. It exercises the scanner without Snowflake
credentials. Add real Snowflake execution only in a separate sanitized CI job or adapter.
