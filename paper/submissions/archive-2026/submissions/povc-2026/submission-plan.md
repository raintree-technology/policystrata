# POVC 2026 / PromptOps Submission Plan

Official page: https://conf.researchr.org/home/povc-2026

Deadline: 2026-07-29.

## Recommended Product

Presentation proposal or tool demonstration/tutorial, not a proceedings paper, while SECUTE is under
review.

## Title

Presentation: Testing Tool-Manifest Drift in LLM Data Agents

## Extended Abstract

LLM data agents depend on prompt and tool surfaces that change over time: model-visible manifests,
semantic-model aliases, tool schemas, query builders, database policies, and release filters. Minor
drift across those artifacts can make a prompt workflow appear valid while it reaches an
unauthorized metric, lowers through a stale tenant key, or releases a result whose lineage should
have stayed internal. This presentation demonstrates a PromptOps workflow for treating prompts,
tools, traces, and release policies as testable engineering artifacts. Using PolicyStrata, we show
how to compare model-visible prompt/tool manifests against canonical policy, import real SQL/tool
traces, identify prompt-manifest drift, and emit minimized witnesses that identify the first
violated transition. The session focuses on practical CI integration and remediation output rather
than product claims.

## Demo Points

- Prompt/tool manifest export.
- Canonical policy comparison.
- Trace import.
- Source map from failed trace to tool or route.
- Remediation todo with expected test and gate command.
