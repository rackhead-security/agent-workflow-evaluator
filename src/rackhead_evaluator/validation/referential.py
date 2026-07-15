"""Referential validation for schema version 0.1."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import Any

from rackhead_evaluator.errors import ValidationIssue, ValidationStage
from rackhead_evaluator.models import WorkflowDocument


def referential_issues(workflow: WorkflowDocument) -> list[ValidationIssue]:
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

    object_refs = known_object_refs(workflow)
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


def known_object_refs(workflow: WorkflowDocument) -> set[str]:
    refs = {
        *(f"tool:{item.id}" for item in workflow.tools),
        *(f"flow:{item.id}" for item in workflow.flows),
        *(f"data_source:{item.id}" for item in workflow.data_sources),
        *(f"output:{item.id}" for item in workflow.outputs),
        *(f"approval:{item.id}" for item in workflow.approvals),
        f"workflow:{workflow.workflow.id}",
        "monitoring:global",
    }
    if workflow.memory is not None:
        refs.add(f"memory:{workflow.memory.id}")
    return refs


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
