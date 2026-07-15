from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from rackhead_evaluator.models import DeclaredException, MemoryRetention, Policy


def test_fixed_days_requires_positive_days() -> None:
    with pytest.raises(ValidationError):
        MemoryRetention.model_validate({"mode": "fixed_days", "days": 0})


def test_non_fixed_retention_rejects_days() -> None:
    with pytest.raises(ValidationError):
        MemoryRetention.model_validate({"mode": "session", "days": 10})


def test_declared_exception_expiry_helper() -> None:
    exception = DeclaredException.model_validate(
        {
            "rule_id": "RH-AWE-006",
            "object_ref": "tool:python_sandbox",
            "justification": "Synthetic test",
            "owner": "security-reviewer",
            "expires_on": "2026-01-01",
        }
    )
    assert exception.is_expired(on_date=date(2026, 1, 2))
    assert not exception.is_expired(on_date=date(2025, 12, 31))


def test_policy_defaults_to_all_rules() -> None:
    policy = Policy.model_validate({"policy_version": "0.1"})
    assert len(policy.enabled_rules) == 8
    assert policy.enabled_rules[0] == "RH-AWE-001"
    assert policy.enabled_rules[-1] == "RH-AWE-008"
