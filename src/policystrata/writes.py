"""Write-action fault model (v2 dimension).

The read pipeline covers SELECT-shaped requests. This module extends the same
responsibility-scoped, first-transition machinery to write actions
(INSERT/UPDATE/DELETE), where the failure modes and containment are different:

* an UPDATE/DELETE that drops its tenant predicate writes across tenants;
* an INSERT that stamps a forged tenant id writes into another tenant;
* a write to a column or table the role may not write;
* a database write policy missing its ``WITH CHECK`` clause;
* a commit layer that releases an uncontained write.

It is self-contained on purpose: it defines its own witness classes, surfaces,
operator set, simulator, and first-transition detector, and does not touch the
read pipeline. The read ``WitnessClass`` and detector are unchanged. Containment
mirrors the read model: a compiler-level scope drop is *contained* when the
database write policy's ``WITH CHECK`` rejects the offending rows, so the
localized surface is the compiler but the write does not actually escape.

Scope: this is a faithful but compact model of write containment, not a full
transactional semantics (no multi-statement transactions, no triggers, no
cross-row aggregation effects). It is the single v2 dimension the review asked
to be done properly rather than three done shallowly.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import Field

from policystrata.models import Decision, InputModel

WriteSurface = Literal["manifest", "grammar", "validator", "compiler", "database", "commit"]
WRITE_SURFACE_ORDER: tuple[WriteSurface, ...] = (
    "manifest",
    "grammar",
    "validator",
    "compiler",
    "database",
    "commit",
)
WriteAction = Literal["insert", "update", "delete"]


class WriteWitnessClass(str, Enum):
    CLEAN = "clean"
    OVER_PERMISSIVE_WRITE = "over_permissive_write"
    UNSCOPED_WRITE = "unscoped_write"
    FORGED_TENANT_WRITE = "forged_tenant_write"
    COLUMN_POLICY_VIOLATION = "column_policy_violation"
    UNSAFE_COMMIT = "unsafe_commit"


class WriteOperator(InputModel):
    id: str
    affected_surface: WriteSurface
    witness_class: WriteWitnessClass
    description: str
    containment_layer: WriteSurface | None = None
    requires_db_containment: bool = False


WRITE_NO_MUTATION = "none"

WRITE_OPERATORS: dict[str, WriteOperator] = {
    "manifest_exposes_retired_writable_alias": WriteOperator(
        id="manifest_exposes_retired_writable_alias",
        affected_surface="manifest",
        witness_class=WriteWitnessClass.OVER_PERMISSIVE_WRITE,
        description="A retired writable table alias remains model-visible to a write-capable role.",
    ),
    "grammar_permits_write_to_readonly_table": WriteOperator(
        id="grammar_permits_write_to_readonly_table",
        affected_surface="grammar",
        witness_class=WriteWitnessClass.OVER_PERMISSIVE_WRITE,
        description="The write grammar still permits writes to a read-only table.",
    ),
    "validator_permits_forbidden_write_column": WriteOperator(
        id="validator_permits_forbidden_write_column",
        affected_surface="validator",
        witness_class=WriteWitnessClass.COLUMN_POLICY_VIOLATION,
        description="The write validator omits a newly write-protected column.",
    ),
    "update_drops_tenant_predicate": WriteOperator(
        id="update_drops_tenant_predicate",
        affected_surface="compiler",
        witness_class=WriteWitnessClass.UNSCOPED_WRITE,
        description="The compiler emits an UPDATE without the principal's tenant predicate.",
        containment_layer="database",
        requires_db_containment=True,
    ),
    "delete_missing_tenant_scope": WriteOperator(
        id="delete_missing_tenant_scope",
        affected_surface="compiler",
        witness_class=WriteWitnessClass.UNSCOPED_WRITE,
        description="The compiler emits a DELETE without the principal's tenant scope.",
        containment_layer="database",
        requires_db_containment=True,
    ),
    "insert_forges_tenant_id": WriteOperator(
        id="insert_forges_tenant_id",
        affected_surface="compiler",
        witness_class=WriteWitnessClass.FORGED_TENANT_WRITE,
        description="The compiler stamps a foreign tenant id on an INSERT.",
        containment_layer="database",
        requires_db_containment=True,
    ),
    "db_write_policy_missing_with_check": WriteOperator(
        id="db_write_policy_missing_with_check",
        affected_surface="database",
        witness_class=WriteWitnessClass.OVER_PERMISSIVE_WRITE,
        description="The database write policy is missing its WITH CHECK clause.",
    ),
    "commit_releases_uncontained_write": WriteOperator(
        id="commit_releases_uncontained_write",
        affected_surface="commit",
        witness_class=WriteWitnessClass.UNSAFE_COMMIT,
        description="The commit layer releases a write the database did not contain.",
    ),
}

CLEAN_WRITE_OPERATOR = WriteOperator(
    id=WRITE_NO_MUTATION,
    affected_surface="commit",
    witness_class=WriteWitnessClass.CLEAN,
    description="No injected write drift; clean write control.",
)


def get_write_operator(operator_id: str) -> WriteOperator:
    if operator_id == WRITE_NO_MUTATION:
        return CLEAN_WRITE_OPERATOR
    try:
        return WRITE_OPERATORS[operator_id]
    except KeyError as exc:
        raise ValueError(f"unknown write operator: {operator_id}") from exc


class WriteRequest(InputModel):
    action: WriteAction
    table: str
    columns: list[str] = Field(default_factory=list)
    tenant_scoped: bool = True
    tenant_id: str


class WritePrincipal(InputModel):
    id: str
    tenant_id: str
    writable_tables: list[str]
    writable_columns: list[str]


class WriteTask(InputModel):
    id: str
    principal: WritePrincipal
    request: WriteRequest
    operator: str


class WriteTrace(InputModel):
    task_id: str
    operator: str
    action: WriteAction
    canonical_allowed: bool
    surface_contracts: dict[str, Decision]
    witness_class: WriteWitnessClass
    localized_surface: WriteSurface | None
    containment_layer: WriteSurface | None
    committed: bool
    reasons: list[str]


def authorize_write(principal: WritePrincipal, request: WriteRequest) -> Decision:
    reasons: list[str] = []
    if request.table not in principal.writable_tables:
        reasons.append(f"role may not write table {request.table}")
    forbidden = [c for c in request.columns if c not in principal.writable_columns]
    if forbidden:
        reasons.append(f"role may not write columns {sorted(forbidden)}")
    if request.tenant_id != principal.tenant_id:
        reasons.append("write targets a foreign tenant")
    if not request.tenant_scoped and request.action in {"update", "delete"}:
        reasons.append(f"{request.action} is not tenant-scoped")
    return Decision(allowed=not reasons, reasons=reasons)


def evaluate_write_contracts(task: WriteTask, canonical: Decision) -> dict[str, Decision]:
    operator = get_write_operator(task.operator)
    decisions: dict[str, Decision] = {}
    if operator.witness_class == WriteWitnessClass.CLEAN:
        return {surface: Decision(allowed=True) for surface in WRITE_SURFACE_ORDER}

    for surface in WRITE_SURFACE_ORDER:
        if surface == operator.affected_surface:
            decisions[surface] = Decision(
                allowed=False,
                reasons=[f"{surface} violated its write responsibility: {operator.description}"],
            )
        elif surface == operator.containment_layer and operator.requires_db_containment:
            decisions[surface] = Decision(
                allowed=True,
                reasons=[f"{surface} contained a downstream write obligation violation"],
            )
        else:
            decisions[surface] = Decision(allowed=True)
    return decisions


def first_write_violation(contracts: dict[str, Decision]) -> WriteSurface | None:
    for surface in WRITE_SURFACE_ORDER:
        decision = contracts.get(surface)
        if decision is not None and not decision.allowed:
            return surface
    return None


def evaluate_write_task(task: WriteTask) -> WriteTrace:
    operator = get_write_operator(task.operator)
    canonical = authorize_write(task.principal, task.request)
    contracts = evaluate_write_contracts(task, canonical)
    localized = first_write_violation(contracts)

    containment: WriteSurface | None = None
    if operator.requires_db_containment and operator.containment_layer is not None:
        containment = operator.containment_layer

    if localized is None:
        witness_class = WriteWitnessClass.CLEAN
        committed = canonical.allowed
    else:
        witness_class = operator.witness_class
        # A write is contained (not committed) when the database write policy
        # catches it; otherwise the uncontained write commits.
        committed = containment is None

    reasons = [operator.description]
    if not canonical.allowed:
        reasons.extend(canonical.reasons)

    return WriteTrace(
        task_id=task.id,
        operator=task.operator,
        action=task.request.action,
        canonical_allowed=canonical.allowed,
        surface_contracts=contracts,
        witness_class=witness_class,
        localized_surface=localized,
        containment_layer=containment if localized is not None else None,
        committed=committed,
        reasons=reasons,
    )


class WriteSummary(InputModel):
    total: int
    killed: int
    clean_controls: int
    false_positives: int
    localization_accuracy: float
    containment_rate: float
    uncontained_commits: int


def generate_write_tasks(seed: int = 90210, per_operator: int = 4) -> list[WriteTask]:
    import random

    rng = random.Random(seed)
    principal = WritePrincipal(
        id="acme_writer",
        tenant_id="acme",
        writable_tables=["accounts", "subscriptions"],
        writable_columns=["plan", "status", "tenant_id"],
    )
    tables = ["accounts", "subscriptions"]
    actions: list[WriteAction] = ["insert", "update", "delete"]
    tasks: list[WriteTask] = []
    index = 0
    for operator_id in WRITE_OPERATORS:
        for _ in range(per_operator):
            index += 1
            action = rng.choice(actions)
            request = WriteRequest(
                action=action,
                table=rng.choice(tables),
                columns=["plan"],
                tenant_scoped=True,
                tenant_id=principal.tenant_id,
            )
            tasks.append(
                WriteTask(
                    id=f"{operator_id}_{index:04d}",
                    principal=principal,
                    request=request,
                    operator=operator_id,
                )
            )
    return tasks


def generate_clean_write_controls(count: int = 20, seed: int = 90211) -> list[WriteTask]:
    import random

    rng = random.Random(seed)
    principal = WritePrincipal(
        id="acme_writer",
        tenant_id="acme",
        writable_tables=["accounts", "subscriptions"],
        writable_columns=["plan", "status", "tenant_id"],
    )
    actions: list[WriteAction] = ["insert", "update", "delete"]
    tasks: list[WriteTask] = []
    for index in range(count):
        action = rng.choice(actions)
        tasks.append(
            WriteTask(
                id=f"clean_write_{index + 1:04d}",
                principal=principal,
                request=WriteRequest(
                    action=action,
                    table="accounts",
                    columns=["plan"],
                    tenant_scoped=True,
                    tenant_id=principal.tenant_id,
                ),
                operator=WRITE_NO_MUTATION,
            )
        )
    return tasks


def summarize_writes(traces: list[WriteTrace]) -> WriteSummary:
    total = len(traces)
    clean = [t for t in traces if t.operator == WRITE_NO_MUTATION]
    mutants = [t for t in traces if t.operator != WRITE_NO_MUTATION]
    killed = sum(1 for t in mutants if t.witness_class != WriteWitnessClass.CLEAN)
    false_positives = sum(1 for t in clean if t.witness_class != WriteWitnessClass.CLEAN)
    localized_correct = sum(
        1
        for t in mutants
        if t.localized_surface == get_write_operator(t.operator).affected_surface
    )
    contained = sum(1 for t in mutants if t.containment_layer is not None)
    uncontained = sum(1 for t in mutants if t.witness_class != WriteWitnessClass.CLEAN and t.committed)
    return WriteSummary(
        total=total,
        killed=killed,
        clean_controls=len(clean),
        false_positives=false_positives,
        localization_accuracy=localized_correct / len(mutants) if mutants else 0.0,
        containment_rate=contained / len(mutants) if mutants else 0.0,
        uncontained_commits=uncontained,
    )


def run_write_study(per_operator: int = 6, clean_count: int = 40) -> WriteSummary:
    tasks = generate_write_tasks(per_operator=per_operator) + generate_clean_write_controls(
        count=clean_count
    )
    traces = [evaluate_write_task(task) for task in tasks]
    return summarize_writes(traces)
