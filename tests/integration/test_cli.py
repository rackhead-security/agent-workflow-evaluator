from __future__ import annotations

from pathlib import Path

import pytest
from conftest import clone_workflow, write_yaml
from typer.testing import CliRunner

from rackhead_evaluator import cli

runner = CliRunner()


def test_cli_valid_input_returns_zero(tmp_path: Path) -> None:
    workflow = write_yaml(tmp_path / "workflow.yaml", clone_workflow())
    result = runner.invoke(cli.app, [str(workflow)])
    assert result.exit_code == 0
    assert "valid: demo-support-agent" in result.stdout
    assert result.stderr == ""


def test_cli_invalid_input_returns_two(tmp_path: Path) -> None:
    data = clone_workflow()
    data["flows"][0]["carries"] = []
    workflow = write_yaml(tmp_path / "workflow.yaml", data)
    result = runner.invoke(cli.app, [str(workflow)])
    assert result.exit_code == 2
    assert "RH-SCHEMA-SEM-002" in result.stderr
    assert "valid:" not in result.stdout


def test_cli_missing_file_returns_two_without_traceback(tmp_path: Path) -> None:
    result = runner.invoke(cli.app, [str(tmp_path / "missing.yaml")])
    assert result.exit_code == 2
    assert "RH-CONFIG-001" in result.stderr
    assert "Traceback" not in result.stderr


def test_cli_validates_optional_policy(tmp_path: Path) -> None:
    workflow = write_yaml(tmp_path / "workflow.yaml", clone_workflow())
    policy = tmp_path / "policy.yaml"
    policy.write_text(
        'policy_version: "0.1"\nenabled_rules:\n  - RH-AWE-001\n',
        encoding="utf-8",
    )
    result = runner.invoke(cli.app, [str(workflow), "--policy", str(policy)])
    assert result.exit_code == 0


def test_cli_unknown_policy_rule_returns_two(tmp_path: Path) -> None:
    workflow = write_yaml(tmp_path / "workflow.yaml", clone_workflow())
    policy = tmp_path / "policy.yaml"
    policy.write_text(
        'policy_version: "0.1"\nenabled_rules:\n  - RH-AWE-999\n',
        encoding="utf-8",
    )
    result = runner.invoke(cli.app, [str(workflow), "--policy", str(policy)])
    assert result.exit_code == 2
    assert "RH-POLICY-STRUCT-005" in result.stderr


def test_cli_unexpected_internal_error_returns_three_without_leak(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    workflow = write_yaml(tmp_path / "workflow.yaml", clone_workflow())

    def explode(_: Path) -> None:
        raise RuntimeError("secret-token=do-not-print")

    monkeypatch.setattr(cli, "load_workflow", explode)
    result = runner.invoke(cli.app, [str(workflow)])
    assert result.exit_code == 3
    assert "RH-EVALUATOR-INTERNAL-001" in result.stderr
    assert "secret-token" not in result.stderr
    assert "Traceback" not in result.stderr


def test_cli_does_not_echo_unknown_field_secret(tmp_path: Path) -> None:
    data = clone_workflow()
    data["workflow"]["api_key"] = "secret-value-that-must-not-be-printed"
    workflow = write_yaml(tmp_path / "workflow.yaml", data)

    result = runner.invoke(cli.app, [str(workflow)])

    assert result.exit_code == 2
    assert "RH-SCHEMA-STRUCT-003" in result.stderr
    assert "workflow.api_key" in result.stderr
    assert "secret-value" not in result.stderr


def test_cli_does_not_echo_unsupported_version_value(tmp_path: Path) -> None:
    data = clone_workflow()
    data["schema_version"] = "secret-version-value"
    workflow = write_yaml(tmp_path / "workflow.yaml", data)

    result = runner.invoke(cli.app, [str(workflow)])

    assert result.exit_code == 2
    assert "RH-SCHEMA-STRUCT-VERSION-001" in result.stderr
    assert "secret-version-value" not in result.stderr
