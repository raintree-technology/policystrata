"""Adapter mutation catalog for PolicyStrata's trusted computing base (TCB).

The scanner trusts three adapter layers: the imported-trace loader
(``policystrata.trace_import``), the read-only SQL guard
(``policystrata.database.assert_read_only_sql``), and the finding-emission
path in ``policystrata.scanner``. A fault in any of them can hide a real
policy violation or invent a false one without failing the scan.

Each catalog entry installs a small runtime behavior override (an "adapter
mutation") over one of those layers, replays a fixed detection scenario, and
compares the observable output (gate outcome plus finding ids and severities)
against the intact baseline:

- HIDDEN: a true finding disappears, or severity/gate is weakened
- INVENTED: a false finding appears, or severity/gate is escalated
- NEUTRAL: the observable output is unchanged
- LOUD: the mutation raises an explicit error (the desired failure mode)

The adapters under test are never modified on disk; overrides are module
attribute patches that are always undone. ``tests/test_tcb_mutation.py`` pins
the current classification and ``scripts/tcb-mutation-report.py`` renders the
table used in ``docs/tcb-analysis.md``.

Database-result mutations are emulated: the real ``PostgresAdapter.query``
needs a live database, so an in-memory adapter reproduces its result shape
and the mutation distorts that shape (row truncation, column renames).
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from policystrata import database, scanner, trace_import
from policystrata.evidence import markdown_table
from policystrata.models import WitnessClass
from policystrata.scan_models import (
    FindingConfidence,
    FindingSeverity,
    GateDecision,
    GateOutcome,
    ImportedTrace,
    ScanConfig,
    ScanFinding,
    StateAssertionConfig,
)

ADAPTER_TRACE_IMPORT = "trace_import"
ADAPTER_SQL_GUARD = "sql_guard"
ADAPTER_DB_RESULTS = "db_results"
ADAPTER_FINDING_EMISSION = "finding_emission"

SCENARIO_MAIN = "main"
SCENARIO_MALFORMED = "malformed_line"
SCENARIO_WRITE_SQL = "write_sql"
SCENARIO_CLEAN_CTE = "clean_cte"
SCENARIO_STATE = "state"

SCENARIO_CONFIGS = {
    SCENARIO_MAIN: "policystrata_main.yaml",
    SCENARIO_MALFORMED: "policystrata_malformed.yaml",
    SCENARIO_WRITE_SQL: "policystrata_write_sql.yaml",
    SCENARIO_CLEAN_CTE: "policystrata_clean_cte.yaml",
    SCENARIO_STATE: "policystrata_state.yaml",
}

Undo = Callable[[], None]
RowShaper = Callable[[list[dict[str, object]]], list[dict[str, object]]]

_GATE_RANK = {"pass": 0, "warn": 1, "fail": 2}
_SEVERITY_RANK = {"info": 0, "warning": 1, "high": 2, "critical": 3}
_THIS_MODULE = sys.modules[__name__]


class Outcome(str, Enum):
    HIDDEN = "HIDDEN"
    INVENTED = "INVENTED"
    NEUTRAL = "NEUTRAL"
    LOUD = "LOUD"


@dataclass(frozen=True)
class ScenarioSignature:
    """Observable scan output: gate outcome plus (finding id, severity) pairs."""

    gate: str
    findings: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class Mutation:
    id: str
    adapter: str
    scenario: str
    description: str
    consequence: str
    apply: Callable[[], Undo]


@dataclass(frozen=True)
class MutationResult:
    mutation_id: str
    adapter: str
    scenario: str
    outcome: Outcome
    consequence: str
    baseline: ScenarioSignature
    mutated: ScenarioSignature | None
    error: str | None


def _patch(target: Any, name: str, value: Any) -> Undo:
    original = getattr(target, name)

    def undo() -> None:
        setattr(target, name, original)

    setattr(target, name, value)
    return undo


def _patch_many(patches: Sequence[tuple[Any, str, Any]]) -> Undo:
    undos = [_patch(target, name, value) for target, name, value in patches]

    def undo() -> None:
        for item in reversed(undos):
            item()

    return undo


def _patch_sql_guard(guard: Callable[[str], None]) -> Undo:
    return _patch_many(
        [
            (database, "assert_read_only_sql", guard),
            (trace_import, "assert_read_only_sql", guard),
            (scanner, "assert_read_only_sql", guard),
        ]
    )


def _apply_trace_rewrite(rewrite: Callable[[ImportedTrace], ImportedTrace]) -> Undo:
    real = trace_import.load_imported_traces

    def loader(paths: list[Path]) -> list[ImportedTrace]:
        return [rewrite(trace) for trace in real(paths)]

    return _patch(scanner, "load_imported_traces", loader)


def _apply_drop_tenant_ids() -> Undo:
    return _apply_trace_rewrite(lambda trace: trace.model_copy(update={"tenant_ids": []}))


def _apply_force_release_denied() -> Undo:
    return _apply_trace_rewrite(lambda trace: trace.model_copy(update={"release_allowed": False}))


def _apply_drop_semantic_ir() -> Undo:
    return _apply_trace_rewrite(lambda trace: trace.model_copy(update={"semantic_ir": None}))


def _swap_denied_metric(trace: ImportedTrace) -> ImportedTrace:
    if trace.semantic_ir is None or trace.semantic_ir.metric != "bookings":
        return trace
    swapped = trace.semantic_ir.model_copy(update={"metric": "ticket_count"})
    return trace.model_copy(update={"semantic_ir": swapped})


def _apply_swap_denied_metric() -> Undo:
    return _apply_trace_rewrite(_swap_denied_metric)


def _apply_stamp_default_principal() -> Undo:
    return _apply_trace_rewrite(lambda trace: trace.model_copy(update={"principal": "acme_analyst"}))


def _apply_drop_source_field() -> Undo:
    return _apply_trace_rewrite(lambda trace: trace.model_copy(update={"source": "imported_trace"}))


def _apply_drop_all_traces() -> Undo:
    def loader(paths: list[Path]) -> list[ImportedTrace]:
        return []

    return _patch(scanner, "load_imported_traces", loader)


def _apply_return_none() -> Undo:
    def loader(paths: list[Path]) -> Any:
        return None

    return _patch(scanner, "load_imported_traces", loader)


def _apply_skip_malformed_lines() -> Undo:
    def loader(paths: list[Path]) -> list[ImportedTrace]:
        traces: list[ImportedTrace] = []
        for path in paths:
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue
                normalized = trace_import.normalize_imported_trace_record(raw)
                if normalized is None:
                    continue
                trace = ImportedTrace.model_validate(normalized)
                trace_import.assert_read_only_sql(trace.sql)
                traces.append(trace)
        return traces

    return _patch(scanner, "load_imported_traces", loader)


def _apply_permissive_sql_guard() -> Undo:
    def guard(sql: str) -> None:
        lowered = sql.strip().lower()
        if not lowered.startswith(("select", "with")):
            raise ValueError("only read-only SELECT or WITH queries are allowed")

    return _patch_sql_guard(guard)


def _apply_cte_rejecting_sql_guard() -> Undo:
    real = database.assert_read_only_sql

    def guard(sql: str) -> None:
        real(sql)
        if sql.lstrip().lower().startswith("with"):
            raise ValueError("adapter mutation: CTE queries rejected as unsafe")

    return _patch_sql_guard(guard)


_STATE_ROWS: tuple[dict[str, object], ...] = (
    {"tenant_id": "acme", "value": 2},
    {"tenant_id": "beta", "value": 1},
)


def _identity_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return rows


_state_row_shaper: RowShaper = _identity_rows


class _StateFixtureAdapter:
    def query(self, sql: str, tenant_id: str | None = None) -> list[dict[str, object]]:
        return _state_row_shaper([dict(row) for row in _STATE_ROWS])


def _truncate_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return rows[:1]


def _rename_tenant_column(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return [
        {("tenant" if key == "tenant_id" else key): value for key, value in row.items()} for row in rows
    ]


def _apply_truncate_result_rows() -> Undo:
    return _patch(_THIS_MODULE, "_state_row_shaper", _truncate_rows)


def _apply_rename_result_columns() -> Undo:
    return _patch(_THIS_MODULE, "_state_row_shaper", _rename_tenant_column)


def _apply_ignore_forbidden_values() -> Undo:
    real = scanner.evaluate_state_assertion

    def weakened(
        check: StateAssertionConfig,
        rows: list[dict[str, Any]],
    ) -> tuple[list[str], WitnessClass]:
        return real(check.model_copy(update={"forbidden_values": {}}), rows)

    return _patch(scanner, "evaluate_state_assertion", weakened)


def _apply_drop_release_findings() -> Undo:
    def silenced(config_path: Path, trace: ImportedTrace, canonical: Any) -> list[ScanFinding]:
        return []

    return _patch(scanner, "scan_trace_authorization", silenced)


def _apply_duplicate_static_findings() -> Undo:
    real = scanner.scan_trace_static_sql

    def doubled(*args: Any, **kwargs: Any) -> list[ScanFinding]:
        found = real(*args, **kwargs)
        return [*found, *(item.model_copy(deep=True) for item in found)]

    return _patch(scanner, "scan_trace_static_sql", doubled)


def _apply_demote_severity() -> Undo:
    real = scanner.finding

    def demoted(
        finding_id: str,
        title: str,
        severity: FindingSeverity,
        confidence: FindingConfidence,
        *args: Any,
        **kwargs: Any,
    ) -> ScanFinding:
        return real(finding_id, title, FindingSeverity.INFO, confidence, *args, **kwargs)

    return _patch(scanner, "finding", demoted)


def _apply_gate_always_passes() -> Undo:
    def gate(findings: list[ScanFinding], config: ScanConfig) -> GateDecision:
        return GateDecision(outcome=GateOutcome.PASS, reasons=["adapter mutation: gate disabled"])

    return _patch(scanner, "decide_gate", gate)


CATALOG: tuple[Mutation, ...] = (
    Mutation(
        id="import_drops_tenant_ids",
        adapter=ADAPTER_TRACE_IMPORT,
        scenario=SCENARIO_MAIN,
        description="Importer strips the tenant_ids field from every trace.",
        consequence=(
            "A placeholder-bound clean trace loses its tenant binding and is falsely "
            "reported as missing tenant scope."
        ),
        apply=_apply_drop_tenant_ids,
    ),
    Mutation(
        id="import_forces_release_denied",
        adapter=ADAPTER_TRACE_IMPORT,
        scenario=SCENARIO_MAIN,
        description="Importer coerces release_allowed to false on every trace.",
        consequence=(
            "Both unsafe-release findings for a released, policy-denied query disappear."
        ),
        apply=_apply_force_release_denied,
    ),
    Mutation(
        id="import_drops_semantic_ir",
        adapter=ADAPTER_TRACE_IMPORT,
        scenario=SCENARIO_MAIN,
        description="Importer drops the semantic IR from every trace.",
        consequence="The policy oracle is never consulted, so authorization findings vanish.",
        apply=_apply_drop_semantic_ir,
    ),
    Mutation(
        id="import_swaps_denied_metric",
        adapter=ADAPTER_TRACE_IMPORT,
        scenario=SCENARIO_MAIN,
        description="Importer rewrites the denied metric alias to an allowed metric.",
        consequence=(
            "Two high release findings collapse into one medium metric-drift warning."
        ),
        apply=_apply_swap_denied_metric,
    ),
    Mutation(
        id="import_stamps_default_principal",
        adapter=ADAPTER_TRACE_IMPORT,
        scenario=SCENARIO_MAIN,
        description="Importer stamps every trace with the default service principal.",
        consequence="The unknown-principal finding disappears and the trace scans clean.",
        apply=_apply_stamp_default_principal,
    ),
    Mutation(
        id="import_drops_all_traces",
        adapter=ADAPTER_TRACE_IMPORT,
        scenario=SCENARIO_MAIN,
        description="Importer silently yields zero traces.",
        consequence=(
            "Every trace finding disappears and the gate passes; no count invariant notices."
        ),
        apply=_apply_drop_all_traces,
    ),
    Mutation(
        id="import_returns_none",
        adapter=ADAPTER_TRACE_IMPORT,
        scenario=SCENARIO_MAIN,
        description="Importer returns None instead of a trace list.",
        consequence="The scan crashes with a TypeError; the fault cannot pass unnoticed.",
        apply=_apply_return_none,
    ),
    Mutation(
        id="import_drops_source_field",
        adapter=ADAPTER_TRACE_IMPORT,
        scenario=SCENARIO_MAIN,
        description="Importer discards trace provenance (source falls back to the default).",
        consequence="Provenance is lost but no finding, severity, or gate outcome changes.",
        apply=_apply_drop_source_field,
    ),
    Mutation(
        id="import_skips_malformed_lines",
        adapter=ADAPTER_TRACE_IMPORT,
        scenario=SCENARIO_MALFORMED,
        description="Importer silently skips malformed JSONL lines instead of rejecting the file.",
        consequence=(
            "A critical input-rejection finding is replaced by a passing scan over partial input."
        ),
        apply=_apply_skip_malformed_lines,
    ),
    Mutation(
        id="sql_guard_accepts_multi_statement",
        adapter=ADAPTER_SQL_GUARD,
        scenario=SCENARIO_WRITE_SQL,
        description="Read-only guard weakened to a bare select/with prefix check.",
        consequence=(
            "A smuggled 'select ...; drop table ...' trace loads and the critical "
            "rejection finding disappears."
        ),
        apply=_apply_permissive_sql_guard,
    ),
    Mutation(
        id="sql_guard_rejects_cte",
        adapter=ADAPTER_SQL_GUARD,
        scenario=SCENARIO_CLEAN_CTE,
        description="Read-only guard over-tightened to reject WITH queries.",
        consequence="A valid CTE trace is rejected, inventing a critical input finding.",
        apply=_apply_cte_rejecting_sql_guard,
    ),
    Mutation(
        id="db_truncates_result_rows",
        adapter=ADAPTER_DB_RESULTS,
        scenario=SCENARIO_STATE,
        description="Adapter query returns only the first result row (emulated).",
        consequence="The cross-tenant row is dropped, so the leak assertion passes.",
        apply=_apply_truncate_result_rows,
    ),
    Mutation(
        id="db_renames_result_columns",
        adapter=ADAPTER_DB_RESULTS,
        scenario=SCENARIO_STATE,
        description="Adapter query renames the tenant_id result column (emulated).",
        consequence="Forbidden-value checks become vacuous and the leak assertion passes.",
        apply=_apply_rename_result_columns,
    ),
    Mutation(
        id="state_eval_ignores_forbidden_values",
        adapter=ADAPTER_FINDING_EMISSION,
        scenario=SCENARIO_STATE,
        description="State-assertion evaluator skips forbidden-value checks.",
        consequence="The cross-tenant leak finding is silenced.",
        apply=_apply_ignore_forbidden_values,
    ),
    Mutation(
        id="emit_drops_release_findings",
        adapter=ADAPTER_FINDING_EMISSION,
        scenario=SCENARIO_MAIN,
        description="Emitter drops the release-authorization finding class.",
        consequence=(
            "Both release findings disappear while the rest of the scan looks healthy."
        ),
        apply=_apply_drop_release_findings,
    ),
    Mutation(
        id="emit_duplicates_static_findings",
        adapter=ADAPTER_FINDING_EMISSION,
        scenario=SCENARIO_MAIN,
        description="Emitter emits every static-SQL finding twice.",
        consequence="A duplicate copy of the tenant-scope finding is invented.",
        apply=_apply_duplicate_static_findings,
    ),
    Mutation(
        id="emit_downgrades_severity",
        adapter=ADAPTER_FINDING_EMISSION,
        scenario=SCENARIO_MAIN,
        description="Emitter forces every finding severity to info.",
        consequence="Every finding id survives but the gate flips from fail to pass.",
        apply=_apply_demote_severity,
    ),
    Mutation(
        id="gate_always_passes",
        adapter=ADAPTER_FINDING_EMISSION,
        scenario=SCENARIO_MAIN,
        description="Gate decision hardcoded to pass.",
        consequence="Findings remain listed but the failure verdict is hidden.",
        apply=_apply_gate_always_passes,
    ),
)


def _signature_rows(findings: Sequence[ScanFinding]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted((item.id, item.severity.value) for item in findings))


def run_scenario(scenario: str, fixture_dir: Path, out_dir: Path) -> ScenarioSignature:
    config_path = fixture_dir / SCENARIO_CONFIGS[scenario]
    if scenario == SCENARIO_STATE:
        config = scanner.load_scan_config(config_path)
        adapter = _StateFixtureAdapter()
        findings = scanner.scan_state_assertions(config, config_path, adapter)
        gate = scanner.decide_gate(findings, config)
        return ScenarioSignature(gate=gate.outcome.value, findings=_signature_rows(findings))
    result = scanner.run_scan(config_path, out_dir)
    return ScenarioSignature(gate=result.gate.outcome.value, findings=_signature_rows(result.findings))


def classify(
    baseline: ScenarioSignature,
    mutated: ScenarioSignature | None,
    error: str | None,
) -> Outcome:
    if error is not None or mutated is None:
        return Outcome.LOUD
    if mutated == baseline:
        return Outcome.NEUTRAL
    base = dict(baseline.findings)
    mut = dict(mutated.findings)
    hidden = any(finding_id not in mut for finding_id in base)
    hidden = hidden or any(
        finding_id in mut and _SEVERITY_RANK[mut[finding_id]] < _SEVERITY_RANK[severity]
        for finding_id, severity in base.items()
    )
    hidden = hidden or _GATE_RANK[mutated.gate] < _GATE_RANK[baseline.gate]
    invented = any(finding_id not in base for finding_id in mut)
    invented = invented or any(
        finding_id in base and _SEVERITY_RANK[severity] > _SEVERITY_RANK[base[finding_id]]
        for finding_id, severity in mut.items()
    )
    invented = invented or _GATE_RANK[mutated.gate] > _GATE_RANK[baseline.gate]
    if hidden:
        return Outcome.HIDDEN
    if invented:
        return Outcome.INVENTED
    return Outcome.NEUTRAL


def run_catalog(fixture_dir: Path, work_dir: Path) -> list[MutationResult]:
    baselines: dict[str, ScenarioSignature] = {}
    results: list[MutationResult] = []
    for index, mutation in enumerate(CATALOG):
        if mutation.scenario not in baselines:
            baselines[mutation.scenario] = run_scenario(
                mutation.scenario,
                fixture_dir,
                work_dir / f"baseline-{mutation.scenario}",
            )
        baseline = baselines[mutation.scenario]
        mutated: ScenarioSignature | None = None
        error: str | None = None
        undo = mutation.apply()
        try:
            mutated = run_scenario(
                mutation.scenario,
                fixture_dir,
                work_dir / f"mutant-{index:02d}-{mutation.id}",
            )
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        finally:
            undo()
        results.append(
            MutationResult(
                mutation_id=mutation.id,
                adapter=mutation.adapter,
                scenario=mutation.scenario,
                outcome=classify(baseline, mutated, error),
                consequence=mutation.consequence,
                baseline=baseline,
                mutated=mutated,
                error=error,
            )
        )
    return results


def outcome_tally(results: Sequence[MutationResult]) -> dict[str, int]:
    return dict(Counter(result.outcome.value for result in results))


def render_markdown_report(results: Sequence[MutationResult]) -> str:
    rows = [
        [result.mutation_id, result.adapter, result.scenario, result.outcome.value, result.consequence]
        for result in results
    ]
    return markdown_table(["Mutation", "Adapter", "Scenario", "Outcome", "Consequence"], rows)
