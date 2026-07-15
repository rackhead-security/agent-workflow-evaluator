"""Typed models for workflow schema and policy version 0.1."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StringConstraints,
    field_validator,
    model_validator,
)

Identifier = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
    ),
]
NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
RuleId = Literal[
    "RH-AWE-001",
    "RH-AWE-002",
    "RH-AWE-003",
    "RH-AWE-004",
    "RH-AWE-005",
    "RH-AWE-006",
    "RH-AWE-007",
    "RH-AWE-008",
]

DEFAULT_RULE_IDS: tuple[RuleId, ...] = (
    "RH-AWE-001",
    "RH-AWE-002",
    "RH-AWE-003",
    "RH-AWE-004",
    "RH-AWE-005",
    "RH-AWE-006",
    "RH-AWE-007",
    "RH-AWE-008",
)


def default_rule_ids() -> list[RuleId]:
    """Return a new list so model instances do not share mutable state."""

    return list(DEFAULT_RULE_IDS)


class StrictModel(BaseModel):
    """Base model that rejects unknown fields and silent coercion drift."""

    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
        str_strip_whitespace=True,
    )


class DeploymentStage(StrEnum):
    TOY = "toy"
    INTERNAL = "internal"
    PRODUCTION = "production"


class MaxAutonomy(StrEnum):
    DRAFT_ONLY = "draft_only"
    READ_ONLY = "read_only"
    APPROVED_ACTIONS = "approved_actions"
    AUTONOMOUS_ACTIONS = "autonomous_actions"


class DataSourceType(StrEnum):
    DOCUMENT_STORE = "document_store"
    WEB = "web"
    EMAIL = "email"
    CHAT = "chat"
    DATABASE = "database"
    FILE_SYSTEM = "file_system"
    API = "api"
    SYNTHETIC = "synthetic"


class TrustLevel(StrEnum):
    TRUSTED = "trusted"
    MIXED = "mixed"
    UNTRUSTED = "untrusted"


class Sensitivity(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


SENSITIVITY_ORDER: dict[Sensitivity, int] = {
    Sensitivity.PUBLIC: 0,
    Sensitivity.INTERNAL: 1,
    Sensitivity.CONFIDENTIAL: 2,
    Sensitivity.RESTRICTED: 3,
}


class AccessControl(StrEnum):
    NONE = "none"
    USER_SCOPED = "user_scoped"
    SERVICE_SCOPED = "service_scoped"
    REPOSITORY_SCOPED = "repository_scoped"


class ToolMode(StrEnum):
    READ = "read"
    INTERNAL_WRITE = "internal_write"
    EXTERNAL_WRITE = "external_write"
    DESTRUCTIVE = "destructive"
    CODE_EXECUTION = "code_execution"


class ToolIdentity(StrEnum):
    USER_DELEGATED = "user_delegated"
    SERVICE_ACCOUNT = "service_account"
    ANONYMOUS = "anonymous"
    UNKNOWN = "unknown"


class RetentionMode(StrEnum):
    NONE = "none"
    SESSION = "session"
    FIXED_DAYS = "fixed_days"
    INDEFINITE = "indefinite"


class OutputType(StrEnum):
    CHAT = "chat"
    FILE = "file"
    EMAIL = "email"
    TICKET = "ticket"
    API = "api"
    PUBLIC_WEB = "public_web"
    CODE_CHANGE = "code_change"


class OutputBoundary(StrEnum):
    INTERNAL = "internal"
    EXTERNAL = "external"
    PUBLIC = "public"


class Severity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class WorkflowMetadata(StrictModel):
    id: Identifier
    name: NonEmptyString
    version: NonEmptyString
    description: str | None = None
    owners: list[NonEmptyString] = Field(min_length=1)


class RiskProfile(StrictModel):
    deployment_stage: DeploymentStage
    max_autonomy: MaxAutonomy


class DataSource(StrictModel):
    id: Identifier
    name: NonEmptyString
    type: DataSourceType
    trust: TrustLevel
    sensitivity: Sensitivity
    access_control: AccessControl


class Tool(StrictModel):
    id: Identifier
    name: NonEmptyString
    mode: ToolMode
    identity: ToolIdentity
    allowed_domains: list[NonEmptyString]
    allowed_paths: list[str]
    logs_arguments: StrictBool
    logs_results: StrictBool


class MemoryRetention(StrictModel):
    mode: RetentionMode
    days: StrictInt | None = None

    @model_validator(mode="after")
    def validate_days(self) -> MemoryRetention:
        if self.mode is RetentionMode.FIXED_DAYS:
            if self.days is None or self.days <= 0:
                raise ValueError(
                    "days must be a positive integer when mode is fixed_days"
                )
        elif self.days is not None:
            raise ValueError("days is allowed only when mode is fixed_days")
        return self


class Memory(StrictModel):
    id: Identifier
    enabled: StrictBool
    writes_allowed: StrictBool
    review_required: StrictBool
    retention: MemoryRetention
    sensitivity: Sensitivity


class Output(StrictModel):
    id: Identifier
    name: NonEmptyString
    type: OutputType
    boundary: OutputBoundary
    sensitivity_allowed: Sensitivity


class Flow(StrictModel):
    id: Identifier
    from_: Identifier = Field(alias="from")
    through: list[Identifier]
    to: Identifier
    carries: list[Sensitivity]
    transforms: list[NonEmptyString] = Field(default_factory=list)


class Approval(StrictModel):
    id: Identifier
    actions: list[NonEmptyString] = Field(min_length=1)
    approver_role: NonEmptyString
    required: StrictBool

    @field_validator("actions")
    @classmethod
    def validate_action_shape(cls, actions: list[str]) -> list[str]:
        for action in actions:
            prefix, separator, target = action.partition(":")
            if separator != ":" or prefix not in {"tool", "flow"} or not target:
                raise ValueError("actions must use tool:<id> or flow:<id>")
        return actions


class Monitoring(StrictModel):
    log_tool_calls: StrictBool = False
    log_tool_arguments: StrictBool = False
    log_tool_results: StrictBool = False
    log_retrieved_sources: StrictBool = False
    alert_on_external_write: StrictBool = False
    alert_on_policy_block: StrictBool = False
    retention_days: StrictInt | None = Field(default=None, gt=0)


class DeclaredException(StrictModel):
    rule_id: RuleId
    object_ref: NonEmptyString
    justification: NonEmptyString
    owner: NonEmptyString
    expires_on: date

    def is_expired(self, *, on_date: date | None = None) -> bool:
        comparison_date = on_date or date.today()
        return self.expires_on < comparison_date


class WorkflowDocument(StrictModel):
    schema_version: Literal["0.1"]
    workflow: WorkflowMetadata
    risk_profile: RiskProfile
    data_sources: list[DataSource]
    tools: list[Tool]
    memory: Memory | None
    outputs: list[Output]
    flows: list[Flow]
    approvals: list[Approval]
    monitoring: Monitoring
    exceptions: list[DeclaredException]


class Policy(StrictModel):
    policy_version: Literal["0.1"]
    blocking_severity: Severity = Severity.HIGH
    enabled_rules: list[RuleId] = Field(default_factory=default_rule_ids)
