from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from conftest import clone_workflow, write_yaml

from rackhead_evaluator.errors import ValidationFailure
from rackhead_evaluator.validation import effective_flow_sensitivity, load_workflow


def issue_codes(error: ValidationFailure) -> set[str]:
    return {issue.code for issue in error.issues}


def validate_data(tmp_path: Path, data: dict[str, Any]) -> ValidationFailure:
    path = write_yaml(tmp_path / "workflow.yaml", data)
    with pytest.raises(ValidationFailure) as caught:
        load_workflow(path)
    return caught.value


def test_valid_workflow_loads(tmp_path: Path) -> None:
    workflow = load_workflow(write_yaml(tmp_path / "workflow.yaml", clone_workflow()))
    assert workflow.workflow.id == "demo-support-agent"
    assert (
        effective_flow_sensitivity(workflow, flow_id="ticket_to_customer_email").value
        == "confidential"
    )


def test_unsupported_schema_version(tmp_path: Path) -> None:
    data = clone_workflow()
    data["schema_version"] = "0.2"
    assert "RH-SCHEMA-STRUCT-VERSION-001" in issue_codes(validate_data(tmp_path, data))


def test_invalid_enum(tmp_path: Path) -> None:
    data = clone_workflow()
    data["risk_profile"]["deployment_stage"] = "live"
    assert "RH-SCHEMA-STRUCT-005" in issue_codes(validate_data(tmp_path, data))


def test_string_boolean_is_rejected(tmp_path: Path) -> None:
    data = clone_workflow()
    data["tools"][0]["logs_arguments"] = "false"
    assert "RH-SCHEMA-STRUCT-006" in issue_codes(validate_data(tmp_path, data))


def test_string_integer_is_rejected(tmp_path: Path) -> None:
    data = clone_workflow()
    data["memory"]["retention"]["days"] = "30"
    assert "RH-SCHEMA-STRUCT-006" in issue_codes(validate_data(tmp_path, data))


def test_unknown_field(tmp_path: Path) -> None:
    data = clone_workflow()
    data["workflow"]["mystery"] = True
    assert "RH-SCHEMA-STRUCT-003" in issue_codes(validate_data(tmp_path, data))


def test_missing_required_field(tmp_path: Path) -> None:
    data = clone_workflow()
    del data["workflow"]["owners"]
    assert "RH-SCHEMA-STRUCT-004" in issue_codes(validate_data(tmp_path, data))


def test_tool_requires_approval_is_rejected(tmp_path: Path) -> None:
    data = clone_workflow()
    data["tools"][0]["requires_approval"] = True
    error = validate_data(tmp_path, data)
    assert "RH-SCHEMA-STRUCT-APPROVAL-001" in issue_codes(error)
    assert any(issue.path == "tools[0].requires_approval" for issue in error.issues)


def test_flow_requires_approval_is_rejected(tmp_path: Path) -> None:
    data = clone_workflow()
    data["flows"][0]["requires_approval"] = True
    error = validate_data(tmp_path, data)
    assert "RH-SCHEMA-STRUCT-APPROVAL-001" in issue_codes(error)
    assert any(issue.path == "flows[0].requires_approval" for issue in error.issues)


def test_duplicate_id_within_collection(tmp_path: Path) -> None:
    data = clone_workflow()
    data["tools"].append(deepcopy(data["tools"][0]))
    assert "RH-SCHEMA-REF-007" in issue_codes(validate_data(tmp_path, data))


def test_node_id_collision_across_namespaces(tmp_path: Path) -> None:
    data = clone_workflow()
    data["outputs"][0]["id"] = "search_tickets"
    assert "RH-SCHEMA-REF-008" in issue_codes(validate_data(tmp_path, data))


def test_missing_flow_source_reference(tmp_path: Path) -> None:
    data = clone_workflow()
    data["flows"][0]["from"] = "missing_source"
    assert "RH-SCHEMA-REF-001" in issue_codes(validate_data(tmp_path, data))


def test_missing_through_tool_reference(tmp_path: Path) -> None:
    data = clone_workflow()
    data["flows"][0]["through"][0] = "missing_tool"
    assert "RH-SCHEMA-REF-002" in issue_codes(validate_data(tmp_path, data))


def test_missing_destination_reference(tmp_path: Path) -> None:
    data = clone_workflow()
    data["flows"][0]["to"] = "missing_output"
    assert "RH-SCHEMA-REF-003" in issue_codes(validate_data(tmp_path, data))


def test_repeated_node_in_flow(tmp_path: Path) -> None:
    data = clone_workflow()
    data["flows"][0]["through"].append("search_tickets")
    assert "RH-SCHEMA-REF-004" in issue_codes(validate_data(tmp_path, data))


def test_approval_reference_to_missing_object(tmp_path: Path) -> None:
    data = clone_workflow()
    data["approvals"][0]["actions"] = ["tool:not_declared"]
    assert "RH-SCHEMA-REF-005" in issue_codes(validate_data(tmp_path, data))


def test_exception_reference_to_missing_object(tmp_path: Path) -> None:
    data = clone_workflow()
    data["exceptions"] = [
        {
            "rule_id": "RH-AWE-006",
            "object_ref": "tool:not_declared",
            "justification": "Synthetic test",
            "owner": "security-reviewer",
            "expires_on": "2026-10-01",
        }
    ]
    assert "RH-SCHEMA-REF-006" in issue_codes(validate_data(tmp_path, data))


def test_disabled_memory_with_writes_enabled(tmp_path: Path) -> None:
    data = clone_workflow()
    data["memory"]["enabled"] = False
    data["memory"]["writes_allowed"] = True
    assert "RH-SCHEMA-SEM-001" in issue_codes(validate_data(tmp_path, data))


def test_invalid_memory_retention(tmp_path: Path) -> None:
    data = clone_workflow()
    data["memory"]["retention"] = {"mode": "fixed_days"}
    assert "RH-SCHEMA-STRUCT-009" in issue_codes(validate_data(tmp_path, data))


def test_empty_carries(tmp_path: Path) -> None:
    data = clone_workflow()
    data["flows"][0]["carries"] = []
    assert "RH-SCHEMA-SEM-002" in issue_codes(validate_data(tmp_path, data))


def test_understated_flow_sensitivity(tmp_path: Path) -> None:
    data = clone_workflow()
    data["flows"][0]["carries"] = ["internal"]
    assert "RH-SCHEMA-SEM-003" in issue_codes(validate_data(tmp_path, data))


def test_more_sensitive_flow_declaration_is_valid(tmp_path: Path) -> None:
    data = clone_workflow()
    data["flows"][0]["carries"] = ["restricted"]
    workflow = load_workflow(write_yaml(tmp_path / "workflow.yaml", data))
    assert (
        effective_flow_sensitivity(workflow, flow_id="ticket_to_customer_email").value
        == "restricted"
    )


def test_empty_exception_owner_is_rejected(tmp_path: Path) -> None:
    data = clone_workflow()
    data["exceptions"] = [
        {
            "rule_id": "RH-AWE-006",
            "object_ref": "tool:send_customer_email",
            "justification": "Synthetic test",
            "owner": " ",
            "expires_on": "2026-10-01",
        }
    ]
    assert "RH-SCHEMA-STRUCT-008" in issue_codes(validate_data(tmp_path, data))


def test_malformed_exception_date_is_rejected(tmp_path: Path) -> None:
    data = clone_workflow()
    data["exceptions"] = [
        {
            "rule_id": "RH-AWE-006",
            "object_ref": "tool:send_customer_email",
            "justification": "Synthetic test",
            "owner": "security-reviewer",
            "expires_on": "tomorrow-ish",
        }
    ]
    assert "RH-SCHEMA-STRUCT-010" in issue_codes(validate_data(tmp_path, data))


def test_expired_exception_is_structurally_valid_in_slice_one(tmp_path: Path) -> None:
    data = clone_workflow()
    data["exceptions"] = [
        {
            "rule_id": "RH-AWE-006",
            "object_ref": "tool:send_customer_email",
            "justification": "Historical synthetic exception",
            "owner": "security-reviewer",
            "expires_on": "2020-01-01",
        }
    ]
    workflow = load_workflow(write_yaml(tmp_path / "workflow.yaml", data))
    assert workflow.exceptions[0].is_expired()
