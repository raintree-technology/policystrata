# OSS TODO Policy

The root `todo.txt` remains the active PolicyStrata OSS checklist because it is visible in source
checkouts and release reviews. Keep it focused on local package, scanner, runner, gateway, schema,
artifact, and documentation work.

Hosted Clearance / agent-assurance work belongs in:

```text
/Users/mb1/Code/raintree/apps/agent-assurance/todo.txt
```

When an item is app-only, record the boundary in the OSS checklist instead of implementing hosted
auth, UI, billing, or operations in this repository. Only bring app work back into OSS when it is a
public contract dependency such as schema shape, runner upload payloads, or metadata-only artifact
rules.
