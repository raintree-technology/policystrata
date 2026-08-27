# Independent Run Protocol

Use this file to record clean-room artifact checks before submission.

## Protocol

For each run:

- start from a fresh checkout or clean worktree;
- install only the documented `uv` path;
- run `./conference-kit/reproduce-final.sh`;
- record operating system, CPU class, Python version, runtime, first failure, and final status;
- attach `runs/final/evidence.md` and `runs/final/artifact-report.md`;
- do not use an LLM API key;
- do not use host `psql`.

## Run Log

| Run | Environment | Command | Runtime | Result | Notes |
| --- | --- | --- | ---: | --- | --- |
| 1 | local macOS arm64 | `./conference-kit/reproduce-final.sh` | TBD | TBD | Maintainer run |
| 2 | clean laptop/container | `./conference-kit/reproduce-final.sh` | TBD | TBD | Reviewer-style run |
| 3 | CI or second machine | `./conference-kit/reproduce-final.sh` | TBD | TBD | Independent confirmation |
