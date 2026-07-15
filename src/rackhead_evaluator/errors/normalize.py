"""Normalize third-party validation errors into the public error contract."""

from __future__ import annotations

from pydantic import ValidationError

from .types import ValidationIssue, ValidationStage


def normalize_pydantic_errors(
    error: ValidationError,
    *,
    subject: str,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for item in error.errors(
        include_url=False, include_context=False, include_input=True
    ):
        path = format_path(item["loc"])
        error_type = str(item["type"])
        raw_value = item.get("input")
        message = str(item["msg"])
        stage = (
            ValidationStage.STRUCTURAL
            if subject == "workflow"
            else ValidationStage.POLICY
        )

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

        code, suggestion = pydantic_error_code(error_type, subject=subject)
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


def pydantic_error_code(error_type: str, *, subject: str) -> tuple[str, str]:
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


def format_path(location: tuple[int | str, ...]) -> str:
    path = ""
    for part in location:
        if isinstance(part, int):
            path += f"[{part}]"
        elif path:
            path += f".{part}"
        else:
            path = str(part)
    return path or "$"
