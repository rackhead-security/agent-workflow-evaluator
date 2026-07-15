from __future__ import annotations

import socket
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
import yaml


@pytest.fixture(autouse=True)
def block_network_access(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make tests fail immediately if production code attempts network access."""

    def blocked(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("network access is forbidden in the test suite")

    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket.socket, "connect", blocked)


def valid_workflow_data() -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "workflow": {
            "id": "demo-support-agent",
            "name": "Demo Support Agent",
            "version": "0.1.0",
            "description": "Synthetic validation fixture",
            "owners": ["rackhead-security-demo"],
        },
        "risk_profile": {
            "deployment_stage": "internal",
            "max_autonomy": "approved_actions",
        },
        "data_sources": [
            {
                "id": "support_tickets",
                "name": "Support tickets",
                "type": "chat",
                "trust": "mixed",
                "sensitivity": "confidential",
                "access_control": "user_scoped",
            }
        ],
        "tools": [
            {
                "id": "search_tickets",
                "name": "Search tickets",
                "mode": "read",
                "identity": "service_account",
                "allowed_domains": [],
                "allowed_paths": [],
                "logs_arguments": True,
                "logs_results": False,
            },
            {
                "id": "send_customer_email",
                "name": "Send customer email",
                "mode": "external_write",
                "identity": "user_delegated",
                "allowed_domains": ["example.invalid"],
                "allowed_paths": [],
                "logs_arguments": True,
                "logs_results": False,
            },
        ],
        "memory": {
            "id": "agent_memory",
            "enabled": True,
            "writes_allowed": True,
            "review_required": True,
            "retention": {"mode": "fixed_days", "days": 30},
            "sensitivity": "confidential",
        },
        "outputs": [
            {
                "id": "customer_email",
                "name": "Customer email",
                "type": "email",
                "boundary": "external",
                "sensitivity_allowed": "confidential",
            }
        ],
        "flows": [
            {
                "id": "ticket_to_customer_email",
                "from": "support_tickets",
                "through": ["search_tickets", "send_customer_email"],
                "to": "customer_email",
                "carries": ["confidential"],
                "transforms": ["summarize"],
            }
        ],
        "approvals": [
            {
                "id": "approve_external_email",
                "actions": [
                    "tool:send_customer_email",
                    "flow:ticket_to_customer_email",
                ],
                "approver_role": "support_lead",
                "required": True,
            }
        ],
        "monitoring": {
            "log_tool_calls": True,
            "log_tool_arguments": True,
            "log_tool_results": False,
            "log_retrieved_sources": True,
            "alert_on_external_write": True,
            "alert_on_policy_block": True,
            "retention_days": 90,
        },
        "exceptions": [],
    }


def clone_workflow() -> dict[str, Any]:
    return deepcopy(valid_workflow_data())


def write_yaml(path: Path, data: dict[str, Any]) -> Path:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path
