# Distribution Roadmap

PolicyStrata should be distributed in layers, with the deterministic core staying inspectable and
reproducible.

## 1. CLI And PyPI Package

The first public artifact is the `policystrata` Python package:

- `policystrata` console script for demos, deterministic benchmark runs, scanner gates, exports,
  baselines, summaries, and witness minimization;
- importable Python modules for researchers and adapter authors;
- built-in deterministic domains and fixtures packaged in the wheel;
- no LLM API key or hosted account requirement for deterministic runs.

This is the surface that should be published to PyPI first.

## 2. GitHub Action

The next integration is a first-party GitHub Action wrapping `policystrata scan`.

The primary workflow is release gating: checkout a repository, run a configured scan, and block the
workflow if high-confidence policy drift is found. This matches how teams adopt regression testing
in pull requests and deployment pipelines.

The action should stay thin. It should install PolicyStrata, call the CLI, expose output paths, and
leave artifact upload or database service setup to the caller's workflow.

## 3. SDK

PolicyStrata is importable today, but that is not the same as a stable SDK.

If SDK positioning becomes important, add an explicit `policystrata.sdk` module with stable request
and result types, compatibility tests, and documentation. Until that exists, treat internal modules
as useful but not as a committed application-facing API.

## 4. MCP Server

An MCP server can be useful later for agent workflows that need to inspect scanner output, generate
domain templates, or run deterministic checks through a tool interface.

It should wrap the CLI or stable SDK. It should not become the primary execution path, and it
should not weaken the message that constrained generation and agent tooling are reliability layers,
not authorization boundaries.

## 5. GitHub CLI Extension

A `gh policystrata` extension could be convenient for local triage, but it should follow demand.
CI users need the GitHub Action, and local users already get a normal `policystrata` CLI from the
Python package.
