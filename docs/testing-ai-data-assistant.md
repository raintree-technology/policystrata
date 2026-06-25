# Testing An AI Data Assistant

Use this workflow when an application has an Ask AI, BI copilot, warehouse chat, or text-to-SQL
tool that can call SQL.

## 1. Create A Scanner Scaffold

```bash
uv run policystrata init-scan --out policystrata
```

This creates:

```text
policystrata/policystrata.yaml
policystrata/domain/policy.yaml
policystrata/domain/surfaces.yaml
policystrata/traces.example.jsonl
```

Run the generated command once before wiring production traces:

```bash
uv run policystrata scan --config policystrata/policystrata.yaml --out runs/policystrata-smoke
```

## 2. Map Tool Arguments To Semantic IR

Capture the user-facing query plan before SQL lowering:

```json
{
  "metric": "ticket_count",
  "dimensions": ["region"],
  "filters": {"severity": "high"},
  "time_range": "last_month",
  "grain": "month",
  "limit": 100
}
```

Keep this mapping independent from the SQL compiler. PolicyStrata uses it to ask the policy oracle
whether the request should have been authorized before comparing SQL behavior.

## 3. Capture Tool-Call SQL

Emit one JSONL line per SQL tool call:

```json
{
  "id": "ask_ai_2026_06_24_001",
  "principal": "acme_analyst",
  "tenant_ids": ["acme"],
  "semantic_ir": {"metric": "ticket_count", "dimensions": ["region"], "limit": 100},
  "sql": "select count(distinct support_tickets.id) as value from accounts left join support_tickets on support_tickets.account_id = accounts.id where accounts.tenant_id in ('acme') group by accounts.region limit 100",
  "release_allowed": true,
  "source": "ask_ai"
}
```

If SQL relies on RLS rather than literal tenant predicates, declare that explicitly:

```json
{
  "expected_policy": {"allow_rls_only": true}
}
```

Then add RLS or state assertions under `database:` so the containment layer is still checked.

## 4. Configure Tenancy Vocabulary

Replace built-in tenant names with your application terms:

```yaml
tenancy:
  canonical_predicates:
    - "transactions.household_id = :principal.tenant_id"
    - "accounts.household_id = :principal.tenant_id"
  tenant_columns:
    - transactions.household_id
    - accounts.household_id
```

Use this for `household_id`, `organization_id`, RLS GUCs, join-derived ownership, or helper
functions that are canonical in your application.

## 5. Run The Scanner

```bash
uv run policystrata scan --config policystrata/policystrata.yaml --out runs/policystrata
```

Review:

```text
runs/policystrata/report.md
runs/policystrata/findings.jsonl
runs/policystrata/witnesses/*.json
```

Findings include:

- `what_changed`
- `owner`
- `probable_fix`
- `minimal_repro_trace`
- `ci_gate_command`

## 6. Fail CI On Unsafe Drift

```bash
uv run policystrata scan --config policystrata/policystrata.yaml --out runs/policystrata
```

The command exits `1` on high-confidence gate failures such as unsafe release, missing tenant scope,
RLS leakage, or semantic drift. Keep trace generation deterministic in CI by replaying sanitized
tool-call fixtures rather than requiring an LLM API key.
