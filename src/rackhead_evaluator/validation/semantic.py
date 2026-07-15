"""Semantic consistency validation for schema version 0.1."""

from __future__ import annotations

from rackhead_evaluator.errors import ValidationIssue, ValidationStage
from rackhead_evaluator.models import SENSITIVITY_ORDER, Sensitivity, WorkflowDocument


def semantic_issues(workflow: WorkflowDocument) -> list[ValidationIssue]:
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
    if not values:
        raise ValueError("cannot calculate sensitivity for an empty flow")
    return max(values, key=SENSITIVITY_ORDER.__getitem__)
