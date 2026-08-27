# ISSRE 2026 Industry Track Fields

Official page: https://cyprusconferences.org/issre2026/industry-track/

Submission page: https://easychair.org/conferences/?conf=issre2026

## Recommended Product

Submit a 1-2 page tool-demo abstract if the abstract window is still open. If the proceedings path
is too risky or closed, use the August 15 non-proceedings enlightening talk/tool-demo route.

## Title

PolicyStrata: Reliability Regression Testing for Governed LLM Data Agents

## Authors

Zachary Roth, Raintree Technology, USA, admin@raintree.technology

## Abstract

LLM data agents can pass model, compiler, database, and release-layer checks independently while the
composed workflow violates tenant scope, semantic meaning, or release policy. PolicyStrata is a
deterministic reliability-regression and stack-audit tool for governed data-agent deployments. It
checks whether authorization, semantic, lineage, version, and release obligations survive translation
across model-visible manifests, semantic validators, SQL lowerings, database policy/RLS, and release
filters. The tool emits minimized witnesses that identify the first violated transition and includes
a doctor mode that reports which real stack surfaces are wired: SQL traces, dbt semantic files,
PostgreSQL schema/RLS metadata, privacy policies, terms of service, prompt/tool manifests, source
maps, release coverage, and CI gates. In deterministic artifact suites, PolicyStrata reports
witnesses for 1720/1720 covered non-equivalent injected faults with 0 false positives over 80 clean
controls. A BetterOff brownfield wiring check exercises real application surfaces with synthetic
fixture data and validates doctor/scan CI gates.

## Keywords

software reliability; LLM data agents; policy regression testing; row-level security; CI gates

## Notes

- This is non-anonymous.
- Use IEEE format if uploading a paper/abstract PDF.
- Keep the BetterOff result framed as integration feasibility, not production fault discovery.
- Built PDF: `issre-industry-tool-demo-abstract.pdf`.
- Built PDF SHA256: `cd35b40bd9713c95ddade16697c8774bfa82dc7b87a7ad4af39a729be2f77069`.
- Submitted through EasyChair as Submission 406.
- Portal status text: `The submission has been saved!`
