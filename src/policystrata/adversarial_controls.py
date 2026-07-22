"""Adversarial clean controls at scale.

The shipped clean-control suite has 80 cases, which the review flagged as too
small a denominator for a precision claim. This module generates 1000+ clean
controls built from adversarial archetypes - legitimate configurations that a
naive detector is tempted to flag but that carry no policy violation:

* ``authorized`` - an ordinary allowed query.
* ``staged_rollout`` - an allowed query whose surface versions are legitimately
  skewed (a rollout in progress), which a version-equality check would flag.
* ``feature_flag`` - an allowed query carrying a flag filter.
* ``boundary_budget`` - an allowed query at exactly the role's row budget.
* ``service_account_ambient`` - the broadest-tenant principal legitimately
  reading across the tenants it owns.
* ``correctly_denied_metric`` / ``correctly_denied_dimension`` - a request the
  policy legitimately denies and the whole stack correctly denies. The
  responsibility-contract detector returns CLEAN (the layers agreed to deny),
  but a naive "flag anything the policy denies" checker false-positives here.

All archetypes are ``mutation = none`` and expected CLEAN. The existing 80-case
suite is untouched, so its frozen bytes are unchanged; this is a separate,
opt-in suite.

Why this matters and its honest limit: in the deterministic simulator a clean
control cannot make a *decision-based* detector fire, because clean-by-
construction means every surface agrees. So the contract detector's
false-positive rate here is 0 by construction, and so is a version-equality
check (nothing reads surface versions). The archetypes that actually separate
detectors are the *correctly-denied* ones: naive denial-flagging baselines
false-positive on legitimate denials while the contract detector does not
(measure this with :func:`policystrata.baselines.evaluate_false_positives`).
Strong precision evidence on genuinely ambiguous benign skew still has to come
from the scanner on real inputs, not from this simulator.
"""

from __future__ import annotations

import random

from policystrata.generator import (
    authorized_query,
    denied_dimension_query,
    denied_metric_query,
    validate_generated_count,
)
from policystrata.models import Policy, Principal, SurfaceVersions, Task, WitnessClass

ADVERSARIAL_CLEAN_CONTROLS_SUITE = "adversarial_clean_controls"
NO_MUTATION_ID = "none"
DEFAULT_ADVERSARIAL_CLEAN_COUNT = 1000
DEFAULT_ADVERSARIAL_CLEAN_SEED = 260628

ARCHETYPES = (
    "authorized",
    "staged_rollout",
    "feature_flag",
    "boundary_budget",
    "service_account_ambient",
    "correctly_denied_metric",
    "correctly_denied_dimension",
)


def _broadest_principal(policy: Policy) -> Principal:
    return max(policy.principals.values(), key=lambda principal: (len(principal.tenant_ids), principal.id))


def generate_adversarial_clean_control_tasks(
    domain: str,
    policy: Policy,
    surface_versions: SurfaceVersions,
    count: int = DEFAULT_ADVERSARIAL_CLEAN_COUNT,
    seed: int = DEFAULT_ADVERSARIAL_CLEAN_SEED,
) -> list[Task]:
    count = validate_generated_count(count)
    rng = random.Random(seed)
    principals = sorted(policy.principals.values(), key=lambda principal: principal.id)
    non_admin = [p for p in principals if "admin" not in p.role] or principals
    broadest = _broadest_principal(policy)
    versions = surface_versions.as_dict()
    tasks: list[Task] = []

    for index in range(count):
        archetype = ARCHETYPES[index % len(ARCHETYPES)]
        principal = non_admin[index % len(non_admin)]
        role = policy.roles[principal.role]
        task_versions = surface_versions

        if archetype == "authorized":
            query = authorized_query(policy, principal, rng)
            request = f"Adversarial clean {index + 1}: authorized query stays clean."
        elif archetype == "staged_rollout":
            query = authorized_query(policy, principal, rng)
            # Benign version skew: grammar and validator are mid-rollout ahead of
            # the manifest. A version-equality check would flag this; policy is
            # not violated.
            task_versions = surface_versions.model_copy(
                update={
                    "grammar": f"{versions['grammar']}-rollout",
                    "validator": f"{versions['validator']}-rollout",
                }
            )
            request = f"Adversarial clean {index + 1}: staged rollout skews versions but not policy."
        elif archetype == "feature_flag":
            base = authorized_query(policy, principal, rng)
            query = base.model_copy(update={"filters": {**base.filters, "feature_flag": True}})
            request = f"Adversarial clean {index + 1}: feature-flagged query is authorized."
        elif archetype == "boundary_budget":
            query = authorized_query(policy, principal, rng).model_copy(
                update={"limit": role.max_rows}
            )
            request = f"Adversarial clean {index + 1}: exactly the row budget is still clean."
        elif archetype == "service_account_ambient":
            principal = broadest
            query = authorized_query(policy, broadest, rng)
            request = (
                f"Adversarial clean {index + 1}: service account reads across its "
                f"{len(broadest.tenant_ids)} owned tenants (legitimate ambient authority)."
            )
        elif archetype == "correctly_denied_metric":
            query = denied_metric_query(policy, principal, rng)
            request = (
                f"Adversarial clean {index + 1}: policy correctly denies this metric; "
                "the stack agrees, so there is no drift."
            )
        else:  # correctly_denied_dimension
            query = denied_dimension_query(policy, principal, rng)
            request = (
                f"Adversarial clean {index + 1}: policy correctly denies this dimension; "
                "the stack agrees, so there is no drift."
            )

        tasks.append(
            Task(
                id=f"adversarial_clean_{index + 1:05d}",
                domain=domain,
                principal=principal.id,
                request=request,
                policy_version=policy.version,
                surface_versions=task_versions,
                mutation=NO_MUTATION_ID,
                semantic_query=query,
                expected_witness_class=WitnessClass.CLEAN,
                expected_localized_surface="release",
            )
        )

    rng.shuffle(tasks)
    return tasks
