"""Stable public validation error contract."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, NoReturn


class ValidationStage(StrEnum):
    """Validation stage associated with a controlled issue."""

    STRUCTURAL = "structural"
    REFERENTIAL = "referential"
    SEMANTIC = "semantic"
    POLICY = "policy"
    CONFIGURATION = "configuration"


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """A normalized, safe, and deterministic validation issue."""

    code: str
    stage: ValidationStage
    message: str
    path: str | None = None
    value: Any | None = None
    suggestion: str | None = None

    def render(self) -> str:
        """Render a human-readable representation without process state."""

        parts = [f"{self.code} [{self.stage}] {self.message}"]
        if self.path:
            parts.append(f"path: {self.path}")
        if self.value is not None:
            rendered_value = _safe_value(self.value, stage=self.stage)
            if rendered_value is not None:
                parts.append(f"value: {rendered_value}")
        if self.suggestion:
            parts.append(f"suggestion: {self.suggestion}")
        return "\n  ".join(parts)


class ValidationFailure(Exception):
    """Controlled validation failure containing one or more normalized issues."""

    def __init__(self, issues: list[ValidationIssue]) -> None:
        if not issues:
            raise ValueError("ValidationFailure requires at least one issue")
        self.issues = tuple(issues)
        super().__init__("; ".join(issue.code for issue in issues))


def fail(issue: ValidationIssue) -> NoReturn:
    """Raise a controlled failure for one issue."""

    raise ValidationFailure([issue])


def _safe_value(value: Any, *, stage: ValidationStage) -> str | None:
    """Render bounded values without echoing arbitrary structural input."""

    if stage in {ValidationStage.STRUCTURAL, ValidationStage.POLICY} and not isinstance(
        value, (bool, int, float)
    ):
        return None
    rendered = repr(value)
    if len(rendered) > 200:
        return f"{rendered[:197]}..."
    return rendered
