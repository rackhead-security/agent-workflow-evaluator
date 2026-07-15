from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from rackhead_evaluator.errors import ValidationFailure
from rackhead_evaluator.validation import load_policy


def write_policy(path: Path, data: dict[str, object]) -> Path:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def test_valid_policy(tmp_path: Path) -> None:
    policy = load_policy(
        write_policy(
            tmp_path / "policy.yaml",
            {
                "policy_version": "0.1",
                "blocking_severity": "high",
                "enabled_rules": ["RH-AWE-001", "RH-AWE-007"],
            },
        )
    )
    assert policy.enabled_rules == ["RH-AWE-001", "RH-AWE-007"]


def test_unsupported_policy_version(tmp_path: Path) -> None:
    with pytest.raises(ValidationFailure) as caught:
        load_policy(write_policy(tmp_path / "policy.yaml", {"policy_version": "0.2"}))
    assert caught.value.issues[0].code == "RH-POLICY-STRUCT-VERSION-001"


def test_unknown_policy_rule_id(tmp_path: Path) -> None:
    with pytest.raises(ValidationFailure) as caught:
        load_policy(
            write_policy(
                tmp_path / "policy.yaml",
                {
                    "policy_version": "0.1",
                    "enabled_rules": ["RH-AWE-999"],
                },
            )
        )
    assert {issue.code for issue in caught.value.issues} == {"RH-POLICY-STRUCT-005"}


def test_policy_cannot_contain_unknown_fields(tmp_path: Path) -> None:
    with pytest.raises(ValidationFailure) as caught:
        load_policy(
            write_policy(
                tmp_path / "policy.yaml",
                {"policy_version": "0.1", "disable_schema_validation": True},
            )
        )
    assert {issue.code for issue in caught.value.issues} == {"RH-POLICY-STRUCT-003"}
