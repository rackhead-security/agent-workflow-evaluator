"""Fail-closed structural, referential, and semantic validation."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from rackhead_evaluator.errors import ValidationFailure, ValidationIssue, ValidationStage
from rackhead_evaluator.models import (
    SENSITIVITY_ORDER,
    Policy,
    Sensitivity,
    WorkflowDocument,
)
from rackhead_evaluator.parser import read_yaml_mapping

RULE_IDS = {f"RH-AWE-{number:03d}" for number in range(1, 9)}


def load_workflow(path: Path) -> WorkflowDocument:
    """Load and fully validate one workflow document."""

    raw = read_yaml_mapping(path, subject="workflow")
    workflow = _validate_model(WorkflowDocument, raw, subject="workflow")
    issues = [*_referential_issues(workflow), *_semantic_issues(workflow)]
    if issues:
        raise ValidationFailure(issues)
    return workflow


def load_policy(path: Path) -> Policy:
    """Load and structurally validate one optional policy document."""

    raw = read_yaml_mapping(path, subject="policy")
    return _validate_model(Policy, raw, subject="policy")


def _validate_model[ModelT: BaseModel](
    model_type: type[ModelT],
    raw: dict[str, Any],
    *,
    subject: str,
) -> ModelT:
    _validate_version_precondition(raw, subject=subject)
    try:
        return model_type.model_validate(raw)
    except ValidationError as exc:
        raise ValidationFailure(_normalize_pydantic_errors(exc, subject=subject)) from None


def _validate_version_precondition(raw: dict[str, Any], *, subject: str) -> None:
    field = "schema_version" if subject == "workflow" else "policy_version"
    value = raw.get(field)
    if value != "0.1":
        raise ValidationFailure(
            [
                ValidationIssue(
                    code=(
                        "RH-SCHEMA-STRUCT-VERSION-001"
                        if subject == "workflow"
                        else "RH-POLICY-STRUCT-VERSION-001"
                    ),
                    stage=(
                        ValidationStage.STRUCTURAL
                        if subject == "workflow"
                        else ValidationStage.POLICY
                    ),
                    message=f"unsupported or missing {field}",
                    path=field,
                    value=value,
                    suggestion=f'set {field}: "0.1"',
                )
            ]
        )


def _normalize_pydantic_errors(
    error: ValidationError,
    *,
    subject: str,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for item in error.errors(include_url=False, include_context=False, include_input=True):
        path = _format_path(item["loc"])
        error_type = str(item["type"])
        raw_value = item.get("input")
        message = str(item["msg"])
        stage = ValidationStage.STRUCTURAL if subject == "workflow" else ValidationStage.POLICY

        if error_type == "extra_forbidden" and path.endswith("requires_approval"):
            issues.append(
                ValidationIssue(
                    code="RH-SCHEMA-STRUCT-APPROVAL-001",
                    stage=stage,
                    message="approval-like fields are forbidden outside top-level approvals",
                    path=path,
                    value=raw_value,
                    suggestion="remove this field and add a required entry under approvals",
                )
            )
            continue

        code, suggestion = _pydantic_error_code(error_type, subject=subject)
        issues.append(
            ValidationIssue(
                code=code,
                stage=stage,
                message=message,
                path=path,
                value=raw_value,
                suggestion=suggestion,
            )
        )
    return issues


def _pydantic_error_code(error_type: str, *, subject: str) -> tuple[str, str]:
    prefix = "RH-SCHEMA-STRUCT" if subject == "workflow" else "RH-POLICY-STRUCT"
    if error_type == "extra_forbidden":
        return f"{prefix}-003", "remove the unknown field or correct its spelling"
    if error_type == "missing":
        return f"{prefix}-004", "add the required field"
    if error_type in {"enum", "literal_error"}:
        return f"{prefix}-005", "use one of the documented enum values"
    if error_type in {
        "bool_type",
        "date_from_datetime_inexact",
        "date_type",
        "dict_type",
        "int_type",
        "list_type",
        "string_type",
    }:
        return f"{prefix}-006", "use the documented value type"
    if error_type == "string_pattern_mismatch":
        return f"{prefix}-007", "use lowercase letters, digits, hyphens, or underscores"
    if error_type in {"string_too_short", "too_short"}:
        return f"{prefix}-008", "provide a non-empty value"
    if error_type in {"greater_than", "value_error"}:
        return f"{prefix}-009", "use a value consistent with the documented field rules"
    return f"{prefix}-010", "correct the value according to docs/v0.1-spec.md"


def _referential_issues(workflow: WorkflowDocument) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    issues.extend(_duplicate_issues(workflow))

    source_ids = {item.id for item in workflow.data_sources}
    tool_ids = {item.id for item in workflow.tools}
    output_ids = {item.id for item in workflow.outputs}
    memory_ids = {workflow.memory.id} if workflow.memory is not None else set()
    flow_ids = {item.id for item in workflow.flows}

    valid_from = source_ids | tool_ids | memory_ids
    valid_to = output_ids | tool_ids | memory_ids

    for index, flow in enumerate(workflow.flows):
        if flow.from_ not in valid_from:
            issues.append(
                _ref_issue(
                    code="RH-SCHEMA-REF-001",
                    message=f'unknown flow source id "{flow.from_}"',
                    path=f"flows[{index}].from",
                    value=flow.from_,
                    suggestion="reference a declared data source, memory object, or tool",
                )
            )
        for tool_index, tool_id in enumerate(flow.through):
            if tool_id not in tool_ids:
                issues.append(
                    _ref_issue(
                        code="RH-SCHEMA-REF-002",
                        message=f'unknown tool id "{tool_id}"',
                        path=f"flows[{index}].through[{tool_index}]",
                        value=tool_id,
                        suggestion="reference a declared tool id",
                    )
                )
        if flow.to not in valid_to:
            issues.append(
                _ref_issue(
                    code="RH-SCHEMA-REF-003",
                    message=f'unknown flow destination id "{flow.to}"',
                    path=f"flows[{index}].to",
                    value=flow.to,
                    suggestion="reference a declared output, memory object, or tool",
                )
            )
        path_nodes = [flow.from_, *flow.through, flow.to]
        repeated = [node for node, count in Counter(path_nodes).items() if count > 1]
        if repeated:
            issues.append(
                _ref_issue(
                    code="RH-SCHEMA-REF-004",
                    message="flow contains repeated nodes",
                    path=f"flows[{index}]",
                    value=sorted(repeated),
                    suggestion="remove cycles and repeated nodes from the explicit flow",
                )
            )

    for approval_index, approval in enumerate(workflow.approvals):
        for action_index, action in enumerate(approval.actions):
            prefix, _, target = action.partition(":")
            known = target in (tool_ids if prefix == "tool" else flow_ids)
            if not known:
                issues.append(
                    _ref_issue(
                        code="RH-SCHEMA-REF-005",
                        message=f'approval references unknown {prefix} id "{target}"',
                        path=f"approvals[{approval_index}].actions[{action_index}]",
                        value=action,
                        suggestion=f"reference a declared {prefix} id",
                    )
                )

    object_refs = _known_object_refs(workflow)
    for exception_index, exception in enumerate(workflow.exceptions):
        if exception.object_ref not in object_refs:
            issues.append(
                _ref_issue(
                    code="RH-SCHEMA-REF-006",
                    message="exception references an unknown object",
                    path=f"exceptions[{exception_index}].object_ref",
                    value=exception.object_ref,
                    suggestion="use a canonical object reference for a declared workflow object",
                )
            )

    return issues


def _duplicate_issues(workflow: WorkflowDocument) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    collections: list[tuple[str, Iterable[str]]] = [
        ("data_sources", (item.id for item in workflow.data_sources)),
        ("tools", (item.id for item in workflow.tools)),
        ("outputs", (item.id for item in workflow.outputs)),
        ("flows", (item.id for item in workflow.flows)),
        ("approvals", (item.id for item in workflow.approvals)),
    ]
    for name, identifiers in collections:
        duplicates = sorted(item for item, count in Counter(identifiers).items() if count > 1)
        if duplicates:
            issues.append(
                _ref_issue(
                    code="RH-SCHEMA-REF-007",
                    message=f"duplicate ids in {name}",
                    path=name,
                    value=duplicates,
                    suggestion="assign a unique id to each object",
                )
            )

    node_identifiers: list[str] = [
        *(item.id for item in workflow.data_sources),
        *(item.id for item in workflow.tools),
        *(item.id for item in workflow.outputs),
    ]
    if workflow.memory is not None:
        node_identifiers.append(workflow.memory.id)
    collisions = sorted(item for item, count in Counter(node_identifiers).items() if count > 1)
    if collisions:
        issues.append(
            _ref_issue(
                code="RH-SCHEMA-REF-008",
                message="node ids collide across data sources, tools, memory, or outputs",
                path="$",
                value=collisions,
                suggestion="use globally unique ids for every flow-addressable node",
            )
        )
    return issues


def _semantic_issues(workflow: WorkflowDocument) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if (
        workflow.memory is not None
        and not workflow.memory.enabled
        and workflow.memory.writes_allowed
    ):
        issues.append(
            ValidationIssue(
                code="RH-SCHEMA-SEM-001",
                stage=ValidationStage.SEMANTIC,
                message="disabled memory cannot allow writes",
                path="memory.writes_allowed",
                value=True,
                suggestion="set writes_allowed to false or enable memory",
            )
        )

    source_sensitivity = {item.id: item.sensitivity for item in workflow.data_sources}
    if workflow.memory is not None:
        source_sensitivity[workflow.memory.id] = workflow.memory.sensitivity

    for index, flow in enumerate(workflow.flows):
        if not flow.carries:
            issues.append(
                ValidationIssue(
                    code="RH-SCHEMA-SEM-002",
                    stage=ValidationStage.SEMANTIC,
                    message="flow carries must be non-empty",
                    path=f"flows[{index}].carries",
                    value=[],
                    suggestion="declare every possible data classification carried by the flow",
                )
            )
            continue
        declared_max = max(SENSITIVITY_ORDER[item] for item in flow.carries)
        source = source_sensitivity.get(flow.from_)
        if source is not None and declared_max < SENSITIVITY_ORDER[source]:
            issues.append(
                ValidationIssue(
                    code="RH-SCHEMA-SEM-003",
                    stage=ValidationStage.SEMANTIC,
                    message="flow understates source or memory sensitivity",
                    path=f"flows[{index}].carries",
                    value=[item.value for item in flow.carries],
                    suggestion=f"include {source.value} or a more sensitive classification",
                )
            )
    return issues


def effective_flow_sensitivity(
    workflow: WorkflowDocument,
    *,
    flow_id: str,
) -> Sensitivity:
    """Calculate effective sensitivity after validation."""

    flow = next((item for item in workflow.flows if item.id == flow_id), None)
    if flow is None:
        raise KeyError(flow_id)
    values = list(flow.carries)
    source = next(
        (item.sensitivity for item in workflow.data_sources if item.id == flow.from_),
        None,
    )
    if workflow.memory is not None and workflow.memory.id == flow.from_:
        source = workflow.memory.sensitivity
    if source is not None:
        values.append(source)
    return max(values, key=SENSITIVITY_ORDER.__getitem__)


def _known_object_refs(workflow: WorkflowDocument) -> set[str]:
    refs = {
        *(f"tool:{item.id}" for item in workflow.tools),
        *(f"flow:{item.id}" for item in workflow.flows),
        *(f"data_source:{item.id}" for item in workflow.data_sources),
        *(f"output:{item.id}" for item in workflow.outputs),
        f"workflow:{workflow.workflow.id}",
        "monitoring:global",
    }
    if workflow.memory is not None:
        refs.add(f"memory:{workflow.memory.id}")
    return refs


def _ref_issue(
    *,
    code: str,
    message: str,
    path: str,
    value: Any,
    suggestion: str,
) -> ValidationIssue:
    return ValidationIssue(
        code=code,
        stage=ValidationStage.REFERENTIAL,
        message=message,
        path=path,
        value=value,
        suggestion=suggestion,
    )


def _format_path(location: tuple[int | str, ...]) -> str:
    path = ""
    for part in location:
        if isinstance(part, int):
            path += f"[{part}]"
        elif path:
            path += f".{part}"
        else:
            path = str(part)
    return path or "$"
