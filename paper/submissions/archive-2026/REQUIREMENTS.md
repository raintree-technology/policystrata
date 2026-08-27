# Requirements

## Required

- macOS or Linux shell environment.
- Python 3.10 or newer.
- `uv` for environment management and command execution.
- The canonical PolicyStrata artifact checkout beside this paper repository:

```text
workspace/
  papers/
  policystrata/
```

Set `POLICYSTRATA_ARTIFACT_ROOT=/path/to/policystrata` if the checkout is elsewhere.

## Not Required

- LLM API key.
- Host `psql`.
- External proprietary datasets.

## Optional

- Docker or compatible container runtime for PostgreSQL/RLS smoke tests.

## Expected Runtime

The deterministic suite is intended to finish in minutes on a developer laptop. On the local checked
machine with an already prepared `uv` environment, the run completed well under one minute. First-time
dependency setup may take longer.
