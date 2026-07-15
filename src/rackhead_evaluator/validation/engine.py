"""Fail-closed validation orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from rackhead_evaluator.errors import (
    ValidationFailure,
    ValidationIssue,
    ValidationStage,
    normalize_pydantic_errors,
)
from rackhead_evaluator.models import Policy, WorkflowDocument
from rackhead_evaluator.parser import read_yaml_mapping

from .referential import referential_issues
from .semantic import semantic_issues


def load_workflow(path: Path) -> WorkflowDocument:
    raw = read_yaml_mapping(path, subject="workflow")
    return validate_workflow_mapping(raw)


def load_policy(path: Path) -> Policy:
    raw = read_yaml_mapping(path, subject="policy")
    return validate_policy_mapping(raw)


def validate_workflow_mapping(raw: dict[str, Any]) -> WorkflowDocument:
    workflow = _validate_model(WorkflowDocument, raw, subject="workflow")
    issues = [*referential_issues(workflow), *semantic_issues(workflow)]
    if issues:
        raise ValidationFailure(issues)
    return workflow


def validate_policy_mapping(raw: dict[str, Any]) -> Policy:
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
        raise ValidationFailure(normalize_pydantic_errors(exc, subject=subject)) from None


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
