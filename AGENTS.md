# PolicyStrata agent instructions

PolicyStrata is a deterministic policy-regression testing artifact for AI data-agent
stacks.

- Preserve the independence of the policy oracle and SQL compiler path.
- Treat constrained generation as a reliability layer, never an authorization boundary.
- Keep trace and finding schemas backward-compatible unless a versioned breaking change
  is explicitly requested.
- Keep deterministic tests free of hosted services, LLM keys, and host database tools.
- Use synthetic fixtures and keep credentials, customer data, and proprietary schemas
  out of evidence artifacts.
- Use uv for Python and Bun 1.3.11/Node 24 for JavaScript packages.
- Run focused tests while iterating and `bun run validate:full` for repository-wide or
  release-facing changes.
