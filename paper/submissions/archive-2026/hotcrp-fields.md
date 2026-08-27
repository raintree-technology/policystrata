# HotCRP Fields

Submission site: https://splashissta2026-demo.hotcrp.com

## Title

PolicyStrata: Testing Policy Drift in LLM Data Agents

## Authors

Zachary Roth  
Raintree Technology  
USA  
admin@raintree.technology

## Abstract

PolicyStrata is a deterministic regression-testing and stack-audit tool for governed LLM data-agent stacks. It detects cross-layer policy drift among model-visible manifests, grammars, semantic-plan validators, SQL compilers, database policy and row-level security, lineage, and release filters. Given canonical authorization, semantic, and release specifications, PolicyStrata generates principals, requests, semantic plans, database states, version vectors, and lowerings; checks responsibility-scoped contracts; and emits minimized witnesses that identify the first violated transition. Its doctor mode audits what a real stack has wired: SQL traces, dbt semantic files, PostgreSQL schema/RLS metadata, privacy policies, terms of service, data-processing and internal-policy documents, prompt/tool manifests, source maps, release coverage, and CI gates. The demonstration runs the reproducible artifact path, inspects JSONL traces and witnesses, shows an audit report with remediation todos, and compares PolicyStrata with grammar-only, validator-only, SQL-policy, DB-only, release-only, final-answer, and defense-in-depth baselines.

## Keywords

LLM data agents; policy testing; software testing; authorization; semantic drift; text-to-SQL; row-level security; reproducibility; regression testing

## PDF

`/Users/mb1/Code/raintree/papers/conference-kit/issta-splash-tool-demo-paper.pdf`

Use this short tool-demo PDF, not `paper-anon.pdf` and not the full archival paper. This track is single-blind.

## Video

Uploaded `/Users/mb1/Code/raintree/papers/conference-kit/policystrata-demo-video.mp4` to YouTube as an unlisted video:

https://www.youtube.com/watch?v=skQQajjI7-0

Finalizer command:

```bash
cd /Users/mb1/Code/raintree/papers/conference-kit
./fill-demo-video-url.sh 'https://www.youtube.com/watch?v=skQQajjI7-0'
```

The script inserts the URL, rebuilds the PDF, checks that no TODO remains, verifies that the PDF is 3 pages, and prints the SHA256.

Current PDF SHA256:

```text
de90c8d2d44cb79cf7751902c105d64d6303f2fa67ed9779a234b626d4b95642  issta-splash-tool-demo-paper.pdf
```

Current video SHA256:

```text
ae9a7a9b4e9ff2e886c34ec2ea1dfad76d928f6fbbbc366ee8079b58cf4c86f5  policystrata-demo-video.mp4
```

## Availability Links

- Repository: https://github.com/raintree-technology/policystrata
- Stable release: https://github.com/raintree-technology/policystrata/releases/tag/v1.0.0
- PyPI: https://pypi.org/project/policystrata/1.0.0/
- Public paper: https://raintree.technology/papers/PolicyStrata.pdf
- Paper artifact kit: https://github.com/raintree-technology/policystrata/releases/tag/policystrata-paper-2026-06-26

## Final Upload Check

Before pressing submit in HotCRP:

- Open the uploaded PDF preview.
- Confirm the Tool Availability section contains the YouTube URL.
- Confirm the final YouTube URL appears.
- Confirm page count is 3.
- Confirm authors are visible.
