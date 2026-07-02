from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

RuntimeMode = Literal["shadow", "enforce"]
RuntimeDecisionPoint = Literal["pre_model", "execution"]
RuntimeApprovalState = Literal["not_required", "pending", "satisfied"]
RuntimeWriteState = Literal["disabled", "enabled"]


@dataclass(frozen=True)
class RuntimeDecision:
    allowed: bool
    reasons: list[str]
    action: str
    resource: str
    normalized_roles: list[str]
    manifest_version: str
    enforcement_mode: RuntimeMode

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reasons": self.reasons,
            "action": self.action,
            "resource": self.resource,
            "normalizedRoles": self.normalized_roles,
            "manifestVersion": self.manifest_version,
            "enforcementMode": self.enforcement_mode,
        }


@dataclass(frozen=True)
class RuntimeToolDecision(RuntimeDecision):
    tool_name: str
    normalized_role: str | None
    tool_kind: str | None
    user_id: str | None
    household_id: str | None
    write_state: RuntimeWriteState
    approval_state: RuntimeApprovalState
    decision_point: RuntimeDecisionPoint

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result["toolName"] = self.tool_name
        result["normalizedRole"] = self.normalized_role
        result["toolKind"] = self.tool_kind
        result["userId"] = self.user_id
        result["householdId"] = self.household_id
        result["writeState"] = self.write_state
        result["approvalState"] = self.approval_state
        result["decisionPoint"] = self.decision_point
        return result


@dataclass(frozen=True)
class RuntimeReleaseDecision(RuntimeDecision):
    boundary: str

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        result["boundary"] = self.boundary
        return result


@dataclass(frozen=True)
class _RuntimeAction:
    name: str
    kind: str | None
    allowed_roles: tuple[str, ...]
    approval_required: bool
    requires_write_grant: bool
    semantic_constraints: Mapping[str, Any] | None
    release_constraints: Mapping[str, Any] | None


@dataclass(frozen=True)
class _RuntimeResource:
    name: str
    type: str | None
    actions: dict[str, _RuntimeAction]


class PolicyStrataAuthorizer:
    def __init__(self, manifest: Mapping[str, Any]) -> None:
        _validate_manifest(manifest)
        self._manifest = manifest
        self._resources_by_name = _normalize_resources(manifest)
        self._known_roles = _collect_known_roles(manifest, self._resources_by_name)

    def authorize(self, request: Mapping[str, Any]) -> RuntimeDecision:
        mode = _mode(request.get("mode"))
        resource_name = _resource_ref_name(request.get("resource"))
        action_name = _string_value(request.get("action")) or ""
        subject_roles = _subject_role_values(request.get("subject"))
        normalized_roles = _normalize_roles(subject_roles, _role_aliases(self._manifest))
        reasons: list[str] = []
        resource = self._resources_by_name.get(resource_name) if resource_name else None
        action = resource.actions.get(action_name) if resource is not None else None

        if not resource_name:
            reasons.append("missing resource")
        elif resource is None:
            reasons.append(f"unknown resource: {resource_name}")

        if not action_name:
            reasons.append("missing action")
        elif resource is not None and action is None:
            reasons.append(f"unknown action: {action_name} for resource {resource.name}")

        if not subject_roles:
            reasons.append("missing role")
        else:
            for index, subject_role in enumerate(subject_roles):
                normalized_role = normalized_roles[index]
                if normalized_role not in self._known_roles:
                    reasons.append(f"unknown role: {subject_role}")

        if action is not None and normalized_roles:
            allowed_roles = set(action.allowed_roles)
            if not any(role in allowed_roles for role in normalized_roles):
                reasons.append(
                    f"roles {', '.join(normalized_roles)} are not allowed to "
                    f"{action.name} {resource_name}"
                )
            context = request.get("context")
            if action.requires_write_grant and _write_grant_satisfied(context) is not True:
                reasons.append(f"action {action.name} on {resource_name} requires allowWriteTools")
            if action.approval_required and _approval_satisfied(context) is not True:
                reasons.append(f"action {action.name} on {resource_name} requires approval")
            reasons.extend(_semantic_reasons(resource_name, action, _semantic_ir(context)))
            reasons.extend(_release_reasons(resource_name, action, _release_context(context)))

        return RuntimeDecision(
            allowed=not reasons,
            reasons=reasons,
            action=action_name,
            resource=resource_name or "",
            normalized_roles=normalized_roles,
            manifest_version=str(self._manifest.get("version", "")),
            enforcement_mode=mode,
        )

    def authorize_tool(self, request: Mapping[str, Any]) -> RuntimeToolDecision:
        tool_name = _string_value(request.get("toolName")) or _string_value(request.get("tool_name")) or ""
        action_name = _string_value(request.get("action")) or _tool_action_name(
            self._resources_by_name,
            tool_name,
        )
        runtime_resource = self._resources_by_name.get(tool_name)
        runtime_action = runtime_resource.actions.get(action_name) if runtime_resource is not None else None
        decision_point = _decision_point(request.get("decisionPoint") or request.get("decision_point"))
        write_state = _write_state(
            request.get("writeState") or request.get("write_state"),
            request.get("allowWriteTools") or request.get("allow_write_tools"),
        )
        approval_state = _approval_state(
            request.get("approvalState") or request.get("approval_state"),
            request.get("approvalRequiredSatisfied") or request.get("approval_required_satisfied"),
            runtime_action,
        )
        decision = self.authorize(
            {
                "subject": {"role": request.get("role")},
                "action": action_name,
                "resource": tool_name,
                "context": {
                    "allowWriteTools": write_state == "enabled",
                    "approvalRequiredSatisfied": (
                        approval_state == "satisfied" if decision_point == "execution" else True
                    ),
                    "semanticIr": request.get("semanticIr"),
                },
                "mode": request.get("mode"),
            }
        )
        reasons = [
            f"unknown tool: {tool_name}" if reason == f"unknown resource: {tool_name}" else reason
            for reason in decision.reasons
        ]
        requested_tool_kind = _string_value(request.get("toolKind")) or _string_value(
            request.get("tool_kind")
        )
        if (
            runtime_action is not None
            and runtime_action.kind
            and requested_tool_kind
            and requested_tool_kind != runtime_action.kind
        ):
            reasons.append(
                f"tool kind context {requested_tool_kind} does not match manifest kind "
                f"{runtime_action.kind} for {tool_name}"
            )
        return RuntimeToolDecision(
            allowed=not reasons,
            reasons=reasons,
            action=decision.action,
            resource=decision.resource,
            normalized_roles=decision.normalized_roles,
            manifest_version=decision.manifest_version,
            enforcement_mode=decision.enforcement_mode,
            tool_name=tool_name,
            normalized_role=decision.normalized_roles[0] if decision.normalized_roles else None,
            tool_kind=runtime_action.kind if runtime_action is not None else None,
            user_id=_string_value(request.get("userId")) or _string_value(request.get("user_id")),
            household_id=_string_value(request.get("householdId"))
            or _string_value(request.get("household_id")),
            write_state=write_state,
            approval_state=approval_state,
            decision_point=decision_point,
        )

    def authorize_release(self, request: Mapping[str, Any]) -> RuntimeReleaseDecision:
        context: dict[str, Any] = {}
        raw_context = request.get("context")
        if isinstance(raw_context, Mapping):
            context.update(raw_context)
        context["release"] = {
            "boundary": request.get("boundary"),
            "result": request.get("result"),
            "lineage": request.get("lineage"),
        }
        decision = self.authorize(
            {
                "subject": request.get("subject"),
                "action": "release",
                "resource": request.get("resource"),
                "context": context,
                "mode": request.get("mode"),
            }
        )
        boundary = _string_value(request.get("boundary")) or ""
        return RuntimeReleaseDecision(
            allowed=decision.allowed,
            reasons=decision.reasons,
            action=decision.action,
            resource=decision.resource,
            normalized_roles=decision.normalized_roles,
            manifest_version=decision.manifest_version,
            enforcement_mode=decision.enforcement_mode,
            boundary=boundary,
        )


def create_policystrata_authorizer(manifest: Mapping[str, Any]) -> PolicyStrataAuthorizer:
    return PolicyStrataAuthorizer(manifest)


def authorize(manifest: Mapping[str, Any], request: Mapping[str, Any]) -> RuntimeDecision:
    return create_policystrata_authorizer(manifest).authorize(request)


def authorize_tool(manifest: Mapping[str, Any], request: Mapping[str, Any]) -> RuntimeToolDecision:
    return create_policystrata_authorizer(manifest).authorize_tool(request)


def authorize_release(manifest: Mapping[str, Any], request: Mapping[str, Any]) -> RuntimeReleaseDecision:
    return create_policystrata_authorizer(manifest).authorize_release(request)


def _validate_manifest(manifest: Mapping[str, Any]) -> None:
    if manifest.get("defaultDecision") != "deny":
        raise ValueError("PolicyStrata runtime manifests must default to deny")
    if not manifest.get("resources") and not manifest.get("tools"):
        raise ValueError("PolicyStrata runtime manifests must declare resources or tools")
    _normalize_resources(manifest)


def _normalize_resources(manifest: Mapping[str, Any]) -> dict[str, _RuntimeResource]:
    resources_by_name: dict[str, _RuntimeResource] = {}

    for resource in _mapping_sequence(manifest.get("resources")):
        raw_actions = _mapping_sequence(resource.get("actions"))
        actions = {
            action.name: action
            for action in (_normalize_action(raw_action) for raw_action in raw_actions)
        }
        _add_resource(
            resources_by_name,
            _RuntimeResource(
                name=_required_string(resource.get("name"), "PolicyStrata runtime resource is missing name"),
                type=_string_value(resource.get("type")),
                actions=actions,
            ),
        )

    for tool in _mapping_sequence(manifest.get("tools")):
        kind = _required_string(tool.get("kind"), "PolicyStrata runtime tool is missing kind")
        name = _required_string(tool.get("name"), "PolicyStrata runtime tool is missing name")
        action = _normalize_action(
            {
                "name": kind,
                "kind": kind,
                "allowedRoles": tool.get("allowedRoles"),
                "approvalRequired": tool.get("approvalRequired"),
                "requiresWriteGrant": kind == "write",
                "metrics": tool.get("metrics"),
                "dimensions": tool.get("dimensions"),
            }
        )
        _add_resource(
            resources_by_name,
            _RuntimeResource(name=name, type="tool", actions={action.name: action}),
        )

    return resources_by_name


def _normalize_action(action: Mapping[str, Any]) -> _RuntimeAction:
    name = _required_string(action.get("name"), "PolicyStrata runtime action is missing name")
    allowed_roles = tuple(_string_sequence(action.get("allowedRoles")))
    if not allowed_roles:
        raise ValueError(f"PolicyStrata runtime action has no allowed roles: {name}")
    kind = _string_value(action.get("kind"))
    release_constraints = action.get("releaseConstraints")
    return _RuntimeAction(
        name=name,
        kind=kind,
        allowed_roles=allowed_roles,
        approval_required=action.get("approvalRequired") is True,
        requires_write_grant=action.get("requiresWriteGrant") is True or kind == "write",
        semantic_constraints=_semantic_constraints(
            action.get("semanticConstraints"),
            action.get("metrics"),
            action.get("dimensions"),
        ),
        release_constraints=release_constraints if isinstance(release_constraints, Mapping) else None,
    )


def _semantic_constraints(
    raw_constraints: object,
    metrics: object,
    dimensions: object,
) -> Mapping[str, Any] | None:
    if isinstance(raw_constraints, Mapping):
        return raw_constraints
    if metrics is None and dimensions is None:
        return None
    return {"metrics": metrics, "dimensions": dimensions}


def _add_resource(resources_by_name: dict[str, _RuntimeResource], resource: _RuntimeResource) -> None:
    if resource.name in resources_by_name:
        raise ValueError(f"duplicate PolicyStrata runtime resource: {resource.name}")
    if not resource.actions:
        raise ValueError(f"PolicyStrata runtime resource has no actions: {resource.name}")
    resources_by_name[resource.name] = resource


def _collect_known_roles(
    manifest: Mapping[str, Any],
    resources_by_name: Mapping[str, _RuntimeResource],
) -> set[str]:
    known_roles = set(_role_aliases(manifest).values())
    for resource in resources_by_name.values():
        for action in resource.actions.values():
            known_roles.update(action.allowed_roles)
    return known_roles


def _role_aliases(manifest: Mapping[str, Any]) -> Mapping[str, str]:
    aliases = manifest.get("roleAliases")
    if not isinstance(aliases, Mapping):
        return {}
    return {str(key): value for key, value in aliases.items() if isinstance(value, str)}


def _resource_ref_name(resource: object) -> str | None:
    if isinstance(resource, str):
        return resource or None
    if isinstance(resource, Mapping):
        return _string_value(resource.get("name")) or _string_value(resource.get("id"))
    return None


def _subject_role_values(subject: object) -> list[str]:
    if subject is None:
        return []
    if isinstance(subject, str):
        return [subject]
    if not isinstance(subject, Mapping):
        return []

    roles: list[str] = []
    role = _string_value(subject.get("role"))
    if role:
        roles.append(role)
    for item in _string_sequence(subject.get("roles")):
        if item not in roles:
            roles.append(item)
    return roles


def _normalize_roles(roles: Sequence[str], aliases: Mapping[str, str]) -> list[str]:
    return [aliases.get(role, role) for role in roles]


def _write_grant_satisfied(context: object) -> bool | None:
    if not isinstance(context, Mapping):
        return None
    return _bool_value(context.get("allowWriteTools"), context.get("allow_write_tools"))


def _approval_satisfied(context: object) -> bool | None:
    if not isinstance(context, Mapping):
        return None
    return _bool_value(context.get("approvalRequiredSatisfied"), context.get("approval_required_satisfied"))


def _semantic_ir(context: object) -> Mapping[str, Any] | None:
    if not isinstance(context, Mapping):
        return None
    semantic = context.get("semanticIr")
    if not isinstance(semantic, Mapping):
        semantic = context.get("semantic_ir")
    return semantic if isinstance(semantic, Mapping) else None


def _release_context(context: object) -> Mapping[str, Any] | None:
    if not isinstance(context, Mapping):
        return None
    release = context.get("release")
    return release if isinstance(release, Mapping) else None


def _tool_action_name(resources_by_name: Mapping[str, _RuntimeResource], tool_name: str) -> str:
    resource = resources_by_name.get(tool_name)
    if resource is None:
        return "run"
    non_release_actions = [action_name for action_name in resource.actions if action_name != "release"]
    if len(non_release_actions) == 1:
        return non_release_actions[0]
    if len(resource.actions) != 1:
        return "run"
    return next(iter(resource.actions))


def _semantic_reasons(
    resource_name: str | None,
    action: _RuntimeAction,
    semantic_ir: Mapping[str, Any] | None,
) -> list[str]:
    if semantic_ir is None or action.semantic_constraints is None:
        return []

    reasons: list[str] = []
    metrics = set(_string_sequence(action.semantic_constraints.get("metrics")))
    metric = _string_value(semantic_ir.get("metric"))
    if metric and metrics and metric not in metrics:
        reasons.append(f"metric {metric} is not declared for {action.name} {resource_name}")

    dimensions = set(_string_sequence(action.semantic_constraints.get("dimensions")))
    for dimension in _string_sequence(semantic_ir.get("dimensions")):
        if dimensions and dimension not in dimensions:
            reasons.append(f"dimension {dimension} is not declared for {action.name} {resource_name}")
    return reasons


def _release_reasons(
    resource_name: str | None,
    action: _RuntimeAction,
    release: Mapping[str, Any] | None,
) -> list[str]:
    constraints = action.release_constraints
    if constraints is None:
        return []
    if release is None:
        return [f"missing release context for {action.name} {resource_name}"]

    reasons: list[str] = []
    boundary = _string_value(release.get("boundary"))
    boundaries = set(_string_sequence(constraints.get("boundaries")))
    if boundary is None:
        reasons.append(f"missing release boundary for {action.name} {resource_name}")
    elif boundaries and boundary not in boundaries:
        reasons.append(f"release boundary {boundary} is not declared for {action.name} {resource_name}")

    result = release.get("result")
    result_mapping = result if isinstance(result, Mapping) else {}
    result_kind = _string_value(result_mapping.get("kind"))
    result_kinds = set(_string_sequence(constraints.get("resultKinds")))
    if result_kind and result_kinds and result_kind not in result_kinds:
        reasons.append(f"result kind {result_kind} is not declared for {action.name} {resource_name}")

    row_count = result_mapping.get("rowCount")
    max_rows = constraints.get("maxRows")
    if isinstance(row_count, int) and isinstance(max_rows, int) and row_count > max_rows:
        reasons.append(f"row count {row_count} exceeds release max rows {max_rows}")
    contains_sensitive = result_mapping.get("containsSensitiveValues") is True
    if contains_sensitive and constraints.get("allowSensitive") is not True:
        reasons.append(f"release result contains sensitive values for {action.name} {resource_name}")

    lineage = release.get("lineage")
    lineage_mapping = lineage if isinstance(lineage, Mapping) else {}
    lineage_sources = _string_sequence(lineage_mapping.get("sources"))
    if constraints.get("requireLineage") is True and not lineage_sources:
        reasons.append(f"release lineage is required for {action.name} {resource_name}")
    if lineage_mapping.get("containsRawRows") is True and constraints.get("allowRawRows") is not True:
        reasons.append(f"release lineage contains raw rows for {action.name} {resource_name}")

    allowed_sources = set(_string_sequence(constraints.get("lineageSources")))
    if allowed_sources:
        for source in lineage_sources:
            if source not in allowed_sources:
                reasons.append(f"lineage source {source} is not declared for {action.name} {resource_name}")

    return reasons


def _mode(value: object) -> RuntimeMode:
    if value == "enforce":
        return "enforce"
    return "shadow"


def _decision_point(value: object) -> RuntimeDecisionPoint:
    if value == "pre_model":
        return "pre_model"
    return "execution"


def _write_state(value: object, allow_write_tools: object) -> RuntimeWriteState:
    if value == "enabled":
        return "enabled"
    if value == "disabled":
        return "disabled"
    return "enabled" if allow_write_tools is True else "disabled"


def _approval_state(
    value: object,
    approval_required_satisfied: object,
    runtime_action: _RuntimeAction | None,
) -> RuntimeApprovalState:
    if value == "not_required":
        return "not_required"
    if value == "pending":
        return "pending"
    if value == "satisfied":
        return "satisfied"
    if approval_required_satisfied is True:
        return "satisfied"
    return "pending" if runtime_action is not None and runtime_action.approval_required else "not_required"


def _mapping_sequence(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _string_sequence(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _string_value(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _required_string(value: object, message: str) -> str:
    result = _string_value(value)
    if result is None:
        raise ValueError(message)
    return result


def _bool_value(primary: object, fallback: object) -> bool | None:
    if isinstance(primary, bool):
        return primary
    return fallback if isinstance(fallback, bool) else None
